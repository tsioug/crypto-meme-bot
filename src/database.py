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
