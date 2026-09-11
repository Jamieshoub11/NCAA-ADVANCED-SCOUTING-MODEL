"""Pitching metrics: fastball architecture, secondary shape, command/control,
and rate stats — pulled from pitch-level TrackMan data and/or box-score CSVs.
"""

from __future__ import annotations

import pandas as pd

from .stat_utils import safe_div

PITCHING_COUNTING_FIELDS = ["bf", "ip", "er", "r", "h", "hr_allowed", "bb", "so"]


def aggregate_pitching_counts(boxscore_dfs: list[pd.DataFrame]) -> dict:
    counts = {f: None for f in PITCHING_COUNTING_FIELDS}
    if not boxscore_dfs:
        return counts

    combined = pd.concat(boxscore_dfs, ignore_index=True, sort=False)
    for f in PITCHING_COUNTING_FIELDS:
        if f in combined.columns:
            total = pd.to_numeric(combined[f], errors="coerce").sum(skipna=True)
            counts[f] = float(total) if pd.notna(total) else None

    if counts["hr_allowed"] is None and "hr" in combined.columns:
        total = pd.to_numeric(combined["hr"], errors="coerce").sum(skipna=True)
        counts["hr_allowed"] = float(total) if pd.notna(total) else None

    return counts


def pitching_rate_stats(counts: dict) -> dict:
    bf = counts.get("bf")
    k_pct = safe_div(counts.get("so"), bf)
    bb_pct = safe_div(counts.get("bb"), bf)
    k_bb_ratio = safe_div(counts.get("so"), counts.get("bb"))
    whip = None
    if counts.get("ip") not in (None, 0) and counts.get("h") is not None and counts.get("bb") is not None:
        whip = safe_div(counts["h"] + counts["bb"], counts["ip"])
    era = None
    if counts.get("ip") not in (None, 0) and counts.get("er") is not None:
        era = safe_div(counts["er"] * 9, counts["ip"])
    return {"k_pct": k_pct, "bb_pct": bb_pct, "k_bb_ratio": k_bb_ratio, "whip": whip, "era": era, "bf": bf, "ip": counts.get("ip")}


def _filter_to_pitcher(df: pd.DataFrame, pitcher_name: str) -> pd.DataFrame:
    if "pitcher_name" not in df.columns:
        return df
    mask = df["pitcher_name"].astype(str).str.lower().str.contains(pitcher_name.strip().lower(), na=False)
    filtered = df[mask]
    return filtered if not filtered.empty else df


def _in_zone(row, sz: dict) -> bool | None:
    side, height = row.get("plate_loc_side"), row.get("plate_loc_height")
    if pd.isna(side) or pd.isna(height):
        return None
    return (sz["side_min"] <= side <= sz["side_max"]) and (sz["height_min"] <= height <= sz["height_max"])


def _is_edge(row, sz: dict) -> bool | None:
    side, height = row.get("plate_loc_side"), row.get("plate_loc_height")
    if pd.isna(side) or pd.isna(height):
        return None
    band = sz.get("edge_band", 0.25)
    in_outer = (sz["side_min"] - band <= side <= sz["side_max"] + band) and (
        sz["height_min"] - band <= height <= sz["height_max"] + band
    )
    in_inner = (sz["side_min"] + band <= side <= sz["side_max"] - band) and (
        sz["height_min"] + band <= height <= sz["height_max"] - band
    )
    return in_outer and not in_inner


_SWING_CALLS = {"strikeswinging", "foulball", "inplay", "foul", "swinging"}
_WHIFF_CALLS = {"strikeswinging", "swinging"}


def pitch_arsenal(pitch_level_dfs: list[pd.DataFrame], pitcher_name: str, benchmarks: dict) -> dict:
    """Per-pitch-type velo/movement/release/usage/whiff, plus overall command metrics."""
    result = {"arsenal": {}, "zone_pct": None, "edge_pct": None, "whiff_pct": None, "chase_pct": None, "pitch_n": 0}
    if not pitch_level_dfs:
        return result

    combined = pd.concat([_filter_to_pitcher(df, pitcher_name) for df in pitch_level_dfs], ignore_index=True, sort=False)
    if combined.empty:
        return result

    total_n = combined.shape[0]
    result["pitch_n"] = int(total_n)

    if "pitch_type" in combined.columns:
        grouped = combined.groupby(combined["pitch_type"].astype(str).str.strip())
        arsenal = {}
        for pitch_name, group in grouped:
            entry = {"usage_pct": round(group.shape[0] / total_n, 3) if total_n else None}
            for canon, col in (("velo", "rel_speed"), ("spin_rate", "spin_rate"),
                               ("ivb", "induced_vert_break"), ("hvb", "horz_break"),
                               ("rel_height", "rel_height"), ("rel_side", "rel_side"),
                               ("extension", "extension")):
                if col in group.columns:
                    vals = pd.to_numeric(group[col], errors="coerce").dropna()
                    entry[canon] = float(vals.mean()) if not vals.empty else None
                else:
                    entry[canon] = None
            if "rel_speed" in group.columns:
                vals = pd.to_numeric(group["rel_speed"], errors="coerce").dropna()
                entry["velo_max"] = float(vals.max()) if not vals.empty else None
            else:
                entry["velo_max"] = None

            if "pitch_call" in group.columns:
                calls = group["pitch_call"].astype(str).str.lower().str.replace(r"[^a-z]", "", regex=True)
                swings = calls.isin(_SWING_CALLS)
                whiffs = calls.isin(_WHIFF_CALLS)
                entry["whiff_pct"] = safe_div(int(whiffs.sum()), int(swings.sum())) if swings.sum() > 0 else None
            else:
                entry["whiff_pct"] = None
            arsenal[pitch_name] = entry
        result["arsenal"] = arsenal

    if {"plate_loc_side", "plate_loc_height"} <= set(combined.columns):
        sz = benchmarks["strike_zone"] if "strike_zone" in benchmarks else benchmarks
        combined = combined.copy()
        combined["in_zone"] = combined.apply(lambda r: _in_zone(r, sz), axis=1)
        combined["is_edge"] = combined.apply(lambda r: _is_edge(r, sz), axis=1)
        located = combined[combined["in_zone"].notna()]
        if not located.empty:
            result["zone_pct"] = float(located["in_zone"].mean())
            result["edge_pct"] = float(located["is_edge"].mean())

            if "pitch_call" in located.columns:
                calls = located["pitch_call"].astype(str).str.lower().str.replace(r"[^a-z]", "", regex=True)
                swings = calls.isin(_SWING_CALLS)
                whiffs = calls.isin(_WHIFF_CALLS)
                result["whiff_pct"] = safe_div(int(whiffs.sum()), int(swings.sum())) if swings.sum() > 0 else None

                out_of_zone = located[~located["in_zone"]]
                if not out_of_zone.empty:
                    oz_calls = out_of_zone["pitch_call"].astype(str).str.lower().str.replace(r"[^a-z]", "", regex=True)
                    chase_swings = oz_calls.isin(_SWING_CALLS).sum()
                    result["chase_pct"] = safe_div(int(chase_swings), out_of_zone.shape[0])

    return result


def rank_arsenal_by_usage(arsenal: dict) -> list[tuple[str, dict]]:
    return sorted(arsenal.items(), key=lambda kv: kv[1].get("usage_pct") or 0, reverse=True)


def putaway_pitch(arsenal: dict, min_swings: int = 5) -> str | None:
    best_name, best_whiff = None, -1.0
    for name, entry in arsenal.items():
        whiff = entry.get("whiff_pct")
        if whiff is not None and whiff > best_whiff:
            best_whiff, best_name = whiff, name
    if best_name is None:
        return None
    return f"{best_name} (Whiff% {best_whiff * 100:.1f}%)"


def build_pitcher_profile(counts: dict, arsenal_data: dict, benchmarks: dict) -> dict:
    rates = pitching_rate_stats(counts)
    return {**rates, **arsenal_data}
