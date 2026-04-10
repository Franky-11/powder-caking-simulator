export type IntegrationMethod = 'euler' | 'heun'

export interface ClimatePoint {
  time_d: number
  temperature_c: number
  relative_humidity_pct: number
}

export interface ClimatePreview {
  duration_d: number
  n_points: number
  temperature_min_c: number
  temperature_max_c: number
  temperature_mean_c: number
  relative_humidity_min_pct: number
  relative_humidity_max_pct: number
  relative_humidity_mean_pct: number
}

export interface ClimateProfileInput {
  preset_name?: string
  points?: ClimatePoint[]
  csv_text?: string
  dt_d?: number
}

export interface ClimatePreset {
  name: string
  source: string | null
  preview: ClimatePreview
  warnings: string[]
}

export interface GabParameters {
  c: number
  f: number
  mo: number
}

export interface PermeabilityParameters {
  mode: 'temperature_dependent' | 'constant'
  k0: number
  activation_energy_j_per_kmol: number
  gas_constant_j_per_kmol_k: number
  k_over_delta_kg_per_m2_d_pa: number | null
}

export interface CakingRateParameters {
  sigma1_kpa: number
  a_param_pa_per_h: number
  k_param_per_c: number
}

export interface SimulationParameters {
  sack_mass_kg: number
  sack_area_m2: number
  initial_sigma_c_kpa: number
  critical_sigma_c_kpa: number
  integration_method: string
  gab: GabParameters
  permeability: PermeabilityParameters
  caking_rate: CakingRateParameters
}

export interface ModelDefaults {
  initial_moisture_db_pct: number
  critical_sigma_c_kpa: number
  integration_methods: IntegrationMethod[]
  default_integration_method: IntegrationMethod
  default_consolidation_stress_kpa: number
  available_consolidation_stress_kpa: number[]
  parameters: SimulationParameters
  climate_presets: string[]
}

export interface ProfilePreviewResponse {
  source: string | null
  preview: ClimatePreview
  warnings: string[]
}

export interface SimulationRequest {
  climate_profile: ClimateProfileInput
  initial_moisture_db_pct: number
  consolidation_stress_kpa: number
  integration_method: IntegrationMethod
  dt_d?: number
  parameter_overrides?: ParameterOverrides
}

export interface ParameterOverrides {
  gab?: Partial<GabParameters>
  permeability?: Partial<PermeabilityParameters>
  sack?: Partial<Pick<SimulationParameters, 'sack_mass_kg' | 'sack_area_m2'>>
  caking_threshold?: Partial<Pick<SimulationParameters, 'initial_sigma_c_kpa' | 'critical_sigma_c_kpa'>>
}

export interface MoistureLimitSearchBounds {
  min_initial_moisture_db_pct: number
  max_initial_moisture_db_pct: number
  tolerance_db_pct: number
  max_iterations?: number
}

export interface MoistureLimitRequest extends SimulationRequest {
  search_bounds: MoistureLimitSearchBounds
}

export interface MoistureLimitResponse {
  safe_initial_moisture_db_pct: number | null
  current_initial_moisture_db_pct: number
  moisture_margin_db_pct: number | null
  is_current_profile_safe: boolean
  critical_sigma_c_kpa: number
  final_sigma_c_kpa_at_limit: number | null
  iterations: number
  warnings: string[]
}

export interface SimulationSummary {
  final_time_d: number
  final_sigma_c_kpa: number
  critical_sigma_c_kpa: number
  is_caked: boolean
  time_to_critical_d: number | null
  final_moisture_db_pct: number
  final_water_activity: number
  max_t_minus_tg_c: number
  max_dfc_dt_pa_per_h: number
  consolidation_stress_kpa: number
  integration_method: string
}

export interface SimulationTimeStep {
  time_d: number
  temperature_c: number
  relative_humidity_pct: number
  water_mass_kg: number
  dry_mass_kg: number
  moisture_fraction: number
  moisture_db_pct: number
  water_activity: number
  saturation_vapor_pressure_pa: number
  k_over_delta_kg_per_m2_d_pa: number
  dmw_dt_kg_per_d: number
  tg_vuataz_c: number
  tg_linear_c: number
  tg_mean_c: number
  t_minus_tg_c: number
  dfc_dt_pa_per_h: number
  sigma_c_kpa: number
  is_caked: boolean
}

export interface SimulationResponse {
  summary: SimulationSummary
  parameters: SimulationParameters
  time_series: SimulationTimeStep[]
  warnings: string[]
}
