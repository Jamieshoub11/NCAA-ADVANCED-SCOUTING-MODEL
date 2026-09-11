"""Phase-4-style opposing-hitter advance scouting: performance vs. pitcher
handedness, vs. pitch type, vs. velocity band, approach by count, and
evidence-gated vulnerability labels — built entirely from pitch-level data.

Same honesty rule as pitcher_advance.py: this does NOT compute Chase%, damage
zones, or pull/center/oppo direction. Chase% and zone-based damage both
require a plate-location field in feet, which this data source doesn't
reliably provide (see docs/data_dictionary_pitcher_export.md); pull/center/
oppo requires a spray-angle/batted-ball-direction field that isn't present
either. Rather than guess, those sections report N/A with the reason.
"""

from __future__ import annotations

import pandas as pd

from . import pitch_outcomes as po
from .confidence import HIGH, MODERATE, confidence_tier
from .pitcher_advance import SITUATIONS
from .stat_utils import safe_div

VELOCITY_BANDS = [
    ("< 90 mph", lambda v: v < 90),
    ("90-94.9 mph", lambda v: 90 <= v < 95),
    ("95+ mph", lambda v: v >= 95),
]


def prepare_hitter_pitch_data(pitch_level_dfs: list[pd.DataFrame], batter_name: str) -> pd.DataFrame:
    if not pitch_level_dfs:
        return pd.DataFrame()
    combined = pd.concat(pitch_level_dfs, ignore_index=True, sort=False)
    if "batter_name" in combined.columns:
        mask = combined["batter_name"].astype(str).str.lower().str.contains(batter_name.strip().lower(), na=False)
        filtered = combined[mask]
        combined = filtered if not filtered.empty else combined
    if "pitch_type" in combined.columns:
        combined["pitch_type"] = combined["pitch_type"].astype(str).str.strip()
    return combined


def _outcome_stats(group_df: pd.DataFrame) -> dict:
    n_pitches = len(group_df)
    outcomes = group_df["pitch_call"].map(po.classify) if "pitch_call" in group_df.columns else pd.Series(dtype=object)
    is_swing = outcomes.isin(("whiff", "foul", "inplay"))
    is_whiff = outcomes == "whiff"
    is_inplay = outcomes == "inplay"

    n_swings = int(is_swing.sum())
    swing_pct = safe_div(n_swings, n_pitches)
    whiff_pct = safe_div(int(is_whiff.sum()), n_swings) if n_swings else None
    contact_pct = safe_div(n_swings - int(is_whiff.sum()), n_swings) if n_swings else None

    avg_ev, hard_hit_pct, n_batted = None, None, 0
    if "exit_speed" in group_df.columns:
        batted = group_df[is_inplay].copy()
        batted["exit_speed"] = pd.to_numeric(batted["exit_speed"], errors="coerce")
        ev = batted["exit_speed"].dropna()
        ev = ev[ev > 0]
        if not ev.empty:
            avg_ev = float(ev.mean())
            hard_hit_pct = float((ev >= 95.0).mean())
            n_batted = int(ev.shape[0])

    return {
        "n_pitches": n_pitches, "n_swings": n_swings, "swing_pct": swing_pct,
        "whiff_pct": whiff_pct, "contact_pct": contact_pct,
        "avg_ev": avg_ev, "hard_hit_pct": hard_hit_pct, "n_batted": n_batted,
        "confidence": confidence_tier(n_pitches),
    }


def performance_by_group(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    if df.empty or group_col not in df.columns:
        return pd.DataFrame()
    rows = []
    for group_value, group_df in df.groupby(group_col):
        stats = _outcome_stats(group_df)
        stats["group"] = group_value
        rows.append(stats)
    return pd.DataFrame(rows)


def performance_vs_pitcher_hand(df: pd.DataFrame) -> pd.DataFrame:
    return performance_by_group(df, "pitcher_hand")


def performance_vs_pitch_type(df: pd.DataFrame) -> pd.DataFrame:
    return performance_by_group(df, "pitch_type")


def performance_vs_velocity_band(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "rel_speed" not in df.columns:
        return pd.DataFrame()
    df = df.copy()
    df["rel_speed"] = pd.to_numeric(df["rel_speed"], errors="coerce")
    df = df.dropna(subset=["rel_speed"])

    def _band(v):
        for name, predicate in VELOCITY_BANDS:
            if predicate(v):
                return name
        return None

    df["_band"] = df["rel_speed"].map(_band)
    return performance_by_group(df, "_band")


def approach_by_count(df: pd.DataFrame) -> pd.DataFrame:
    return performance_by_group(df, "ball_strike_count")


def approach_by_situation(df: pd.DataFrame) -> pd.DataFrame:
    """Mirrors pitcher_advance.usage_by_situation's overlap-safe design:
    each situation (First Pitch/Even/Pitcher Ahead/Hitter Ahead/Two Strikes)
    is its own independent filter, not a mutually-exclusive partition."""
    if df.empty or "ball_strike_count" not in df.columns:
        return pd.DataFrame()
    frames = []
    for situation_name, counts in SITUATIONS.items():
        subset = df[df["ball_strike_count"].isin(counts)]
        if subset.empty:
            continue
        stats = _outcome_stats(subset)
        stats["group"] = situation_name
        frames.append(stats)
    return pd.DataFrame(frames)


def vulnerability_labels(df: pd.DataFrame, benchmarks: dict) -> list[dict]:
    """Evidence-gated approach/vulnerability labels. Every label requires
    MODERATE+ confidence on its backing sample; weak evidence produces no
    label at all rather than a forced one, per the explicit "do not force a
    label when the evidence is weak" instruction.
    """
    labels = []
    if df.empty:
        return labels

    hb = benchmarks.get("hitting", {})

    # First-pitch aggressiveness
    first_pitch = df[df["ball_strike_count"] == "0-0"] if "ball_strike_count" in df.columns else pd.DataFrame()
    if not first_pitch.empty:
        stats = _outcome_stats(first_pitch)
        if confidence_tier(stats["n_pitches"]) in (MODERATE, HIGH) and stats["swing_pct"] is not None:
            if stats["swing_pct"] >= 0.50:
                labels.append({"label": "Aggressive early", "evidence": f"Swings at {stats['swing_pct']*100:.0f}% of first pitches (N={stats['n_pitches']}).", "confidence": confidence_tier(stats["n_pitches"])})
            elif stats["swing_pct"] <= 0.25:
                labels.append({"label": "Patient early", "evidence": f"Swings at only {stats['swing_pct']*100:.0f}% of first pitches (N={stats['n_pitches']}).", "confidence": confidence_tier(stats["n_pitches"])})

    # Overall contact/whiff profile vs. D1 benchmark
    overall = _outcome_stats(df)
    whiff_bm = hb.get("whiff_pct", {})
    if confidence_tier(overall["n_swings"]) in (MODERATE, HIGH) and overall["whiff_pct"] is not None and whiff_bm:
        if overall["whiff_pct"] <= whiff_bm["mean"] - whiff_bm["sd"]:
            labels.append({"label": "High-contact", "evidence": f"Whiff% {overall['whiff_pct']*100:.1f}% vs. D1 avg approx. {whiff_bm['mean']*100:.0f}% (N={overall['n_swings']} swings).", "confidence": confidence_tier(overall["n_swings"])})
        elif overall["whiff_pct"] >= whiff_bm["mean"] + whiff_bm["sd"]:
            labels.append({"label": "Chase-the-whiff / low-contact", "evidence": f"Whiff% {overall['whiff_pct']*100:.1f}% vs. D1 avg approx. {whiff_bm['mean']*100:.0f}% (N={overall['n_swings']} swings).", "confidence": confidence_tier(overall["n_swings"])})

    # Power orientation vs. D1 benchmark
    hh_bm = hb.get("hard_hit_pct", {})
    if overall["n_batted"] and confidence_tier(overall["n_batted"]) in (MODERATE, HIGH) and overall["hard_hit_pct"] is not None and hh_bm:
        if overall["hard_hit_pct"] >= hh_bm["mean"] + hh_bm["sd"]:
            labels.append({"label": "Power-oriented", "evidence": f"Hard-Hit% {overall['hard_hit_pct']*100:.1f}% vs. D1 avg approx. {hh_bm['mean']*100:.0f}% (N={overall['n_batted']} batted balls).", "confidence": confidence_tier(overall["n_batted"])})

    # Pitch-type vulnerability: any pitch type with materially higher whiff% than his overall rate
    by_type = performance_vs_pitch_type(df)
    if not by_type.empty and overall["whiff_pct"] is not None:
        for _, row in by_type.iterrows():
            if row["confidence"] not in (MODERATE, HIGH) or row["whiff_pct"] is None:
                continue
            if row["whiff_pct"] >= overall["whiff_pct"] + 0.15:
                labels.append({
                    "label": f"Vulnerable to {row['group']}",
                    "evidence": f"{row['whiff_pct']*100:.0f}% whiff vs. {row['group']} against his own {overall['whiff_pct']*100:.0f}% overall whiff rate (N={row['n_swings']} swings).",
                    "confidence": row["confidence"],
                })

    # Velocity sensitivity
    by_velo = performance_vs_velocity_band(df)
    if not by_velo.empty and len(by_velo) > 1 and overall["whiff_pct"] is not None:
        by_velo_sorted = by_velo.sort_values("whiff_pct", ascending=False)
        top = by_velo_sorted.iloc[0]
        if top["confidence"] in (MODERATE, HIGH) and top["whiff_pct"] is not None and top["whiff_pct"] >= overall["whiff_pct"] + 0.15:
            labels.append({
                "label": f"Struggles vs. {top['group']}",
                "evidence": f"{top['whiff_pct']*100:.0f}% whiff rate at {top['group']} (N={top['n_swings']} swings) vs. {overall['whiff_pct']*100:.0f}% overall.",
                "confidence": top["confidence"],
            })

    labels.append({
        "label": "Chase tendency, damage zones, pull/oppo direction: N/A — Insufficient Data",
        "evidence": "These require plate-location and/or batted-ball-direction fields not present in this data source (see docs/data_dictionary_pitcher_export.md).",
        "confidence": None,
    })

    return labels
