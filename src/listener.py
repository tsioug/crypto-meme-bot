"""Telethon listener entrypoint and channel helpers."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from telethon import TelegramClient, events

from src.channels import list_enabled
from src.config import Settings, load_settings
from src.notifier import send_telegram_message
from src.pipeline import handle_message


def alerts_allowed(stop_path: str) -> bool:
    """Return whether alert delivery is enabled."""
    return not Path(stop_path).exists()


def enabled_channel_keys(path: str) -> list[str | int]:
    """Return all usable usernames and IDs for enabled channels."""
    keys: list[str | int] = []
    for channel in list_enabled(path):
        if channel.username is not None:
            keys.append(channel.username)
        if channel.id is not None:
            keys.append(channel.id)
    return keys


async def run_listener(settings: Settings) -> None:
    """Listen to enabled Telegram channels and process new messages."""
    client = TelegramClient(
        settings.telethon_session,
        settings.telegram_api_id,
        settings.telegram_api_hash,
    )

    def send_alert(text: str) -> None:
        if alerts_allowed(settings.stop_path):
            send_telegram_message(
                settings.alert_bot_token,
                settings.alert_chat_id,
                text,
            )

    @client.on(events.NewMessage(chats=enabled_channel_keys(settings.channels_path)))
    async def on_new_message(event) -> None:
        handle_message(
            settings,
            text=event.raw_text or "",
            channel_id=str(event.chat_id) if event.chat_id is not None else None,
            user_id=str(event.sender_id) if event.sender_id is not None else None,
            account_age_days=None,
            now=event.date or datetime.now(timezone.utc),
            send_alert=send_alert,
            recent_hashes=None,
        )

    await client.start()
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(run_listener(load_settings()))
