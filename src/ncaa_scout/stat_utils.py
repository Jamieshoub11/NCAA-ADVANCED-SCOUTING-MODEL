"""Small shared helpers. Missing/uncomputable values are represented as `None`
everywhere in metrics/grading code; only the report-building layer turns `None`
into the "N/A — Insufficient Data" string the report template requires.
"""

from __future__ import annotations

NA_TEXT = "N/A — Insufficient Data"


def _is_missing(value) -> bool:
    """True for None and for NaN. Values built via pd.DataFrame(list_of_dicts)
    silently upcast a column's `None` entries to float NaN whenever any other
    row in that column is a float — so every formatter here must treat NaN
    the same as None, or a missing value prints as the literal text "nan"
    instead of the N/A sentinel.
    """
    if value is None:
        return True
    return isinstance(value, float) and value != value


def safe_div(numerator, denominator):
    if numerator is None or denominator is None:
        return None
    try:
        if denominator == 0:
            return None
        return numerator / denominator
    except (TypeError, ZeroDivisionError):
        return None


def fmt(value, decimals: int = 3, suffix: str = "", na_text: str = NA_TEXT) -> str:
    if _is_missing(value):
        return na_text
    try:
        return f"{value:.{decimals}f}{suffix}"
    except (TypeError, ValueError):
        return na_text


def fmt_pct(value, decimals: int = 1, na_text: str = NA_TEXT) -> str:
    if _is_missing(value):
        return na_text
    try:
        return f"{value * 100:.{decimals}f}%"
    except (TypeError, ValueError):
        return na_text


def fmt_avg(value, na_text: str = NA_TEXT) -> str:
    """Batting-average style formatting: .312 instead of 0.312."""
    if _is_missing(value):
        return na_text
    try:
        s = f"{value:.3f}"
        return s[1:] if s.startswith("0.") else s
    except (TypeError, ValueError):
        return na_text
