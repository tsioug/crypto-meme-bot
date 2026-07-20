"""Shared pytest fixtures."""

import pytest

_SETTINGS_ENV_KEYS = (
    "TELEGRAM_API_ID",
    "TELEGRAM_API_HASH",
    "TELETHON_SESSION",
    "ALERT_BOT_TOKEN",
    "ALERT_CHAT_ID",
    "DATA_DIR",
    "DB_PATH",
    "CHANNELS_PATH",
    "STOP_PATH",
    "WINDOW_MINUTES",
    "MIN_MENTIONS",
    "MIN_POSITIVE_RATIO",
    "ALERT_COOLDOWN_MINUTES",
    "VERBOSE",
    "POSITIVE_COMPOUND_THRESHOLD",
    "MAX_CAS_PER_MESSAGE",
    "DISCOVER_INTERVAL_HOURS",
    "DISCOVER_KEYWORDS",
)


@pytest.fixture(autouse=True)
def _clear_settings_env(monkeypatch):
    for key in _SETTINGS_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
