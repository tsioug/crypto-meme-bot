from datetime import datetime, timezone

from src.aggregator import evaluate_window


def _m(positive: bool, text: str = "x") -> dict:
    return {
        "is_positive": positive,
        "channel_id": "c1",
        "text": text,
        "created_at": "2026-07-20T12:00:00+00:00",
    }


def test_fires_when_thresholds_met():
    mentions = [_m(True, f"t{i}") for i in range(5)]
    d = evaluate_window(
        mentions,
        key="PEPE",
        min_mentions=5,
        min_positive_ratio=0.7,
        last_alert_at=None,
        now=datetime(2026, 7, 20, 12, 5, tzinfo=timezone.utc),
        cooldown_minutes=30,
    )
    assert d.should_alert is True
    assert d.mention_count == 5
    assert d.positive_ratio == 1.0


def test_below_min_mentions():
    d = evaluate_window(
        [_m(True)],
        key="PEPE",
        min_mentions=5,
        min_positive_ratio=0.7,
        last_alert_at=None,
        now=datetime(2026, 7, 20, 12, 5, tzinfo=timezone.utc),
        cooldown_minutes=30,
    )
    assert d.should_alert is False
    assert d.reason == "below_min_mentions"


def test_below_positive_ratio():
    mentions = [_m(True)] * 2 + [_m(False)] * 3
    d = evaluate_window(
        mentions,
        key="PEPE",
        min_mentions=5,
        min_positive_ratio=0.7,
        last_alert_at=None,
        now=datetime(2026, 7, 20, 12, 5, tzinfo=timezone.utc),
        cooldown_minutes=30,
    )
    assert d.should_alert is False
    assert d.reason == "below_positive_ratio"


def test_cooldown_blocks():
    mentions = [_m(True) for _ in range(5)]
    d = evaluate_window(
        mentions,
        key="PEPE",
        min_mentions=5,
        min_positive_ratio=0.7,
        last_alert_at="2026-07-20T12:00:00+00:00",
        now=datetime(2026, 7, 20, 12, 10, tzinfo=timezone.utc),
        cooldown_minutes=30,
    )
    assert d.should_alert is False
    assert d.reason == "cooldown"
