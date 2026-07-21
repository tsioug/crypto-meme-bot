"""Tests for dashboard overview builder."""

from __future__ import annotations

from datetime import datetime, timezone

from src.database import init_db, insert_mention, record_alert
from src.overview import build_overview


def _write_channels(path, yaml_text: str) -> None:
    path.write_text(yaml_text)


def test_build_overview_counts_and_hot_keys(tmp_path):
    db = str(tmp_path / "meme.db")
    init_db(db)
    channels = tmp_path / "channels.yaml"
    stop = tmp_path / "STOP"
    now = datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc)

    _write_channels(
        channels,
        "channels:\n"
        "  - id: 1\n"
        "    username: alpha\n"
        "    status: enabled\n"
        "    score: 0.5\n"
        "    reason: density\n"
        "    updated_at: '2026-07-21T00:00:00+00:00'\n",
    )

    for i in range(3):
        insert_mention(
            db,
            created_at="2026-07-21T11:30:00+00:00",
            channel_id="c1",
            user_id=f"u{i}",
            text_hash=f"h{i}",
            text=f"moon $PEPE {i}",
            symbols=["PEPE"],
            cas=[],
            sentiment_compound=0.8,
            is_positive=True,
            is_spam=False,
        )
    insert_mention(
        db,
        created_at="2026-07-20T10:00:00+00:00",
        channel_id="c1",
        user_id="old",
        text_hash="old",
        text="old $PEPE",
        symbols=["PEPE"],
        cas=[],
        sentiment_compound=0.8,
        is_positive=True,
        is_spam=False,
    )
    insert_mention(
        db,
        created_at="2026-07-21T11:00:00+00:00",
        channel_id="c1",
        user_id="spam",
        text_hash="spam",
        text="spam $PEPE",
        symbols=["PEPE"],
        cas=[],
        sentiment_compound=0.8,
        is_positive=True,
        is_spam=True,
    )
    record_alert(
        db,
        key="PEPE",
        sent_at="2026-07-21T11:45:00+00:00",
        payload_summary="mentions=3",
    )

    stop.write_text("")

    overview = build_overview(
        channels_path=str(channels),
        db_path=db,
        stop_path=str(stop),
        now=now,
    )

    assert overview["stop_active"] is True
    assert overview["mentions_1h"] == 3
    assert overview["mentions_24h"] == 3
    assert overview["alerts_24h"] == 1
    assert overview["hot_keys"][0]["key"] == "PEPE"
    assert overview["hot_keys"][0]["mentions"] == 3
    assert overview["hot_keys"][0]["positive_ratio"] == 1.0
    assert overview["channels"][0]["username"] == "alpha"
    assert overview["recent_alerts"][0]["key"] == "PEPE"


def test_build_overview_empty_db(tmp_path):
    channels = tmp_path / "channels.yaml"
    channels.write_text("channels: []\n")
    overview = build_overview(
        channels_path=str(channels),
        db_path=str(tmp_path / "missing.db"),
        stop_path=str(tmp_path / "STOP"),
    )
    assert overview["mentions_24h"] == 0
    assert overview["hot_keys"] == []
    assert overview["channels"] == []
