# Processed Data

Dieses Verzeichnis enthaelt die im oeffentlichen Repo verbleibenden, fuer App-Betrieb und Parametrisierung benoetigten CSV-Dateien.

## `caking_time_fit_params.csv`

Exponentialfits fuer die beobachtete Caking-Time in Abhaengigkeit von `T-Tg`:

`t_cake = a * exp(k * (T - Tg))`

Die exportierten Parameter reproduzieren die in MATLAB verwendeten Zusammenhaenge fuer `20 kPa` und `11 kPa`.

## `caking_rate_fit_params.csv`

Exponentialfits fuer die gemessene Verfestigungsrate:

`dfc/dt = a * exp(k * (T - Tg))`

Die Rate ist in `Pa/h`. Fuer Integration ueber Zeitschritte in Tagen muss daher mit `24 * dt_d` multipliziert werden.

## `wdd_arrhenius_parameters.csv`

Arrhenius-Parameter der Temperaturabhaengigkeit von `k/delta`, extrahiert aus `Messung WDD Sackmaterial`.

## `real_container_logger_profile.csv`

Reales Klimaprofil fuer den Default-Fall in der App. Die Zeitreihe enthaelt Tageswerte fuer:

- `time_d`
- `temperature_c`
- `relative_humidity_pct`
