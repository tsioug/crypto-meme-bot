"""Pure message ingestion and alert pipeline."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

from src.aggregator import evaluate_window
from src.config import Settings
from src.database import (
    fetch_mentions_since,
    insert_mention,
    last_alert_at,
    record_alert,
)
from src.filter import extract_targets
from src.notifier import format_aggregate_alert
from src.sentiment import score_text


def handle_message(
    settings: Settings,
    *,
    text: str,
    channel_id: str | None,
    user_id: str | None,
    account_age_days: float | None,
    now: datetime,
    send_alert: Callable[[str], None],
    recent_hashes: set[str] | None,
) -> dict:
    """Store one targeted message and emit any eligible alerts."""
    targets = extract_targets(
        text,
        max_cas_per_message=settings.max_cas_per_message,
        recent_hashes=recent_hashes,
        account_age_days=account_age_days,
    )
    keys = targets.symbols + targets.cas
    result = {
        "stored": False,
        "keys": keys,
        "alerts_sent": 0,
        "skipped_alert_due_to_stop": False,
    }
    if not keys:
        return result

    compound, is_positive = score_text(
        text,
        positive_threshold=settings.positive_compound_threshold,
    )
    now_iso = now.isoformat()
    insert_mention(
        settings.db_path,
        created_at=now_iso,
        channel_id=channel_id,
        user_id=user_id,
        text_hash=targets.text_hash,
        text=text,
        symbols=targets.symbols,
        cas=targets.cas,
        sentiment_compound=compound,
        is_positive=is_positive,
        is_spam=targets.is_spam,
    )
    result["stored"] = True
    if targets.is_spam:
        return result

    stop_exists = Path(settings.stop_path).exists()
    result["skipped_alert_due_to_stop"] = stop_exists
    since_iso = (now - timedelta(minutes=settings.window_minutes)).isoformat()

    for key in keys:
        mentions = fetch_mentions_since(
            settings.db_path,
            key=key,
            since_iso=since_iso,
        )
        decision = evaluate_window(
            mentions,
            key=key,
            min_mentions=settings.min_mentions,
            min_positive_ratio=settings.min_positive_ratio,
            last_alert_at=last_alert_at(settings.db_path, key=key),
            now=now,
            cooldown_minutes=settings.alert_cooldown_minutes,
        )
        if not decision.should_alert or stop_exists:
            continue

        payload = format_aggregate_alert(
            decision,
            window_minutes=settings.window_minutes,
        )
        send_alert(payload)
        record_alert(
            settings.db_path,
            key=key,
            sent_at=now_iso,
            payload_summary=payload,
        )
        result["alerts_sent"] += 1

    if settings.verbose and not stop_exists:
        send_alert(f"RAW HIT {', '.join(keys)}\n{text[:240]}")
        result["alerts_sent"] += 1

    return result
