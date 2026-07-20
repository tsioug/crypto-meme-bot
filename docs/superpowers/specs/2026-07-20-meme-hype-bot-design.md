# Memecoin Telegram Hype Bot — Design

**Date:** 2026-07-20  
**Status:** Approved for planning  
**Project path:** `/home/tsioug/Claude/crypto-meme-bot/`

## Goal

Experimental, free-to-run bot that listens to Telegram channels for memecoin hype (cashtags + Solana contract addresses), scores sentiment locally with VADER, and alerts via a dedicated Telegram bot when aggregate positive mentions spike.

## Non-goals (MVP)

- No connection to `crypto-bot` or `crypto-trading-bot`
- No writes to `sentiment.db`
- No trading / Jupiter / DEX execution
- No X/Twitter data source
- No on-chain CA verification
- No user allowlist (phase 2 if needed)

## Decisions (locked)

| Topic | Choice |
|-------|--------|
| Placement | New folder `crypto-meme-bot/` beside existing projects |
| Data source | Telegram via Telethon (user account) |
| Sentiment | Local VADER (no paid AI APIs) |
| Alerts | Separate Telegram bot token/chat |
| Target filter | Any cashtag + Solana CA heuristics |
| Alert style | Aggregate window by default; optional verbose raw hits |
| Spam | Heuristics first; allowlist later |
| Channels | `channels.yaml`; discover → `suggested`; human enables |
| Process model | Two processes: `listener` + `discover` |

## Architecture

```
crypto-meme-bot/
├── src/
│   ├── listener.py       # process 1: realtime listen → analyze → alert
│   ├── discover.py       # process 2: search/rank → suggested channels
│   ├── filter.py         # cashtags + Solana CA + spam heuristics
│   ├── sentiment.py      # VADER wrapper
│   ├── aggregator.py     # window + positive ratio → alert decision
│   ├── notifier.py       # alert Telegram bot
│   ├── channels.py       # read/write channels.yaml
│   ├── database.py       # SQLite
│   └── config.py         # env + defaults
├── channels.yaml
├── data/meme.db
├── .env                  # secrets only
├── .env.example
├── requirements.txt
└── tests/
```

### Process boundaries

1. **`discover.py`** — periodic Telethon search by configured keywords; ranks public channels/groups; writes/updates `status: suggested` in `channels.yaml`. Never auto-enables. Does not send hype alerts.
2. **`listener.py`** — listens only to `status: enabled` channels. Pipeline: message → filter → sentiment → SQLite → aggregator → notifier (if threshold + cooldown).
3. Human gate: set `enabled: true` (and ensure the Telethon account has joined the channel) before listening.

### Isolation

- Own SQLite (`data/meme.db`), own `.env`, own Telegram alert bot.
- Must not import from or write into the other two repos.

## Components

### `filter.py`

- Extract cashtags matching `$TICKER` (alphanumeric, reasonable length bounds).
- Extract Solana-like CAs: base58 strings ~32–44 characters (heuristic only in MVP).
- Spam heuristics (configurable thresholds):
  - Duplicate / near-duplicate text (hash)
  - Excessive CAs per single message
  - Very new sender accounts when Telethon exposes account age/metadata
- Spam-flagged messages are stored (optional) or dropped from aggregation — default: excluded from aggregate counts, logged.

### `sentiment.py`

- VADER compound score per message text.
- Positive for aggregation when `compound > 0.05` (tunable).
- Negative / neutral still stored for ratio math.

### `aggregator.py`

- Sliding window per symbol **or** per CA key.
- Defaults:
  - `WINDOW_MINUTES=5`
  - `MIN_MENTIONS=5`
  - `MIN_POSITIVE_RATIO=0.70`
  - `ALERT_COOLDOWN_MINUTES=30` per key
- Fires at most one aggregate alert per key per cooldown.
- `VERBOSE=true`: also notify on individual non-spam hits (debug only; default off).

### `notifier.py`

- Uses `ALERT_BOT_TOKEN` + `ALERT_CHAT_ID`.
- Aggregate alert payload: key (ticker/CA), mention count, positive ratio, sample channels, window size, top message snippets (truncated).
- Failures logged; do not roll back DB writes.

### `channels.py` + `channels.yaml`

Example shape:

```yaml
channels:
  - id: null
    username: example_channel
    status: suggested   # suggested | enabled | ignored
    score: 0.82
    reason: "high cashtag density"
    updated_at: "2026-07-20T00:00:00+00:00"
```

- `suggested`: discover output; not listened to.
- `enabled`: listener subscribes.
- `ignored`: discover must not re-promote without explicit human change (or only after score improves past a high bar — MVP: never auto-unignore).

### `discover.py` ranking (MVP)

Inputs from Telethon search results + lightweight sampling of recent messages when available:

- Member count
- Message rate
- Cashtag/CA density in sample
- Spam penalty (heuristic)

Keywords default: `solana`, `memecoin`, `pumpfun` (`DISCOVER_KEYWORDS`).  
Interval default: every 12 hours (`DISCOVER_INTERVAL_HOURS`).

### `database.py`

Table `mentions` (minimum columns):

- `id`, `created_at`
- `channel_id`, `user_id`
- `text_hash`, `text` (or truncated text)
- `symbols` (JSON), `cas` (JSON)
- `sentiment_compound`, `is_positive`, `is_spam`

Optional `alerts` table for cooldown audit: `key`, `sent_at`, `payload_summary`.

### `config.py` / `.env`

Required secrets:

- `TELEGRAM_API_ID`
- `TELEGRAM_API_HASH`
- Telethon session (file path or string — document in README)
- `ALERT_BOT_TOKEN`
- `ALERT_CHAT_ID`

Operational knobs as in the defaults table above.

### Kill switch

- If `data/STOP` exists, `listener` **skips alerts but continues ingest** so turning STOP off does not lose window context.

## Error handling

- One failing channel does not stop others.
- Telethon flood/rate limits → exponential backoff + log.
- Missing/corrupt `channels.yaml` → treat as empty list + warning; do not crash discover/listener hard loops without recovery path.
- Alert send failure → log; mention rows remain.

## Testing

### Unit

- Filter: cashtags, CA heuristics, spam rules (fixture strings).
- Sentiment: positive / negative / neutral samples.
- Aggregator: fire / no-fire / cooldown.
- Channels helpers: status transitions; ignored not listened.

### Integration

- Mock message stream → DB → mock notifier on aggregate threshold.
- Mock discover search results → `suggested` written correctly; never `enabled`.

### Smoke

- Discover config load without crash.
- Listener with `data/STOP` does not call notifier.
- Lint + full test suite green before considering MVP done.

## Success criteria (MVP)

1. Discover writes `suggested` channels without auto-enable.
2. With ≥1 enabled channel, aggregate alerts reach the alert Telegram chat when thresholds are met (real or synthetic feed in tests).
3. Verbose off by default; alert chat not flooded under normal noise.
4. Zero runtime dependency on the other two repos.

## Phase 2 (explicitly later)

- User/channel allowlist
- Stronger CA validation (RPC / format libraries)
- Optional X source
- Auto-enable top-N (rejected for MVP; only if revisiting risk appetite)
- Optional read-only metrics export (still not feeding trading bot unless separately designed)

## Implementation next step

After user review of this spec: invoke **writing-plans** to produce a step-by-step implementation plan under `docs/superpowers/plans/`.
