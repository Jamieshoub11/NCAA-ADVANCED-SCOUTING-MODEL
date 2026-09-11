"""Hitting metrics: traditional slash line, advanced (wOBA/wRC+/ISO/BABIP),
and contact-quality / swing-decision metrics pulled from pitch-level data.

All functions return plain dicts of canonical-stat-name -> float | None.
`None` means "couldn't be computed from what was provided" — never fabricated.
"""

from __future__ import annotations

import pandas as pd

from .stat_utils import safe_div

COUNTING_FIELDS = ["pa", "ab", "h", "b1", "b2", "b3", "hr", "bb", "ibb", "hbp", "so", "sf", "sh"]


def aggregate_counts(boxscore_dfs: list[pd.DataFrame]) -> dict:
    """Sum counting stats across one or more box-score/TruMedia aggregate CSVs."""
    counts = {f: None for f in COUNTING_FIELDS}
    if not boxscore_dfs:
        return counts

    combined = pd.concat(boxscore_dfs, ignore_index=True, sort=False)
    for f in COUNTING_FIELDS:
        if f in combined.columns:
            total = pd.to_numeric(combined[f], errors="coerce").sum(skipna=True)
            counts[f] = float(total) if pd.notna(total) else None

    # Derive singles if we have hits + extra-base breakdown but no explicit 1B column.
    if counts["b1"] is None and counts["h"] is not None:
        b2 = counts["b2"] or 0
        b3 = counts["b3"] or 0
        hr = counts["hr"] or 0
        if counts["b2"] is not None or counts["b3"] is not None or counts["hr"] is not None:
            counts["b1"] = counts["h"] - b2 - b3 - hr

    # Derive PA if missing but AB/BB/HBP/SF/SH present.
    if counts["pa"] is None and counts["ab"] is not None:
        counts["pa"] = sum(counts[f] or 0 for f in ("ab", "bb", "hbp", "sf", "sh"))

    return counts


def slash_line(counts: dict) -> dict:
    ab, h = counts.get("ab"), counts.get("h")
    bb, hbp, sf = counts.get("bb"), counts.get("hbp"), counts.get("sf")
    b1, b2, b3, hr = counts.get("b1"), counts.get("b2"), counts.get("b3"), counts.get("hr")

    avg = safe_div(h, ab)

    obp_num = None
    if h is not None:
        obp_num = h + (bb or 0) + (hbp or 0)
    obp_den = None
    if ab is not None:
        obp_den = ab + (bb or 0) + (hbp or 0) + (sf or 0)
    obp = safe_div(obp_num, obp_den)

    tb = None
    if None not in (b1, b2, b3, hr):
        tb = b1 + 2 * b2 + 3 * b3 + 4 * hr
    slg = safe_div(tb, ab)

    ops = None if (obp is None or slg is None) else obp + slg
    iso = None if (slg is None or avg is None) else slg - avg

    babip_num = None if (h is None or hr is None) else h - hr
    babip_den = None
    if None not in (ab, counts.get("so"), hr):
        babip_den = ab - counts["so"] - hr + (sf or 0)
    babip = safe_div(babip_num, babip_den)

    k_pct = safe_div(counts.get("so"), counts.get("pa"))
    bb_pct = safe_div(bb, counts.get("pa"))

    return {
        "avg": avg, "obp": obp, "slg": slg, "ops": ops, "iso": iso, "babip": babip,
        "k_pct": k_pct, "bb_pct": bb_pct, "pa": counts.get("pa"), "ab": ab,
    }


def woba(counts: dict, weights: dict) -> float | None:
    bb, hbp = counts.get("bb"), counts.get("hbp")
    b1, b2, b3, hr = counts.get("b1"), counts.get("b2"), counts.get("b3"), counts.get("hr")
    ab, sf = counts.get("ab"), counts.get("sf")
    ibb = counts.get("ibb") or 0

    if None in (bb, hbp, b1, b2, b3, hr, ab):
        return None

    uibb = bb - ibb
    numerator = (
        weights["bb"] * uibb + weights["hbp"] * hbp + weights["b1"] * b1
        + weights["b2"] * b2 + weights["b3"] * b3 + weights["hr"] * hr
    )
    denominator = ab + bb + (sf or 0) + hbp
    return safe_div(numerator, denominator)


def wrc_plus(woba_value: float | None, pa: float | None, benchmarks: dict) -> float | None:
    """Simplified wRC+ using generic D1-approximate league constants from
    config/benchmarks.yaml (lg_woba, woba_scale, lg_r_pa). Update those constants
    with real conference averages for a more precise number — this is a
    context-setting estimate, not a certified league-relative figure.
    """
    if woba_value is None or pa is None or pa <= 0:
        return None
    lg_woba = benchmarks["lg_woba"]
    woba_scale = benchmarks["woba_scale"]
    lg_r_pa = benchmarks["lg_r_pa"]

    wraa_per_pa = (woba_value - lg_woba) / woba_scale
    return round((wraa_per_pa + lg_r_pa) / lg_r_pa * 100, 0)


def _filter_to_player(df: pd.DataFrame, player_name: str) -> pd.DataFrame:
    if "batter_name" not in df.columns:
        return df
    mask = df["batter_name"].astype(str).str.lower().str.contains(player_name.strip().lower(), na=False)
    filtered = df[mask]
    return filtered if not filtered.empty else df


def contact_quality(pitch_level_dfs: list[pd.DataFrame], player_name: str, benchmarks: dict) -> dict:
    out = {"max_ev": None, "avg_ev": None, "hard_hit_pct": None, "batted_ball_n": 0}
    if not pitch_level_dfs:
        return out

    combined = pd.concat([_filter_to_player(df, player_name) for df in pitch_level_dfs], ignore_index=True, sort=False)
    if "exit_speed" not in combined.columns:
        return out

    ev = pd.to_numeric(combined["exit_speed"], errors="coerce").dropna()
    ev = ev[ev > 0]
    if ev.empty:
        return out

    hb = benchmarks["hitting"] if "hitting" in benchmarks else benchmarks
    threshold = hb.get("hard_hit_threshold_mph", 95.0)
    out["max_ev"] = float(ev.max())
    out["avg_ev"] = float(ev.mean())
    out["hard_hit_pct"] = float((ev >= threshold).mean())
    out["batted_ball_n"] = int(ev.shape[0])
    return out


_SWING_CALLS = {"strikeswinging", "foulball", "inplay", "foul", "swinging"}
_WHIFF_CALLS = {"strikeswinging", "swinging"}
_INPLAY_CALLS = {"inplay"}


def _in_zone(row, sz: dict) -> bool | None:
    side, height = row.get("plate_loc_side"), row.get("plate_loc_height")
    if pd.isna(side) or pd.isna(height):
        return None
    return (sz["side_min"] <= side <= sz["side_max"]) and (sz["height_min"] <= height <= sz["height_max"])


def swing_discipline(pitch_level_dfs: list[pd.DataFrame], player_name: str, benchmarks: dict) -> dict:
    out = {"whiff_pct": None, "chase_pct": None, "zone_whiff_pct": None, "zone_pct": None, "pitch_n": 0}
    if not pitch_level_dfs:
        return out

    combined = pd.concat([_filter_to_player(df, player_name) for df in pitch_level_dfs], ignore_index=True, sort=False)
    if "pitch_call" not in combined.columns:
        return out

    combined = combined.copy()
    combined["pitch_call_norm"] = combined["pitch_call"].astype(str).str.lower().str.replace(r"[^a-z]", "", regex=True)
    sz = benchmarks["strike_zone"] if "strike_zone" in benchmarks else benchmarks
    combined["in_zone"] = combined.apply(lambda r: _in_zone(r, sz), axis=1)

    has_loc = combined["in_zone"].notna()
    n_pitches = int(has_loc.sum())
    out["pitch_n"] = n_pitches
    if n_pitches == 0:
        return out

    located = combined[has_loc]
    is_swing = located["pitch_call_norm"].isin(_SWING_CALLS)
    is_whiff = located["pitch_call_norm"].isin(_WHIFF_CALLS)

    out["zone_pct"] = float(located["in_zone"].mean())

    out["whiff_pct"] = safe_div(int(is_whiff.sum()), int(is_swing.sum())) if is_swing.sum() > 0 else None

    out_of_zone = located[~located["in_zone"]]
    if not out_of_zone.empty:
        chase_swings = out_of_zone["pitch_call_norm"].isin(_SWING_CALLS).sum()
        out["chase_pct"] = safe_div(int(chase_swings), out_of_zone.shape[0])

    in_zone_df = located[located["in_zone"]]
    if not in_zone_df.empty:
        zone_swings = in_zone_df["pitch_call_norm"].isin(_SWING_CALLS)
        zone_whiffs = in_zone_df["pitch_call_norm"].isin(_WHIFF_CALLS)
        out["zone_whiff_pct"] = safe_div(int(zone_whiffs.sum()), int(zone_swings.sum())) if zone_swings.sum() > 0 else None

    return out


def _zone_label(side: float, height: float, sz: dict) -> str:
    side_span = (sz["side_max"] - sz["side_min"]) / 3
    height_span = (sz["height_max"] - sz["height_min"]) / 3
    if side < sz["side_min"] + side_span:
        side_band = "left third"
    elif side > sz["side_max"] - side_span:
        side_band = "right third"
    else:
        side_band = "middle third"
    if height < sz["height_min"] + height_span:
        height_band = "lower third"
    elif height > sz["height_max"] - height_span:
        height_band = "upper third"
    else:
        height_band = "middle third"
    return f"{height_band}, {side_band} (catcher's view)"


def zonal_profile(pitch_level_dfs: list[pd.DataFrame], player_name: str, benchmarks: dict, min_n: int = 3) -> dict:
    """Damage zone (highest avg exit velo on balls in play) and weakness zone
    (highest whiff rate on swings), bucketed into a 3x3 zone grid. Requires
    plate location on every row; returns None for either side if there isn't
    enough located data to support a claim.
    """
    out = {"damage_zone": None, "weakness_zone": None}
    if not pitch_level_dfs:
        return out
    combined = pd.concat([_filter_to_player(df, player_name) for df in pitch_level_dfs], ignore_index=True, sort=False)
    if not {"plate_loc_side", "plate_loc_height"} <= set(combined.columns):
        return out

    sz = benchmarks["strike_zone"] if "strike_zone" in benchmarks else benchmarks
    combined = combined.dropna(subset=["plate_loc_side", "plate_loc_height"]).copy()
    if combined.empty:
        return out
    combined["zone_label"] = combined.apply(lambda r: _zone_label(r["plate_loc_side"], r["plate_loc_height"], sz), axis=1)

    if "exit_speed" in combined.columns and "pitch_call" in combined.columns:
        calls = combined["pitch_call"].astype(str).str.lower().str.replace(r"[^a-z]", "", regex=True)
        inplay = combined[calls.isin(_INPLAY_CALLS)].copy()
        inplay["exit_speed"] = pd.to_numeric(inplay["exit_speed"], errors="coerce")
        inplay = inplay.dropna(subset=["exit_speed"])
        if not inplay.empty:
            grp = inplay.groupby("zone_label")["exit_speed"].agg(["mean", "count"])
            grp = grp[grp["count"] >= min_n]
            if not grp.empty:
                best = grp["mean"].idxmax()
                out["damage_zone"] = f"{best} — avg EV {grp.loc[best, 'mean']:.1f} mph on {int(grp.loc[best, 'count'])} batted balls"

    if "pitch_call" in combined.columns:
        calls = combined["pitch_call"].astype(str).str.lower().str.replace(r"[^a-z]", "", regex=True)
        combined["is_swing"] = calls.isin(_SWING_CALLS)
        combined["is_whiff"] = calls.isin(_WHIFF_CALLS)
        swings = combined[combined["is_swing"]]
        if not swings.empty:
            grp = swings.groupby("zone_label").agg(swings=("is_swing", "sum"), whiffs=("is_whiff", "sum"))
            grp = grp[grp["swings"] >= min_n]
            if not grp.empty:
                grp["whiff_rate"] = grp["whiffs"] / grp["swings"]
                worst = grp["whiff_rate"].idxmax()
                out["weakness_zone"] = f"{worst} — {grp.loc[worst, 'whiff_rate'] * 100:.1f}% whiff rate on {int(grp.loc[worst, 'swings'])} swings"

    return out


def build_hitter_profile(counts: dict, contact: dict, discipline: dict, benchmarks: dict) -> dict:
    hb = benchmarks["hitting"] if "hitting" in benchmarks else benchmarks
    line = slash_line(counts)
    woba_val = woba(counts, hb["linear_weights"])
    wrc = wrc_plus(woba_val, line.get("pa"), hb)
    profile = {**line, "woba": woba_val, "wrc_plus": wrc, **contact, **discipline}
    return profile
