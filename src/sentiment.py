"""Local VADER sentiment scoring."""

from __future__ import annotations

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_analyzer = SentimentIntensityAnalyzer()


def score_text(text: str, *, positive_threshold: float = 0.05) -> tuple[float, bool]:
    compound = float(_analyzer.polarity_scores(text)["compound"])
    return compound, compound > positive_threshold
