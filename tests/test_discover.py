from __future__ import annotations

import pytest

from src.channels import Channel, load_channels, save_channels
from src.config import Settings
from src.discover import run_discover_once
from src.discover_rank import ChannelSample


class FakeClient:
    def __init__(self) -> None:
        self.keywords: list[str] = []

    def search(self, keyword: str) -> list[ChannelSample]:
        self.keywords.append(keyword)
        return [
            ChannelSample("alpha", 10, 20_000, 20.0, ["$PEPE moon"]),
            ChannelSample("beta", 11, 5_000, 5.0, ["$WIF"]),
        ]


def _settings(tmp_path, *, keywords: list[str] | None = None) -> Settings:
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
        discover_keywords=keywords or ["solana"],
        db_path=str(tmp_path / "meme.db"),
        channels_path=str(tmp_path / "channels.yaml"),
        stop_path=str(tmp_path / "STOP"),
        data_dir=str(tmp_path),
    )


def test_discover_writes_suggested_only(tmp_path):
    settings = _settings(tmp_path)
    client = FakeClient()

    count = run_discover_once(settings, client)

    assert count == 2
    assert client.keywords == ["solana"]
    channels = load_channels(settings.channels_path)
    assert channels
    assert all(channel.status == "suggested" for channel in channels)


@pytest.mark.parametrize("existing_status", ["enabled", "ignored"])
def test_discover_preserves_existing_status(tmp_path, existing_status):
    settings = _settings(tmp_path)
    save_channels(
        settings.channels_path,
        [
            Channel(
                id=10,
                username="alpha",
                status=existing_status,
                score=0.0,
                reason="manual decision",
                updated_at="2026-01-01T00:00:00+00:00",
            )
        ],
    )

    run_discover_once(settings, FakeClient())

    channels = load_channels(settings.channels_path)
    alpha = next(channel for channel in channels if channel.id == 10)
    assert alpha.status == existing_status
