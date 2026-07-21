"""Build read-only dashboard overview payload from yaml + SQLite."""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.channels import Channel, load_channels

HOT_KEY_LIMIT = 5
RECENT_ALERT_LIMIT = 20


def _parse_ts(value: str) -> datetime:
    ts = datetime.fromisoformat(value)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def _cutoff_iso(hours: int, *, now: datetime) -> str:
    return (now - timedelta(hours=hours)).isoformat()


def _query_readonly(db_path: str, sql: str, params: tuple = ()) -> list[tuple]:
    path = Path(db_path)
    if not path.exists():
        return []
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return []
    try:
        return conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def _count_mentions(db_path: str, since_iso: str) -> int:
    rows = _query_readonly(
        db_path,
        "SELECT COUNT(*) FROM mentions WHERE is_spam = 0 AND created_at >= ?",
        (since_iso,),
    )
    return int(rows[0][0]) if rows else 0


def _count_alerts(db_path: str, since_iso: str) -> int:
    rows = _query_readonly(
        db_path,
        "SELECT COUNT(*) FROM alerts WHERE sent_at >= ?",
        (since_iso,),
    )
    return int(rows[0][0]) if rows else 0


def _recent_alerts(db_path: str, *, limit: int = RECENT_ALERT_LIMIT) -> list[dict]:
    rows = _query_readonly(
        db_path,
        """
        SELECT key, sent_at, payload_summary
        FROM alerts
        ORDER BY sent_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [
        {"sent_at": sent_at, "key": key, "summary": summary}
        for key, sent_at, summary in rows
    ]


def _hot_keys(db_path: str, since_iso: str, *, limit: int = HOT_KEY_LIMIT) -> list[dict]:
    rows = _query_readonly(
        db_path,
        """
        SELECT symbols, cas, is_positive
        FROM mentions
        WHERE is_spam = 0 AND created_at >= ?
        """,
        (since_iso,),
    )
    totals: dict[str, int] = defaultdict(int)
    positives: dict[str, int] = defaultdict(int)

    for symbols_json, cas_json, is_positive in rows:
        keys: list[str] = []
        try:
            keys.extend(json.loads(symbols_json))
            keys.extend(json.loads(cas_json))
        except (TypeError, json.JSONDecodeError):
            continue
        for key in keys:
            if not key:
                continue
            totals[key] += 1
            if bool(is_positive):
                positives[key] += 1

    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)[:limit]
    out: list[dict] = []
    for key, mention_count in ranked:
        pos = positives.get(key, 0)
        ratio = pos / mention_count if mention_count else 0.0
        out.append(
            {
                "key": key,
                "mentions": mention_count,
                "positive_ratio": round(ratio, 4),
            }
        )
    return out


def _channels_payload(channels: list[Channel]) -> list[dict]:
    ranked = sorted(channels, key=lambda c: c.score, reverse=True)
    return [
        {
            "username": channel.username,
            "status": channel.status,
            "score": channel.score,
            "reason": channel.reason,
        }
        for channel in ranked
    ]


def build_overview(
    *,
    channels_path: str,
    db_path: str,
    stop_path: str,
    listener_hint: str = "unknown",
    discover_hint: str = "unknown",
    now: datetime | None = None,
) -> dict:
    """Assemble overview JSON matching dashboard/mock/overview.json contract."""
    now = now or datetime.now(timezone.utc)
    since_1h = _cutoff_iso(1, now=now)
    since_24h = _cutoff_iso(24, now=now)

    return {
        "stop_active": Path(stop_path).exists(),
        "listener_hint": listener_hint,
        "discover_hint": discover_hint,
        "mentions_1h": _count_mentions(db_path, since_1h),
        "mentions_24h": _count_mentions(db_path, since_24h),
        "alerts_24h": _count_alerts(db_path, since_24h),
        "hot_keys": _hot_keys(db_path, since_24h),
        "recent_alerts": _recent_alerts(db_path),
        "channels": _channels_payload(load_channels(channels_path)),
    }
