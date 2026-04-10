# Powder Caking Frontend

React/Vite/TypeScript frontend for the powder caking simulation.

## Run Locally

Backend:

```bash
source /home/frank/toolvenvs/codex-tools/bin/activate
cd /home/frank/workspace/code/apps/powder-caking
PYTHONPATH=src uvicorn powder_caking.api:app --reload
```

UI:

```bash
cd /home/frank/workspace/code/apps/powder-caking/frontend
npm run dev
```

In Vite development mode, the API client uses `http://localhost:8000`. For other backends, set `VITE_API_BASE_URL`. Without that variable, the client uses relative API URLs so the built frontend can run together with FastAPI on the same host.

## Build For Single-Server Operation

```bash
npm install
npm run build
cd ..
PYTHONPATH=src uvicorn powder_caking.api:app --host 0.0.0.0 --port 8000
```

## Checks

```bash
npm run build
npm run lint
```
