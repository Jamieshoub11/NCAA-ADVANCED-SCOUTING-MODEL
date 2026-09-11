"""Sample-size confidence tiers for tendency statistics (Phase 9).

Thresholds are set from the half-width of a normal-approximation 95% CI for a
proportion at its most conservative point (p=0.5, where variance is
maximized: half-width = 1.96 * sqrt(0.25/n)). This gives an honest, derivable
reason for each cutoff rather than a round number picked by feel:

    n=10  -> half-width ~0.31  (a reported 50% could really be anywhere 19-81%: uninformative)
    n=30  -> half-width ~0.18  (50% could really be 32-68%: usable as a lean, not a plan)
    n=75  -> half-width ~0.11  (50% could really be 39-61%: tight enough to act on)

These are deliberately conservative (p=0.5 is the worst case; a tendency near
0% or 100% is more precisely known at the same N) — the tiers under-claim
confidence rather than over-claim it.
"""

from __future__ import annotations

import math

INSUFFICIENT, LOW, MODERATE, HIGH = "INSUFFICIENT SAMPLE", "LOW CONFIDENCE", "MODERATE CONFIDENCE", "HIGH CONFIDENCE"

_THRESHOLDS = (
    (75, HIGH),
    (30, MODERATE),
    (10, LOW),
)


def confidence_tier(n: int) -> str:
    for threshold, label in _THRESHOLDS:
        if n >= threshold:
            return label
    return INSUFFICIENT


def ci_half_width(n: int, p: float = 0.5) -> float | None:
    """95% normal-approximation CI half-width for a proportion — the
    quantitative backing shown alongside every tier label."""
    if n <= 0:
        return None
    return 1.96 * math.sqrt(p * (1 - p) / n)


def with_n(label: str, n: int) -> str:
    return f"{label} (N={n})"
