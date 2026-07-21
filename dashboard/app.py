"""
Read-only meme-bot dashboard (FastAPI).

Serves the static UI and `/api/overview` JSON built from channels.yaml and
meme.db (SQLite opened mode=ro only). Run:

    .venv/bin/uvicorn dashboard.app:app --host 127.0.0.1 --port 8001

Put nginx + HTTPS + HTTP Basic Auth in front on the VPS.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

from src.config import load_settings
from src.overview import build_overview

DASHBOARD_DIR = Path(__file__).resolve().parent

app = FastAPI(title="crypto-meme-bot dashboard")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(DASHBOARD_DIR / "index.html")


@app.get("/styles.css")
def styles() -> FileResponse:
    return FileResponse(DASHBOARD_DIR / "styles.css")


@app.get("/api/overview")
def api_overview() -> JSONResponse:
    settings = load_settings()
    payload = build_overview(
        channels_path=settings.channels_path,
        db_path=settings.db_path,
        stop_path=settings.stop_path,
    )
    return JSONResponse(payload)
