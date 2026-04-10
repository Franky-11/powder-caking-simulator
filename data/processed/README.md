# Processed Data

Dieses Verzeichnis enthaelt reproduzierbar aus den Rohquellen abgeleitete Datensaetze.

## `mmp1_time_consolidation.csv`

Tidyer Export der MMP-1-Rohmessungen aus `excel/2 MMP Zvf.xlsx`, Blatt `MMP 1`.

Enthaltene Spalten:

- `material`
- `sigma1_kpa`
- `temperature_c`
- `time_h`
- `fc_pa`
- `fc_err_pa`
- `source_workbook`
- `source_sheet`
- `source_row`
- `source_range`

Die Zeilen stammen aus den drei Messbloecken:

- `20 kPa` in `L:N`
- `11 kPa` in `Q:S`
- `3.1 kPa` in `V:X`

## `mmp1_kinetics_summary.csv`

Verdichtete Kinetikpunkte aus `excel/2 MMP Zvf.xlsx`, Blatt `MMP 1`.

Enthaelt pro Lagerbedingung:

- `sigma1_kpa`
- `temperature_c`
- `t_minus_tg_c`
- `dfc_dt_pa_per_h`
- abgeleitete Caking-Zeiten

## `relative_change_summary.csv`

Hilfstabelle aus Blatt `realtive change` mit den in Excel bereits hinterlegten Zusammenhaengen zwischen Restfeuchte, `Tg`, `T-Tg` und `t_cake`.

## `aw_tg_data.csv`

Kalibrierdaten aus Blatt `aw vs Tg` fuer die Zuordnung zwischen Wasseraktivitaet, Pulverfeuchte und Glasuebergangstemperatur.

## `permeation_time_series.csv`

Zeitreihe aus `excel/Wasseraufnahme 25 Sack Milchpulver.xlsx`, Blatt `Permeationsmodell mit WDD est.` mit:

- Temperaturprofil
- relative Feuchte
- Wasseraktivitaet
- `Tg` nach Gordon-Taylor und linearer Naeherung
- `T-Tg`
- modellierter Festigkeit
- kumulativer Wasseraufnahme
- Pulverfeuchte

## `table2_scenario_series.csv`

Szenario-Zeitreihen aus Blatt `Tabelle2` fuer drei Startfeuchten (`3.8`, `4.0`, `4.2 % db`) mit:

- `cake_strength_kpa`
- `moisture_db_pct`
- `tg_c`
- `time_d`

## `caking_time_fit_params.csv`

Exponentialfits fuer die beobachtete Caking-Time in Abhaengigkeit von `T-Tg`:

`t_cake = a * exp(k * (T - Tg))`

Die exportierten Parameter reproduzieren die in MATLAB verwendeten Zusammenhaenge fuer `20 kPa` und `11 kPa`.

## `caking_rate_fit_params.csv`

Exponentialfits fuer die gemessene Verfestigungsrate:

`dfc/dt = a * exp(k * (T - Tg))`

Die Rate ist in `Pa/h`. Fuer Integration ueber Zeitschritte in Tagen muss daher mit `24 * dt_d` multipliziert werden.

## `wdd_permeability_summary.csv`

Auswertung der Wasserdampfdurchlaessigkeitsmessungen des Sackmaterials bei `15`, `23` und `35 degC`, inklusive `WDD`, `k/delta`, `1/T` und `ln(k/delta)`.

## `wdd_arrhenius_parameters.csv`

Arrhenius-Parameter der Temperaturabhaengigkeit von `k/delta`, extrahiert aus `Messung WDD Sackmaterial`.

## `wdd_measurement_timeseries.csv`

Roh-Zeitreihen der Massenmessungen fuer die Wasserdampfdurchlaessigkeit bei `15`, `23` und `35 degC`.
