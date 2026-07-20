"""Extract cashtags / Solana-like CAs and apply spam heuristics."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

CASHTAG_RE = re.compile(r"\$([A-Za-z][A-Za-z0-9]{1,14})\b")
# Base58 alphabet excluding 0,O,I,l — length 32..44
BASE58_RE = re.compile(r"\b([1-9A-HJ-NP-Za-km-z]{32,44})\b")
MIN_ACCOUNT_AGE_DAYS = 7.0


@dataclass(frozen=True)
class FilterResult:
    symbols: list[str]
    cas: list[str]
    is_spam: bool
    spam_reason: str | None
    text_hash: str


def _hash_text(text: str) -> str:
    normalized = " ".join(text.lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def extract_targets(
    text: str,
    *,
    max_cas_per_message: int = 3,
    recent_hashes: set[str] | None = None,
    account_age_days: float | None = None,
) -> FilterResult:
    text_hash = _hash_text(text)
    symbols = sorted({m.group(1).upper() for m in CASHTAG_RE.finditer(text)})
    cas = sorted(set(BASE58_RE.findall(text)))

    if recent_hashes is not None and text_hash in recent_hashes:
        return FilterResult(symbols, cas, True, "duplicate_text", text_hash)
    if len(cas) > max_cas_per_message:
        return FilterResult(symbols, cas, True, "too_many_cas", text_hash)
    if account_age_days is not None and account_age_days < MIN_ACCOUNT_AGE_DAYS:
        return FilterResult(symbols, cas, True, "new_account", text_hash)

    return FilterResult(symbols, cas, False, None, text_hash)
