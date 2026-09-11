"""20-80 scouting scale grading.

Each grade is a z-score against the D1 benchmark mean/SD in config/benchmarks.yaml,
mapped onto the classic 20-80 scale (50 = average, +/-10 per standard deviation),
clipped to [20, 80] and rounded to the nearest 5 — matching how traditional scouting
grades are expressed. These benchmarks are approximations (see benchmarks.yaml); the
grade is only as good as the reference numbers, and the report always labels it as
a D1-relative estimate, not a certified number.
"""

from __future__ import annotations

NA = None


def grade_from_value(value, mean: float, sd: float, lower_is_better: bool = False) -> int | None:
    if value is None or sd in (None, 0):
        return None
    z = (value - mean) / sd
    if lower_is_better:
        z = -z
    grade = 50 + z * 10
    grade = max(20, min(80, grade))
    return int(round(grade / 5) * 5)


def _avg_grades(grades: list[int | None]) -> int | None:
    present = [g for g in grades if g is not None]
    if not present:
        return None
    return int(round(sum(present) / len(present) / 5) * 5)


def grade_hitter(profile: dict, benchmarks: dict) -> dict:
    hb = benchmarks["hitting"]

    hit = _avg_grades([
        grade_from_value(profile.get("avg"), hb["avg"]["mean"], hb["avg"]["sd"]),
        grade_from_value(profile.get("whiff_pct"), hb["whiff_pct"]["mean"], hb["whiff_pct"]["sd"], lower_is_better=True),
        grade_from_value(profile.get("k_pct"), hb["k_pct"]["mean"], hb["k_pct"]["sd"], lower_is_better=True),
    ])
    power = _avg_grades([
        grade_from_value(profile.get("iso"), hb["iso"]["mean"], hb["iso"]["sd"]),
        grade_from_value(profile.get("max_ev"), hb["max_ev"]["mean"], hb["max_ev"]["sd"]),
        grade_from_value(profile.get("hard_hit_pct"), hb["hard_hit_pct"]["mean"], hb["hard_hit_pct"]["sd"]),
    ])
    approach = _avg_grades([
        grade_from_value(profile.get("bb_pct"), hb["bb_pct"]["mean"], hb["bb_pct"]["sd"]),
        grade_from_value(profile.get("chase_pct"), hb["chase_pct"]["mean"], hb["chase_pct"]["sd"], lower_is_better=True),
    ])
    speed = None    # not derivable from hitting-side batted-ball/box-score data alone
    defense = None  # out of scope for offensive CSV data — needs Synergy defensive charting
    overall = _avg_grades([hit, power, approach])

    return {"hit": hit, "power": power, "approach": approach, "speed": speed, "defense": defense, "overall": overall}


def grade_pitcher(profile: dict, benchmarks: dict) -> dict:
    pb = benchmarks["pitching"]
    arsenal = profile.get("arsenal", {})

    fb_entry = _find_pitch(arsenal, ["FF", "FB", "FASTBALL", "SINKER", "SI", "TWO-SEAM", "2S"])
    fastball = grade_from_value(fb_entry["velo"], pb["velo_fb"]["mean"], pb["velo_fb"]["sd"]) if fb_entry else None

    bb_entry = _find_pitch(arsenal, ["SL", "SLIDER", "CB", "CURVEBALL", "CURVE", "SWEEPER", "SW"])
    breaking_ball = grade_from_value(bb_entry["whiff_pct"], pb["whiff_pct"]["mean"], pb["whiff_pct"]["sd"]) if bb_entry else None

    ch_entry = _find_pitch(arsenal, ["CH", "CHANGEUP", "CHANGE", "SPLIT", "SPLITTER"])
    changeup = grade_from_value(ch_entry["whiff_pct"], pb["whiff_pct"]["mean"], pb["whiff_pct"]["sd"]) if ch_entry else None

    command = grade_from_value(profile.get("edge_pct"), pb["edge_pct"]["mean"], pb["edge_pct"]["sd"])
    control = grade_from_value(profile.get("bb_pct"), pb["bb_pct"]["mean"], pb["bb_pct"]["sd"], lower_is_better=True)

    overall = _avg_grades([fastball, breaking_ball, changeup, command, control])

    return {
        "fastball": fastball, "breaking_ball": breaking_ball, "changeup": changeup,
        "command": command, "control": control, "overall": overall,
    }


def _find_pitch(arsenal: dict, name_candidates: list[str]) -> dict | None:
    for pitch_name, entry in arsenal.items():
        norm = str(pitch_name).strip().upper()
        if norm in name_candidates or any(c in norm for c in name_candidates):
            return entry
    return None
