from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ClimatePointDTO(BaseModel):
    time_d: float
    temperature_c: float
    relative_humidity_pct: float = Field(ge=0, le=100)


class ClimatePreviewDTO(BaseModel):
    duration_d: float
    n_points: int
    temperature_min_c: float
    temperature_max_c: float
    temperature_mean_c: float
    relative_humidity_min_pct: float
    relative_humidity_max_pct: float
    relative_humidity_mean_pct: float


class ClimateProfileInputDTO(BaseModel):
    points: list[ClimatePointDTO] | None = None
    csv_text: str | None = None
    preset_name: str | None = None
    dt_d: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def exactly_one_profile_source(self) -> ClimateProfileInputDTO:
        sources = [self.points is not None, self.csv_text is not None, self.preset_name is not None]
        if sum(sources) != 1:
            raise ValueError("provide exactly one of points, csv_text, or preset_name")
        return self


class ProfilePreviewRequestDTO(ClimateProfileInputDTO):
    pass


class ClimatePresetDTO(BaseModel):
    name: str
    source: str | None
    preview: ClimatePreviewDTO
    warnings: list[str]


class GabParametersDTO(BaseModel):
    c: float
    f: float
    mo: float


class PermeabilityParametersDTO(BaseModel):
    mode: Literal["temperature_dependent", "constant"] = "temperature_dependent"
    k0: float
    activation_energy_j_per_kmol: float
    gas_constant_j_per_kmol_k: float
    k_over_delta_kg_per_m2_d_pa: float | None = None


class CakingRateParametersDTO(BaseModel):
    sigma1_kpa: float
    a_param_pa_per_h: float
    k_param_per_c: float


class SimulationParametersDTO(BaseModel):
    sack_mass_kg: float
    sack_area_m2: float
    initial_sigma_c_kpa: float
    critical_sigma_c_kpa: float
    integration_method: str
    gab: GabParametersDTO
    permeability: PermeabilityParametersDTO
    caking_rate: CakingRateParametersDTO


class GabParameterOverridesDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    c: float | None = Field(default=None, gt=0)
    f: float | None = Field(default=None, gt=0)
    mo: float | None = Field(default=None, gt=0)


class PermeabilityParameterOverridesDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["temperature_dependent", "constant"] | None = None
    k0: float | None = Field(default=None, gt=0)
    activation_energy_j_per_kmol: float | None = Field(default=None, gt=0)
    gas_constant_j_per_kmol_k: float | None = Field(default=None, gt=0)
    k_over_delta_kg_per_m2_d_pa: float | None = Field(default=None, gt=0)


class SackParameterOverridesDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sack_mass_kg: float | None = Field(default=None, gt=0)
    sack_area_m2: float | None = Field(default=None, gt=0)


class CakingThresholdParameterOverridesDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    initial_sigma_c_kpa: float | None = Field(default=None, ge=0)
    critical_sigma_c_kpa: float | None = Field(default=None, gt=0)


class ParameterOverridesDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gab: GabParameterOverridesDTO | None = None
    permeability: PermeabilityParameterOverridesDTO | None = None
    sack: SackParameterOverridesDTO | None = None
    caking_threshold: CakingThresholdParameterOverridesDTO | None = None


class SimulationRequestDTO(BaseModel):
    climate_profile: ClimateProfileInputDTO
    initial_moisture_db_pct: float = Field(ge=0)
    consolidation_stress_kpa: float = 20.0
    integration_method: Literal["euler", "heun"] = "euler"
    dt_d: float | None = Field(default=None, gt=0)
    parameter_overrides: ParameterOverridesDTO | None = None


class MoistureLimitSearchBoundsDTO(BaseModel):
    min_initial_moisture_db_pct: float = Field(default=3.0, gt=0)
    max_initial_moisture_db_pct: float = Field(default=5.0, gt=0)
    tolerance_db_pct: float = Field(default=0.01, gt=0)
    max_iterations: int = Field(default=40, gt=0)

    @model_validator(mode="after")
    def valid_search_bounds(self) -> MoistureLimitSearchBoundsDTO:
        if self.min_initial_moisture_db_pct >= self.max_initial_moisture_db_pct:
            raise ValueError("min_initial_moisture_db_pct must be less than max_initial_moisture_db_pct")
        span = self.max_initial_moisture_db_pct - self.min_initial_moisture_db_pct
        if self.tolerance_db_pct >= span:
            raise ValueError("tolerance_db_pct must be smaller than the search interval")
        return self


class MoistureLimitRequestDTO(BaseModel):
    climate_profile: ClimateProfileInputDTO
    initial_moisture_db_pct: float = Field(ge=0)
    consolidation_stress_kpa: float = 20.0
    integration_method: Literal["euler", "heun"] = "euler"
    dt_d: float | None = Field(default=None, gt=0)
    parameter_overrides: ParameterOverridesDTO | None = None
    search_bounds: MoistureLimitSearchBoundsDTO = Field(default_factory=MoistureLimitSearchBoundsDTO)


class MoistureLimitResponseDTO(BaseModel):
    safe_initial_moisture_db_pct: float | None
    current_initial_moisture_db_pct: float
    moisture_margin_db_pct: float | None
    is_current_profile_safe: bool
    critical_sigma_c_kpa: float
    final_sigma_c_kpa_at_limit: float | None
    iterations: int
    warnings: list[str]

    model_config = ConfigDict(protected_namespaces=())


class SimulationResponseDTO(BaseModel):
    summary: dict[str, float | bool | str | None]
    parameters: SimulationParametersDTO
    time_series: list[dict[str, float | bool]]
    warnings: list[str]

    model_config = ConfigDict(protected_namespaces=())


class ModelDefaultsDTO(BaseModel):
    initial_moisture_db_pct: float
    critical_sigma_c_kpa: float
    integration_methods: list[str]
    default_integration_method: str
    default_consolidation_stress_kpa: float
    available_consolidation_stress_kpa: list[float]
    parameters: SimulationParametersDTO
    climate_presets: list[str]


class CriticalCakeStrengthRecordDTO(BaseModel):
    material: str
    sigma_c_kpa: float
    sieve_residue_pct: float | None
    sieving_time_min: float
    sieving_amplitude_mm: float


class CakingRateFitRecordDTO(BaseModel):
    sigma1_kpa: float
    n_points: int
    rate_column: str
    a_param_pa_per_h: float
    k_param_per_c: float
    r_squared: float
    fit_equation: str


class WddPermeabilityRecordDTO(BaseModel):
    temperature_c: float
    mass_gain_g_per_d: float
    wdd_g_per_m2_d: float
    k_over_delta_kg_per_m2_d_pa: float
    inverse_temperature_1_per_k: float
    ln_k_over_delta: float
    source_workbook: str
    source_sheet: str
    source_row: int
    source_range: str


class WddArrheniusParameterDTO(BaseModel):
    parameter: str
    symbol: str
    value: float
    unit: str
    source_cell: str
    source_workbook: str
    source_sheet: str


class WddPermeabilityResponseDTO(BaseModel):
    permeability_summary: list[WddPermeabilityRecordDTO]
    arrhenius_parameters: list[WddArrheniusParameterDTO]
