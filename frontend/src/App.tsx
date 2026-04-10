import { useEffect, useMemo, useState } from 'react'
import type { ChangeEvent, ReactNode } from 'react'
import type { EChartsOption } from 'echarts'
import './App.css'
import {
  calculateMoistureLimit,
  getClimatePresets,
  getModelDefaults,
  previewProfile,
  simulate,
} from './apiClient'
import type {
  ClimateProfileInput,
  ClimatePreset,
  IntegrationMethod,
  ModelDefaults,
  MoistureLimitResponse,
  ParameterOverrides,
  ProfilePreviewResponse,
  SimulationRequest,
  SimulationResponse,
} from './apiTypes'
import TimeSeriesChart from './TimeSeriesChart'
import heroPowderSacks from './assets/start-hero-powder-sacks.jpg'
import labMoistureAnalysis from './assets/start-lab-moisture-analysis.jpg'

type ApiStatus = 'checking' | 'online' | 'offline'
type AppView = 'start' | 'simulator' | 'model'
type ProfileSource = 'preset' | 'csv'
type PermeabilityMode = 'temperature_dependent' | 'constant'
type ChartTab = 'climate' | 'moisture' | 'glass' | 'caking' | 'parameters'
type ParameterRow = {
  label: string
  value: string
  unit?: string
}
type ParameterSection = {
  title: string
  rows: ParameterRow[]
}
type FormulaBlock = {
  title: string
  formula: ReactNode
  description: string
}
type ProcessStep = {
  index: string
  title: string
  description: ReactNode
}
type ExpertParameterState = {
  gabMo: string
  gabC: string
  gabF: string
  sackMassKg: string
  sackAreaM2: string
  initialSigmaCKpa: string
  criticalSigmaCKpa: string
  permeabilityMode: PermeabilityMode
  permeabilityK0: string
  permeabilityActivationEnergy: string
  permeabilityGasConstant: string
  permeabilityConstantK: string
}
type MoistureLimitBoundsState = {
  minInitialMoisture: string
  maxInitialMoisture: string
  tolerance: string
}

const presetLabels: Record<string, string> = {
  neutral_reference_transport: 'Referenztransport neutral',
  tropical_sea_transport_southeast_asia: 'Tropischer Seetransport',
  hot_humid_worst_case: 'Heiss-feuchter Worst Case',
  day_night_container_profile: 'Tag/Nacht Containerprofil',
  real_container_logger_profile: 'Reales Loggerprofil',
}

const emptyExpertParameters: ExpertParameterState = {
  gabMo: '',
  gabC: '',
  gabF: '',
  sackMassKg: '',
  sackAreaM2: '',
  initialSigmaCKpa: '',
  criticalSigmaCKpa: '',
  permeabilityMode: 'temperature_dependent',
  permeabilityK0: '',
  permeabilityActivationEnergy: '',
  permeabilityGasConstant: '',
  permeabilityConstantK: '',
}
const constantPermeabilityPlaceholder = '4.38427E-07'
const defaultMoistureLimitBounds: MoistureLimitBoundsState = {
  minInitialMoisture: '3',
  maxInitialMoisture: '5',
  tolerance: '0.01',
}

function App() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>('checking')
  const [defaults, setDefaults] = useState<ModelDefaults | null>(null)
  const [presets, setPresets] = useState<ClimatePreset[]>([])
  const [activeView, setActiveView] = useState<AppView>('start')
  const [profileSource, setProfileSource] = useState<ProfileSource>('preset')
  const [selectedPreset, setSelectedPreset] = useState('')
  const [csvText, setCsvText] = useState(sampleCsvText)
  const [csvFileName, setCsvFileName] = useState<string | null>(null)
  const [initialMoisture, setInitialMoisture] = useState('3.8')
  const [consolidationStress, setConsolidationStress] = useState('20')
  const [integrationMethod, setIntegrationMethod] = useState<IntegrationMethod>('euler')
  const [dtD, setDtD] = useState('0.0416667')
  const [isExpertOpen, setIsExpertOpen] = useState(false)
  const [expertParameters, setExpertParameters] = useState<ExpertParameterState>(emptyExpertParameters)
  const [isMoistureLimitBoundsOpen, setIsMoistureLimitBoundsOpen] = useState(false)
  const [moistureLimitBounds, setMoistureLimitBounds] = useState<MoistureLimitBoundsState>(
    defaultMoistureLimitBounds,
  )
  const [preview, setPreview] = useState<ProfilePreviewResponse | null>(null)
  const [result, setResult] = useState<SimulationResponse | null>(null)
  const [moistureLimit, setMoistureLimit] = useState<MoistureLimitResponse | null>(null)
  const [isPreviewing, setIsPreviewing] = useState(false)
  const [isSimulating, setIsSimulating] = useState(false)
  const [isCalculatingMoistureLimit, setIsCalculatingMoistureLimit] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [activeChartTab, setActiveChartTab] = useState<ChartTab>('climate')

  useEffect(() => {
    let isMounted = true

    Promise.all([getModelDefaults(), getClimatePresets()])
      .then(([modelDefaults, climatePresets]) => {
        if (!isMounted) {
          return
        }
        setDefaults(modelDefaults)
        setPresets(climatePresets)
        setSelectedPreset(defaultClimatePreset(modelDefaults.climate_presets, climatePresets))
        setInitialMoisture(formatInputNumber(modelDefaults.initial_moisture_db_pct))
        setConsolidationStress(formatInputNumber(modelDefaults.default_consolidation_stress_kpa))
        setIntegrationMethod(modelDefaults.default_integration_method)
        setExpertParameters(expertParametersFromDefaults(modelDefaults))
        setApiStatus('online')
      })
      .catch((error: unknown) => {
        if (!isMounted) {
          return
        }
        setApiStatus('offline')
        setMessage(error instanceof Error ? error.message : 'API nicht erreichbar')
      })

    return () => {
      isMounted = false
    }
  }, [])

  const selectedPresetDetails = presets.find((preset) => preset.name === selectedPreset)
  const allWarnings = [
    ...(preview?.warnings ?? []),
    ...(result?.warnings ?? []),
    ...(moistureLimit?.warnings.map((warning) => `Startfeuchte: ${warning}`) ?? []),
  ]
  const statusClass = result?.summary.is_caked ? 'danger' : 'success'
  const canSubmit = apiStatus === 'online' && isProfileInputReady(profileSource, selectedPreset, csvText)
  const previewSourceLabel = buildPreviewSourceLabel(
    profileSource,
    selectedPreset,
    csvFileName,
    preview?.source,
  )
  const parameterSections = useMemo(() => buildParameterSections(result), [result])
  const moistureMarginStatus = getMoistureMarginStatus(moistureLimit)
  const canCalculateMoistureLimit = canSubmit && result !== null

  const climateChartOption = useMemo<EChartsOption | null>(() => {
    if (!result) {
      return null
    }

    return {
      animation: false,
      color: ['#0f62fe', '#009d9a'],
      grid: { left: 52, right: 52, top: 48, bottom: 48 },
      legend: { top: 8, textStyle: { color: '#525252', fontSize: 12 } },
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'value',
        name: 'Zeit d',
        nameLocation: 'middle',
        nameGap: 30,
        axisLabel: { color: '#525252', fontSize: 12 },
        splitLine: { lineStyle: { color: '#e0e0e0' } },
      },
      yAxis: [
        {
          type: 'value',
          name: 'Temperatur C',
          axisLabel: { color: '#525252', fontSize: 12 },
          splitLine: { lineStyle: { color: '#e0e0e0' } },
        },
        {
          type: 'value',
          name: 'rF %',
          axisLabel: { color: '#525252', fontSize: 12 },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: 'Temperatur',
          type: 'line',
          showSymbol: false,
          lineStyle: { width: 2 },
          data: result.time_series.map((row) => [row.time_d, row.temperature_c]),
        },
        {
          name: 'Relative Feuchte',
          type: 'line',
          yAxisIndex: 1,
          showSymbol: false,
          lineStyle: { width: 2 },
          data: result.time_series.map((row) => [row.time_d, row.relative_humidity_pct]),
        },
      ],
    }
  }, [result])

  const strengthChartOption = useMemo<EChartsOption | null>(() => {
    if (!result) {
      return null
    }

    const critical = result.summary.critical_sigma_c_kpa
    return {
      animation: false,
      color: ['#da1e28'],
      grid: { left: 56, right: 24, top: 48, bottom: 48 },
      legend: { top: 8, textStyle: { color: '#525252', fontSize: 12 } },
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'value',
        name: 'Zeit d',
        nameLocation: 'middle',
        nameGap: 30,
        axisLabel: { color: '#525252', fontSize: 12 },
        splitLine: { lineStyle: { color: '#e0e0e0' } },
      },
      yAxis: {
        type: 'value',
        name: 'sigma_c kPa',
        axisLabel: { color: '#525252', fontSize: 12 },
        splitLine: { lineStyle: { color: '#e0e0e0' } },
      },
      series: [
        {
          name: 'Cake-Festigkeit',
          type: 'line',
          showSymbol: false,
          lineStyle: { width: 2 },
          data: result.time_series.map((row) => [row.time_d, row.sigma_c_kpa]),
          markLine: {
            symbol: 'none',
            label: {
              formatter: 'kritische Festigkeit 20 kPa',
              color: '#da1e28',
            },
            lineStyle: { color: '#da1e28', width: 2, type: 'dashed' },
            data: [{ yAxis: critical }],
          },
        },
      ],
    }
  }, [result])

  const moistureChartOption = useMemo<EChartsOption | null>(() => {
    if (!result) {
      return null
    }

    return {
      animation: false,
      color: ['#8a3ffc', '#009d9a'],
      grid: { left: 56, right: 56, top: 48, bottom: 48 },
      legend: { top: 8, textStyle: { color: '#525252', fontSize: 12 } },
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'value',
        name: 'Zeit d',
        nameLocation: 'middle',
        nameGap: 30,
        axisLabel: { color: '#525252', fontSize: 12 },
        splitLine: { lineStyle: { color: '#e0e0e0' } },
      },
      yAxis: [
        {
          type: 'value',
          name: 'Feuchte % db',
          axisLabel: { color: '#525252', fontSize: 12 },
          splitLine: { lineStyle: { color: '#e0e0e0' } },
        },
        {
          type: 'value',
          name: 'aw',
          axisLabel: { color: '#525252', fontSize: 12 },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: 'Pulverfeuchte',
          type: 'line',
          showSymbol: false,
          lineStyle: { width: 2 },
          data: result.time_series.map((row) => [row.time_d, row.moisture_db_pct]),
        },
        {
          name: 'Wasseraktivität',
          type: 'line',
          yAxisIndex: 1,
          showSymbol: false,
          lineStyle: { width: 2 },
          data: result.time_series.map((row) => [row.time_d, row.water_activity]),
        },
      ],
    }
  }, [result])

  const glassChartOption = useMemo<EChartsOption | null>(() => {
    if (!result) {
      return null
    }

    return {
      animation: false,
      color: ['#0f62fe', '#6f6f6f', '#fa4d56'],
      grid: { left: 56, right: 24, top: 48, bottom: 48 },
      legend: {
        data: ['Temperatur', 'Tg Vuataz', 'T > Tg'],
        top: 8,
        textStyle: { color: '#525252', fontSize: 12 },
      },
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'value',
        name: 'Zeit d',
        nameLocation: 'middle',
        nameGap: 30,
        axisLabel: { color: '#525252', fontSize: 12 },
        splitLine: { lineStyle: { color: '#e0e0e0' } },
      },
      yAxis: {
        type: 'value',
        name: 'Temperatur C',
        axisLabel: { color: '#525252', fontSize: 12 },
        splitLine: { lineStyle: { color: '#e0e0e0' } },
      },
      series: [
        {
          name: 'Temperatur',
          type: 'line',
          showSymbol: false,
          lineStyle: { width: 2 },
          data: result.time_series.map((row) => [row.time_d, row.temperature_c]),
        },
        {
          name: 'Tg Vuataz',
          type: 'line',
          showSymbol: false,
          lineStyle: { width: 2 },
          data: result.time_series.map((row) => [row.time_d, row.tg_vuataz_c]),
        },
        {
          name: 'T > Tg',
          type: 'line',
          showSymbol: false,
          connectNulls: false,
          lineStyle: { width: 3 },
          data: result.time_series.map((row) => [
            row.time_d,
            row.temperature_c > row.tg_vuataz_c ? row.temperature_c : null,
          ]),
        },
      ],
    }
  }, [result])

  const cakingRateChartOption = useMemo<EChartsOption | null>(() => {
    if (!result) {
      return null
    }

    return {
      animation: false,
      color: ['#fa4d56'],
      grid: { left: 64, right: 24, top: 48, bottom: 48 },
      legend: { top: 8, textStyle: { color: '#525252', fontSize: 12 } },
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'value',
        name: 'Zeit d',
        nameLocation: 'middle',
        nameGap: 30,
        axisLabel: { color: '#525252', fontSize: 12 },
        splitLine: { lineStyle: { color: '#e0e0e0' } },
      },
      yAxis: {
        type: 'value',
        name: 'dfc/dt Pa/h',
        axisLabel: { color: '#525252', fontSize: 12 },
        splitLine: { lineStyle: { color: '#e0e0e0' } },
      },
      series: [
        {
          name: 'Caking-Rate',
          type: 'line',
          showSymbol: false,
          lineStyle: { width: 2 },
          data: result.time_series.map((row) => [row.time_d, row.dfc_dt_pa_per_h]),
        },
      ],
    }
  }, [result])

  async function handlePreview() {
    if (!canSubmit) {
      return
    }

    setIsPreviewing(true)
    setMessage(null)
    try {
      const profilePreview = await previewProfile(buildProfileInput())
      setPreview(profilePreview)
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Profilprüfung fehlgeschlagen')
    } finally {
      setIsPreviewing(false)
    }
  }

  async function handleSimulate() {
    if (!canSubmit) {
      return
    }

    setIsSimulating(true)
    setMessage(null)
    setMoistureLimit(null)
    try {
      const simulationResult = await simulate(buildSimulationRequest())
      setResult(simulationResult)
      setPreview({
        source: profileSource === 'preset' ? selectedPreset : 'api_csv',
        preview: {
          duration_d: simulationResult.summary.final_time_d,
          n_points: simulationResult.time_series.length,
          temperature_min_c: Math.min(...simulationResult.time_series.map((row) => row.temperature_c)),
          temperature_max_c: Math.max(...simulationResult.time_series.map((row) => row.temperature_c)),
          temperature_mean_c: mean(simulationResult.time_series.map((row) => row.temperature_c)),
          relative_humidity_min_pct: Math.min(
            ...simulationResult.time_series.map((row) => row.relative_humidity_pct),
          ),
          relative_humidity_max_pct: Math.max(
            ...simulationResult.time_series.map((row) => row.relative_humidity_pct),
          ),
          relative_humidity_mean_pct: mean(
            simulationResult.time_series.map((row) => row.relative_humidity_pct),
          ),
        },
        warnings: simulationResult.warnings,
      })
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Simulation fehlgeschlagen')
    } finally {
      setIsSimulating(false)
    }
  }

  async function handleCalculateMoistureLimit() {
    if (!canCalculateMoistureLimit) {
      return
    }

    setIsCalculatingMoistureLimit(true)
    setMessage(null)
    try {
      const limitResult = await calculateMoistureLimit({
        ...buildSimulationRequest(),
        search_bounds: {
          min_initial_moisture_db_pct: parseRequiredNumber(moistureLimitBounds.minInitialMoisture),
          max_initial_moisture_db_pct: parseRequiredNumber(moistureLimitBounds.maxInitialMoisture),
          tolerance_db_pct: parseRequiredNumber(moistureLimitBounds.tolerance),
        },
      })
      setMoistureLimit(limitResult)
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Startfeuchte-Rückrechnung fehlgeschlagen')
    } finally {
      setIsCalculatingMoistureLimit(false)
    }
  }

  function buildSimulationRequest(): SimulationRequest {
    const climateProfile = buildProfileInput(false)
    const parameterOverrides = buildParameterOverrides(defaults, expertParameters)
    return {
      climate_profile: climateProfile,
      initial_moisture_db_pct: parseRequiredNumber(initialMoisture),
      consolidation_stress_kpa: parseRequiredNumber(consolidationStress),
      integration_method: integrationMethod,
      dt_d: parseOptionalPositiveNumber(dtD),
      ...(parameterOverrides ? { parameter_overrides: parameterOverrides } : {}),
    }
  }

  function buildProfileInput(includeDtD = true): ClimateProfileInput {
    const profileInput: ClimateProfileInput =
      profileSource === 'preset'
        ? { preset_name: selectedPreset }
        : { csv_text: csvText.trim() }
    const parsedDtD = parseOptionalPositiveNumber(dtD)

    if (includeDtD && parsedDtD !== undefined) {
      profileInput.dt_d = parsedDtD
    }

    return profileInput
  }

  async function handleCsvFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) {
      return
    }

    setMessage(null)
    try {
      const text = await file.text()
      setCsvText(text)
      setCsvFileName(file.name)
      setPreview(null)
      clearResultOutputs()
    } catch {
      setMessage('CSV-Datei konnte nicht gelesen werden')
    }
  }

  function handleProfileSourceChange(nextSource: ProfileSource) {
    setProfileSource(nextSource)
    setPreview(null)
    clearResultOutputs()
    setMessage(null)
  }

  function handleExpertFieldChange(field: keyof ExpertParameterState, value: string) {
    setExpertParameters((current) => ({ ...current, [field]: value }) as ExpertParameterState)
    clearResultOutputs()
  }

  function handleMoistureLimitBoundsChange(field: keyof MoistureLimitBoundsState, value: string) {
    setMoistureLimitBounds((current) => ({ ...current, [field]: value }))
    setMoistureLimit(null)
  }

  function handleMoistureLimitBoundsReset() {
    setMoistureLimitBounds(defaultMoistureLimitBounds)
    setMoistureLimit(null)
  }

  function handleExpertReset() {
    if (!defaults) {
      return
    }
    setExpertParameters(expertParametersFromDefaults(defaults))
    clearResultOutputs()
  }

  function clearResultOutputs() {
    setResult(null)
    setMoistureLimit(null)
  }

  function handleDownloadTimeSeries() {
    if (!result) {
      return
    }

    const csv = timeSeriesToCsv(result, {
      profileSource,
      selectedPreset,
      csvFileName,
      initialMoistureDbPct: parseRequiredNumber(initialMoisture),
      consolidationStressKpa: parseRequiredNumber(consolidationStress),
      integrationMethod,
      dtD: parseOptionalPositiveNumber(dtD),
    })
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = buildTimeSeriesFilename(profileSource, selectedPreset, csvFileName)
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <>
      <header className="top-bar">
        <div className="brand">
          <span className="brand-title">Powder Caking Simulator</span>
          <span className="brand-subtitle">Magermilchpulver im 25-kg-Sack</span>
        </div>
        <nav className="top-nav" aria-label="Hauptansicht">
          <button
            type="button"
            className={activeView === 'start' ? 'active' : ''}
            onClick={() => setActiveView('start')}
          >
            Start
          </button>
          <button
            type="button"
            className={activeView === 'simulator' ? 'active' : ''}
            onClick={() => setActiveView('simulator')}
          >
            Simulator
          </button>
          <button
            type="button"
            className={activeView === 'model' ? 'active' : ''}
            onClick={() => setActiveView('model')}
          >
            Modellgrundlage
          </button>
        </nav>
      </header>

      {activeView === 'start' ? (
        <StartView onNavigate={setActiveView} />
      ) : activeView === 'simulator' ? (
        <main className="page">
        <div className="layout">
          <section className="panel input-panel" aria-labelledby="input-title">
            <div className="panel-header">
              <h1 id="input-title" className="panel-title">
                Simulationseingaben
              </h1>
              <p className="panel-meta">Caking-Fit, Klimaprofil und Integrationsschritt</p>
            </div>
            <div className="panel-body field-stack">
              <fieldset className="segmented-field">
                <legend>Profilquelle</legend>
                <div className="segmented-control">
                  <label className={profileSource === 'preset' ? 'selected' : ''}>
                    <input
                      type="radio"
                      name="profile-source"
                      value="preset"
                      checked={profileSource === 'preset'}
                      onChange={() => handleProfileSourceChange('preset')}
                    />
                    Preset
                  </label>
                  <label className={profileSource === 'csv' ? 'selected' : ''}>
                    <input
                      type="radio"
                      name="profile-source"
                      value="csv"
                      checked={profileSource === 'csv'}
                      onChange={() => handleProfileSourceChange('csv')}
                    />
                    CSV
                  </label>
                </div>
              </fieldset>

              <div className="field">
                <label htmlFor="preset">Klimaprofil</label>
                <select
                  id="preset"
                  value={selectedPreset}
                  onChange={(event) => {
                    setSelectedPreset(event.target.value)
                    setPreview(null)
                    clearResultOutputs()
                  }}
                  disabled={!defaults || profileSource !== 'preset'}
                >
                  {presets.map((preset) => (
                    <option key={preset.name} value={preset.name}>
                      {presetLabels[preset.name] ?? preset.name}
                    </option>
                  ))}
                </select>
                {profileSource === 'preset' && selectedPresetDetails ? (
                  <span className="helper">Preset aktiv</span>
                ) : profileSource === 'csv' ? (
                  <span className="helper">CSV-Eingabe ist aktiv</span>
                ) : (
                  <span className="helper">Presets werden geladen</span>
                )}
              </div>

              {profileSource === 'csv' && (
                <div className="field">
                  <label htmlFor="csv-file">CSV-Profil</label>
                  <input id="csv-file" type="file" accept=".csv,text/csv" onChange={handleCsvFileChange} />
                  <span className="helper">
                    {csvFileName ?? 'Spalten: time_d, temperature_c, relative_humidity_pct'}
                  </span>
                  <textarea
                    id="csv-text"
                    value={csvText}
                    onChange={(event) => {
                      setCsvText(event.target.value)
                      setCsvFileName(null)
                      clearResultOutputs()
                    }}
                    spellCheck={false}
                    rows={8}
                    aria-label="CSV-Text"
                  />
                </div>
              )}

              <div className="field-row">
                <div className="field">
                  <label htmlFor="initial-moisture">Startfeuchte</label>
                  <input
                    id="initial-moisture"
                    inputMode="decimal"
                    value={initialMoisture}
                    onChange={(event) => {
                      setInitialMoisture(event.target.value)
                      clearResultOutputs()
                    }}
                  />
                  <span className="helper">% db</span>
                </div>
                <div className="field">
                  <label htmlFor="stress">Konsolidierung</label>
                  <select
                    id="stress"
                    value={consolidationStress}
                    onChange={(event) => {
                      setConsolidationStress(event.target.value)
                      clearResultOutputs()
                    }}
                  >
                    {(defaults?.available_consolidation_stress_kpa ?? [11, 20]).map((stress) => (
                      <option key={stress} value={stress}>
                        {formatNumber(stress, 0)} kPa
                      </option>
                    ))}
                  </select>
                  <span className="helper">verfügbare Fits</span>
                </div>
              </div>

              <div className="field-row">
                <div className="field">
                  <label htmlFor="method">Integration</label>
                  <select
                    id="method"
                    value={integrationMethod}
                    onChange={(event) => {
                      setIntegrationMethod(event.target.value as IntegrationMethod)
                      clearResultOutputs()
                    }}
                  >
                    {(defaults?.integration_methods ?? ['euler', 'heun']).map((method) => (
                      <option key={method} value={method}>
                        {method}
                      </option>
                    ))}
                  </select>
                  <span className="helper">Euler oder Heun</span>
                </div>
                <div className="field">
                  <label htmlFor="dt-d">dt_d</label>
                  <input
                    id="dt-d"
                    inputMode="decimal"
                    value={dtD}
                    onChange={(event) => {
                      setDtD(event.target.value)
                      clearResultOutputs()
                    }}
                  />
                  <span className="helper">Tage je Schritt</span>
                </div>
              </div>

              <section className="expert-panel" aria-label="Expertenmodus">
                <button
                  type="button"
                  className="expert-toggle"
                  aria-expanded={isExpertOpen}
                  onClick={() => setIsExpertOpen((current) => !current)}
                >
                  <span>Expertenmodus</span>
                  <span className="expert-toggle-meta">
                    {isExpertOpen ? 'Parameter ausblenden' : 'Parameter bearbeiten'}
                  </span>
                </button>

                {isExpertOpen && (
                  <div className="expert-body">
                    <div className="expert-header">
                      <p>
                        Geänderte Werte werden als Overrides gesendet. Unveränderte Werte bleiben CSV-Defaults.
                      </p>
                      <button
                        type="button"
                        className="button-secondary compact-button"
                        onClick={handleExpertReset}
                        disabled={!defaults}
                      >
                        Defaults
                      </button>
                    </div>

                    <fieldset className="expert-group">
                      <legend>GAB</legend>
                      <div className="field-row">
                        <ExpertNumberField
                          id="expert-gab-mo"
                          label="Mo"
                          value={expertParameters.gabMo}
                          unit="% db"
                          onChange={(value) => handleExpertFieldChange('gabMo', value)}
                        />
                        <ExpertNumberField
                          id="expert-gab-c"
                          label="C"
                          value={expertParameters.gabC}
                          onChange={(value) => handleExpertFieldChange('gabC', value)}
                        />
                      </div>
                      <ExpertNumberField
                        id="expert-gab-f"
                        label="f"
                        value={expertParameters.gabF}
                        onChange={(value) => handleExpertFieldChange('gabF', value)}
                      />
                    </fieldset>

                    <fieldset className="expert-group">
                      <legend>Sack</legend>
                      <div className="field-row">
                        <ExpertNumberField
                          id="expert-sack-mass"
                          label="Sackmasse"
                          value={expertParameters.sackMassKg}
                          unit="kg"
                          onChange={(value) => handleExpertFieldChange('sackMassKg', value)}
                        />
                        <ExpertNumberField
                          id="expert-sack-area"
                          label="Sackfläche"
                          value={expertParameters.sackAreaM2}
                          unit="m2"
                          onChange={(value) => handleExpertFieldChange('sackAreaM2', value)}
                        />
                      </div>
                    </fieldset>

                    <fieldset className="expert-group">
                      <legend>Schwelle</legend>
                      <div className="field-row">
                        <ExpertNumberField
                          id="expert-initial-sigma"
                          label="Initiale sigma_c"
                          value={expertParameters.initialSigmaCKpa}
                          unit="kPa"
                          onChange={(value) => handleExpertFieldChange('initialSigmaCKpa', value)}
                        />
                        <ExpertNumberField
                          id="expert-critical-sigma"
                          label="Kritische sigma_c"
                          value={expertParameters.criticalSigmaCKpa}
                          unit="kPa"
                          onChange={(value) => handleExpertFieldChange('criticalSigmaCKpa', value)}
                        />
                      </div>
                    </fieldset>

                    <fieldset className="expert-group">
                      <legend>Permeabilität</legend>
                      <div className="field">
                        <label htmlFor="expert-permeability-mode">Modus</label>
                        <select
                          id="expert-permeability-mode"
                          value={expertParameters.permeabilityMode}
                          onChange={(event) =>
                            handleExpertFieldChange('permeabilityMode', event.target.value as PermeabilityMode)
                          }
                        >
                          <option value="temperature_dependent">temperature_dependent</option>
                          <option value="constant">constant</option>
                        </select>
                        <span className="helper">Arrhenius oder konstanter k/delta-Wert</span>
                      </div>

                      {expertParameters.permeabilityMode === 'temperature_dependent' ? (
                        <>
                          <ExpertNumberField
                            id="expert-k0"
                            label="k0"
                            value={expertParameters.permeabilityK0}
                            unit="kg/(m2*d*Pa)"
                            onChange={(value) => handleExpertFieldChange('permeabilityK0', value)}
                          />
                          <div className="field-row">
                            <ExpertNumberField
                              id="expert-ea"
                              label="Aktivierungsenergie"
                              value={expertParameters.permeabilityActivationEnergy}
                              unit="J/kmol"
                              onChange={(value) => handleExpertFieldChange('permeabilityActivationEnergy', value)}
                            />
                            <ExpertNumberField
                              id="expert-r"
                              label="Gaskonstante"
                              value={expertParameters.permeabilityGasConstant}
                              unit="J/(kmol*K)"
                              onChange={(value) => handleExpertFieldChange('permeabilityGasConstant', value)}
                            />
                          </div>
                        </>
                      ) : (
                        <ExpertNumberField
                          id="expert-constant-k"
                          label="k/delta konstant"
                          value={expertParameters.permeabilityConstantK}
                          placeholder={constantPermeabilityPlaceholder}
                          unit="kg/(m2*d*Pa)"
                          onChange={(value) => handleExpertFieldChange('permeabilityConstantK', value)}
                        />
                      )}
                    </fieldset>
                  </div>
                )}
              </section>

              <div className="button-row">
                <button className="button-secondary" onClick={handlePreview} disabled={!canSubmit || isPreviewing}>
                  {isPreviewing ? 'Prüfe Profil' : 'Profil prüfen'}
                </button>
                <button className="button-primary" onClick={handleSimulate} disabled={!canSubmit || isSimulating}>
                  {isSimulating ? 'Simuliere' : 'Simulieren'}
                </button>
              </div>

              <section className="moisture-limit-panel" aria-label="Startfeuchte-Rückrechnung">
                <div className="moisture-limit-actions">
                  <div>
                    <h2>Startfeuchte-Rückrechnung</h2>
                    <p>
                      Suchbereich: {formatBoundsLabel(moistureLimitBounds.minInitialMoisture)} bis{' '}
                      {formatBoundsLabel(moistureLimitBounds.maxInitialMoisture)} % db
                    </p>
                  </div>
                  <button
                    type="button"
                    className="button-secondary compact-button"
                    onClick={handleCalculateMoistureLimit}
                    disabled={!canCalculateMoistureLimit || isCalculatingMoistureLimit}
                  >
                    {isCalculatingMoistureLimit ? 'Berechne' : 'Limit berechnen'}
                  </button>
                </div>
                {!result && (
                  <p className="moisture-limit-hint">
                    Bitte zuerst das Profil simulieren. Danach kann das Startfeuchte-Limit berechnet werden.
                  </p>
                )}
                {isCalculatingMoistureLimit && (
                  <div className="moisture-limit-progress" role="status" aria-live="polite">
                    <span className="moisture-limit-progress-bar" />
                    <span>Startfeuchte-Limit wird berechnet</span>
                  </div>
                )}
                <button
                  type="button"
                  className="moisture-limit-toggle"
                  aria-expanded={isMoistureLimitBoundsOpen}
                  onClick={() => setIsMoistureLimitBoundsOpen((current) => !current)}
                >
                  {isMoistureLimitBoundsOpen ? 'Suchgrenzen ausblenden' : 'Suchgrenzen anpassen'}
                </button>

                {isMoistureLimitBoundsOpen && (
                  <div className="moisture-limit-body">
                    <div className="field-row">
                      <ExpertNumberField
                        id="moisture-limit-min"
                        label="Untere Grenze"
                        value={moistureLimitBounds.minInitialMoisture}
                        unit="% db"
                        onChange={(value) => handleMoistureLimitBoundsChange('minInitialMoisture', value)}
                      />
                      <ExpertNumberField
                        id="moisture-limit-max"
                        label="Obere Grenze"
                        value={moistureLimitBounds.maxInitialMoisture}
                        unit="% db"
                        onChange={(value) => handleMoistureLimitBoundsChange('maxInitialMoisture', value)}
                      />
                    </div>
                    <div className="moisture-limit-footer">
                      <ExpertNumberField
                        id="moisture-limit-tolerance"
                        label="Toleranz"
                        value={moistureLimitBounds.tolerance}
                        unit="% db"
                        onChange={(value) => handleMoistureLimitBoundsChange('tolerance', value)}
                      />
                      <button
                        type="button"
                        className="button-secondary compact-button"
                        onClick={handleMoistureLimitBoundsReset}
                      >
                        Zurücksetzen
                      </button>
                    </div>
                  </div>
                )}
              </section>
            </div>
          </section>

          <section className="result-band" aria-label="Simulationsergebnis">
            <div className="kpi-grid">
              <Kpi
                label="End-sigma_c"
                value={result ? formatNumber(result.summary.final_sigma_c_kpa, 2) : '-'}
                unit="kPa"
                status={statusClass}
              />
              <Kpi
                label="Caking-Status"
                value={result ? (result.summary.is_caked ? 'Verklumpt' : 'Nicht verklumpt') : '-'}
                unit="Schwelle 20 kPa"
                status={statusClass}
              />
              <Kpi
                label="Zeit bis kritisch"
                value={
                  result?.summary.time_to_critical_d == null
                    ? '-'
                    : formatNumber(result.summary.time_to_critical_d, 2)
                }
                unit="d"
                status={result?.summary.time_to_critical_d == null ? 'success' : 'danger'}
              />
              <Kpi
                label="Endfeuchte"
                value={result ? formatNumber(result.summary.final_moisture_db_pct, 3) : '-'}
                unit="% db"
              />
              <Kpi
                label="End-aw"
                value={result ? formatNumber(result.summary.final_water_activity, 3) : '-'}
                unit="dimensionslos"
              />
              <Kpi
                label="max. T - Tg"
                value={result ? formatNumber(result.summary.max_t_minus_tg_c, 2) : '-'}
                unit="C"
                status={result && result.summary.max_t_minus_tg_c > 0 ? 'warning' : undefined}
              />
            </div>

            <div className="panel moisture-limit-result">
              <div className="panel-header">
                <h2 className="panel-title">Startfeuchte-Limit</h2>
                <p className="panel-meta">Rückrechnung über den bestehenden Simulationskern</p>
              </div>
              <div className="preview-grid">
                <Metric
                  label="Max. sichere Startfeuchte"
                  value={formatMoistureLimitValue(moistureLimit)}
                  status={getMoistureLimitStatus(moistureLimit)}
                />
                <Metric
                  label="Aktuelle Startfeuchte"
                  value={
                    moistureLimit
                      ? `${formatNumber(moistureLimit.current_initial_moisture_db_pct, 2)} % db`
                      : '-'
                  }
                  status={moistureLimit?.is_current_profile_safe === false ? 'danger' : undefined}
                />
                <Metric
                  label="Feuchtemarge"
                  value={
                    moistureLimit?.moisture_margin_db_pct == null
                      ? '-'
                      : `${formatSignedNumber(moistureLimit.moisture_margin_db_pct, 2)} % db`
                  }
                  status={moistureMarginStatus}
                />
                <Metric
                  label="Aktuelles Profil"
                  value={
                    moistureLimit
                      ? moistureLimit.is_current_profile_safe
                        ? 'Sicher'
                        : 'Verklumpt'
                      : '-'
                  }
                  status={
                    moistureLimit
                      ? moistureLimit.is_current_profile_safe
                        ? 'success'
                        : 'danger'
                      : undefined
                  }
                />
              </div>
              <div className="preview-grid secondary-preview-grid">
                <Metric
                  label="sigma_c am Limit"
                  value={
                    moistureLimit?.final_sigma_c_kpa_at_limit == null
                      ? '-'
                      : `${formatNumber(moistureLimit.final_sigma_c_kpa_at_limit, 2)} kPa`
                  }
                  status={getSigmaLimitStatus(moistureLimit)}
                />
                <Metric
                  label="Kritische sigma_c"
                  value={
                    moistureLimit ? `${formatNumber(moistureLimit.critical_sigma_c_kpa, 2)} kPa` : '-'
                  }
                />
                <Metric
                  label="Iterationen"
                  value={moistureLimit ? String(moistureLimit.iterations) : '-'}
                />
                <Metric
                  label="Suchbereich"
                  value={`${formatBoundsLabel(moistureLimitBounds.minInitialMoisture)} bis ${formatBoundsLabel(
                    moistureLimitBounds.maxInitialMoisture,
                  )} % db`}
                />
              </div>
            </div>

            <div className="panel">
              <div className="panel-header">
                <h2 className="panel-title">Profilvorschau</h2>
                <p className="panel-meta">{previewSourceLabel}</p>
              </div>
              <div className="preview-grid">
                <Metric label="Dauer" value={preview ? `${formatNumber(preview.preview.duration_d, 2)} d` : '-'} />
                <Metric label="Punkte" value={preview ? String(preview.preview.n_points) : '-'} />
                <Metric
                  label="Temperatur"
                  value={
                    preview
                      ? `${formatNumber(preview.preview.temperature_min_c, 1)} bis ${formatNumber(
                          preview.preview.temperature_max_c,
                          1,
                        )} C`
                      : '-'
                  }
                />
                <Metric
                  label="Relative Feuchte"
                  value={
                    preview
                      ? `${formatNumber(preview.preview.relative_humidity_min_pct, 1)} bis ${formatNumber(
                          preview.preview.relative_humidity_max_pct,
                          1,
                        )} %`
                      : '-'
                  }
                />
              </div>
            </div>

            {(message || allWarnings.length > 0) && (
              <div className="warning-list" aria-live="polite">
                {message && <div className="banner danger">{message}</div>}
                {Array.from(new Set(allWarnings)).map((warning) => (
                  <div className="banner" key={warning}>
                    {warning}
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>

        <section className="panel chart-panel" aria-labelledby="chart-tabs-title">
          <div className="panel-header chart-panel-header">
            <div>
              <h2 id="chart-tabs-title" className="panel-title">
                Ergebnisdiagramme
              </h2>
              <p className="panel-meta">Klima, Feuchte, Glasübergang und Caking-Kinetik</p>
            </div>
            <button
              className="button-secondary"
              type="button"
              onClick={handleDownloadTimeSeries}
              disabled={!result}
            >
              Zeitreihe exportieren
            </button>
          </div>
          <div className="chart-tabs" role="tablist" aria-label="Diagrammgruppe">
            {chartTabs.map((tab) => (
              <button
                key={tab.id}
                type="button"
                className={activeChartTab === tab.id ? 'active' : ''}
                role="tab"
                aria-selected={activeChartTab === tab.id}
                onClick={() => setActiveChartTab(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {activeChartTab === 'climate' && (
            <ChartBlock
              description="Temperatur und relative Feuchte über Transportzeit"
              emptyText="Simulation starten, um das Klimaprofil zu laden."
              option={climateChartOption}
            />
          )}
          {activeChartTab === 'moisture' && (
            <ChartBlock
              description="Pulverfeuchte und Wasseraktivität aus der Wasserbilanz"
              emptyText="Simulation starten, um Feuchte und aw zu berechnen."
              option={moistureChartOption}
            />
          )}
          {activeChartTab === 'glass' && (
            <ChartBlock
              description="Temperatur, Tg nach Vuataz und rot markierte Temperatursegmente für T > Tg"
              emptyText="Simulation starten, um Tg und die Überschreitungssegmente zu berechnen."
              option={glassChartOption}
            />
          )}
          {activeChartTab === 'caking' && (
            <div className="chart-stack">
              <ChartBlock
                description="Cake-Festigkeit sigma_c mit roter 20-kPa-Referenzlinie"
                emptyText="Simulation starten, um die Festigkeit zu berechnen."
                option={strengthChartOption}
              />
              <ChartBlock
                description="Caking-Rate dfc/dt in Pa/h"
                emptyText="Simulation starten, um die Caking-Rate zu berechnen."
                option={cakingRateChartOption}
              />
            </div>
          )}
          {activeChartTab === 'parameters' && (
            <ParameterTraceability sections={parameterSections} hasResult={result !== null} />
          )}
        </section>
        </main>
      ) : (
        <ModelFoundationView />
      )}
    </>
  )
}

function StartView({ onNavigate }: { onNavigate: (view: AppView) => void }) {
  return (
    <main className="page start-page">
      <section className="start-hero" aria-labelledby="start-title">
        <img
          className="start-hero-image"
          src={heroPowderSacks}
          alt="Palettierte Pulversäcke im Lager"
        />
        <div className="start-hero-copy">
          <p className="eyebrow">Transport- und Lagerbewertung</p>
          <h1 id="start-title">Caking-Risiko von Magermilchpulver bewerten</h1>
          <p>Feuchteaufnahme, Glasübergang und Festigkeitsaufbau aus Klimaprofilen berechnen.</p>
          <div className="start-hero-actions">
            <button type="button" className="button-primary start-cta" onClick={() => onNavigate('simulator')}>
              Zum Simulator
            </button>
            <button type="button" className="button-secondary start-cta" onClick={() => onNavigate('model')}>
              Zur Modellgrundlage
            </button>
          </div>
        </div>
      </section>

      <section className="start-orientation" aria-labelledby="orientation-title">
        <div className="panel start-orientation-panel">
          <div className="panel-header">
            <h2 id="orientation-title" className="panel-title">
              Einstieg
            </h2>
            <p className="panel-meta">Vom Profil zur sicheren Startfeuchte</p>
          </div>
          <div className="start-points">
            {startOrientationPoints.map((point) => (
              <article className="start-point" key={point.title}>
                <span className="metric-label">{point.title}</span>
                <p>{point.description}</p>
              </article>
            ))}
          </div>
        </div>
        <figure className="start-secondary-image">
          <img src={labMoistureAnalysis} alt="Laboranalyse einer Pulverprobe" />
        </figure>
      </section>
    </main>
  )
}

function Kpi({
  label,
  value,
  unit,
  status,
}: {
  label: string
  value: string
  unit: string
  status?: 'success' | 'warning' | 'danger'
}) {
  return (
    <div className={`kpi ${status ?? ''}`}>
      <span className="kpi-label">{label}</span>
      <strong className="kpi-value">{value}</strong>
      <span className="kpi-unit">{unit}</span>
    </div>
  )
}

function Metric({
  label,
  value,
  status,
}: {
  label: string
  value: string
  status?: 'success' | 'warning' | 'danger'
}) {
  return (
    <div className={`metric ${status ?? ''}`}>
      <span className="metric-label">{label}</span>
      <strong className="metric-value">{value}</strong>
    </div>
  )
}

function ChartBlock({
  description,
  emptyText,
  option,
}: {
  description: string
  emptyText: string
  option: EChartsOption | null
}) {
  return (
    <div className="chart-block" role="tabpanel">
      <p className="chart-description">{description}</p>
      {option ? <TimeSeriesChart option={option} /> : <div className="empty-chart">{emptyText}</div>}
    </div>
  )
}

function ExpertNumberField({
  id,
  label,
  value,
  placeholder,
  unit,
  onChange,
}: {
  id: string
  label: string
  value: string
  placeholder?: string
  unit?: string
  onChange: (value: string) => void
}) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        inputMode="decimal"
        placeholder={placeholder}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
      <span className={unit ? 'helper' : 'helper helper-placeholder'}>{unit ?? 'Einheit'}</span>
    </div>
  )
}

function ModelFoundationView() {
  return (
    <main className="page model-page">
      <section className="model-intro" aria-labelledby="model-title">
        <div>
          <p className="eyebrow">Modellgrundlage</p>
          <h1 id="model-title">Berechnung Caking</h1>
        </div>
      </section>

      <section className="panel model-section" aria-labelledby="process-title">
        <div className="panel-header">
          <h2 id="process-title" className="panel-title">
            Prozesskette
          </h2>
          <p className="panel-meta">Vom Pulverzustand zur Caking-Entscheidung</p>
        </div>
        <p className="process-summary">
          Startfeuchte, Transportklima, Wasserdampftransport, Wasseraktivität, Glasübergang und
          Caking-Kinetik werden zu einer Festigkeitszeitreihe gekoppelt. Die Entscheidung erfolgt bei{' '}
          <span className="inline-equation">
            &sigma;<sub>c</sub> &gt;= 20 kPa
          </span>
          .
        </p>
        <ol className="process-chain">
          {processSteps.map((step) => (
            <li key={step.title}>
              <span className="process-index">{step.index}</span>
              <div>
                <h3>{step.title}</h3>
                <p>{step.description}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className="panel model-section" aria-labelledby="formula-title">
        <div className="panel-header">
          <h2 id="formula-title" className="panel-title">
            Formeln und Einheiten
          </h2>
          <p className="panel-meta">Kernbeziehungen des Simulationskerns</p>
        </div>
        <div className="formula-grid">
          {formulaBlocks.map((block) => (
            <article className="formula-block" key={block.title}>
              <h3>{block.title}</h3>
              <div className="formula-rendered">{block.formula}</div>
              <p>{block.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="panel model-section" aria-labelledby="assumptions-title">
        <div className="panel-header">
          <h2 id="assumptions-title" className="panel-title">
            Modellannahmen und Grenzen
          </h2>
          <p className="panel-meta">Vereinfachungen und fachlicher Gültigkeitsbereich</p>
        </div>
        <div className="model-assumptions">
          {modelAssumptions.map((item) => (
            <article className="model-assumption" key={item.title}>
              <h3>{item.title}</h3>
              <p>{item.description}</p>
            </article>
          ))}
        </div>
      </section>
    </main>
  )
}

const startOrientationPoints = [
  {
    title: 'Klimaprofil wählen',
    description: 'Preset, CSV oder reales Loggerprofil.',
  },
  {
    title: 'Caking-Risiko berechnen',
    description: (
      <>
        Verlauf von Pulverfestigkeit (
        <span className="inline-equation">
          σ<sub>c</sub>
        </span>
        ), Feuchte, Wasseraktivität, Glasübergang und Caking-Risiko für Klimaprofile bestimmen.
      </>
    ),
  },
  {
    title: 'Sichere Startfeuchte bestimmen',
    description:
      'Sichere Startfeuchte für gegebene Klimaprofile bestimmen um Caking während des Transports zu vermeiden.',
  },
]

function Fraction({
  numerator,
  denominator,
}: {
  numerator: ReactNode
  denominator: ReactNode
}) {
  return (
    <span className="math-frac">
      <span>{numerator}</span>
      <span>{denominator}</span>
    </span>
  )
}

function ParameterTraceability({
  sections,
  hasResult,
}: {
  sections: ParameterSection[]
  hasResult: boolean
}) {
  if (!hasResult) {
    return (
      <div className="parameter-empty" role="tabpanel">
        Simulation starten, um die verwendeten Parameter zu laden.
      </div>
    )
  }

  return (
    <div className="parameter-view" role="tabpanel">
      <p className="chart-description">
        Verwendete Lauf-, Modell- und Entscheidungsparameter aus der SimulationResponse
      </p>
      <div className="parameter-section-grid">
        {sections.map((section) => (
          <section className="parameter-section" key={section.title} aria-label={section.title}>
            <h3>{section.title}</h3>
            <table className="parameter-table">
              <tbody>
                {section.rows.map((row) => (
                  <tr key={row.label}>
                    <th scope="row">{row.label}</th>
                    <td className="mono">{row.value}</td>
                    <td>{row.unit ?? ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        ))}
      </div>
    </div>
  )
}

function parseRequiredNumber(value: string): number {
  const parsed = Number(value.replace(',', '.'))
  if (!Number.isFinite(parsed)) {
    throw new Error('Bitte numerische Eingaben prüfen')
  }
  return parsed
}

function parseOptionalPositiveNumber(value: string): number | undefined {
  if (value.trim() === '') {
    return undefined
  }
  const parsed = parseRequiredNumber(value)
  if (parsed <= 0) {
    throw new Error('dt_d muss größer als 0 sein')
  }
  return parsed
}

function parseOptionalExpertNumber(value: string, label: string): number | undefined {
  if (value.trim() === '') {
    return undefined
  }
  const parsed = Number(value.replace(',', '.'))
  if (!Number.isFinite(parsed)) {
    throw new Error(`${label}: numerischen Wert prüfen`)
  }
  return parsed
}

function expertParametersFromDefaults(defaults: ModelDefaults): ExpertParameterState {
  const { parameters } = defaults
  return {
    gabMo: formatInputNumber(parameters.gab.mo),
    gabC: formatInputNumber(parameters.gab.c),
    gabF: formatInputNumber(parameters.gab.f),
    sackMassKg: formatInputNumber(parameters.sack_mass_kg),
    sackAreaM2: formatInputNumber(parameters.sack_area_m2),
    initialSigmaCKpa: formatInputNumber(parameters.initial_sigma_c_kpa),
    criticalSigmaCKpa: formatInputNumber(parameters.critical_sigma_c_kpa),
    permeabilityMode: parameters.permeability.mode,
    permeabilityK0: formatInputNumber(parameters.permeability.k0),
    permeabilityActivationEnergy: formatInputNumber(parameters.permeability.activation_energy_j_per_kmol),
    permeabilityGasConstant: formatInputNumber(parameters.permeability.gas_constant_j_per_kmol_k),
    permeabilityConstantK:
      parameters.permeability.k_over_delta_kg_per_m2_d_pa == null
        ? ''
        : formatInputNumber(parameters.permeability.k_over_delta_kg_per_m2_d_pa),
  }
}

function buildParameterOverrides(
  defaults: ModelDefaults | null,
  expertParameters: ExpertParameterState,
): ParameterOverrides | undefined {
  if (!defaults) {
    return undefined
  }

  const defaultParameters = defaults.parameters
  const overrides: ParameterOverrides = {}

  const gabMo = parseOptionalExpertNumber(expertParameters.gabMo, 'GAB Mo')
  const gabC = parseOptionalExpertNumber(expertParameters.gabC, 'GAB C')
  const gabF = parseOptionalExpertNumber(expertParameters.gabF, 'GAB f')
  if (gabMo !== undefined && valueDiffers(gabMo, defaultParameters.gab.mo)) {
    overrides.gab = { ...overrides.gab, mo: gabMo }
  }
  if (gabC !== undefined && valueDiffers(gabC, defaultParameters.gab.c)) {
    overrides.gab = { ...overrides.gab, c: gabC }
  }
  if (gabF !== undefined && valueDiffers(gabF, defaultParameters.gab.f)) {
    overrides.gab = { ...overrides.gab, f: gabF }
  }

  const sackMassKg = parseOptionalExpertNumber(expertParameters.sackMassKg, 'Sackmasse')
  const sackAreaM2 = parseOptionalExpertNumber(expertParameters.sackAreaM2, 'Sackfläche')
  if (sackMassKg !== undefined && valueDiffers(sackMassKg, defaultParameters.sack_mass_kg)) {
    overrides.sack = { ...overrides.sack, sack_mass_kg: sackMassKg }
  }
  if (sackAreaM2 !== undefined && valueDiffers(sackAreaM2, defaultParameters.sack_area_m2)) {
    overrides.sack = { ...overrides.sack, sack_area_m2: sackAreaM2 }
  }

  const initialSigmaCKpa = parseOptionalExpertNumber(expertParameters.initialSigmaCKpa, 'Initiale sigma_c')
  const criticalSigmaCKpa = parseOptionalExpertNumber(expertParameters.criticalSigmaCKpa, 'Kritische sigma_c')
  if (initialSigmaCKpa !== undefined && valueDiffers(initialSigmaCKpa, defaultParameters.initial_sigma_c_kpa)) {
    overrides.caking_threshold = { ...overrides.caking_threshold, initial_sigma_c_kpa: initialSigmaCKpa }
  }
  if (criticalSigmaCKpa !== undefined && valueDiffers(criticalSigmaCKpa, defaultParameters.critical_sigma_c_kpa)) {
    overrides.caking_threshold = { ...overrides.caking_threshold, critical_sigma_c_kpa: criticalSigmaCKpa }
  }

  const permeabilityMode = expertParameters.permeabilityMode
  if (permeabilityMode !== defaultParameters.permeability.mode) {
    overrides.permeability = { ...overrides.permeability, mode: permeabilityMode }
  }

  if (permeabilityMode === 'temperature_dependent') {
    const k0 = parseOptionalExpertNumber(expertParameters.permeabilityK0, 'k0')
    const activationEnergy = parseOptionalExpertNumber(
      expertParameters.permeabilityActivationEnergy,
      'Aktivierungsenergie',
    )
    const gasConstant = parseOptionalExpertNumber(expertParameters.permeabilityGasConstant, 'Gaskonstante')
    if (k0 !== undefined && valueDiffers(k0, defaultParameters.permeability.k0)) {
      overrides.permeability = { ...overrides.permeability, k0 }
    }
    if (
      activationEnergy !== undefined &&
      valueDiffers(activationEnergy, defaultParameters.permeability.activation_energy_j_per_kmol)
    ) {
      overrides.permeability = {
        ...overrides.permeability,
        activation_energy_j_per_kmol: activationEnergy,
      }
    }
    if (
      gasConstant !== undefined &&
      valueDiffers(gasConstant, defaultParameters.permeability.gas_constant_j_per_kmol_k)
    ) {
      overrides.permeability = { ...overrides.permeability, gas_constant_j_per_kmol_k: gasConstant }
    }
  } else {
    const constantK = parseOptionalExpertNumber(expertParameters.permeabilityConstantK, 'k/delta konstant')
    if (constantK === undefined) {
      throw new Error('Konstante Permeabilität braucht k/delta')
    }
    if (valueDiffers(constantK, defaultParameters.permeability.k_over_delta_kg_per_m2_d_pa ?? undefined)) {
      overrides.permeability = { ...overrides.permeability, k_over_delta_kg_per_m2_d_pa: constantK }
    }
  }

  return Object.keys(overrides).length > 0 ? overrides : undefined
}

function valueDiffers(value: number | undefined, defaultValue: number | undefined): boolean {
  if (value === undefined) {
    return false
  }
  if (defaultValue === undefined) {
    return true
  }
  return Math.abs(value - defaultValue) > 1e-12
}

function defaultClimatePreset(apiPresetNames: string[], climatePresets: ClimatePreset[]): string {
  const preferredPreset = 'real_container_logger_profile'
  if (apiPresetNames.includes(preferredPreset)) {
    return preferredPreset
  }
  if (climatePresets.some((preset) => preset.name === preferredPreset)) {
    return preferredPreset
  }
  return apiPresetNames[0] ?? climatePresets[0]?.name ?? ''
}

function isProfileInputReady(source: ProfileSource, presetName: string, csvProfileText: string): boolean {
  if (source === 'preset') {
    return presetName !== ''
  }
  return csvProfileText.trim() !== ''
}

function buildPreviewSourceLabel(
  profileSource: ProfileSource,
  selectedPreset: string,
  csvFileName: string | null,
  apiSource: string | null | undefined,
): string {
  if (profileSource === 'preset') {
    return presetLabels[selectedPreset] ?? selectedPreset ?? 'Preset'
  }

  if (csvFileName) {
    return csvFileName
  }

  if (apiSource && !looksLikePath(apiSource)) {
    return apiSource
  }

  return 'CSV-Eingabe'
}

function looksLikePath(value: string): boolean {
  return value.includes('/') || value.includes('\\')
}

function mean(values: number[]): number {
  return values.reduce((sum, value) => sum + value, 0) / values.length
}

function formatNumber(value: number, fractionDigits: number): string {
  return new Intl.NumberFormat('de-DE', {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(value)
}

function formatInputNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : String(value)
}

function formatBoundsLabel(value: string): string {
  const parsed = Number(value.replace(',', '.'))
  if (!Number.isFinite(parsed)) {
    return value || '-'
  }
  return formatNumber(parsed, 1)
}

function formatSignedNumber(value: number, fractionDigits: number): string {
  const formatted = formatNumber(value, fractionDigits)
  return value > 0 ? `+${formatted}` : formatted
}

function formatMoistureLimitValue(moistureLimit: MoistureLimitResponse | null): string {
  if (!moistureLimit) {
    return '-'
  }
  if (moistureLimit.safe_initial_moisture_db_pct == null) {
    return 'kein sicherer Wert'
  }
  const prefix = moistureLimit.warnings.some((warning) => warning.includes('upper search bound remains safe'))
    ? '>= '
    : ''
  return `${prefix}${formatNumber(moistureLimit.safe_initial_moisture_db_pct, 2)} % db`
}

function getMoistureMarginStatus(
  moistureLimit: MoistureLimitResponse | null,
): 'success' | 'warning' | 'danger' | undefined {
  const margin = moistureLimit?.moisture_margin_db_pct
  if (margin == null) {
    return undefined
  }
  if (margin < 0) {
    return 'danger'
  }
  if (margin <= 0.1) {
    return 'warning'
  }
  return 'success'
}

function getMoistureLimitStatus(
  moistureLimit: MoistureLimitResponse | null,
): 'success' | 'warning' | 'danger' | undefined {
  if (!moistureLimit) {
    return undefined
  }
  if (moistureLimit.safe_initial_moisture_db_pct == null) {
    return 'danger'
  }
  if (moistureLimit.warnings.length > 0) {
    return 'warning'
  }
  return 'success'
}

function getSigmaLimitStatus(
  moistureLimit: MoistureLimitResponse | null,
): 'success' | 'warning' | 'danger' | undefined {
  if (!moistureLimit || moistureLimit.final_sigma_c_kpa_at_limit == null) {
    return undefined
  }
  const distanceToCritical = moistureLimit.critical_sigma_c_kpa - moistureLimit.final_sigma_c_kpa_at_limit
  if (distanceToCritical < 0) {
    return 'danger'
  }
  if (distanceToCritical <= 1) {
    return 'warning'
  }
  return 'success'
}

function formatParameterNumber(value: number, fractionDigits = 4): string {
  const absoluteValue = Math.abs(value)
  if (absoluteValue > 0 && (absoluteValue < 0.001 || absoluteValue >= 100000)) {
    return value.toExponential(4)
  }
  return formatNumber(value, fractionDigits)
}

function timeSeriesToCsv(
  simulationResult: SimulationResponse,
  exportContext: TimeSeriesExportContext,
): string {
  const exportMetadata = buildTimeSeriesExportMetadata(simulationResult, exportContext)
  const header = [...exportMetadata.map(([name]) => name), ...timeSeriesExportColumns]
  const rows = simulationResult.time_series.map((row) =>
    [
      ...exportMetadata.map(([, value]) => csvCell(value)),
      ...timeSeriesExportColumns.map((column) => csvCell(row[column])),
    ],
  )
  return [header.join(','), ...rows.map((row) => row.join(','))].join('\n')
}

function buildTimeSeriesExportMetadata(
  simulationResult: SimulationResponse,
  exportContext: TimeSeriesExportContext,
): Array<[string, CsvValue]> {
  const { parameters, summary, warnings } = simulationResult
  const exportedAt = new Date().toISOString()
  const runId = buildRunId(exportContext.profileSource, exportContext.selectedPreset, exportContext.csvFileName)

  return [
    ['run_id', runId],
    ['exported_at', exportedAt],
    ['run_profile_source', exportContext.profileSource],
    [
      'run_profile_label',
      buildPreviewSourceLabel(
        exportContext.profileSource,
        exportContext.selectedPreset,
        exportContext.csvFileName,
        exportContext.profileSource === 'preset' ? exportContext.selectedPreset : null,
      ),
    ],
    ['run_preset_name', exportContext.profileSource === 'preset' ? exportContext.selectedPreset : ''],
    ['run_csv_file_name', exportContext.profileSource === 'csv' ? exportContext.csvFileName ?? '' : ''],
    ['run_initial_moisture_db_pct', exportContext.initialMoistureDbPct],
    ['run_consolidation_stress_kpa', exportContext.consolidationStressKpa],
    ['run_integration_method', exportContext.integrationMethod],
    ['run_dt_d', exportContext.dtD ?? ''],
    ['summary_final_time_d', summary.final_time_d],
    ['summary_final_sigma_c_kpa', summary.final_sigma_c_kpa],
    ['summary_critical_sigma_c_kpa', summary.critical_sigma_c_kpa],
    ['summary_is_caked', summary.is_caked],
    ['summary_time_to_critical_d', summary.time_to_critical_d ?? ''],
    ['summary_final_moisture_db_pct', summary.final_moisture_db_pct],
    ['summary_final_water_activity', summary.final_water_activity],
    ['summary_max_t_minus_tg_c', summary.max_t_minus_tg_c],
    ['summary_max_dfc_dt_pa_per_h', summary.max_dfc_dt_pa_per_h],
    ['parameter_sack_mass_kg', parameters.sack_mass_kg],
    ['parameter_sack_area_m2', parameters.sack_area_m2],
    ['parameter_initial_sigma_c_kpa', parameters.initial_sigma_c_kpa],
    ['parameter_critical_sigma_c_kpa', parameters.critical_sigma_c_kpa],
    ['parameter_gab_mo', parameters.gab.mo],
    ['parameter_gab_c', parameters.gab.c],
    ['parameter_gab_f', parameters.gab.f],
    ['parameter_permeability_mode', parameters.permeability.mode],
    ['parameter_permeability_k0', parameters.permeability.k0],
    ['parameter_permeability_activation_energy_j_per_kmol', parameters.permeability.activation_energy_j_per_kmol],
    ['parameter_permeability_gas_constant_j_per_kmol_k', parameters.permeability.gas_constant_j_per_kmol_k],
    ['parameter_permeability_k_over_delta_kg_per_m2_d_pa', parameters.permeability.k_over_delta_kg_per_m2_d_pa ?? ''],
    ['parameter_caking_sigma1_kpa', parameters.caking_rate.sigma1_kpa],
    ['parameter_caking_a_param_pa_per_h', parameters.caking_rate.a_param_pa_per_h],
    ['parameter_caking_k_param_per_c', parameters.caking_rate.k_param_per_c],
    ['warning_messages', warnings.join(' | ')],
  ]
}

function buildRunId(profileSource: ProfileSource, presetName: string, csvFileName: string | null): string {
  const profilePart =
    profileSource === 'preset'
      ? slugify(presetName || 'preset')
      : slugify(csvFileName?.replace(/\.csv$/i, '') ?? 'csv-profile')
  const timePart = new Date().toISOString().replace(/[:.]/g, '-')
  return `run-${profileSource}-${profilePart}-${timePart}`
}

function csvCell(value: CsvValue): string {
  if (value == null) {
    return ''
  }
  if (typeof value === 'boolean') {
    return value ? 'true' : 'false'
  }
  if (typeof value === 'number') {
    return Number.isFinite(value) ? String(value) : ''
  }
  return /[",\n]/.test(value) ? `"${value.replaceAll('"', '""')}"` : value
}

function buildTimeSeriesFilename(source: ProfileSource, presetName: string, fileName: string | null): string {
  const profileName = source === 'preset' ? presetName : fileName?.replace(/\.csv$/i, '') ?? 'csv_profile'
  return `powder-caking-${slugify(profileName)}-time-series.csv`
}

function slugify(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

function buildParameterSections(simulationResult: SimulationResponse | null): ParameterSection[] {
  if (!simulationResult) {
    return []
  }

  const { parameters, summary } = simulationResult

  return [
    {
      title: 'Eingabe-/Laufparameter',
      rows: [
        { label: 'Konsolidierungsspannung', value: formatParameterNumber(summary.consolidation_stress_kpa, 2), unit: 'kPa' },
        { label: 'Sackmasse', value: formatParameterNumber(parameters.sack_mass_kg, 2), unit: 'kg' },
        { label: 'Sackfläche', value: formatParameterNumber(parameters.sack_area_m2, 3), unit: 'm2' },
        { label: 'Initiale sigma_c', value: formatParameterNumber(parameters.initial_sigma_c_kpa, 3), unit: 'kPa' },
        { label: 'Simulationsdauer', value: formatParameterNumber(summary.final_time_d, 3), unit: 'd' },
      ],
    },
    {
      title: 'Caking-Fit',
      rows: [
        { label: 'sigma1_kpa', value: formatParameterNumber(parameters.caking_rate.sigma1_kpa, 2), unit: 'kPa' },
        {
          label: 'a_param_pa_per_h',
          value: formatParameterNumber(parameters.caking_rate.a_param_pa_per_h, 6),
          unit: 'Pa/h',
        },
        { label: 'k_param_per_c', value: formatParameterNumber(parameters.caking_rate.k_param_per_c, 6), unit: '1/C' },
        { label: 'max. dfc/dt', value: formatParameterNumber(summary.max_dfc_dt_pa_per_h, 6), unit: 'Pa/h' },
      ],
    },
    {
      title: 'GAB-Parameter',
      rows: [
        { label: 'Mo', value: formatParameterNumber(parameters.gab.mo, 4), unit: '% db' },
        { label: 'C', value: formatParameterNumber(parameters.gab.c, 4) },
        { label: 'f', value: formatParameterNumber(parameters.gab.f, 4) },
      ],
    },
    {
      title: 'Permeations-/Arrheniusparameter',
      rows: [
        { label: 'Modus', value: parameters.permeability.mode },
        { label: 'k0', value: formatParameterNumber(parameters.permeability.k0, 8), unit: 'kg/(m2*d*Pa)' },
        {
          label: 'Aktivierungsenergie',
          value: formatParameterNumber(parameters.permeability.activation_energy_j_per_kmol, 4),
          unit: 'J/kmol',
        },
        {
          label: 'Gaskonstante',
          value: formatParameterNumber(parameters.permeability.gas_constant_j_per_kmol_k, 4),
          unit: 'J/(kmol*K)',
        },
        {
          label: 'k/delta konstant',
          value:
            parameters.permeability.k_over_delta_kg_per_m2_d_pa == null
              ? '-'
              : formatParameterNumber(parameters.permeability.k_over_delta_kg_per_m2_d_pa, 8),
          unit: parameters.permeability.k_over_delta_kg_per_m2_d_pa == null ? undefined : 'kg/(m2*d*Pa)',
        },
      ],
    },
    {
      title: 'Schwelle / Integration',
      rows: [
        { label: 'Kritische sigma_c', value: formatParameterNumber(parameters.critical_sigma_c_kpa, 2), unit: 'kPa' },
        { label: 'Summary-Schwelle', value: formatParameterNumber(summary.critical_sigma_c_kpa, 2), unit: 'kPa' },
        { label: 'Integrationsmethode', value: summary.integration_method },
        { label: 'Caking-Status', value: summary.is_caked ? 'Verklumpt' : 'Nicht verklumpt' },
        {
          label: 'Zeit bis kritisch',
          value:
            summary.time_to_critical_d == null
              ? 'nicht erreicht'
              : formatParameterNumber(summary.time_to_critical_d, 3),
          unit: summary.time_to_critical_d == null ? undefined : 'd',
        },
      ],
    },
  ]
}

const processSteps: ProcessStep[] = [
  {
    index: '1',
    title: 'Pulverherstellung und Startzustand',
    description: 'Sprühgetrocknetes Magermilchpulver startet mit definierter Pulverfeuchte in % db.',
  },
  {
    index: '2',
    title: 'Lagerung und Transport',
    description: 'Temperatur und relative Feuchte werden als Klimaprofil über die Transportzeit verarbeitet.',
  },
  {
    index: '3',
    title: 'Feuchtetransport durch den Sack',
    description: 'Wasserdampfstrom folgt aus Permeabilität, Sackfläche, Sättigungsdruck, rF und aw.',
  },
  {
    index: '4',
    title: 'Wasseraufnahme und Wasseraktivität',
    description: 'Die Wasserbilanz aktualisiert die Pulverfeuchte; die GAB-Isotherme liefert aw.',
  },
  {
    index: '5',
    title: 'Glasübergang',
    description: 'Aus aw wird Tg nach Vuataz berechnet; T - Tg treibt die Caking-Kinetik.',
  },
  {
    index: '6',
    title: 'Caking-Kinetik',
    description: 'T - Tg treibt dfc/dt; die Fitparameter hängen von der Konsolidierungsspannung ab.',
  },
  {
    index: '7',
    title: 'Festigkeitsintegration und Entscheidung',
    description: (
      <>
        df<sub>c</sub>/dt in Pa/h wird über &Delta;t<sub>h</sub> integriert; &sigma;<sub>c</sub> &gt;= 20 kPa ist
        verklumpt.
      </>
    ),
  },
]

const formulaBlocks: FormulaBlock[] = [
  {
    title: 'Permeationsmodell',
    formula: (
      <span>
        m&#775;<sub>w</sub> = k/&delta; &middot; A<sub>sack</sub> &middot; p<sub>sv</sub>(T) &middot; (
        <Fraction numerator="RH" denominator="100" /> - a<sub>w</sub>)
      </span>
    ),
    description: 'Der Wasserdampfstrom nutzt kg/(m2*d*Pa), Sackfläche in m2 und Druck in Pa.',
  },
  {
    title: 'Sättigungsdampfdruck',
    formula: (
      <span>
        p<sub>sv</sub>(T) = exp(23.4795 -{' '}
        <Fraction
          numerator="3990.56"
          denominator={
            <>
              T<sub>C</sub> + 233.833
            </>
          }
        />
        )
      </span>
    ),
    description: 'Temperatur wird in degC eingesetzt; p_sv wird in Pa verwendet.',
  },
  {
    title: 'Arrhenius für k/δ',
    formula: (
      <span>
        k/&delta;(T) = k<sub>0</sub> &middot; exp(-
        <Fraction
          numerator={
            <>
              E<sub>a</sub>
            </>
          }
          denominator={
            <>
              R &middot; T<sub>K</sub>
            </>
          }
        />
        )
      </span>
    ),
    description: 'Temperatur wird in K eingesetzt; Ea und R werden in J/kmol bzw. J/(kmol*K) geführt.',
  },
  {
    title: 'Wasserbilanz',
    formula: (
      <span>
        m<sub>w,i+1</sub> = m<sub>w,i</sub> + m&#775;<sub>w,i</sub> &middot; &Delta;t<sub>d</sub>
      </span>
    ),
    description: 'Der Zeitschritt dt_d liegt in Tagen; daraus folgt die aktualisierte Pulverfeuchte.',
  },
  {
    title: 'GAB und aw',
    formula: (
      <>
        <span>
          X ={' '}
          <Fraction
            numerator={
              <>
                100 &middot; X<sub>0</sub> &middot; C &middot; f &middot; a<sub>w</sub>
              </>
            }
            denominator={
              <>
                (1 - f &middot; a<sub>w</sub>) &middot; (1 + (C - 1) &middot; f &middot; a
                <sub>w</sub>)
              </>
            }
          />
        </span>
        <span>
          A = f<sup>2</sup> &middot; (1 - C)
        </span>
        <span>
          B = f &middot; (C - 2 -{' '}
          <Fraction
            numerator={
              <>
                M<sub>0</sub> &middot; C
              </>
            }
            denominator="X"
          />
          )
        </span>
        <span>
          D = B<sup>2</sup> - 4 &middot; A
        </span>
        <span>
          a<sub>w</sub> ={' '}
          <Fraction
            numerator={
              <>
                -B + √D
              </>
            }
            denominator={
              <>
                2 &middot; A
              </>
            }
          />
        </span>
      </>
    ),
    description:
      'X ist Pulverfeuchte in % db; die dargestellte kompakte Lösungsform entspricht der im Simulationskern verwendeten expliziten Umstellung der GAB-Isotherme nach aw.',
  },
  {
    title: 'Glasübergang',
    formula: (
      <>
        <span>
          T<sub>g,Vuataz</sub> = -425 · a<sub>w</sub>
          <sup>3</sup> + 545 · a<sub>w</sub>
          <sup>2</sup> - 355 · a<sub>w</sub> + 101
        </span>
        <span>
          T - T<sub>g</sub> = T - T<sub>g,Vuataz</sub>
        </span>
      </>
    ),
    description:
      'Der Simulationskern verwendet Tg nach Vuataz für T - Tg und damit für die Caking-Rate. Quelle: Vuataz, G. (2002). The phase diagram of milk: a new tool for optimising the drying process. Lait 82 (2002) 485-500. DOI: 10.1051/lait:2002026.',
  },
  {
    title: 'Caking-Rate',
    formula: (
      <span>
        df<sub>c</sub>/dt = a &middot; exp(k &middot; (T - T<sub>g</sub>))
      </span>
    ),
    description: 'dfc/dt liegt in Pa/h und wird aus dem ausgewählten Konsolidierungsfit berechnet.',
  },
  {
    title: 'Integration und Entscheidung',
    formula: (
      <>
        <span>
          &Delta;t<sub>h</sub> = 24 &middot; &Delta;t<sub>d</sub>
        </span>
        <span>
          &sigma;<sub>c,i+1</sub> = &sigma;<sub>c,i</sub> +{' '}
          <Fraction
            numerator={
              <>
                df<sub>c</sub>/dt &middot; &Delta;t<sub>h</sub>
              </>
            }
            denominator="1000"
          />
        </span>
        <span>
          is_caked = &sigma;<sub>c</sub> &gt;= 20 kPa
        </span>
      </>
    ),
    description: 'Die Einheitenumrechnung von Pa nach kPa und Tagen nach Stunden ist explizit.',
  },
]

const modelAssumptions = [
  {
    title: 'Kumulative Verfestigung',
    description:
      'Bereits aufgebaute Festigkeit bleibt erhalten. Bei T - Tg <= 0 wird keine zusätzliche Caking-Rate angesetzt; steigt T - Tg später wieder über 0, wird die Verfestigung vom erreichten Niveau aus fortgesetzt.',
  },
  {
    title: 'Permeation an der Sackgrenze',
    description:
      'Das Modell setzt an der Innenseite des Sackes ein Gleichgewicht zwischen Wasserdampf und der aus der Pulverfeuchte berechneten Wasseraktivität an. Räumliche Feuchtegradienten innerhalb des Pulvers werden nicht separat aufgelöst.',
  },
  {
    title: 'Gesamte Sackoberfläche als Transferfläche',
    description:
      'Der Wasserdampftransport wird über die angesetzte gesamte Sackoberfläche berechnet. Lokale Unterschiede durch Nähte, Falten, Beschädigungen oder partielle Benetzung werden nicht separat modelliert.',
  },
  {
    title: 'Homogene Materialparameter',
    description:
      'GAB-Parameter, Sackpermeabilität und Caking-Fit werden innerhalb eines Laufs als homogen angenommen. Änderungen durch Materialalterung, inhomogene Produktverteilung oder wechselnde Sackeigenschaften sind nicht enthalten.',
  },
  {
    title: 'Gültigkeitsbereich der Datenbasis',
    description:
      'Die Vorhersage stützt sich auf die hinterlegten Messdaten und daraus abgeleiteten Fits. Aussagen außerhalb des abgedeckten Material-, Temperatur- und Klimabereichs sind als Extrapolation mit erhöhter Unsicherheit zu verstehen.',
  },
] as const

const sampleCsvText = [
  'time_d,temperature_c,relative_humidity_pct',
  '0,20,60',
  '1,25,70',
  '2,30,80',
].join('\n')

const chartTabs: { id: ChartTab; label: string }[] = [
  { id: 'climate', label: 'Klima' },
  { id: 'moisture', label: 'Feuchte' },
  { id: 'glass', label: 'Glasübergang' },
  { id: 'caking', label: 'Caking' },
  { id: 'parameters', label: 'Parameter' },
]

const timeSeriesExportColumns = [
  'time_d',
  'temperature_c',
  'relative_humidity_pct',
  'moisture_db_pct',
  'water_activity',
  'tg_vuataz_c',
  't_minus_tg_c',
  'dfc_dt_pa_per_h',
  'sigma_c_kpa',
  'is_caked',
] as const

type CsvValue = string | number | boolean | null | undefined

interface TimeSeriesExportContext {
  profileSource: ProfileSource
  selectedPreset: string
  csvFileName: string | null
  initialMoistureDbPct: number
  consolidationStressKpa: number
  integrationMethod: IntegrationMethod
  dtD?: number
}

export default App
