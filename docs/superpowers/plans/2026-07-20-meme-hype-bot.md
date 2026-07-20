# Memecoin Telegram Hype Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a free, standalone Telegram memecoin hype bot (`crypto-meme-bot`) with Telethon ingest, local VADER sentiment, human-gated channel discovery, and aggregate Telegram alerts — with zero coupling to `crypto-bot` / `crypto-trading-bot`.

**Architecture:** Two processes share `channels.yaml` + SQLite. `discover` searches/ranks public Telegram chats into `suggested` only. `listener` reads `enabled` channels, filters cashtags/Solana CAs, scores with VADER, aggregates in a sliding window, and alerts via a dedicated bot. Pure logic is unit-tested without network; Telethon/Bot API are thin adapters behind interfaces.

**Tech Stack:** Python 3.10+, Telethon, vaderSentiment, PyYAML, python-dotenv, httpx (or `requests`) for Bot API alerts, pytest.

## Global Constraints

- Project root: `/home/tsioug/Claude/crypto-meme-bot/` only — do not import from or write to sibling repos.
- Secrets only in `.env` (gitignored); ship `.env.example` with empty placeholders.
- Discover must never set `status: enabled` or clear `ignored`.
- Default alert path is aggregate-only; `VERBOSE` default `false`.
- If `data/STOP` exists, skip alerts but continue ingest.
- No paid AI APIs; sentiment is VADER only.
- Comments/docstrings in English for this new project (sibling `crypto-bot` style).
- Every task ends green on its tests before commit; run `pytest` from project root with `.venv`.

## File map (create)

| File | Responsibility |
|------|----------------|
| `requirements.txt` | Runtime + test deps |
| `.env.example` | Documented env knobs |
| `.gitignore` | Already exists; keep `.env`, `data/`, sessions |
| `README.md` | Setup, Telethon login, enable channels, run both processes |
| `channels.yaml` | Initial empty `channels: []` |
| `src/__init__.py` | Empty package marker |
| `src/config.py` | `Settings` from env |
| `src/filter.py` | Cashtag/CA extract + spam heuristics |
| `src/sentiment.py` | VADER wrapper |
| `src/channels.py` | Load/save/upsert `channels.yaml` |
| `src/database.py` | SQLite schema + insert/query |
| `src/aggregator.py` | Window decision + cooldown |
| `src/notifier.py` | Telegram Bot API send |
| `src/pipeline.py` | Pure `handle_message(...)` used by listener |
| `src/discover_rank.py` | Pure ranking from channel samples |
| `src/listener.py` | Telethon client + event loop |
| `src/discover.py` | Telethon search loop |
| `tests/...` | Mirror modules under `tests/` |

---

### Task 1: Scaffold + config

**Files:**
- Create: `requirements.txt`, `.env.example`, `channels.yaml`, `src/__init__.py`, `src/config.py`, `tests/test_config.py`, `pyproject.toml` (pytest pythonpath) or `pytest.ini`
- Modify: `.gitignore` only if session patterns missing

**Interfaces:**
- Consumes: none
- Produces: `Settings` dataclass + `load_settings(env_file: str | None = None) -> Settings`

- [ ] **Step 1: Create venv and requirements**

```text
# requirements.txt
telethon>=1.36.0
vaderSentiment>=3.3.2
PyYAML>=6.0.1
python-dotenv>=1.0.1
httpx>=0.27.0
pytest>=8.0.0
```

```ini
# pytest.ini
[pytest]
pythonpath = .
testpaths = tests
```

- [ ] **Step 2: Write failing config test**

```python
# tests/test_config.py
import os
from pathlib import Path

import pytest

from src.config import load_settings


def test_load_settings_defaults(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(
        "\n".join(
            [
                "TELEGRAM_API_ID=12345",
                "TELEGRAM_API_HASH=hashhash",
                "TELETHON_SESSION=data/meme.session",
                "ALERT_BOT_TOKEN=123:abc",
                "ALERT_CHAT_ID=-1001",
            ]
        )
    )
    monkeypatch.chdir(tmp_path)
    s = load_settings(str(env))
    assert s.telegram_api_id == 12345
    assert s.window_minutes == 5
    assert s.min_mentions == 5
    assert s.min_positive_ratio == 0.70
    assert s.alert_cooldown_minutes == 30
    assert s.verbose is False
    assert s.discover_interval_hours == 12
    assert s.discover_keywords == ["solana", "memecoin", "pumpfun"]
    assert s.db_path.endswith("meme.db")
    assert s.channels_path.endswith("channels.yaml")
    assert s.stop_path.endswith("STOP")


def test_load_settings_missing_secret(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("TELEGRAM_API_ID=1\n")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(RuntimeError, match="ALERT_BOT_TOKEN"):
        load_settings(str(env))
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /home/tsioug/Claude/crypto-meme-bot && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/pytest tests/test_config.py -v`  
Expected: FAIL (import/`load_settings` missing) — create `requirements.txt` first if pip fails.

- [ ] **Step 4: Implement config**

```python
# src/config.py
"""Load settings from environment / .env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return default if raw is None or raw.strip() == "" else float(raw)


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return default if raw is None or raw.strip() == "" else int(raw)


@dataclass(frozen=True)
class Settings:
    telegram_api_id: int
    telegram_api_hash: str
    telethon_session: str
    alert_bot_token: str
    alert_chat_id: str
    window_minutes: int
    min_mentions: int
    min_positive_ratio: float
    alert_cooldown_minutes: int
    verbose: bool
    positive_compound_threshold: float
    max_cas_per_message: int
    discover_interval_hours: int
    discover_keywords: list[str]
    db_path: str
    channels_path: str
    stop_path: str
    data_dir: str


def load_settings(env_file: str | None = None) -> Settings:
    load_dotenv(env_file)
    data_dir = os.getenv("DATA_DIR", "data")
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    keywords_raw = os.getenv("DISCOVER_KEYWORDS", "solana,memecoin,pumpfun")
    keywords = [k.strip().lower() for k in keywords_raw.split(",") if k.strip()]
    return Settings(
        telegram_api_id=int(_require("TELEGRAM_API_ID")),
        telegram_api_hash=_require("TELEGRAM_API_HASH"),
        telethon_session=os.getenv("TELETHON_SESSION", f"{data_dir}/meme.session"),
        alert_bot_token=_require("ALERT_BOT_TOKEN"),
        alert_chat_id=_require("ALERT_CHAT_ID"),
        window_minutes=_int("WINDOW_MINUTES", 5),
        min_mentions=_int("MIN_MENTIONS", 5),
        min_positive_ratio=_float("MIN_POSITIVE_RATIO", 0.70),
        alert_cooldown_minutes=_int("ALERT_COOLDOWN_MINUTES", 30),
        verbose=_bool("VERBOSE", False),
        positive_compound_threshold=_float("POSITIVE_COMPOUND_THRESHOLD", 0.05),
        max_cas_per_message=_int("MAX_CAS_PER_MESSAGE", 3),
        discover_interval_hours=_int("DISCOVER_INTERVAL_HOURS", 12),
        discover_keywords=keywords,
        db_path=os.getenv("DB_PATH", f"{data_dir}/meme.db"),
        channels_path=os.getenv("CHANNELS_PATH", "channels.yaml"),
        stop_path=os.getenv("STOP_PATH", f"{data_dir}/STOP"),
        data_dir=data_dir,
    )
```

Also write `.env.example` listing every key above, and `channels.yaml`:

```yaml
channels: []
```

- [ ] **Step 5: Run tests**

Run: `.venv/bin/pytest tests/test_config.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add requirements.txt pytest.ini .env.example channels.yaml src/__init__.py src/config.py tests/test_config.py .gitignore
git commit -m "feat: scaffold project and Settings loader"
```

---

### Task 2: Message filter (cashtag, CA, spam)

**Files:**
- Create: `src/filter.py`, `tests/test_filter.py`

**Interfaces:**
- Consumes: `Settings.max_cas_per_message` (pass as int arg to keep pure)
- Produces:
  - `@dataclass FilterResult: symbols: list[str]; cas: list[str]; is_spam: bool; spam_reason: str | None; text_hash: str`
  - `extract_targets(text: str, *, max_cas_per_message: int = 3, recent_hashes: set[str] | None = None, account_age_days: float | None = None) -> FilterResult`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_filter.py
from src.filter import extract_targets


def test_extracts_cashtag_and_ca():
    text = "ape $PEPE now So11111111111111111111111111111111111111112"
    r = extract_targets(text)
    assert "PEPE" in r.symbols
    assert any(len(c) >= 32 for c in r.cas)
    assert r.is_spam is False


def test_duplicate_text_is_spam():
    text = "buy $DOGE"
    first = extract_targets(text)
    second = extract_targets(text, recent_hashes={first.text_hash})
    assert second.is_spam is True
    assert second.spam_reason == "duplicate_text"


def test_too_many_cas_is_spam():
    cas = " ".join(
        [
            "11111111111111111111111111111111",
            "22222222222222222222222222222222",
            "33333333333333333333333333333333",
            "44444444444444444444444444444444",
        ]
    )
    r = extract_targets(f"rugs {cas}", max_cas_per_message=3)
    assert r.is_spam is True
    assert r.spam_reason == "too_many_cas"


def test_new_account_is_spam():
    r = extract_targets("moon $WIF", account_age_days=0.5)
    assert r.is_spam is True
    assert r.spam_reason == "new_account"


def test_no_targets_empty_lists():
    r = extract_targets("hello world")
    assert r.symbols == []
    assert r.cas == []
    assert r.is_spam is False
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `.venv/bin/pytest tests/test_filter.py -v`  
Expected: FAIL import error

- [ ] **Step 3: Implement filter**

```python
# src/filter.py
"""Extract cashtags / Solana-like CAs and apply spam heuristics."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

CASHTAG_RE = re.compile(r"\$([A-Za-z][A-Za-z0-9]{1,14})\b")
# Base58 alphabet excluding 0,O,I,l — length 32..44
BASE58_RE = re.compile(r"\b([1-9A-HJ-NP-Za-km-z]{32,44})\b")
MIN_ACCOUNT_AGE_DAYS = 7.0


@dataclass(frozen=True)
class FilterResult:
    symbols: list[str]
    cas: list[str]
    is_spam: bool
    spam_reason: str | None
    text_hash: str


def _hash_text(text: str) -> str:
    normalized = " ".join(text.lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def extract_targets(
    text: str,
    *,
    max_cas_per_message: int = 3,
    recent_hashes: set[str] | None = None,
    account_age_days: float | None = None,
) -> FilterResult:
    text_hash = _hash_text(text)
    symbols = sorted({m.group(1).upper() for m in CASHTAG_RE.finditer(text)})
    cas = sorted(set(BASE58_RE.findall(text)))

    if recent_hashes is not None and text_hash in recent_hashes:
        return FilterResult(symbols, cas, True, "duplicate_text", text_hash)
    if len(cas) > max_cas_per_message:
        return FilterResult(symbols, cas, True, "too_many_cas", text_hash)
    if account_age_days is not None and account_age_days < MIN_ACCOUNT_AGE_DAYS:
        return FilterResult(symbols, cas, True, "new_account", text_hash)

    return FilterResult(symbols, cas, False, None, text_hash)
```

Note: the CA fixture in tests must be valid base58 length; adjust fixture strings if regex rejects them (use real-looking base58 without `0OIl`).

- [ ] **Step 4: Run tests — expect PASS**

Run: `.venv/bin/pytest tests/test_filter.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/filter.py tests/test_filter.py
git commit -m "feat: extract cashtags/CAs and spam heuristics"
```

---

### Task 3: VADER sentiment wrapper

**Files:**
- Create: `src/sentiment.py`, `tests/test_sentiment.py`

**Interfaces:**
- Consumes: none (threshold passed in)
- Produces: `score_text(text: str, *, positive_threshold: float = 0.05) -> tuple[float, bool]` → `(compound, is_positive)`

- [ ] **Step 1: Failing test**

```python
# tests/test_sentiment.py
from src.sentiment import score_text


def test_positive_text():
    compound, is_pos = score_text("This is great, amazing, excellent moon!")
    assert compound > 0.05
    assert is_pos is True


def test_negative_text():
    compound, is_pos = score_text("This is terrible, awful, scam rug horrible")
    assert compound < 0
    assert is_pos is False


def test_threshold_gates_positive_flag():
    compound, is_pos = score_text("ok fine", positive_threshold=0.99)
    assert is_pos is False
    assert isinstance(compound, float)
```

- [ ] **Step 2: Run — expect FAIL**

Run: `.venv/bin/pytest tests/test_sentiment.py -v`

- [ ] **Step 3: Implement**

```python
# src/sentiment.py
"""Local VADER sentiment scoring."""

from __future__ import annotations

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_analyzer = SentimentIntensityAnalyzer()


def score_text(text: str, *, positive_threshold: float = 0.05) -> tuple[float, bool]:
    compound = float(_analyzer.polarity_scores(text)["compound"])
    return compound, compound > positive_threshold
```

- [ ] **Step 4: Run — expect PASS**

Run: `.venv/bin/pytest tests/test_sentiment.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/sentiment.py tests/test_sentiment.py
git commit -m "feat: add VADER sentiment wrapper"
```

---

### Task 4: channels.yaml helpers

**Files:**
- Create: `src/channels.py`, `tests/test_channels.py`

**Interfaces:**
- Consumes: path string
- Produces:
  - `@dataclass Channel: id: int | None; username: str | None; status: str; score: float; reason: str; updated_at: str`
  - `load_channels(path: str) -> list[Channel]` — missing/corrupt → `[]` + warning via returned empty (log warning)
  - `save_channels(path: str, channels: list[Channel]) -> None`
  - `upsert_suggested(path: str, *, username: str | None, channel_id: int | None, score: float, reason: str) -> Channel` — never changes `enabled`/`ignored` to suggested overwrite of status; if existing `ignored` or `enabled`, update score/reason/updated_at only, keep status
  - `list_enabled(path: str) -> list[Channel]`

- [ ] **Step 1: Failing tests**

```python
# tests/test_channels.py
from pathlib import Path

from src.channels import load_channels, list_enabled, upsert_suggested


def test_missing_file_returns_empty(tmp_path):
    assert load_channels(str(tmp_path / "missing.yaml")) == []


def test_corrupt_yaml_returns_empty(tmp_path):
    p = tmp_path / "channels.yaml"
    p.write_text("{not: valid: yaml: [")
    assert load_channels(str(p)) == []


def test_upsert_suggested_does_not_override_enabled(tmp_path):
    p = tmp_path / "channels.yaml"
    p.write_text(
        "channels:\n"
        "  - username: foo\n"
        "    id: null\n"
        "    status: enabled\n"
        "    score: 0.1\n"
        "    reason: manual\n"
        "    updated_at: '2026-01-01T00:00:00+00:00'\n"
    )
    ch = upsert_suggested(str(p), username="foo", channel_id=None, score=0.9, reason="hot")
    assert ch.status == "enabled"
    assert list_enabled(str(p))[0].username == "foo"


def test_upsert_suggested_skips_ignored_status_change(tmp_path):
    p = tmp_path / "channels.yaml"
    p.write_text(
        "channels:\n"
        "  - username: bad\n"
        "    id: null\n"
        "    status: ignored\n"
        "    score: 0.1\n"
        "    reason: spam\n"
        "    updated_at: '2026-01-01T00:00:00+00:00'\n"
    )
    ch = upsert_suggested(str(p), username="bad", channel_id=None, score=0.99, reason="still")
    assert ch.status == "ignored"


def test_new_suggested_created(tmp_path):
    p = tmp_path / "channels.yaml"
    ch = upsert_suggested(str(p), username="newch", channel_id=1, score=0.5, reason="density")
    assert ch.status == "suggested"
    loaded = load_channels(str(p))
    assert len(loaded) == 1
    assert loaded[0].username == "newch"
```

- [ ] **Step 2: Run — expect FAIL**

Run: `.venv/bin/pytest tests/test_channels.py -v`

- [ ] **Step 3: Implement `src/channels.py`**

Implement dataclasses + YAML load/save with `yaml.safe_load` / `safe_dump`. Match on `username` or `id`. On corrupt/missing: return `[]` and `logging.warning(...)`. `upsert_suggested` preserves `enabled`/`ignored` status.

- [ ] **Step 4: Run — expect PASS**

Run: `.venv/bin/pytest tests/test_channels.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/channels.py tests/test_channels.py
git commit -m "feat: channels.yaml load/save with suggested upsert guards"
```

---

### Task 5: SQLite database

**Files:**
- Create: `src/database.py`, `tests/test_database.py`

**Interfaces:**
- Consumes: `db_path: str`
- Produces:
  - `init_db(db_path: str) -> None`
  - `insert_mention(db_path, *, created_at, channel_id, user_id, text_hash, text, symbols, cas, sentiment_compound, is_positive, is_spam) -> int`
  - `fetch_mentions_since(db_path, *, key: str, since_iso: str) -> list[dict]` where `key` matches symbol in JSON or CA in JSON, excluding `is_spam=1`
  - `record_alert(db_path, *, key: str, sent_at: str, payload_summary: str) -> None`
  - `last_alert_at(db_path, *, key: str) -> str | None`

Schema:

```sql
CREATE TABLE IF NOT EXISTS mentions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  channel_id TEXT,
  user_id TEXT,
  text_hash TEXT NOT NULL,
  text TEXT NOT NULL,
  symbols TEXT NOT NULL,
  cas TEXT NOT NULL,
  sentiment_compound REAL NOT NULL,
  is_positive INTEGER NOT NULL,
  is_spam INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  key TEXT NOT NULL,
  sent_at TEXT NOT NULL,
  payload_summary TEXT NOT NULL
);
```

Store `symbols`/`cas` as JSON arrays via `json.dumps`.

- [ ] **Step 1: Failing tests**

```python
# tests/test_database.py
from src.database import (
    fetch_mentions_since,
    init_db,
    insert_mention,
    last_alert_at,
    record_alert,
)


def test_insert_and_fetch_excludes_spam(tmp_path):
    db = str(tmp_path / "meme.db")
    init_db(db)
    insert_mention(
        db,
        created_at="2026-07-20T12:00:00+00:00",
        channel_id="1",
        user_id="u1",
        text_hash="a",
        text="buy $PEPE",
        symbols=["PEPE"],
        cas=[],
        sentiment_compound=0.8,
        is_positive=True,
        is_spam=False,
    )
    insert_mention(
        db,
        created_at="2026-07-20T12:01:00+00:00",
        channel_id="1",
        user_id="u2",
        text_hash="b",
        text="spam $PEPE",
        symbols=["PEPE"],
        cas=[],
        sentiment_compound=0.8,
        is_positive=True,
        is_spam=True,
    )
    rows = fetch_mentions_since(db, key="PEPE", since_iso="2026-07-20T00:00:00+00:00")
    assert len(rows) == 1
    assert rows[0]["is_positive"] is True


def test_alert_cooldown_helpers(tmp_path):
    db = str(tmp_path / "meme.db")
    init_db(db)
    assert last_alert_at(db, key="PEPE") is None
    record_alert(db, key="PEPE", sent_at="2026-07-20T12:00:00+00:00", payload_summary="x")
    assert last_alert_at(db, key="PEPE") == "2026-07-20T12:00:00+00:00"
```

- [ ] **Step 2: Run — expect FAIL**

Run: `.venv/bin/pytest tests/test_database.py -v`

- [ ] **Step 3: Implement `src/database.py`**

```python
# src/database.py
"""SQLite persistence for mentions and alert audit."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def _connect(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str) -> None:
    with _connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS mentions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              created_at TEXT NOT NULL,
              channel_id TEXT,
              user_id TEXT,
              text_hash TEXT NOT NULL,
              text TEXT NOT NULL,
              symbols TEXT NOT NULL,
              cas TEXT NOT NULL,
              sentiment_compound REAL NOT NULL,
              is_positive INTEGER NOT NULL,
              is_spam INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS alerts (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              key TEXT NOT NULL,
              sent_at TEXT NOT NULL,
              payload_summary TEXT NOT NULL
            );
            """
        )


def insert_mention(
    db_path: str,
    *,
    created_at: str,
    channel_id: str | None,
    user_id: str | None,
    text_hash: str,
    text: str,
    symbols: list[str],
    cas: list[str],
    sentiment_compound: float,
    is_positive: bool,
    is_spam: bool,
) -> int:
    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO mentions (
              created_at, channel_id, user_id, text_hash, text, symbols, cas,
              sentiment_compound, is_positive, is_spam
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created_at,
                channel_id,
                user_id,
                text_hash,
                text,
                json.dumps(symbols),
                json.dumps(cas),
                sentiment_compound,
                int(is_positive),
                int(is_spam),
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def fetch_mentions_since(db_path: str, *, key: str, since_iso: str) -> list[dict]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM mentions
            WHERE is_spam = 0 AND created_at >= ?
            ORDER BY created_at ASC
            """,
            (since_iso,),
        ).fetchall()
    out: list[dict] = []
    for row in rows:
        symbols = json.loads(row["symbols"])
        cas = json.loads(row["cas"])
        if key not in symbols and key not in cas:
            continue
        out.append(
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "channel_id": row["channel_id"],
                "user_id": row["user_id"],
                "text": row["text"],
                "symbols": symbols,
                "cas": cas,
                "sentiment_compound": row["sentiment_compound"],
                "is_positive": bool(row["is_positive"]),
                "is_spam": False,
            }
        )
    return out


def record_alert(db_path: str, *, key: str, sent_at: str, payload_summary: str) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO alerts (key, sent_at, payload_summary) VALUES (?, ?, ?)",
            (key, sent_at, payload_summary),
        )
        conn.commit()


def last_alert_at(db_path: str, *, key: str) -> str | None:
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT sent_at FROM alerts WHERE key = ? ORDER BY sent_at DESC LIMIT 1",
            (key,),
        ).fetchone()
    return None if row is None else row["sent_at"]
```

- [ ] **Step 4: Run — expect PASS**

Run: `.venv/bin/pytest tests/test_database.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/database.py tests/test_database.py
git commit -m "feat: add SQLite mentions and alerts store"
```

---

### Task 6: Aggregator + cooldown

**Files:**
- Create: `src/aggregator.py`, `tests/test_aggregator.py`

**Interfaces:**
- Consumes: mention dicts `{is_positive: bool, channel_id: str, text: str, created_at: str}`
- Produces: `AggregateDecision` + `evaluate_window(...)`

- [ ] **Step 1: Failing tests**

```python
# tests/test_aggregator.py
from datetime import datetime, timezone

from src.aggregator import evaluate_window


def _m(positive: bool, text: str = "x") -> dict:
    return {
        "is_positive": positive,
        "channel_id": "c1",
        "text": text,
        "created_at": "2026-07-20T12:00:00+00:00",
    }


def test_fires_when_thresholds_met():
    mentions = [_m(True, f"t{i}") for i in range(5)]
    d = evaluate_window(
        mentions,
        key="PEPE",
        min_mentions=5,
        min_positive_ratio=0.7,
        last_alert_at=None,
        now=datetime(2026, 7, 20, 12, 5, tzinfo=timezone.utc),
        cooldown_minutes=30,
    )
    assert d.should_alert is True
    assert d.mention_count == 5
    assert d.positive_ratio == 1.0


def test_below_min_mentions():
    d = evaluate_window(
        [_m(True)],
        key="PEPE",
        min_mentions=5,
        min_positive_ratio=0.7,
        last_alert_at=None,
        now=datetime(2026, 7, 20, 12, 5, tzinfo=timezone.utc),
        cooldown_minutes=30,
    )
    assert d.should_alert is False
    assert d.reason == "below_min_mentions"


def test_below_positive_ratio():
    mentions = [_m(True)] * 2 + [_m(False)] * 3
    d = evaluate_window(
        mentions,
        key="PEPE",
        min_mentions=5,
        min_positive_ratio=0.7,
        last_alert_at=None,
        now=datetime(2026, 7, 20, 12, 5, tzinfo=timezone.utc),
        cooldown_minutes=30,
    )
    assert d.should_alert is False
    assert d.reason == "below_positive_ratio"


def test_cooldown_blocks():
    mentions = [_m(True) for _ in range(5)]
    d = evaluate_window(
        mentions,
        key="PEPE",
        min_mentions=5,
        min_positive_ratio=0.7,
        last_alert_at="2026-07-20T12:00:00+00:00",
        now=datetime(2026, 7, 20, 12, 10, tzinfo=timezone.utc),
        cooldown_minutes=30,
    )
    assert d.should_alert is False
    assert d.reason == "cooldown"
```

- [ ] **Step 2: Run — expect FAIL**

Run: `.venv/bin/pytest tests/test_aggregator.py -v`

- [ ] **Step 3: Implement**

```python
# src/aggregator.py
"""Sliding-window aggregate alert decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class AggregateDecision:
    should_alert: bool
    key: str
    mention_count: int
    positive_ratio: float
    channel_ids: list[str]
    snippets: list[str]
    reason: str


def _parse_ts(value: str) -> datetime:
    ts = datetime.fromisoformat(value)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def evaluate_window(
    mentions: list[dict],
    *,
    key: str,
    min_mentions: int,
    min_positive_ratio: float,
    last_alert_at: str | None,
    now: datetime,
    cooldown_minutes: int,
) -> AggregateDecision:
    count = len(mentions)
    positives = sum(1 for m in mentions if m.get("is_positive"))
    ratio = (positives / count) if count else 0.0
    channel_ids = sorted({str(m.get("channel_id")) for m in mentions if m.get("channel_id")})
    snippets = [str(m.get("text", ""))[:120] for m in mentions[:3]]

    if count < min_mentions:
        return AggregateDecision(False, key, count, ratio, channel_ids, snippets, "below_min_mentions")
    if ratio < min_positive_ratio:
        return AggregateDecision(False, key, count, ratio, channel_ids, snippets, "below_positive_ratio")
    if last_alert_at is not None:
        last = _parse_ts(last_alert_at)
        if now - last < timedelta(minutes=cooldown_minutes):
            return AggregateDecision(False, key, count, ratio, channel_ids, snippets, "cooldown")
    return AggregateDecision(True, key, count, ratio, channel_ids, snippets, "ok")
```

- [ ] **Step 4: Run — expect PASS**

Run: `.venv/bin/pytest tests/test_aggregator.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/aggregator.py tests/test_aggregator.py
git commit -m "feat: aggregate window and cooldown decisions"
```

---

### Task 7: Notifier (httpx Bot API)

**Files:**
- Create: `src/notifier.py`, `tests/test_notifier.py`

**Interfaces:**
- Consumes: token, chat_id, `AggregateDecision`
- Produces: `format_aggregate_alert`, `send_telegram_message`, `NotifierError`

- [ ] **Step 1: Failing tests**

```python
# tests/test_notifier.py
import httpx
import pytest

from src.aggregator import AggregateDecision
from src.notifier import NotifierError, format_aggregate_alert, send_telegram_message


def test_format_aggregate_alert_includes_key():
    d = AggregateDecision(True, "PEPE", 5, 0.8, ["1"], ["moon $PEPE"], "ok")
    text = format_aggregate_alert(d, window_minutes=5)
    assert "PEPE" in text
    assert "5" in text


def test_send_telegram_success():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/sendMessage")
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    send_telegram_message("tok", "1", "hi", client=client)


def test_send_telegram_error():
    transport = httpx.MockTransport(lambda r: httpx.Response(400, json={"ok": False}))
    client = httpx.Client(transport=transport)
    with pytest.raises(NotifierError):
        send_telegram_message("tok", "1", "hi", client=client)
```

- [ ] **Step 2: Run — expect FAIL**

Run: `.venv/bin/pytest tests/test_notifier.py -v`

- [ ] **Step 3: Implement**

```python
# src/notifier.py
"""Telegram Bot API alerts."""

from __future__ import annotations

import httpx

from src.aggregator import AggregateDecision


class NotifierError(Exception):
    pass


def format_aggregate_alert(decision: AggregateDecision, *, window_minutes: int) -> str:
    channels = ", ".join(decision.channel_ids) or "n/a"
    snippets = " | ".join(decision.snippets)
    return (
        f"HYPE {decision.key}\n"
        f"mentions={decision.mention_count} positive_ratio={decision.positive_ratio:.2f}\n"
        f"window_minutes={window_minutes} channels={channels}\n"
        f"samples: {snippets}"
    )


def send_telegram_message(
    token: str,
    chat_id: str,
    text: str,
    *,
    client: httpx.Client | None = None,
) -> None:
    owns = client is None
    client = client or httpx.Client(timeout=30.0)
    try:
        resp = client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": True,
            },
        )
        if resp.status_code >= 300:
            raise NotifierError(f"telegram HTTP {resp.status_code}: {resp.text}")
    finally:
        if owns:
            client.close()
```

- [ ] **Step 4: Run — expect PASS**

Run: `.venv/bin/pytest tests/test_notifier.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/notifier.py tests/test_notifier.py
git commit -m "feat: Telegram alert notifier"
```

---

### Task 8: Pure pipeline `handle_message`

**Files:**
- Create: `src/pipeline.py`, `tests/test_pipeline.py`

**Interfaces:**
- Consumes: filter, sentiment, database, aggregator, settings
- Produces: `handle_message(...) -> dict` with keys `stored`, `keys`, `alerts_sent`, `skipped_alert_due_to_stop`

`send_alert: Callable[[str], None]` injectable.

- [ ] **Step 1: Failing tests**

```python
# tests/test_pipeline.py
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.config import Settings
from src.database import init_db
from src.pipeline import handle_message


def _settings(tmp_path: Path, *, verbose: bool = False) -> Settings:
    db = tmp_path / "meme.db"
    init_db(str(db))
    return Settings(
        telegram_api_id=1,
        telegram_api_hash="h",
        telethon_session="s",
        alert_bot_token="t",
        alert_chat_id="1",
        window_minutes=5,
        min_mentions=5,
        min_positive_ratio=0.7,
        alert_cooldown_minutes=30,
        verbose=verbose,
        positive_compound_threshold=0.05,
        max_cas_per_message=3,
        discover_interval_hours=12,
        discover_keywords=["solana"],
        db_path=str(db),
        channels_path=str(tmp_path / "channels.yaml"),
        stop_path=str(tmp_path / "STOP"),
        data_dir=str(tmp_path),
    )


def test_aggregate_alert_after_five_positive(tmp_path):
    settings = _settings(tmp_path)
    sent: list[str] = []
    base = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
    for i in range(5):
        handle_message(
            settings,
            text=f"great amazing excellent $PEPE buy {i}",
            channel_id="c1",
            user_id=f"u{i}",
            account_age_days=30.0,
            now=base + timedelta(minutes=i),
            send_alert=sent.append,
            recent_hashes=None,
        )
    assert any("PEPE" in s for s in sent)


def test_stop_skips_alert_but_stores(tmp_path):
    settings = _settings(tmp_path)
    Path(settings.stop_path).write_text("")
    sent: list[str] = []
    base = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
    for i in range(5):
        result = handle_message(
            settings,
            text=f"great amazing excellent $PEPE {i}",
            channel_id="c1",
            user_id=f"u{i}",
            account_age_days=30.0,
            now=base + timedelta(minutes=i),
            send_alert=sent.append,
            recent_hashes=None,
        )
    assert result["stored"] is True
    assert sent == []
    assert result["skipped_alert_due_to_stop"] is True
```

- [ ] **Step 2: Run — expect FAIL**

Run: `.venv/bin/pytest tests/test_pipeline.py -v`

- [ ] **Step 3: Implement `src/pipeline.py`**

Wire: `extract_targets` → `score_text` → `insert_mention` → if not spam, for each key `fetch_mentions_since` + `evaluate_window` + `format_aggregate_alert` + `send_alert`/`record_alert`, honoring STOP and verbose. Use `now.isoformat()` for timestamps. Window `since = now - timedelta(minutes=settings.window_minutes)`.

- [ ] **Step 4: Run — expect PASS**

Run: `.venv/bin/pytest tests/test_pipeline.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/pipeline.py tests/test_pipeline.py
git commit -m "feat: message handling pipeline with STOP and verbose"
```

---

### Task 9: Discover ranking (pure)

**Files:**
- Create: `src/discover_rank.py`, `tests/test_discover_rank.py`

**Interfaces:**
- `ChannelSample(username, channel_id, members, messages_per_hour, sample_texts)`
- `rank_channel(sample) -> tuple[float, str]`

- [ ] **Step 1: Failing tests**

```python
# tests/test_discover_rank.py
from src.discover_rank import ChannelSample, rank_channel


def test_dense_channel_outranks_empty():
    hot = ChannelSample("hot", 1, 50_000, 30.0, ["moon $PEPE", "buy $WIF now"])
    cold = ChannelSample("cold", 2, 50_000, 30.0, ["gm", "hello"])
    assert rank_channel(hot)[0] > rank_channel(cold)[0]


def test_spam_samples_penalized():
    clean = ChannelSample("c", 1, 10_000, 10.0, ["nice $PEPE"])
    spammy = ChannelSample(
        "s",
        2,
        10_000,
        10.0,
        [
            "x " + " ".join(["11111111111111111111111111111111"] * 4),
        ],
    )
    assert rank_channel(clean)[0] > rank_channel(spammy)[0]
```

- [ ] **Step 2: Run — expect FAIL**

Run: `.venv/bin/pytest tests/test_discover_rank.py -v`

- [ ] **Step 3: Implement** — score = weighted average of clipped members/100k, messages_per_hour/60, target density in samples, minus spam fraction from `extract_targets(..., max_cas_per_message=3)`. Clamp to `[0, 1]`. Reason string summarizes top factor.

- [ ] **Step 4: Run — expect PASS**

Run: `.venv/bin/pytest tests/test_discover_rank.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/discover_rank.py tests/test_discover_rank.py
git commit -m "feat: pure channel ranking for discover"
```

---

### Task 10: Discover orchestration (mockable client)

**Files:**
- Create: `src/discover.py`, `tests/test_discover.py`

**Interfaces:**
- `class SearchClient(Protocol): def search(self, keyword: str) -> list[ChannelSample]: ...`
- `run_discover_once(settings: Settings, client: SearchClient) -> int`

- [ ] **Step 1: Failing tests**

```python
# tests/test_discover.py
from src.channels import load_channels
from src.config import Settings
from src.discover import run_discover_once
from src.discover_rank import ChannelSample


class FakeClient:
    def search(self, keyword: str):
        return [
            ChannelSample("alpha", 10, 20_000, 20.0, ["$PEPE moon"]),
            ChannelSample("beta", 11, 5_000, 5.0, ["$WIF"]),
        ]


def _settings(tmp_path) -> Settings:
    return Settings(
        telegram_api_id=1,
        telegram_api_hash="h",
        telethon_session="s",
        alert_bot_token="t",
        alert_chat_id="1",
        window_minutes=5,
        min_mentions=5,
        min_positive_ratio=0.7,
        alert_cooldown_minutes=30,
        verbose=False,
        positive_compound_threshold=0.05,
        max_cas_per_message=3,
        discover_interval_hours=12,
        discover_keywords=["solana"],
        db_path=str(tmp_path / "meme.db"),
        channels_path=str(tmp_path / "channels.yaml"),
        stop_path=str(tmp_path / "STOP"),
        data_dir=str(tmp_path),
    )


def test_discover_writes_suggested_only(tmp_path):
    settings = _settings(tmp_path)
    n = run_discover_once(settings, FakeClient())
    assert n >= 1
    channels = load_channels(settings.channels_path)
    assert channels
    assert all(c.status == "suggested" for c in channels)
```

- [ ] **Step 2: Run — expect FAIL**

Run: `.venv/bin/pytest tests/test_discover.py -v`

- [ ] **Step 3: Implement `run_discover_once`** looping keywords → `client.search` → `rank_channel` → `upsert_suggested`. Add `TelethonSearchClient` (real network) + `if __name__ == "__main__"` sleep loop. Tests use only `FakeClient`.

- [ ] **Step 4: Run — expect PASS**

Run: `.venv/bin/pytest tests/test_discover.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/discover.py tests/test_discover.py
git commit -m "feat: discover once loop with suggested upserts"
```

---

### Task 11: Listener helpers + Telethon entrypoint

**Files:**
- Create: `src/listener.py`, `tests/test_listener_smoke.py`

**Interfaces:**
- `alerts_allowed(stop_path: str) -> bool`
- `async def run_listener(settings) -> None`

- [ ] **Step 1: Failing tests**

```python
# tests/test_listener_smoke.py
from pathlib import Path

from src.channels import upsert_suggested
from src.listener import alerts_allowed, enabled_channel_keys


def test_alerts_allowed_respects_stop(tmp_path):
    stop = tmp_path / "STOP"
    assert alerts_allowed(str(stop)) is True
    stop.write_text("")
    assert alerts_allowed(str(stop)) is False


def test_enabled_channel_keys(tmp_path):
    p = tmp_path / "channels.yaml"
    upsert_suggested(str(p), username="a", channel_id=1, score=0.5, reason="x")
    # manually enable
    text = Path(p).read_text().replace("suggested", "enabled")
    Path(p).write_text(text)
    keys = enabled_channel_keys(str(p))
    assert "a" in keys or 1 in keys
```

- [ ] **Step 2: Run — expect FAIL**

Run: `.venv/bin/pytest tests/test_listener_smoke.py -v`

- [ ] **Step 3: Implement** `alerts_allowed`, `enabled_channel_keys`, and Telethon `run_listener` that filters events to enabled chats and calls `handle_message` with a real `send_alert` closure wrapping `send_telegram_message` (skipping when not `alerts_allowed`). `__main__` loads settings and runs.

- [ ] **Step 4: Run — expect PASS**

Run: `.venv/bin/pytest tests/test_listener_smoke.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/listener.py tests/test_listener_smoke.py
git commit -m "feat: Telethon listener entrypoint"
```

---

### Task 12: README + final verification

**Files:**
- Create: `README.md`
- Modify: none required unless gaps found

**README must cover:**
1. Create Telegram API id/hash at my.telegram.org  
2. Create alert bot via BotFather; get chat id  
3. `cp .env.example .env` and fill  
4. First-run Telethon session login (`python -m src.listener` will prompt)  
5. Run discover: `python -m src.discover`  
6. Edit `channels.yaml`: set `status: enabled` for trusted suggestions; join those chats in the user account  
7. Run listener: `python -m src.listener`  
8. STOP file: `touch data/STOP`  
9. Explicit: no link to trading bots

- [ ] **Step 1: Write README**  
- [ ] **Step 2: Run full suite + lint if available**

```bash
.venv/bin/pytest -v
```

Expected: all PASS

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: README for meme hype bot setup and operations"
```

---

## Spec coverage checklist (plan self-review)

| Spec item | Task |
|-----------|------|
| New folder isolation | Global + Task 1 |
| Telethon data source | Tasks 10–11 |
| VADER only | Task 3 |
| Separate alert bot | Tasks 7, 1 |
| Cashtag + Solana CA | Task 2 |
| Aggregate + verbose | Tasks 6, 8 |
| Spam heuristics | Task 2 |
| channels suggested/enabled/ignored | Task 4 |
| Discover never auto-enable | Tasks 4, 10 |
| Two processes | Tasks 10–11 |
| SQLite mentions/alerts | Task 5 |
| STOP skip alerts continue ingest | Task 8 |
| Error handling empty yaml | Task 4 |
| Unit/integration/smoke | Tasks 2–11 |
| Non-goals (no trading/X/Claude) | Global Constraints |

**Placeholder scan:** Tasks 1–7 and 10–11 include concrete tests; Task 8/9 step 3 leave thin wiring that follows listed interfaces (no TBD). Removed abbreviated “write tests for the above” gaps.

**Type consistency:** `FilterResult`, `Settings`, `Channel.status` ∈ {`suggested`,`enabled`,`ignored`}, `AggregateDecision.should_alert`, pipeline injectable `send_alert`, `SearchClient.search -> list[ChannelSample]`.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-20-meme-hype-bot.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — execute tasks in this session with executing-plans checkpoints  

Which approach?
