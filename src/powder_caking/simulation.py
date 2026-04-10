from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from powder_caking.climate import ClimateProfile
from powder_caking.models import predict_caking_rate_pa_per_h


PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"
GRAVITY_M_PER_S2 = 9.80665
VALID_INTEGRATION_METHODS = ("euler", "heun")


@dataclass(frozen=True)
class GabParameters:
    c: float = 8.145
    f: float = 1.0
    mo: float = 4.63


@dataclass(frozen=True)
class PermeabilityParameters:
    mode: str = "temperature_dependent"
    k0: float = 0.033901364997275675
    activation_energy_j_per_kmol: float = 27566729.8
    gas_constant_j_per_kmol_k: float = 8314.0
    k_over_delta_kg_per_m2_d_pa: float | None = None


@dataclass(frozen=True)
class CakingRateParameters:
    sigma1_kpa: float
    a_param_pa_per_h: float
    k_param_per_c: float


@dataclass(frozen=True)
class SimulationParameters:
    sack_mass_kg: float = 25.0
    sack_area_m2: float = 1.26
    initial_sigma_c_kpa: float = 0.8
    critical_sigma_c_kpa: float = 20.0
    integration_method: str = "euler"
    gab: GabParameters = GabParameters()
    permeability: PermeabilityParameters = PermeabilityParameters()
    caking_rate: CakingRateParameters = CakingRateParameters(
        sigma1_kpa=20.0,
        a_param_pa_per_h=60.96614981220336,
        k_param_per_c=0.5329326968060314,
    )


@dataclass(frozen=True)
class SimulationInput:
    climate_profile: ClimateProfile
    initial_moisture_db_pct: float
    parameters: SimulationParameters = SimulationParameters()


@dataclass(frozen=True)
class SimulationResult:
    time_series: pd.DataFrame
    summary: dict[str, float | bool | str | None]
    parameters: SimulationParameters


def simulate_transport(
    climate_profile: ClimateProfile,
    initial_moisture_db_pct: float,
    parameters: SimulationParameters | None = None,
    dt_d: float | None = None,
) -> SimulationResult:
    parameters = parameters or SimulationParameters()
    if initial_moisture_db_pct < 0:
        raise ValueError("initial_moisture_db_pct must be greater than or equal to 0")

    if dt_d is not None:
        climate_profile = climate_profile.resample(dt_d)

    climate = climate_profile.to_dataframe()
    if len(climate) < 1:
        raise ValueError("climate_profile must contain at least one row")
    if parameters.integration_method not in VALID_INTEGRATION_METHODS:
        valid = ", ".join(VALID_INTEGRATION_METHODS)
        raise ValueError(f"integration_method must be one of: {valid}")

    dry_mass_kg = dry_mass_from_total_mass(parameters.sack_mass_kg, initial_moisture_db_pct)
    water_mass_kg = water_mass_from_moisture_db(dry_mass_kg, initial_moisture_db_pct)
    sigma_c_kpa = parameters.initial_sigma_c_kpa

    records: list[dict[str, float | bool]] = []
    for idx, row in climate.iterrows():
        time_d = float(row["time_d"])
        temperature_c = float(row["temperature_c"])
        relative_humidity_pct = float(row["relative_humidity_pct"])

        state = calculate_state(
            water_mass_kg=water_mass_kg,
            dry_mass_kg=dry_mass_kg,
            sigma_c_kpa=sigma_c_kpa,
            temperature_c=temperature_c,
            relative_humidity_pct=relative_humidity_pct,
            parameters=parameters,
        )
        is_caked = sigma_c_kpa >= parameters.critical_sigma_c_kpa

        records.append(
            {
                "time_d": time_d,
                "temperature_c": temperature_c,
                "relative_humidity_pct": relative_humidity_pct,
                "water_mass_kg": water_mass_kg,
                "dry_mass_kg": dry_mass_kg,
                **state,
                "sigma_c_kpa": sigma_c_kpa,
                "is_caked": is_caked,
            }
        )

        if idx < len(climate) - 1:
            next_time_d = float(climate.iloc[idx + 1]["time_d"])
            dt_d = next_time_d - time_d
            if dt_d < 0:
                raise ValueError("climate profile time_d must be monotonically increasing")

            next_row = climate.iloc[idx + 1]
            water_mass_kg, sigma_c_kpa = integrate_step(
                water_mass_kg=water_mass_kg,
                dry_mass_kg=dry_mass_kg,
                sigma_c_kpa=sigma_c_kpa,
                current_temperature_c=temperature_c,
                current_relative_humidity_pct=relative_humidity_pct,
                next_temperature_c=float(next_row["temperature_c"]),
                next_relative_humidity_pct=float(next_row["relative_humidity_pct"]),
                dt_d=dt_d,
                parameters=parameters,
            )

    time_series = pd.DataFrame.from_records(records)
    summary = summarize_simulation(time_series, parameters)
    return SimulationResult(time_series=time_series, summary=summary, parameters=parameters)


def calculate_state(
    water_mass_kg: float,
    dry_mass_kg: float,
    sigma_c_kpa: float,
    temperature_c: float,
    relative_humidity_pct: float,
    parameters: SimulationParameters,
) -> dict[str, float]:
    moisture_fraction = water_mass_kg / dry_mass_kg
    moisture_db_pct = 100 * moisture_fraction
    water_activity = water_activity_from_moisture_fraction(moisture_fraction, parameters.gab)
    p_sv_pa = saturation_vapor_pressure_pa(temperature_c)
    k_over_delta = permeability_k_over_delta(temperature_c, parameters.permeability)
    dmw_dt_kg_per_d = water_mass_rate_kg_per_d(
        k_over_delta_kg_per_m2_d_pa=k_over_delta,
        sack_area_m2=parameters.sack_area_m2,
        saturation_vapor_pressure_pa_value=p_sv_pa,
        relative_humidity_pct=relative_humidity_pct,
        water_activity=water_activity,
    )
    tg_vuataz = tg_vuataz_c(water_activity)
    tg_linear = tg_linear_c(water_activity)
    tg_mean = (tg_vuataz + tg_linear) / 2
    t_minus_tg = temperature_c - tg_vuataz
    dfc_dt_pa_per_h = caking_rate_pa_per_h(
        t_minus_tg_c=t_minus_tg,
        caking_rate=parameters.caking_rate,
    )

    return {
        "moisture_fraction": moisture_fraction,
        "moisture_db_pct": moisture_db_pct,
        "water_activity": water_activity,
        "saturation_vapor_pressure_pa": p_sv_pa,
        "k_over_delta_kg_per_m2_d_pa": k_over_delta,
        "dmw_dt_kg_per_d": dmw_dt_kg_per_d,
        "tg_vuataz_c": tg_vuataz,
        "tg_linear_c": tg_linear,
        "tg_mean_c": tg_mean,
        "t_minus_tg_c": t_minus_tg,
        "dfc_dt_pa_per_h": dfc_dt_pa_per_h,
        "sigma_c_kpa": sigma_c_kpa,
    }


def integrate_step(
    water_mass_kg: float,
    dry_mass_kg: float,
    sigma_c_kpa: float,
    current_temperature_c: float,
    current_relative_humidity_pct: float,
    next_temperature_c: float,
    next_relative_humidity_pct: float,
    dt_d: float,
    parameters: SimulationParameters,
) -> tuple[float, float]:
    current_state = calculate_state(
        water_mass_kg=water_mass_kg,
        dry_mass_kg=dry_mass_kg,
        sigma_c_kpa=sigma_c_kpa,
        temperature_c=current_temperature_c,
        relative_humidity_pct=current_relative_humidity_pct,
        parameters=parameters,
    )
    dt_h = 24 * dt_d

    if parameters.integration_method == "euler":
        next_water_mass_kg = water_mass_kg + current_state["dmw_dt_kg_per_d"] * dt_d
        next_sigma_c_kpa = sigma_c_kpa + integrate_cake_strength_increment_kpa(
            current_state["dfc_dt_pa_per_h"],
            dt_h,
        )
        return next_water_mass_kg, next_sigma_c_kpa

    predicted_water_mass_kg = water_mass_kg + current_state["dmw_dt_kg_per_d"] * dt_d
    predicted_sigma_c_kpa = sigma_c_kpa + integrate_cake_strength_increment_kpa(
        current_state["dfc_dt_pa_per_h"],
        dt_h,
    )
    predicted_state = calculate_state(
        water_mass_kg=predicted_water_mass_kg,
        dry_mass_kg=dry_mass_kg,
        sigma_c_kpa=predicted_sigma_c_kpa,
        temperature_c=next_temperature_c,
        relative_humidity_pct=next_relative_humidity_pct,
        parameters=parameters,
    )

    mean_dmw_dt_kg_per_d = 0.5 * (current_state["dmw_dt_kg_per_d"] + predicted_state["dmw_dt_kg_per_d"])
    mean_dfc_dt_pa_per_h = 0.5 * (current_state["dfc_dt_pa_per_h"] + predicted_state["dfc_dt_pa_per_h"])

    next_water_mass_kg = water_mass_kg + mean_dmw_dt_kg_per_d * dt_d
    next_sigma_c_kpa = sigma_c_kpa + integrate_cake_strength_increment_kpa(mean_dfc_dt_pa_per_h, dt_h)
    return next_water_mass_kg, next_sigma_c_kpa


def load_default_simulation_parameters(
    processed_dir: str | Path = PROCESSED_DIR,
    consolidation_stress_kpa: float = 20.0,
    integration_method: str = "euler",
) -> SimulationParameters:
    processed_dir = Path(processed_dir)
    permeability_params = _load_permeability_parameters(processed_dir)
    caking_rate_params = _load_caking_rate_parameters(processed_dir, consolidation_stress_kpa)
    return SimulationParameters(
        integration_method=integration_method,
        permeability=permeability_params,
        caking_rate=caking_rate_params,
    )


def saturation_vapor_pressure_pa(temperature_c: float) -> float:
    return float(np.exp(23.4795 - (3990.56 / (temperature_c + 233.833))))


def permeability_k_over_delta(
    temperature_c: float,
    parameters: PermeabilityParameters = PermeabilityParameters(),
) -> float:
    if parameters.mode == "constant":
        if parameters.k_over_delta_kg_per_m2_d_pa is None:
            raise ValueError("constant permeability mode requires k_over_delta_kg_per_m2_d_pa")
        return float(parameters.k_over_delta_kg_per_m2_d_pa)
    if parameters.mode != "temperature_dependent":
        raise ValueError("permeability mode must be one of: temperature_dependent, constant")

    temperature_k = temperature_c + 273.15
    return float(
        parameters.k0
        * np.exp(
            -parameters.activation_energy_j_per_kmol
            / (parameters.gas_constant_j_per_kmol_k * temperature_k)
        )
    )


def water_activity_from_moisture_db_pct(moisture_db_pct: float, parameters: GabParameters = GabParameters()) -> float:
    return water_activity_from_moisture_fraction(moisture_db_pct / 100, parameters)


def water_activity_from_moisture_fraction(
    moisture_fraction: float,
    parameters: GabParameters = GabParameters(),
) -> float:
    if moisture_fraction <= 0:
        raise ValueError("moisture_fraction must be greater than 0")

    g = parameters.f * (1 - parameters.c)
    f_value = (((-2 + parameters.c - ((parameters.mo * parameters.c) / (moisture_fraction * 100)))) / g) * -0.5
    e_value = (f_value**2) - (1 / ((parameters.f * parameters.f) * (1 - parameters.c)))
    if e_value < 0:
        raise ValueError("GAB inversion produced a negative square-root argument")

    return float(np.sqrt(e_value) + f_value)


def water_mass_rate_kg_per_d(
    k_over_delta_kg_per_m2_d_pa: float,
    sack_area_m2: float,
    saturation_vapor_pressure_pa_value: float,
    relative_humidity_pct: float,
    water_activity: float,
) -> float:
    return float(
        k_over_delta_kg_per_m2_d_pa
        * sack_area_m2
        * saturation_vapor_pressure_pa_value
        * ((relative_humidity_pct / 100) - water_activity)
    )


def tg_vuataz_c(water_activity: float) -> float:
    return float((-425 * water_activity**3) + (545 * water_activity**2) - (355 * water_activity) + 101)


def tg_linear_c(water_activity: float) -> float:
    return float(88 - 172.55 * water_activity)


def caking_rate_pa_per_h(t_minus_tg_c: float, caking_rate: CakingRateParameters) -> float:
    if t_minus_tg_c < 0:
        return 0.0
    return predict_caking_rate_pa_per_h(
        t_minus_tg_c=t_minus_tg_c,
        a_param_pa_per_h=caking_rate.a_param_pa_per_h,
        k_param_per_c=caking_rate.k_param_per_c,
    )


def integrate_cake_strength_increment_kpa(dfc_dt_pa_per_h: float, dt_h: float) -> float:
    return float((dfc_dt_pa_per_h * dt_h) / 1000)


def consolidation_stress_from_stack_height_kpa(
    stack_height_m: float,
    bulk_density_kg_per_m3: float,
    gravity_m_per_s2: float = GRAVITY_M_PER_S2,
) -> float:
    if stack_height_m < 0:
        raise ValueError("stack_height_m must be greater than or equal to 0")
    if bulk_density_kg_per_m3 <= 0:
        raise ValueError("bulk_density_kg_per_m3 must be greater than 0")
    if gravity_m_per_s2 <= 0:
        raise ValueError("gravity_m_per_s2 must be greater than 0")
    return float((bulk_density_kg_per_m3 * gravity_m_per_s2 * stack_height_m) / 1000)


def dry_mass_from_total_mass(total_mass_kg: float, moisture_db_pct: float) -> float:
    if total_mass_kg <= 0:
        raise ValueError("total_mass_kg must be greater than 0")
    if moisture_db_pct < 0:
        raise ValueError("moisture_db_pct must be greater than or equal to 0")
    return float(total_mass_kg / (1 + (moisture_db_pct / 100)))


def water_mass_from_moisture_db(dry_mass_kg: float, moisture_db_pct: float) -> float:
    if dry_mass_kg <= 0:
        raise ValueError("dry_mass_kg must be greater than 0")
    if moisture_db_pct < 0:
        raise ValueError("moisture_db_pct must be greater than or equal to 0")
    return float(dry_mass_kg * moisture_db_pct / 100)


def summarize_simulation(
    time_series: pd.DataFrame,
    parameters: SimulationParameters,
) -> dict[str, float | bool | str | None]:
    final = time_series.iloc[-1]
    critical_rows = time_series[time_series["sigma_c_kpa"] >= parameters.critical_sigma_c_kpa]
    time_to_critical_d = None
    if not critical_rows.empty:
        time_to_critical_d = float(critical_rows.iloc[0]["time_d"])

    return {
        "final_time_d": float(final["time_d"]),
        "final_sigma_c_kpa": float(final["sigma_c_kpa"]),
        "critical_sigma_c_kpa": float(parameters.critical_sigma_c_kpa),
        "is_caked": bool(final["sigma_c_kpa"] >= parameters.critical_sigma_c_kpa),
        "time_to_critical_d": time_to_critical_d,
        "final_moisture_db_pct": float(final["moisture_db_pct"]),
        "final_water_activity": float(final["water_activity"]),
        "max_t_minus_tg_c": float(time_series["t_minus_tg_c"].max()),
        "max_dfc_dt_pa_per_h": float(time_series["dfc_dt_pa_per_h"].max()),
        "consolidation_stress_kpa": float(parameters.caking_rate.sigma1_kpa),
        "integration_method": parameters.integration_method,
    }


def _load_permeability_parameters(processed_dir: Path) -> PermeabilityParameters:
    frame = pd.read_csv(processed_dir / "wdd_arrhenius_parameters.csv")
    values = dict(zip(frame["parameter"], frame["value"]))
    return PermeabilityParameters(
        k0=float(values["pre_exponential_factor"]),
        activation_energy_j_per_kmol=float(values["activation_energy"]),
        gas_constant_j_per_kmol_k=float(values["gas_constant"]),
    )


def _load_caking_rate_parameters(processed_dir: Path, consolidation_stress_kpa: float) -> CakingRateParameters:
    frame = pd.read_csv(processed_dir / "caking_rate_fit_params.csv")
    matches = frame[np.isclose(frame["sigma1_kpa"], consolidation_stress_kpa)]
    if matches.empty:
        available = ", ".join(str(value) for value in sorted(frame["sigma1_kpa"].unique()))
        raise ValueError(f"No caking-rate fit for {consolidation_stress_kpa} kPa. Available: {available}")

    row = matches.iloc[0]
    return CakingRateParameters(
        sigma1_kpa=float(row["sigma1_kpa"]),
        a_param_pa_per_h=float(row["a_param_pa_per_h"]),
        k_param_per_c=float(row["k_param_per_c"]),
    )
