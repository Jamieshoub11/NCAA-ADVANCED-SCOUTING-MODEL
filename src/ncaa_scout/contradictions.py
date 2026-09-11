"""Rule-based detector for statistical contradictions — pairs of metrics that,
taken together, don't tell a consistent story and deserve a scouting flag
(per the system mandate to surface these automatically rather than let a
report imply false consistency).
"""

from __future__ import annotations


def _level(value, mean: float, sd: float, lower_is_better: bool = False, band: float = 0.5) -> str | None:
    if value is None or not sd:
        return None
    z = (value - mean) / sd
    if lower_is_better:
        z = -z
    if z >= band:
        return "high"
    if z <= -band:
        return "low"
    return "average"


def detect_hitter_contradictions(profile: dict, benchmarks: dict) -> list[str]:
    hb = benchmarks["hitting"]
    flags = []

    slg_level = _level(profile.get("slg"), hb["slg"]["mean"], hb["slg"]["sd"])
    hh_level = _level(profile.get("hard_hit_pct"), hb["hard_hit_pct"]["mean"], hb["hard_hit_pct"]["sd"])
    if slg_level == "high" and hh_level == "low":
        flags.append(
            "SLG/power output is above D1 average but Hard-Hit% is below average — "
            "power production is outrunning underlying contact quality; treat the power "
            "output as inflated until contact-quality data confirms it (small-sample or "
            "matchup-driven risk)."
        )

    bb_level = _level(profile.get("bb_pct"), hb["bb_pct"]["mean"], hb["bb_pct"]["sd"])
    chase_level = _level(profile.get("chase_pct"), hb["chase_pct"]["mean"], hb["chase_pct"]["sd"])
    if bb_level == "high" and chase_level == "high":
        flags.append(
            "Walk rate is above average despite an above-average chase rate — the walks may "
            "reflect pitchers pitching around him or wildness faced rather than advanced plate "
            "discipline; don't grade the Approach tool up on walk rate alone."
        )

    k_level = _level(profile.get("k_pct"), hb["k_pct"]["mean"], hb["k_pct"]["sd"], lower_is_better=True)
    whiff_level = _level(profile.get("whiff_pct"), hb["whiff_pct"]["mean"], hb["whiff_pct"]["sd"], lower_is_better=True)
    if k_level == "low" and whiff_level == "high":
        flags.append(
            "Strikeout rate is elevated but swing-and-miss rate (Whiff%) is not — strikeouts "
            "look driven by called strikes/approach or count management rather than bat-missing "
            "stuff faced; live look should confirm whether this is a timing or a decision-making issue."
        )

    avg_level = _level(profile.get("avg"), hb["avg"]["mean"], hb["avg"]["sd"])
    babip_level = _level(profile.get("babip"), hb["babip"]["mean"], hb["babip"]["sd"])
    if avg_level == "high" and hh_level in ("low", "average") and babip_level == "high":
        flags.append(
            "Batting average is propped up by a high BABIP without the contact quality (Hard-Hit%) "
            "to sustain it — regression risk on the average going forward."
        )

    pa = profile.get("pa")
    min_pa = benchmarks.get("min_sample", {}).get("pa_for_rate_stats", 40)
    if pa is not None and pa < min_pa:
        flags.append(f"Small sample: {int(pa)} PA is below the {min_pa}-PA threshold for stable rate stats — treat all rates here as provisional.")

    bb_n = profile.get("batted_ball_n", 0)
    min_bb = benchmarks.get("min_sample", {}).get("batted_balls_for_ev", 15)
    if bb_n and bb_n < min_bb:
        flags.append(f"Small sample: only {bb_n} batted balls with exit-velo data — Max EV/Hard-Hit% are not yet stable.")

    return flags


def detect_pitcher_contradictions(profile: dict, benchmarks: dict) -> list[str]:
    pb = benchmarks["pitching"]
    flags = []

    k_level = _level(profile.get("k_pct"), pb["k_pct"]["mean"], pb["k_pct"]["sd"])
    whiff_level = _level(profile.get("whiff_pct"), pb["whiff_pct"]["mean"], pb["whiff_pct"]["sd"])
    if k_level == "low" and whiff_level == "high":
        flags.append(
            "Whiff% is above average but strikeout rate is not — swing-and-miss stuff is present "
            "but not converting to punchouts; check two-strike pitch selection and sequencing."
        )
    if k_level == "high" and whiff_level == "low":
        flags.append(
            "Strikeout rate is above average despite a below-average Whiff% — K's look driven by "
            "called strikes/count leverage rather than swing-and-miss stuff; live look should confirm "
            "whether stuff or sequencing is doing the work."
        )

    bb_level = _level(profile.get("bb_pct"), pb["bb_pct"]["mean"], pb["bb_pct"]["sd"], lower_is_better=True)
    zone_level = _level(profile.get("zone_pct"), pb["zone_pct"]["mean"], pb["zone_pct"]["sd"])
    if bb_level == "high" and zone_level == "high":
        flags.append(
            "Walk rate is above average despite an above-average Zone% — free passes are coming on "
            "pitches in the zone, pointing to a barrel/quality-of-strike issue rather than a pure "
            "control issue."
        )

    pitch_n = profile.get("pitch_n", 0)
    min_pitches = benchmarks.get("min_sample", {}).get("pitches_for_pitch_metrics", 30)
    if pitch_n and pitch_n < min_pitches:
        flags.append(f"Small sample: only {pitch_n} tracked pitches — Zone%/Edge%/Whiff% are not yet stable.")

    bf = profile.get("bf")
    min_pa = benchmarks.get("min_sample", {}).get("pa_for_rate_stats", 40)
    if bf is not None and bf < min_pa:
        flags.append(f"Small sample: {int(bf)} batters faced is below the {min_pa}-BF threshold for stable rate stats.")

    return flags
