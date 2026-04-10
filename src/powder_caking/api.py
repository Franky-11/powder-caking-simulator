from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from powder_caking.api_schemas import (
    ClimatePresetDTO,
    ModelDefaultsDTO,
    MoistureLimitRequestDTO,
    MoistureLimitResponseDTO,
    ProfilePreviewRequestDTO,
    SimulationRequestDTO,
    SimulationResponseDTO,
)
from powder_caking.api_service import (
    list_climate_presets,
    model_defaults,
    preview_climate_profile,
    run_moisture_limit,
    run_simulation,
)


def create_app(frontend_dist_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="Powder Caking Simulation API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/model/defaults", response_model=ModelDefaultsDTO)
    async def get_model_defaults() -> ModelDefaultsDTO:
        return model_defaults()

    @app.get("/presets/climate", response_model=list[ClimatePresetDTO])
    async def get_climate_presets() -> list[ClimatePresetDTO]:
        return list_climate_presets()

    @app.post("/profiles/preview")
    async def post_profile_preview(request: ProfilePreviewRequestDTO) -> dict[str, Any]:
        try:
            return preview_climate_profile(request)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/simulate", response_model=SimulationResponseDTO)
    async def post_simulate(request: SimulationRequestDTO) -> SimulationResponseDTO:
        try:
            return run_simulation(request)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/simulate/moisture-limit", response_model=MoistureLimitResponseDTO)
    async def post_moisture_limit(request: MoistureLimitRequestDTO) -> MoistureLimitResponseDTO:
        try:
            return run_moisture_limit(request)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    _mount_frontend(app, frontend_dist_dir or _default_frontend_dist_dir())

    return app


def _default_frontend_dist_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "frontend" / "dist"


def _mount_frontend(app: FastAPI, frontend_dist_dir: Path) -> None:
    index_html = frontend_dist_dir / "index.html"
    if not index_html.is_file():
        return

    assets_dir = frontend_dist_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

    @app.get("/", include_in_schema=False)
    async def serve_frontend_root() -> FileResponse:
        return FileResponse(index_html)

    @app.get("/{path:path}", include_in_schema=False)
    async def serve_frontend_path(path: str) -> FileResponse:
        requested_path = (frontend_dist_dir / path).resolve()
        frontend_root = frontend_dist_dir.resolve()
        if requested_path.is_file() and requested_path.is_relative_to(frontend_root):
            return FileResponse(requested_path)
        return FileResponse(index_html)


app = create_app()
