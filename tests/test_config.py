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
    env.write_text(
        "\n".join(
            [
                "TELEGRAM_API_ID=1",
                "TELEGRAM_API_HASH=hash",
                "ALERT_CHAT_ID=-1001",
            ]
        )
    )
    monkeypatch.chdir(tmp_path)
    with pytest.raises(RuntimeError, match="ALERT_BOT_TOKEN"):
        load_settings(str(env))
