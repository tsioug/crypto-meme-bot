# Meme Dashboard Backend — Implementation Plan

**Stack (confirmed):** Python 3.10+, FastAPI, uvicorn, existing SQLite `data/meme.db` (read-only, no migrations), Jinja not required (static HTML + `/api/overview` JSON).

**Goal:** Replace mock-only preview with live read-only dashboard on VPS behind nginx HTTPS + basic auth.

## Files

| File | Role |
|------|------|
| `src/overview.py` | Pure `build_overview()` from yaml + DB + STOP |
| `dashboard/app.py` | FastAPI: `/`, `/styles.css`, `/api/overview` |
| `dashboard/index.html` | Fetch `/api/overview` (mock fallback for static dev) |
| `tests/test_overview.py` | Unit tests for overview builder |
| `tests/test_dashboard.py` | API smoke tests |
| `dashboard/crypto-meme-dashboard.service` | systemd unit (127.0.0.1:8001) |
| `requirements.txt` | + fastapi, uvicorn |

## Tasks

1. Add deps + `build_overview()` with readonly SQLite queries
2. FastAPI app serving static UI + JSON API
3. Wire UI to `/api/overview`
4. Tests + README (run, nginx basic auth notes)
5. systemd unit for VPS

## VPS deploy (manual)

- App: `uvicorn dashboard.app:app --host 127.0.0.1 --port 8001`
- nginx: `proxy_pass http://127.0.0.1:8001` + `auth_basic` + TLS
- Credentials in htpasswd only on server

## Out of scope

- DB migrations, write APIs, WebSocket, trading-bot coupling
