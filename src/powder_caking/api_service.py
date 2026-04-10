from __future__ import annotations

from dataclasses import asdict, replace
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd

from powder_caking.api_schemas import (
    ClimatePreviewDTO,
    ClimateProfileInputDTO,
    ClimatePresetDTO,
    ModelDefaultsDTO,
    MoistureLimitRequestDTO,
    MoistureLimitResponseDTO,
    ParameterOverridesDTO,
    SimulationParametersDTO,
    SimulationRequestDTO,
    SimulationResponseDTO,
)
from powder_caking.climate import ClimateProfile, climate_preset_names, load_climate_preset
from powder_caking.simulation import (
    PROCESSED_DIR,
    VALID_INTEGRATION_METHODS,
    GabParameters,
    PermeabilityParameters,
    SimulationParameters,
    SimulationResult,
    load_default_simulation_parameters,
    simulate_transport,
)

DEFAULT_INITIAL_MOISTURE_DB_PCT = 3.8


def build_climate_profile(input_dto: ClimateProfileInputDTO) -> ClimateProfile:
    if input_dto.preset_name is not None:
        profile = load_climate_preset(input_dto.preset_name)
    elif input_dto.csv_text is not None:
        profile = _climate_profile_from_csv_text(input_dto.csv_text)
    elif input_dto.points is not None:
        profile = ClimateProfile(
            pd.DataFrame([point.model_dump() for point in input_dto.points]),
            source="api_points",
        )
    else:
        raise ValueError("provide exactly one of points, csv_text, or preset_name")

    if input_dto.dt_d is not None:
        profile = profile.resample(input_dto.dt_d)
    return profile


def preview_climate_profile(input_dto: ClimateProfileInputDTO) -> dict[str, Any]:
    profile = build_climate_profile(input_dto)
    return {
        "source": profile.source,
        "preview": ClimatePreviewDTO(**profile.preview().as_dict()).model_dump(),
        "warnings": list(profile.validation_warnings),
    }


def run_simulation(request: SimulationRequestDTO, processed_dir: str | Path = PROCESSED_DIR) -> SimulationResponseDTO:
    climate_profile = build_climate_profile(request.climate_profile)
    parameters = load_default_simulation_parameters(
        processed_dir=processed_dir,
        consolidation_stress_kpa=request.consolidation_stress_kpa,
        integration_method=request.integration_method,
    )
    parameters = apply_parameter_overrides(parameters, request.parameter_overrides)
    result = simulate_transport(
        climate_profile=climate_profile,
        initial_moisture_db_pct=request.initial_moisture_db_pct,
        parameters=parameters,
        dt_d=request.dt_d,
    )
    return simulation_response_from_result(result, list(climate_profile.validation_warnings))


def run_moisture_limit(
    request: MoistureLimitRequestDTO,
    processed_dir: str | Path = PROCESSED_DIR,
) -> MoistureLimitResponseDTO:
    climate_profile = build_climate_profile(request.climate_profile)
    parameters = load_default_simulation_parameters(
        processed_dir=processed_dir,
        consolidation_stress_kpa=request.consolidation_stress_kpa,
        integration_method=request.integration_method,
    )
    parameters = apply_parameter_overrides(parameters, request.parameter_overrides)
    warnings = list(climate_profile.validation_warnings)
    bounds = request.search_bounds

    def simulate(initial_moisture_db_pct: float) -> SimulationResult:
        return simulate_transport(
            climate_profile=climate_profile,
            initial_moisture_db_pct=initial_moisture_db_pct,
            parameters=parameters,
            dt_d=request.dt_d,
        )

    current_result = simulate(request.initial_moisture_db_pct)
    current_safe = _result_is_safe(current_result)

    lower = bounds.min_initial_moisture_db_pct
    upper = bounds.max_initial_moisture_db_pct
    lower_result = simulate(lower)
    if not _result_is_safe(lower_result):
        warnings.append("lower search bound already cakes; no safe initial moisture found within bounds")
        return _moisture_limit_response(
            safe_initial_moisture_db_pct=None,
            current_initial_moisture_db_pct=request.initial_moisture_db_pct,
            is_current_profile_safe=current_safe,
            critical_sigma_c_kpa=parameters.critical_sigma_c_kpa,
            limit_result=None,
            iterations=0,
            warnings=warnings,
        )

    upper_result = simulate(upper)
    if _result_is_safe(upper_result):
        warnings.append("upper search bound remains safe; limit is at or above the upper bound")
        return _moisture_limit_response(
            safe_initial_moisture_db_pct=upper,
            current_initial_moisture_db_pct=request.initial_moisture_db_pct,
            is_current_profile_safe=current_safe,
            critical_sigma_c_kpa=parameters.critical_sigma_c_kpa,
            limit_result=upper_result,
            iterations=0,
            warnings=warnings,
        )

    safe_moisture = lower
    safe_result = lower_result
    caking_moisture = upper
    iterations = 0
    while (
        caking_moisture - safe_moisture > bounds.tolerance_db_pct
        and iterations < bounds.max_iterations
    ):
        iterations += 1
        candidate = (safe_moisture + caking_moisture) / 2
        candidate_result = simulate(candidate)
        if _result_is_safe(candidate_result):
            safe_moisture = candidate
            safe_result = candidate_result
        else:
            caking_moisture = candidate

    if caking_moisture - safe_moisture > bounds.tolerance_db_pct:
        warnings.append("maximum iterations reached before requested tolerance")

    return _moisture_limit_response(
        safe_initial_moisture_db_pct=safe_moisture,
        current_initial_moisture_db_pct=request.initial_moisture_db_pct,
        is_current_profile_safe=current_safe,
        critical_sigma_c_kpa=parameters.critical_sigma_c_kpa,
        limit_result=safe_result,
        iterations=iterations,
        warnings=warnings,
    )


def apply_parameter_overrides(
    parameters: SimulationParameters,
    overrides: ParameterOverridesDTO | None,
) -> SimulationParameters:
    if overrides is None:
        return parameters

    if overrides.gab is not None:
        parameters = replace(parameters, gab=replace(parameters.gab, **_override_values(overrides.gab)))

    if overrides.sack is not None:
        parameters = replace(parameters, **_override_values(overrides.sack))

    if overrides.caking_threshold is not None:
        parameters = replace(parameters, **_override_values(overrides.caking_threshold))

    if overrides.permeability is not None:
        parameters = replace(
            parameters,
            permeability=replace(parameters.permeability, **_override_values(overrides.permeability)),
        )
        _validate_permeability(parameters.permeability)

    _validate_gab(parameters.gab)
    if parameters.critical_sigma_c_kpa <= parameters.initial_sigma_c_kpa:
        raise ValueError("critical_sigma_c_kpa must be greater than initial_sigma_c_kpa")

    return parameters


def _override_values(override_dto: Any) -> dict[str, object]:
    return override_dto.model_dump(exclude_none=True)


def _validate_gab(parameters: GabParameters) -> None:
    if parameters.c == 1:
        raise ValueError("gab.c must not be 1")


def _validate_permeability(parameters: PermeabilityParameters) -> None:
    if parameters.mode == "constant" and parameters.k_over_delta_kg_per_m2_d_pa is None:
        raise ValueError("constant permeability mode requires k_over_delta_kg_per_m2_d_pa")
    if parameters.mode not in {"temperature_dependent", "constant"}:
        raise ValueError("permeability mode must be one of: temperature_dependent, constant")


def _result_is_safe(result: SimulationResult) -> bool:
    return not bool(result.summary["is_caked"])


def _moisture_limit_response(
    *,
    safe_initial_moisture_db_pct: float | None,
    current_initial_moisture_db_pct: float,
    is_current_profile_safe: bool,
    critical_sigma_c_kpa: float,
    limit_result: SimulationResult | None,
    iterations: int,
    warnings: list[str],
) -> MoistureLimitResponseDTO:
    moisture_margin_db_pct = None
    if safe_initial_moisture_db_pct is not None:
        moisture_margin_db_pct = safe_initial_moisture_db_pct - current_initial_moisture_db_pct

    final_sigma_c_kpa_at_limit = None
    if limit_result is not None:
        final_sigma_c_kpa_at_limit = float(limit_result.summary["final_sigma_c_kpa"])

    return MoistureLimitResponseDTO(
        safe_initial_moisture_db_pct=safe_initial_moisture_db_pct,
        current_initial_moisture_db_pct=current_initial_moisture_db_pct,
        moisture_margin_db_pct=moisture_margin_db_pct,
        is_current_profile_safe=is_current_profile_safe,
        critical_sigma_c_kpa=critical_sigma_c_kpa,
        final_sigma_c_kpa_at_limit=final_sigma_c_kpa_at_limit,
        iterations=iterations,
        warnings=warnings,
    )


def simulation_response_from_result(result: SimulationResult, warnings: list[str] | None = None) -> SimulationResponseDTO:
    return SimulationResponseDTO(
        summary=result.summary,
        parameters=SimulationParametersDTO(**asdict(result.parameters)),
        time_series=_frame_records(result.time_series),
        warnings=warnings or [],
    )


def list_climate_presets() -> list[ClimatePresetDTO]:
    presets: list[ClimatePresetDTO] = []
    for name in climate_preset_names():
        profile = load_climate_preset(name)
        presets.append(
            ClimatePresetDTO(
                name=name,
                source=profile.source,
                preview=ClimatePreviewDTO(**profile.preview().as_dict()),
                warnings=list(profile.validation_warnings),
            )
        )
    return presets


def model_defaults(processed_dir: str | Path = PROCESSED_DIR) -> ModelDefaultsDTO:
    parameters = load_default_simulation_parameters(processed_dir=processed_dir)
    return ModelDefaultsDTO(
        initial_moisture_db_pct=DEFAULT_INITIAL_MOISTURE_DB_PCT,
        critical_sigma_c_kpa=parameters.critical_sigma_c_kpa,
        integration_methods=list(VALID_INTEGRATION_METHODS),
        default_integration_method=parameters.integration_method,
        default_consolidation_stress_kpa=parameters.caking_rate.sigma1_kpa,
        available_consolidation_stress_kpa=_available_consolidation_stresses(processed_dir),
        parameters=SimulationParametersDTO(**asdict(parameters)),
        climate_presets=list(climate_preset_names()),
    )


def _climate_profile_from_csv_text(csv_text: str) -> ClimateProfile:
    frame = pd.read_csv(StringIO(csv_text))
    if "time_d" not in frame.columns and "timestamp" in frame.columns:
        timestamps = pd.to_datetime(frame["timestamp"], errors="raise")
        frame["time_d"] = (timestamps - timestamps.iloc[0]).dt.total_seconds() / 86400
    return ClimateProfile(frame, source="api_csv")


def _available_consolidation_stresses(processed_dir: str | Path) -> list[float]:
    frame = pd.read_csv(Path(processed_dir) / "caking_rate_fit_params.csv")
    return [float(value) for value in sorted(frame["sigma1_kpa"].unique())]


def _frame_records(frame: pd.DataFrame) -> list[dict[str, float | bool]]:
    records = frame.to_dict(orient="records")
    return [{str(key): value for key, value in record.items()} for record in records]
