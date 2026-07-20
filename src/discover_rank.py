"""Pure ranking for Telegram channel discovery samples."""

from __future__ import annotations

from dataclasses import dataclass

from src.filter import extract_targets


@dataclass(frozen=True)
class ChannelSample:
    username: str
    channel_id: int
    members: int
    messages_per_hour: float
    sample_texts: list[str]


def _clip(value: float) -> float:
    return min(1.0, max(0.0, value))


def rank_channel(sample: ChannelSample) -> tuple[float, str]:
    members = _clip(sample.members / 100_000)
    activity = _clip(sample.messages_per_hour / 60)

    target_samples = 0
    spam_samples = 0
    recent_hashes: set[str] = set()
    for text in sample.sample_texts:
        result = extract_targets(
            text,
            max_cas_per_message=3,
            recent_hashes=recent_hashes,
        )
        recent_hashes.add(result.text_hash)
        target_samples += bool(result.symbols or result.cas)
        repeated_ca_spam = any(text.count(ca) > 3 for ca in result.cas)
        spam_samples += result.is_spam or repeated_ca_spam

    sample_count = len(sample.sample_texts)
    density = target_samples / sample_count if sample_count else 0.0
    spam_fraction = spam_samples / sample_count if sample_count else 0.0

    score = _clip((members + activity + density) / 3 - spam_fraction)
    factors = {
        "members": members / 3,
        "activity": activity / 3,
        "target density": density / 3,
        "spam penalty": spam_fraction,
    }
    top_factor = max(factors, key=factors.get)
    reason = f"top factor: {top_factor} ({factors[top_factor]:.0%})"
    return score, reason
