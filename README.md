# Powder Caking Simulator

Web-App zur Bewertung des Caking-Risikos von Magermilchpulver im 25-kg-Sack während Transport und Lagerung. Die App berechnet aus Klimaprofilen die Feuchteaufnahme, Wasseraktivität, Glasübergangstemperatur, Pulverfestigkeit und das daraus abgeleitete Verklumpungsrisiko.

## Funktionen

- Startseite mit fachlichem Einstieg und direkter Navigation zum Simulator.
- Klimaprofile als Preset, reales Loggerprofil oder eigenes CSV-Profil.
- Profilprüfung mit Dauer, Datenpunkten, Temperaturbereich und relativer Feuchte.
- Simulation von Pulverfeuchte, `aw`, `Tg`, `T - Tg`, Caking-Rate und Verfestigungssapnnung `σ_c`.
- Ergebnis-KPIs für Endfestigkeit, Caking-Status, Zeit bis zur kritischen Schwelle, Endfeuchte, End-`aw` und maximale `T - Tg`-Differenz.
- Diagramme für Klima, Feuchte, Glasübergang und Caking-Kinetik.
- Rückrechnung der maximal sicheren Startfeuchte für ein gegebenes Klimaprofil.
- Expertenmodus für Modellparameter wie GAB, Sackdaten, Schwellenwerte und Permeabilität.
- Modellgrundlage mit Prozesskette, Formeln und kompakten Erläuterungen zur verwendeten Modellbasis.

## Eindruck der App

### Startseite

<img src="frontend/public/readme/start-overview.png" alt="Startseite" width="960" />

### Simulator

<img src="frontend/public/readme/simulator-results.png" alt="Simulator - Ergebnisse" width="960" />

<img src="frontend/public/readme/simulator-figures.png" alt="Simulator - Eingaben und Diagramme" width="960" />



## Datenherkunft

Die in der App verwendeten Messdaten und daraus abgeleiteten Tabellen wurden im Rahmen des
Forschungsvorhabens AiF 18643 BR erhoben bzw. aufbereitet.

## Voraussetzungen

- Git.
- Python 3.12 oder eine kompatible Python-3-Version.
- Node.js und npm.
- Optional Docker und Docker Compose für den einfachsten lokalen Start.
- Die App nutzt die versionierten CSV-Daten unter `data/processed/`. Lokale Rohdaten aus `excel/`, `docs/`, `fig/`, `matlab/` oder `equations/` sind für den Betrieb nicht erforderlich und werden nicht versioniert.

## Schnellstart mit Docker

Repository klonen und in den Projektordner wechseln:

```bash
git clone <repo-url>
cd powder-caking
```

Container bauen und starten:

```bash
docker compose up --build
```

Die komplette App läuft dann unter:

```text
http://localhost:8000
```

Container stoppen:

```bash
docker compose stop
```

Container stoppen und entfernen:

```bash
docker compose down
```

## Manuelle Installation

Repository klonen und in den Projektordner wechseln:

```bash
git clone <repo-url>
cd powder-caking
```

Python-Umgebung für das Backend anlegen und Abhängigkeiten installieren:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Unter Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Frontend-Abhängigkeiten installieren und Frontend bauen:

```bash
cd frontend
npm install
npm run build
cd ..
```

## Lokal Starten Ohne Docker

Für die normale lokale Nutzung reicht ein Server. FastAPI liefert dabei zusätzlich
zu den API-Endpunkten das gebaute Frontend aus `frontend/dist/` aus.

Im Repo-Root starten:

```bash
source .venv/bin/activate
PYTHONPATH=src uvicorn powder_caking.api:app --host 0.0.0.0 --port 8000
```

Unter Windows:

```powershell
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "src"
uvicorn powder_caking.api:app --host 0.0.0.0 --port 8000
```

Die komplette App läuft dann unter:

```text
http://localhost:8000
```

React-Routen fallen auf `frontend/dist/index.html` zurück.

## Entwicklungsmodus mit Vite

Für UI-Entwicklung kann das Frontend weiterhin separat mit Vite-Hot-Reload
laufen. Backend im Repo-Root starten:

```bash
source .venv/bin/activate
PYTHONPATH=src uvicorn powder_caking.api:app --reload
```

Frontend in einem zweiten Terminal starten:

```bash
cd frontend
npm run dev
```

Das Frontend läuft dann unter:

```text
http://localhost:5173
```

Im Vite-Entwicklungsmodus nutzt der Frontend-Client `http://localhost:8000` als API. Für ein anderes Backend kann `VITE_API_BASE_URL` gesetzt werden.

## Bedienung

1. App öffnen und auf der Startseite `Zum Simulator` wählen.
2. Profilquelle auswählen:
   - `Preset` für vordefinierte Klimaprofile.
   - `CSV` für eigene Zeitreihen.
3. Startfeuchte, Konsolidierungsspannung, Integrationsmethode und Zeitschritt prüfen.
4. Optional `Profil prüfen` ausführen, um Datenbereich und Warnungen zu sehen.
5. `Simulieren` starten.
6. Ergebnis-KPIs und Diagramme auswerten.
7. Optional `Limit berechnen` ausführen, um die maximal sichere Startfeuchte für dasselbe Profil zu bestimmen.
8. Unter `Modellgrundlage` die verwendeten Gleichungen, Prozessschritte und Referenzdaten prüfen.

## CSV-Profil

Eigene Klimaprofile können als CSV-Datei oder per Texteingabe geladen werden. Erwartete Spalten:

```csv
time_d,temperature_c,relative_humidity_pct
0,25,60
1,28,70
2,30,75
```

`time_d` ist die Zeit in Tagen. Alternativ kann die API Zeitstempelprofile verarbeiten und auf verstrichene Tage abbilden.

## Ergebnisinterpretation

- `σ_c` beschreibt die berechnete Pulverfestigkeit.
- Die kritische Schwelle liegt standardmäßig bei `20 kPa`.
- `Nicht verklumpt` bedeutet, dass die berechnete Festigkeit unter der kritischen Schwelle bleibt.
- `Verklumpt` bedeutet, dass die kritische Schwelle erreicht oder überschritten wurde.
- Die Startfeuchte-Rückrechnung sucht die höchste Startfeuchte, bei der das Profil unterhalb der kritischen Schwelle bleibt.

## Tests und Checks

Backend-Tests:

```bash
source .venv/bin/activate
python -m unittest discover -s tests -v
```

Frontend-Build und Lint:

```bash
cd frontend
npm run build
npm run lint
```

Wenn lokale Excel-Rohdaten fehlen, werden nur die Excel-abhängigen Extractor-Tests übersprungen. Die App-, API-, Klima- und Simulations-Tests laufen weiterhin.

## Repository-Inhalt

- `src/powder_caking/`: Backend, Simulationskern, API-Service und Modelllogik.
- `frontend/`: React/Vite/TypeScript-Frontend.
- `data/processed/`: verarbeitete CSV-Daten für Modellparameter, Referenzdaten und Klimaprofile.
- `tests/`: Backend-, API-, Klima-, Simulations- und optionale Extractor-Tests.
- `scripts/`: Hilfsskripte zur Datenextraktion und Modellparametrisierung.
