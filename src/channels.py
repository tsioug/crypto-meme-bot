"""Helpers for reading and updating the channel registry."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

VALID_STATUSES = {"suggested", "enabled", "ignored"}


@dataclass
class Channel:
    id: int | None
    username: str | None
    status: str
    score: float
    reason: str
    updated_at: str


def _channel_from_dict(value: Any) -> Channel:
    if not isinstance(value, dict):
        raise ValueError("channel entry must be a mapping")

    channel = Channel(
        id=value["id"],
        username=value["username"],
        status=value["status"],
        score=float(value["score"]),
        reason=value["reason"],
        updated_at=value["updated_at"],
    )
    if channel.status not in VALID_STATUSES:
        raise ValueError(f"invalid channel status: {channel.status}")
    return channel


def load_channels(path: str) -> list[Channel]:
    channel_path = Path(path)
    try:
        raw = yaml.safe_load(channel_path.read_text())
        if raw is None:
            return []
        if not isinstance(raw, dict) or not isinstance(raw.get("channels"), list):
            raise ValueError("root must contain a channels list")
        return [_channel_from_dict(value) for value in raw["channels"]]
    except FileNotFoundError:
        logging.warning("Channels file is missing: %s", channel_path)
    except (OSError, KeyError, TypeError, ValueError, yaml.YAMLError) as exc:
        logging.warning("Could not load channels file %s: %s", channel_path, exc)
    return []


def save_channels(path: str, channels: list[Channel]) -> None:
    channel_path = Path(path)
    channel_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"channels": [asdict(channel) for channel in channels]}
    channel_path.write_text(yaml.safe_dump(payload, sort_keys=False))


def _matches(
    channel: Channel, *, username: str | None, channel_id: int | None
) -> bool:
    return (username is not None and channel.username == username) or (
        channel_id is not None and channel.id == channel_id
    )


def upsert_suggested(
    path: str,
    *,
    username: str | None,
    channel_id: int | None,
    score: float,
    reason: str,
) -> Channel:
    channels = load_channels(path)
    updated_at = datetime.now(timezone.utc).isoformat()

    for index, channel in enumerate(channels):
        if _matches(channel, username=username, channel_id=channel_id):
            updated = replace(
                channel,
                score=score,
                reason=reason,
                updated_at=updated_at,
            )
            channels[index] = updated
            save_channels(path, channels)
            return updated

    suggested = Channel(
        id=channel_id,
        username=username,
        status="suggested",
        score=score,
        reason=reason,
        updated_at=updated_at,
    )
    channels.append(suggested)
    save_channels(path, channels)
    return suggested


def list_enabled(path: str) -> list[Channel]:
    return [channel for channel in load_channels(path) if channel.status == "enabled"]
