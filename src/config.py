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
