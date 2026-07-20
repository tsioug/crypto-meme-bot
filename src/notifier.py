"""Telegram Bot API alerts."""

from __future__ import annotations

import httpx

from src.aggregator import AggregateDecision


class NotifierError(Exception):
    pass


def format_aggregate_alert(decision: AggregateDecision, *, window_minutes: int) -> str:
    channels = ", ".join(decision.channel_ids) or "n/a"
    snippets = " | ".join(decision.snippets)
    return (
        f"HYPE {decision.key}\n"
        f"mentions={decision.mention_count} positive_ratio={decision.positive_ratio:.2f}\n"
        f"window_minutes={window_minutes} channels={channels}\n"
        f"samples: {snippets}"
    )


def send_telegram_message(
    token: str,
    chat_id: str,
    text: str,
    *,
    client: httpx.Client | None = None,
) -> None:
    owns = client is None
    client = client or httpx.Client(timeout=30.0)
    try:
        resp = client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": True,
            },
        )
        if resp.status_code >= 300:
            raise NotifierError(f"telegram HTTP {resp.status_code}: {resp.text}")
    finally:
        if owns:
            client.close()
