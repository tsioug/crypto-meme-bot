from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.config import Settings
from src.database import fetch_mentions_since, init_db
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


def _handle(
    settings: Settings,
    text: str,
    now: datetime,
    sent: list[str],
    *,
    account_age_days: float = 30.0,
) -> dict:
    return handle_message(
        settings,
        text=text,
        channel_id="c1",
        user_id="u1",
        account_age_days=account_age_days,
        now=now,
        send_alert=sent.append,
        recent_hashes=None,
    )


def test_no_targets_returns_without_storing(tmp_path):
    settings = _settings(tmp_path)
    result = _handle(
        settings,
        "great amazing excellent",
        datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc),
        [],
    )

    assert result == {
        "stored": False,
        "keys": [],
        "alerts_sent": 0,
        "skipped_alert_due_to_stop": False,
    }


def test_aggregate_alert_after_five_positive(tmp_path):
    settings = _settings(tmp_path)
    sent: list[str] = []
    base = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)

    for i in range(5):
        result = _handle(
            settings,
            f"great amazing excellent $PEPE buy {i}",
            base + timedelta(minutes=i),
            sent,
        )

    assert result["stored"] is True
    assert result["keys"] == ["PEPE"]
    assert result["alerts_sent"] == 1
    assert any("PEPE" in message for message in sent)


def test_spam_is_stored_but_does_not_aggregate_or_send_verbose(tmp_path):
    settings = _settings(tmp_path, verbose=True)
    sent: list[str] = []
    now = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)

    result = _handle(settings, "great amazing $PEPE", now, sent, account_age_days=1.0)

    rows = fetch_mentions_since(
        settings.db_path,
        key="PEPE",
        since_iso=(now - timedelta(minutes=5)).isoformat(),
    )
    assert result["stored"] is True
    assert result["alerts_sent"] == 0
    assert rows == []
    assert sent == []


def test_stop_skips_alert_but_stores(tmp_path):
    settings = replace(_settings(tmp_path, verbose=True), min_mentions=1)
    Path(settings.stop_path).write_text("")
    sent: list[str] = []
    now = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)

    result = _handle(settings, "great amazing excellent $PEPE", now, sent)

    rows = fetch_mentions_since(
        settings.db_path,
        key="PEPE",
        since_iso=(now - timedelta(minutes=5)).isoformat(),
    )
    assert result["stored"] is True
    assert result["alerts_sent"] == 0
    assert result["skipped_alert_due_to_stop"] is True
    assert len(rows) == 1
    assert sent == []


def test_each_symbol_and_ca_is_aggregated_with_one_verbose_raw_hit(tmp_path):
    settings = replace(_settings(tmp_path, verbose=True), min_mentions=1)
    sent: list[str] = []
    now = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
    ca = "7GCihgDB8fe6KNjn2MYTKz1c2J4q8Z4Um8cb8a8Sn2nd"

    result = _handle(settings, f"great amazing $PEPE {ca}", now, sent)

    assert result["keys"] == ["PEPE", ca]
    assert result["alerts_sent"] == 3
    assert sum(message.startswith("HYPE ") for message in sent) == 2
    assert sum(message.startswith("RAW HIT ") for message in sent) == 1
