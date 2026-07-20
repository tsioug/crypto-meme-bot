"""Sliding-window aggregate alert decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class AggregateDecision:
    should_alert: bool
    key: str
    mention_count: int
    positive_ratio: float
    channel_ids: list[str]
    snippets: list[str]
    reason: str


def _parse_ts(value: str) -> datetime:
    ts = datetime.fromisoformat(value)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def evaluate_window(
    mentions: list[dict],
    *,
    key: str,
    min_mentions: int,
    min_positive_ratio: float,
    last_alert_at: str | None,
    now: datetime,
    cooldown_minutes: int,
) -> AggregateDecision:
    count = len(mentions)
    positives = sum(1 for m in mentions if m.get("is_positive"))
    ratio = (positives / count) if count else 0.0
    channel_ids = sorted({str(m.get("channel_id")) for m in mentions if m.get("channel_id")})
    snippets = [str(m.get("text", ""))[:120] for m in mentions[:3]]

    if count < min_mentions:
        return AggregateDecision(False, key, count, ratio, channel_ids, snippets, "below_min_mentions")
    if ratio < min_positive_ratio:
        return AggregateDecision(False, key, count, ratio, channel_ids, snippets, "below_positive_ratio")
    if last_alert_at is not None:
        last = _parse_ts(last_alert_at)
        if now - last < timedelta(minutes=cooldown_minutes):
            return AggregateDecision(False, key, count, ratio, channel_ids, snippets, "cooldown")
    return AggregateDecision(True, key, count, ratio, channel_ids, snippets, "ok")
