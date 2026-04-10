# Powder Caking Frontend

React/Vite/TypeScript frontend fuer die Powder-Caking-Simulation.

## Lokal starten

Backend:

```bash
source /home/frank/toolvenvs/codex-tools/bin/activate
cd /home/frank/workspace/code/apps/powder-caking
PYTHONPATH=src uvicorn powder_caking.api:app --reload
```

Frontend:

```bash
cd /home/frank/workspace/code/apps/powder-caking/frontend
npm run dev
```

Im Vite-Entwicklungsmodus nutzt der API-Client `http://localhost:8000`. Fuer andere
Backends kann `VITE_API_BASE_URL` gesetzt werden. Ohne gesetzte Variable nutzt der
Client relative API-URLs, damit das gebaute Frontend zusammen mit FastAPI unter
demselben Host laufen kann.

## Build fuer Ein-Server-Betrieb

```bash
npm install
npm run build
cd ..
PYTHONPATH=src uvicorn powder_caking.api:app --host 0.0.0.0 --port 8000
```

## Pruefung

```bash
npm run build
npm run lint
```
