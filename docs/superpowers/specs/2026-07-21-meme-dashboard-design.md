# Meme Bot Dashboard — Design

**Date:** 2026-07-21  
**Status:** Approved for planning  
**Project:** `/home/tsioug/Claude/crypto-meme-bot/`

## Goal

Read-only web dashboard on the VPS so the operator can see meme-bot health, recent alerts, hot keys, and channel discover status — accessible via public HTTPS URL protected with HTTP Basic Auth.

## Locked decisions

| Topic | Choice |
|-------|--------|
| Scope | Overview: snapshot + recent alerts + channels table (suggested/enabled/ignored) |
| Placement | Inside `crypto-meme-bot` only (not merged into trading-bot dashboard) |
| Access | Public URL + HTTPS + HTTP Basic Auth |
| Mutations | Read-only (no enable/ignore buttons in MVP) |
| Delivery | Phase 0 mock UI → Phase 1 backend plan `.md` → Phase 2 real backend |
| Recommended backend (to confirm before Phase 2) | FastAPI + Jinja, reuse existing SQLite `data/meme.db` (no new DB / migrations) |

## Non-goals (MVP)

- Write actions (enable/ignore/STOP from UI)
- WebSocket / live tick stream
- Coupling to `crypto-trading-bot` or `crypto-bot`
- Public unauthenticated access
- Paid AI / external analytics

## UI (single page)

**Header:** product name `crypto-meme-bot`, STOP indicator, best-effort listener/discover hints.

**Section — Snapshot:** mentions 1h / 24h, alerts 24h, top hot keys (ticker/CA).

**Section — Recent alerts:** time, key, summary (from `alerts` table).

**Section — Channels:** username, status, score, reason (from `channels.yaml`).

Desktop + mobile stack. Dashboard-appropriate layout (status panels allowed).

## Data contract

Mock file and future `GET /api/overview` share one JSON shape:

```json
{
  "stop_active": false,
  "listener_hint": "unknown",
  "discover_hint": "unknown",
  "mentions_1h": 0,
  "mentions_24h": 0,
  "alerts_24h": 0,
  "hot_keys": [{"key": "PEPE", "mentions": 0, "positive_ratio": 0.0}],
  "recent_alerts": [{"sent_at": "", "key": "", "summary": ""}],
  "channels": [{"username": "", "status": "suggested", "score": 0.0, "reason": ""}]
}
```

### Live sources (Phase 2)

| Field | Source |
|-------|--------|
| `channels` | `channels.yaml` via existing `src.channels` |
| mention counts / `hot_keys` | `data/meme.db` `mentions` (exclude spam) |
| `recent_alerts` / `alerts_24h` | `data/meme.db` `alerts` |
| `stop_active` | existence of `data/STOP` |
| `listener_hint` / `discover_hint` | best-effort (`unknown` until pid/heartbeat exists) |

## Access & security

- App binds to localhost (e.g. `127.0.0.1:8001`).
- Reverse proxy (nginx) terminates HTTPS and enforces **HTTP Basic Auth**.
- Credentials only in server env / htpasswd — never committed.
- Dashboard remains read-only against DB and yaml (open SQLite `mode=ro` like trading dashboard).

SSH tunnel remains optional debug fallback, not the primary access path.

## Phases

### Phase 0 — Mock UI (next after this spec)

- `dashboard/index.html` (+ CSS)
- `dashboard/mock/overview.json` matching the contract
- Static preview (file open or tiny static server)
- No FastAPI yet

### Phase 1 — Backend implementation plan (markdown)

- Write `docs/superpowers/plans/` or a dedicated `docs/dashboard-backend-plan.md` with phases, endpoints, systemd, nginx/basic-auth notes.
- **Hard gate:** before any backend code, confirm with the user: language/framework, database, migrations. Default proposal: Python FastAPI, existing `meme.db`, no migrations.

### Phase 2 — Real backend

- FastAPI app serving Jinja page + `/api/overview`
- Wire mock UI to live data
- systemd unit + nginx basic auth docs/snippets
- Tests for overview builder (unit) + smoke

## Success criteria

1. Mock page renders all three sections from JSON.
2. After Phase 2, same UI shows live channels/alerts/mentions without writes.
3. Remote access requires valid basic-auth credentials over HTTPS.
4. No dependency on sibling repos.

## Implementation next step

User reviews this spec → Phase 0 mock UI → Phase 1 backend plan `.md` → ask stack confirmation → Phase 2 (writing-plans / SDD as appropriate).
