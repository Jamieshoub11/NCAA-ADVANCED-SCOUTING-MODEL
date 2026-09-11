"""Turns computed grades/metrics/contradiction-flags into the prose sections
of the report (executive summary, ranked strengths/weaknesses, projection,
live-scouting questions, confidence rating). Every sentence here is derived
from an actual computed value passed in — nothing is invented independent
of the data; where a component has no data, it is skipped rather than guessed.
"""

from __future__ import annotations

from .stat_utils import fmt_avg, fmt_pct, fmt, NA_TEXT

HITTER_COMPONENTS = {
    "hit": {
        "label": "Hit Tool / Contact Ability",
        "evidence": lambda p: f"AVG {fmt_avg(p.get('avg'))}, K% {fmt_pct(p.get('k_pct'))}, Whiff% {fmt_pct(p.get('whiff_pct'))}",
        "strength_text": "Puts the bat on the ball at a rate that stands out for the level — limits empty at-bats and keeps him in favorable counts.",
        "weakness_text": "Contact rate lags D1 average — expect swing-and-miss to show up more against better stuff, particularly quality spin.",
    },
    "power": {
        "label": "Power / Damage",
        "evidence": lambda p: f"ISO {fmt(p.get('iso'), 3)}, Max EV {fmt(p.get('max_ev'), 1, ' mph')}, Hard-Hit% {fmt_pct(p.get('hard_hit_pct'))}",
        "strength_text": "Contact quality and damage numbers exceed D1 average — carries game-changing pop when he gets to it.",
        "weakness_text": "Underlying contact quality (EV/Hard-Hit%) is light for the level — profile leans more line-drive/contact than impact until it shows up.",
    },
    "approach": {
        "label": "Plate Discipline / Approach",
        "evidence": lambda p: f"BB% {fmt_pct(p.get('bb_pct'))}, Chase% {fmt_pct(p.get('chase_pct'))}",
        "strength_text": "Controls the strike zone well — limits chase and forces pitchers to work in the zone.",
        "weakness_text": "Chases out of the zone more than D1 average — vulnerable to a pitcher who can expand once ahead in the count.",
    },
}

PITCHER_COMPONENTS = {
    "fastball": {
        "label": "Fastball Architecture",
        "evidence": lambda p: _fb_evidence(p),
        "strength_text": "Velocity plays above D1 average and gives him margin to work off of.",
        "weakness_text": "Velocity sits below D1 average — will need plus command/shape elsewhere to miss bats at the next level.",
    },
    "breaking_ball": {
        "label": "Breaking Ball",
        "evidence": lambda p: _pitch_evidence(p, ["SL", "SLIDER", "CB", "CURVEBALL", "CURVE", "SWEEPER", "SW"]),
        "strength_text": "Breaking ball generates swing-and-miss at an above-average clip — a legitimate weapon to land in any count.",
        "weakness_text": "Breaking ball whiff rate lags D1 average — hitters are picking it up or it lacks the shape to miss bats consistently.",
    },
    "changeup": {
        "label": "Changeup",
        "evidence": lambda p: _pitch_evidence(p, ["CH", "CHANGEUP", "CHANGE", "SPLIT", "SPLITTER"]),
        "strength_text": "Changeup misses bats at an above-average rate — gives him a real answer against opposite-side hitters.",
        "weakness_text": "Changeup whiff rate is below average — needs more separation from the fastball (velo or shape) to be a reliable weapon.",
    },
    "command": {
        "label": "Command (Edge%)",
        "evidence": lambda p: f"Edge% {fmt_pct(p.get('edge_pct'))}, Zone% {fmt_pct(p.get('zone_pct'))}",
        "strength_text": "Works the shadow zone (Edge%) at an above-average rate — pitches to soft/hard contact spots rather than the middle of the zone.",
        "weakness_text": "Edge% is below average — pitches catch more of the heart of the zone than ideal, leaving margin for hitters to do damage.",
    },
    "control": {
        "label": "Control (BB%)",
        "evidence": lambda p: f"BB% {fmt_pct(p.get('bb_pct'))}, K/BB {fmt(p.get('k_bb_ratio'), 2)}",
        "strength_text": "Throws enough strikes to stay ahead in counts and keep the defense engaged.",
        "weakness_text": "Walk rate runs above D1 average — free passes are extending innings and putting stress on the pitch count.",
    },
}


def _fb_evidence(profile: dict) -> str:
    arsenal = profile.get("arsenal", {})
    fb = None
    for pitch_name, entry in arsenal.items():
        if str(pitch_name).strip().upper() in ("FF", "FB", "FASTBALL", "SINKER", "SI", "2S", "TWO-SEAM"):
            fb = entry
            break
    if not fb:
        return NA_TEXT
    return f"Velo {fmt(fb.get('velo'), 1, ' mph')} (max {fmt(fb.get('velo_max'), 1, ' mph')}), IVB {fmt(fb.get('ivb'), 1)}, Whiff% {fmt_pct(fb.get('whiff_pct'))}"


def _pitch_evidence(profile: dict, name_candidates: list[str]) -> str:
    arsenal = profile.get("arsenal", {})
    for pitch_name, entry in arsenal.items():
        norm = str(pitch_name).strip().upper()
        if norm in name_candidates or any(c in norm for c in name_candidates):
            return f"Usage {fmt_pct(entry.get('usage_pct'), 0)}, Whiff% {fmt_pct(entry.get('whiff_pct'))}, Spin {fmt(entry.get('spin_rate'), 0, ' rpm')}"
    return NA_TEXT


def grade_label(grade: int | None) -> str:
    if grade is None:
        return NA_TEXT
    labels = {20: "Well Below Avg", 30: "Well Below Avg", 35: "Below Avg", 40: "Below Avg",
              45: "Fringe-Average", 50: "Average", 55: "Above Average", 60: "Plus",
              65: "Plus", 70: "Plus-Plus", 75: "Plus-Plus", 80: "Elite"}
    return labels.get(grade, "Average")


def rank_components(grades: dict, components: dict, profile: dict, high: bool, limit: int = 5) -> list[dict]:
    """Only surfaces components that actually cross the strength/weakness
    threshold — an average-graded tool never gets mislabeled as either just
    to fill out the list. An empty result means grades cluster near average.
    """
    scored = [(k, v) for k, v in grades.items() if k in components and v is not None]
    scored.sort(key=lambda kv: kv[1], reverse=high)
    threshold = 55 if high else 45
    chosen = [kv for kv in scored if (kv[1] >= threshold if high else kv[1] <= threshold)]
    out = []
    for key, grade in chosen[:limit]:
        meta = components[key]
        out.append({
            "name": meta["label"],
            "evidence": meta["evidence"](profile),
            "interpretation": meta["strength_text"] if high else meta["weakness_text"],
            "grade": grade,
        })
    return out


def executive_summary(name: str, player_type: str, grades: dict, strengths: list[dict], weaknesses: list[dict],
                       contradictions: list[str], sample_note: str | None) -> str:
    role = "hitter" if player_type == "hitter" else "pitcher"
    overall = grades.get("overall")
    overall_txt = grade_label(overall) if overall is not None else "not yet gradable from the data provided"

    sentences = [f"{name} profiles as a {overall_txt.lower()} D1 {role} based on the data available."]

    if strengths:
        top = strengths[0]
        sentences.append(f"The clearest asset is his {top['name'].lower()} ({top['evidence']}), which projects as an above-average tool at this level.")
    if weaknesses:
        bottom = weaknesses[0]
        sentences.append(f"The main vulnerability is his {bottom['name'].lower()} ({bottom['evidence']}) — the biggest swing factor for his projection.")
    if not strengths and not weaknesses:
        sentences.append("No single tool stands out as clearly above or below D1 average — this is a balanced, unremarkable profile on the data available.")
    if contradictions:
        sentences.append(f"One data contradiction stands out: {contradictions[0]}")
    if sample_note:
        sentences.append(sample_note)
    sentences.append(
        "Overall, he looks like a role player worth continued tracking rather than a settled evaluation — "
        "the numbers here should be confirmed live before locking in a final grade."
    )
    return " ".join(sentences)


def projection_text(player_type: str, grades: dict) -> str:
    overall = grades.get("overall")
    if overall is None:
        return NA_TEXT
    if player_type == "hitter":
        if overall >= 60:
            return "Everyday D1 offensive contributor; ceiling as a middle-of-the-order threat if power/contact combo holds against better arms."
        if overall >= 50:
            return "Likely everyday D1 role player; floor as a bottom-of-the-order regular, ceiling tied to development priorities below."
        if overall >= 40:
            return "Platoon/complementary bat at present; needs at least one tool to tick up to project as a full-time D1 regular."
        return "Below-average offensive profile at present; role likely limited to depth/situational use until tools develop."
    else:
        if overall >= 60:
            return "Profiles as a weekend rotation piece; ceiling tied to secondary-pitch consistency and command development."
        if overall >= 50:
            return "Likely mid-week starter or high-leverage relief piece; floor as a bullpen arm."
        if overall >= 40:
            return "Depth arm/multi-inning relief profile at present; needs a swing-and-miss secondary or better control to move up the staff."
        return "Below-average pitching profile at present; likely limited to low-leverage relief work until stuff or command develops."


def development_priorities(weaknesses: list[dict], limit: int = 3) -> list[str]:
    if not weaknesses:
        return ["No graded weakness stands out from D1 average — maintain current development track and re-check as sample size grows."]
    return [f"Improve {w['name']} — {w['interpretation']}" for w in weaknesses[:limit]]


def live_scouting_questions(player_type: str, weaknesses: list[dict]) -> list[str]:
    base = (
        ["Does the swing/delivery hold up against premium velocity (94+) live, not just in the data window sampled?",
         "How does the player's demeanor/body language change in high-leverage counts or after adversity?"]
        if player_type == "hitter" else
        ["Does velocity/shape hold in the 5th-7th inning, or is there a notable dropoff?",
         "How does the delivery/release repeat late in an outing or on the road?"]
    )
    for w in weaknesses[:3]:
        base.append(f"Live-verify: does the {w['name'].lower()} concern from the data hold up in person, or is it a small-sample artifact?")
    return base[:5]


def confidence_rating(sample_flags: list[str], has_pitch_level: bool, has_boxscore: bool) -> tuple[str, str]:
    n_flags = len(sample_flags)
    if not has_pitch_level and not has_boxscore:
        return "Low", "No usable data was found for this player — every section above is N/A."
    if n_flags == 0 and has_pitch_level and has_boxscore:
        return "High", "Both traditional box-score and pitch-level tracking data were available with adequate sample sizes."
    if n_flags >= 2:
        return "Low", f"{n_flags} small-sample/contradiction flags were raised — treat grades as provisional until more data accumulates."
    return "Medium", "Some data was available but either sample size is limited or one data source (pitch-level or box score) is missing."
