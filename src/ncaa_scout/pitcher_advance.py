"""Phase-3-style pitcher advance scouting: usage by count, batter-handedness
splits, sequencing, two-strike tendencies, and evidence-backed "How to Attack"
findings — built entirely from pitch-level data (one row per pitch).

Deliberately does NOT attempt Zone%/Edge%/Chase%/location heatmaps: this
pitcher's Movement.csv export has no plate-location field that fits a
TrackMan-style feet-based strike zone (see docs/data_dictionary_pitcher_export.md).
Rather than guess at a coordinate system and risk confidently-wrong zone
numbers, every location-dependent metric here stays absent until a real
location source is available.

Every situational/count/handedness cut is defined using TruMedia's own count
groupings (visible in its SplitBy Count export) rather than an invented
scheme: Even = {0-0, 1-1, 3-2}, Pitcher-ahead = {0-1, 0-2, 1-2, 2-2},
Hitter-ahead (pitcher behind) = {2-0, 3-0, 2-1, 3-1, 1-0}.
"""

from __future__ import annotations

import pandas as pd

from . import pitch_outcomes as po
from .confidence import HIGH, MODERATE, confidence_tier
from .stat_utils import safe_div

FIRST_PITCH_COUNTS = {"0-0"}
EVEN_COUNTS = {"0-0", "1-1", "3-2"}
PITCHER_AHEAD_COUNTS = {"0-1", "0-2", "1-2", "2-2"}
HITTER_AHEAD_COUNTS = {"2-0", "3-0", "2-1", "3-1", "1-0"}
TWO_STRIKE_COUNTS = {"0-2", "1-2", "2-2", "3-2"}

SITUATIONS = {
    "First Pitch": FIRST_PITCH_COUNTS,
    "Even": EVEN_COUNTS,
    "Pitcher Ahead": PITCHER_AHEAD_COUNTS,
    "Hitter Ahead": HITTER_AHEAD_COUNTS,
    "Two Strikes": TWO_STRIKE_COUNTS,
}


def prepare_pitch_data(pitch_level_dfs: list[pd.DataFrame], pitcher_name: str) -> pd.DataFrame:
    if not pitch_level_dfs:
        return pd.DataFrame()
    combined = pd.concat(pitch_level_dfs, ignore_index=True, sort=False)
    if "pitcher_name" in combined.columns:
        mask = combined["pitcher_name"].astype(str).str.lower().str.contains(pitcher_name.strip().lower(), na=False)
        filtered = combined[mask]
        combined = filtered if not filtered.empty else combined
    if "pitch_type" in combined.columns:
        combined["pitch_type"] = combined["pitch_type"].astype(str).str.strip()
    return combined


def usage_table(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """Pitch-type usage % within each value of group_col, with N and a
    confidence tier per group. Returns empty if the grouping column or
    pitch_type isn't present."""
    if df.empty or group_col not in df.columns or "pitch_type" not in df.columns:
        return pd.DataFrame()
    rows = []
    for group_value, group_df in df.groupby(group_col):
        n_total = len(group_df)
        counts = group_df["pitch_type"].value_counts()
        for pitch_type, n_pitch in counts.items():
            rows.append({
                "group": group_value, "pitch_type": pitch_type,
                "n_pitch": int(n_pitch), "n_group": int(n_total),
                "usage_pct": n_pitch / n_total,
                "confidence": confidence_tier(int(n_total)),
            })
    return pd.DataFrame(rows)


def usage_by_count(df: pd.DataFrame) -> pd.DataFrame:
    return usage_table(df, "ball_strike_count")


def usage_by_handedness(df: pd.DataFrame) -> pd.DataFrame:
    return usage_table(df, "batter_hand")


def usage_by_situation(df: pd.DataFrame) -> pd.DataFrame:
    """Usage % within each situation bucket. Buckets overlap by design (a 0-2
    count is both "Pitcher Ahead" and "Two Strikes") so each is computed as
    its own independent filter rather than a mutually-exclusive partition —
    a pitch can and should show up in more than one bucket's table.
    """
    if df.empty or "ball_strike_count" not in df.columns:
        return pd.DataFrame()

    frames = []
    for situation_name, counts in SITUATIONS.items():
        subset = df[df["ball_strike_count"].isin(counts)].copy()
        if subset.empty:
            continue
        subset["situation"] = situation_name
        table = usage_table(subset, "situation")
        if not table.empty:
            frames.append(table)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def whiff_pct_by_group(df: pd.DataFrame, group_cols: list[str], min_swings: int = 1) -> pd.DataFrame:
    """Whiff% (of swings) for each combination of group_cols x pitch_type."""
    if df.empty or "pitch_call" not in df.columns or "pitch_type" not in df.columns:
        return pd.DataFrame()
    if not all(c in df.columns for c in group_cols):
        return pd.DataFrame()
    df = df.copy()
    df["_outcome"] = df["pitch_call"].map(po.classify)
    df["_is_swing"] = df["_outcome"].isin(("whiff", "foul", "inplay"))
    df["_is_whiff"] = df["_outcome"] == "whiff"

    rows = []
    for keys, group_df in df.groupby(group_cols + ["pitch_type"]):
        swings = int(group_df["_is_swing"].sum())
        if swings < min_swings:
            continue
        whiffs = int(group_df["_is_whiff"].sum())
        row = dict(zip(group_cols, keys if isinstance(keys, tuple) else (keys,)))
        row["pitch_type"] = keys[-1] if isinstance(keys, tuple) else keys
        row["n_swings"] = swings
        row["whiff_pct"] = safe_div(whiffs, swings)
        row["confidence"] = confidence_tier(swings)
        rows.append(row)
    return pd.DataFrame(rows)


def sequencing_transitions(df: pd.DataFrame) -> pd.DataFrame:
    """Previous-pitch-type -> next-pitch-type transition table within each
    at-bat (ordered by ab_num_in_game, pitch_num_in_ab). Requires those two
    columns plus pitch_type; returns empty otherwise."""
    required = {"ab_num_in_game", "pitch_num_in_ab", "pitch_type"}
    if df.empty or not required <= set(df.columns):
        return pd.DataFrame()

    sort_cols = ["ab_num_in_game", "pitch_num_in_ab"]
    if "game_id" in df.columns:
        sort_cols = ["game_id"] + sort_cols
    ordered = df.sort_values(sort_cols).copy()

    group_key = ["game_id", "ab_num_in_game"] if "game_id" in ordered.columns else ["ab_num_in_game"]
    ordered["_prev_pitch"] = ordered.groupby(group_key)["pitch_type"].shift(1)
    transitions = ordered.dropna(subset=["_prev_pitch"])

    rows = []
    for prev_type, group_df in transitions.groupby("_prev_pitch"):
        n_total = len(group_df)
        for next_type, n_next in group_df["pitch_type"].value_counts().items():
            rows.append({
                "prev_pitch": prev_type, "next_pitch": next_type,
                "n": int(n_next), "n_prev_total": int(n_total),
                "prob": n_next / n_total,
                "confidence": confidence_tier(int(n_total)),
            })
    return pd.DataFrame(rows)


def outcome_to_next_pitch(df: pd.DataFrame) -> pd.DataFrame:
    """What he throws after a whiff / foul / ball / called strike (Phase 10)."""
    required = {"ab_num_in_game", "pitch_num_in_ab", "pitch_type", "pitch_call"}
    if df.empty or not required <= set(df.columns):
        return pd.DataFrame()

    sort_cols = ["ab_num_in_game", "pitch_num_in_ab"]
    if "game_id" in df.columns:
        sort_cols = ["game_id"] + sort_cols
    ordered = df.sort_values(sort_cols).copy()
    ordered["_outcome"] = ordered["pitch_call"].map(po.classify)

    group_key = ["game_id", "ab_num_in_game"] if "game_id" in ordered.columns else ["ab_num_in_game"]
    ordered["_prev_outcome"] = ordered.groupby(group_key)["_outcome"].shift(1)
    transitions = ordered.dropna(subset=["_prev_outcome"])
    transitions = transitions[transitions["_prev_outcome"] != "unknown"]

    rows = []
    for prev_outcome, group_df in transitions.groupby("_prev_outcome"):
        n_total = len(group_df)
        for next_type, n_next in group_df["pitch_type"].value_counts().items():
            rows.append({
                "prev_outcome": prev_outcome, "next_pitch": next_type,
                "n": int(n_next), "n_prev_total": int(n_total),
                "prob": n_next / n_total,
                "confidence": confidence_tier(int(n_total)),
            })
    return pd.DataFrame(rows)


def build_attack_findings(df: pd.DataFrame, zone_info: dict | None = None, benchmarks: dict | None = None) -> list[dict]:
    """Evidence-backed 'How to Attack' findings. Every finding requires at
    least MODERATE confidence (N>=30) on the group it's drawn from — a
    tendency isn't reported as actionable unless the sample backs it. Purely
    descriptive tables (usage_by_count, etc.) are separate and can be shown
    at any confidence tier with their N visible; this function is only for
    the "act on this" recommendations, which are held to a higher bar.

    zone_info (optional): the dict returned by metrics_pitching.pitch_arsenal
    (zone_pct/edge_pct/chase_pct/zone_calibration) — when supplied and backed
    by adequate confidence, adds a command/control-based finding.
    """
    findings = []
    if df.empty or "pitch_type" not in df.columns:
        return findings

    if zone_info and benchmarks and zone_info.get("zone_pct") is not None:
        pitch_n = zone_info.get("pitch_n", 0)
        if confidence_tier(pitch_n) in (MODERATE, HIGH):
            pb = benchmarks.get("pitching", {})
            zone_bm = pb.get("zone_pct", {})
            chase_bm = pb.get("chase_pct", {})
            zone_pct, chase_pct = zone_info["zone_pct"], zone_info["chase_pct"]
            if zone_bm and zone_pct <= zone_bm["mean"] - zone_bm["sd"]:
                findings.append({
                    "finding": "Works out of the zone more than a typical D1 arm — living on the edges/expanded, not pounding the zone.",
                    "evidence": f"Zone% {zone_pct * 100:.0f}% vs. D1 avg approx. {zone_bm['mean']*100:.0f}% (N={pitch_n} pitches).",
                    "confidence": confidence_tier(pitch_n),
                })
            if chase_bm and chase_pct is not None and chase_pct >= chase_bm["mean"] + chase_bm["sd"]:
                findings.append({
                    "finding": "Generates chases at an above-average rate — hitters are expanding the zone against him.",
                    "evidence": f"Chase% {chase_pct * 100:.0f}% vs. D1 avg approx. {chase_bm['mean']*100:.0f}% (N={pitch_n} pitches).",
                    "confidence": confidence_tier(pitch_n),
                })

    overall_usage = df["pitch_type"].value_counts(normalize=True)

    situations = usage_by_situation(df)
    if not situations.empty:
        for situation_name, threshold in (("First Pitch", 0.45), ("Two Strikes", 0.40), ("Hitter Ahead", 0.45)):
            subset = situations[situations["group"] == situation_name]
            if subset.empty:
                continue
            top = subset.sort_values("usage_pct", ascending=False).iloc[0]
            if top["usage_pct"] >= threshold and confidence_tier(int(top["n_group"])) in (MODERATE, HIGH):
                verb = {"First Pitch": "Establishes early with", "Two Strikes": "Primary two-strike weapon is",
                        "Hitter Ahead": "Leans on"}[situation_name]
                suffix = " when behind in the count" if situation_name == "Hitter Ahead" else ""
                findings.append({
                    "finding": f"{verb} {top['pitch_type']}{suffix}.",
                    "evidence": f"{top['pitch_type']} thrown {top['usage_pct'] * 100:.0f}% of the time in {situation_name} counts (N={int(top['n_group'])}).",
                    "confidence": confidence_tier(int(top["n_group"])),
                })

    seq = sequencing_transitions(df)
    if not seq.empty:
        most_used_pitch = overall_usage.index[0] if len(overall_usage) else None
        if most_used_pitch is not None:
            from_most_used = seq[(seq["prev_pitch"] == most_used_pitch) & (seq["next_pitch"] != most_used_pitch)]
            if not from_most_used.empty:
                top = from_most_used.sort_values("prob", ascending=False).iloc[0]
                if top["prob"] >= 0.30 and confidence_tier(int(top["n_prev_total"])) in (MODERATE, HIGH):
                    findings.append({
                        "finding": f"After a {most_used_pitch}, turns to {top['next_pitch']} more than any other follow-up.",
                        "evidence": f"{top['prob'] * 100:.0f}% of pitches following a {most_used_pitch} are {top['next_pitch']} (N={int(top['n_prev_total'])} {most_used_pitch}s thrown non-last-in-AB).",
                        "confidence": confidence_tier(int(top["n_prev_total"])),
                    })

    whiffs = whiff_pct_by_group(df, [], min_swings=10)
    if not whiffs.empty:
        best = whiffs.sort_values("whiff_pct", ascending=False).iloc[0]
        if confidence_tier(int(best["n_swings"])) in (MODERATE, HIGH):
            findings.append({
                "finding": f"Best swing-and-miss weapon is the {best['pitch_type']}.",
                "evidence": f"{best['whiff_pct'] * 100:.0f}% whiff rate on {int(best['n_swings'])} swings against it.",
                "confidence": confidence_tier(int(best["n_swings"])),
            })

    if "batter_hand" in df.columns:
        by_hand = usage_by_handedness(df)
        if not by_hand.empty:
            pivot = by_hand.pivot_table(index="pitch_type", columns="group", values="usage_pct", fill_value=0)
            n_by_hand = by_hand.groupby("group")["n_group"].first()
            if {"L", "R"} <= set(pivot.columns) and all(confidence_tier(int(n_by_hand.get(h, 0))) in (MODERATE, HIGH) for h in ("L", "R")):
                gap = (pivot["L"] - pivot["R"]).abs().sort_values(ascending=False)
                if not gap.empty and gap.iloc[0] >= 0.15:
                    pitch = gap.index[0]
                    l_pct, r_pct = pivot.loc[pitch, "L"], pivot.loc[pitch, "R"]
                    more_side = "left-handed" if l_pct > r_pct else "right-handed"
                    findings.append({
                        "finding": f"Uses the {pitch} noticeably more against {more_side} hitters.",
                        "evidence": f"{pitch} usage: {l_pct * 100:.0f}% vs LHH (N={int(n_by_hand.get('L', 0))}), {r_pct * 100:.0f}% vs RHH (N={int(n_by_hand.get('R', 0))}).",
                        "confidence": confidence_tier(min(int(n_by_hand.get("L", 0)), int(n_by_hand.get("R", 0)))),
                    })

    return findings
