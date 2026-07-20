"""Orchestrate Telegram channel discovery without coupling it to Telethon."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Protocol

from src.channels import upsert_suggested
from src.config import Settings, load_settings
from src.discover_rank import ChannelSample, rank_channel


class SearchClient(Protocol):
    def search(self, keyword: str) -> list[ChannelSample]:
        """Return channel samples matching one discovery keyword."""


def run_discover_once(settings: Settings, client: SearchClient) -> int:
    """Search configured keywords and persist candidates as suggestions."""
    upserted = 0
    for keyword in settings.discover_keywords:
        for sample in client.search(keyword):
            score, reason = rank_channel(sample)
            upsert_suggested(
                settings.channels_path,
                username=sample.username,
                channel_id=sample.channel_id,
                score=score,
                reason=reason,
            )
            upserted += 1
    return upserted


class TelethonSearchClient:
    """Synchronous Telethon adapter used only by the executable loop."""

    def __init__(
        self,
        client: Any,
        *,
        search_limit: int = 50,
        message_limit: int = 50,
    ) -> None:
        self._client = client
        self._search_limit = search_limit
        self._message_limit = message_limit

    def search(self, keyword: str) -> list[ChannelSample]:
        from telethon.tl.functions.contacts import SearchRequest

        result = self._client(
            SearchRequest(q=keyword, limit=self._search_limit)
        )
        samples: list[ChannelSample] = []
        for chat in result.chats:
            username = getattr(chat, "username", None)
            channel_id = getattr(chat, "id", None)
            if not username or channel_id is None:
                continue

            messages = list(
                self._client.iter_messages(chat, limit=self._message_limit)
            )
            texts = [
                message.message
                for message in messages
                if isinstance(getattr(message, "message", None), str)
                and message.message
            ]
            samples.append(
                ChannelSample(
                    username=username,
                    channel_id=channel_id,
                    members=int(getattr(chat, "participants_count", 0) or 0),
                    messages_per_hour=_messages_per_hour(messages),
                    sample_texts=texts,
                )
            )
        return samples


def _messages_per_hour(messages: list[Any]) -> float:
    dated = [
        message.date
        for message in messages
        if isinstance(getattr(message, "date", None), datetime)
    ]
    if not dated:
        return 0.0

    newest = max(dated)
    if newest.tzinfo is None:
        newest = newest.replace(tzinfo=timezone.utc)
    oldest = min(dated)
    if oldest.tzinfo is None:
        oldest = oldest.replace(tzinfo=timezone.utc)
    elapsed_hours = max((newest - oldest).total_seconds() / 3600, 1.0)
    return len(dated) / elapsed_hours


def main() -> None:
    from telethon.sync import TelegramClient

    settings = load_settings()
    with TelegramClient(
        settings.telethon_session,
        settings.telegram_api_id,
        settings.telegram_api_hash,
    ) as telethon:
        client = TelethonSearchClient(telethon)
        while True:
            run_discover_once(settings, client)
            time.sleep(settings.discover_interval_hours * 3600)


if __name__ == "__main__":
    main()
