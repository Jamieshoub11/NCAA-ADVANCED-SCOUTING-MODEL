"""Pitching metrics: fastball architecture, secondary shape, command/control,
and rate stats — pulled from pitch-level TrackMan data and/or box-score CSVs.
"""

from __future__ import annotations

import pandas as pd

from . import pitch_outcomes as po
from . import zone_calibration as zc
from .stat_utils import safe_div

PITCHING_COUNTING_FIELDS = ["bf", "ip", "er", "r", "h", "hr_allowed", "bb", "so"]


def _ip_notation_to_outs(ip_value: float) -> int | None:
    """Converts baseball innings notation (4.1 = 4 and 1/3 innings, i.e. 13
    outs — NOT 4.1 decimal innings) to a whole number of outs, so multiple
    appearances can be summed correctly. ".0"/".1"/".2" are the only valid
    fractional parts; anything else is treated as plain decimal innings
    (defensive fallback for a source that doesn't use this notation).
    """
    if ip_value is None:
        return None
    whole = int(ip_value)
    frac_tenths = round((ip_value - whole) * 10)
    if frac_tenths not in (0, 1, 2):
        return round(ip_value * 3)
    return whole * 3 + frac_tenths


def _outs_to_ip_notation(outs: float) -> float:
    whole, remainder = divmod(int(round(outs)), 3)
    return whole + remainder / 10.0


def aggregate_pitching_counts(boxscore_dfs: list[pd.DataFrame]) -> dict:
    """Sums per-appearance pitching counts across one or more game-log CSVs.

    IP is summed via outs (see _ip_notation_to_outs) rather than naive decimal
    addition, since "4.1" means 4 1/3 innings, not 4.1 decimal innings — summing
    it as a plain float silently understates/overstates multi-game totals.
    """
    counts = {f: None for f in PITCHING_COUNTING_FIELDS}
    if not boxscore_dfs:
        return counts

    combined = pd.concat(boxscore_dfs, ignore_index=True, sort=False)
    for f in PITCHING_COUNTING_FIELDS:
        if f == "ip":
            continue
        if f in combined.columns:
            total = pd.to_numeric(combined[f], errors="coerce").sum(skipna=True)
            counts[f] = float(total) if pd.notna(total) else None

    if "ip" in combined.columns:
        ip_values = pd.to_numeric(combined["ip"], errors="coerce").dropna()
        if not ip_values.empty:
            total_outs = sum(_ip_notation_to_outs(v) for v in ip_values)
            counts["ip"] = total_outs / 3.0
            counts["ip_display"] = _outs_to_ip_notation(total_outs)

    if counts["hr_allowed"] is None and "hr" in combined.columns:
        total = pd.to_numeric(combined["hr"], errors="coerce").sum(skipna=True)
        counts["hr_allowed"] = float(total) if pd.notna(total) else None

    return counts


def pitching_rate_stats(counts: dict) -> dict:
    bf = counts.get("bf")
    ip = counts.get("ip")
    k_pct = safe_div(counts.get("so"), bf)
    bb_pct = safe_div(counts.get("bb"), bf)
    k_bb_ratio = safe_div(counts.get("so"), counts.get("bb"))
    k_per9 = safe_div((counts.get("so") or 0) * 9 if counts.get("so") is not None else None, ip)
    bb_per9 = safe_div((counts.get("bb") or 0) * 9 if counts.get("bb") is not None else None, ip)
    whip = None
    if ip not in (None, 0) and counts.get("h") is not None and counts.get("bb") is not None:
        whip = safe_div(counts["h"] + counts["bb"], ip)
    era = None
    if ip not in (None, 0) and counts.get("er") is not None:
        era = safe_div(counts["er"] * 9, ip)
    return {
        "k_pct": k_pct, "bb_pct": bb_pct, "k_bb_ratio": k_bb_ratio,
        "k_per9": k_per9, "bb_per9": bb_per9,
        "whip": whip, "era": era, "bf": bf, "ip": ip,
        "ip_display": counts.get("ip_display", ip),
    }


def _filter_to_pitcher(df: pd.DataFrame, pitcher_name: str) -> pd.DataFrame:
    if "pitcher_name" not in df.columns:
        return df
    mask = df["pitcher_name"].astype(str).str.lower().str.contains(pitcher_name.strip().lower(), na=False)
    filtered = df[mask]
    return filtered if not filtered.empty else df


def pitch_arsenal(pitch_level_dfs: list[pd.DataFrame], pitcher_name: str, benchmarks: dict) -> dict:
    """Per-pitch-type velo/movement/release/usage/whiff, plus overall command metrics."""
    result = {"arsenal": {}, "zone_pct": None, "edge_pct": None, "whiff_pct": None, "chase_pct": None,
              "pitch_n": 0, "zone_calibration": None}
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
                outcomes = group["pitch_call"].map(po.classify)
                swings = outcomes.isin(("whiff", "foul", "inplay"))
                whiffs = outcomes == "whiff"
                entry["whiff_pct"] = safe_div(int(whiffs.sum()), int(swings.sum())) if swings.sum() > 0 else None
            else:
                entry["whiff_pct"] = None
            arsenal[pitch_name] = entry
        result["arsenal"] = arsenal

    in_zone, is_edge, calibration = zc.get_zone_columns(combined, benchmarks)
    if in_zone is not None:
        combined = combined.copy()
        combined["in_zone"] = in_zone
        combined["is_edge"] = is_edge
        result["zone_calibration"] = calibration
        located = combined[combined["in_zone"].notna()]
        if not located.empty:
            result["zone_pct"] = float(located["in_zone"].mean())
            result["edge_pct"] = float(located["is_edge"].mean())

            if "pitch_call" in located.columns:
                outcomes = located["pitch_call"].map(po.classify)
                swings = outcomes.isin(("whiff", "foul", "inplay"))
                whiffs = outcomes == "whiff"
                result["whiff_pct"] = safe_div(int(whiffs.sum()), int(swings.sum())) if swings.sum() > 0 else None

                out_of_zone = located[~located["in_zone"]]
                if not out_of_zone.empty:
                    oz_outcomes = out_of_zone["pitch_call"].map(po.classify)
                    chase_swings = oz_outcomes.isin(("whiff", "foul", "inplay")).sum()
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
