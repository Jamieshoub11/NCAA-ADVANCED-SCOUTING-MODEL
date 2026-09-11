"""Assembles the full markdown scouting report matching the fixed template:
Executive Summary -> Metric Profile -> Advanced Analysis -> Tool Eval/Zonal Map ->
Strengths -> Weaknesses -> Projection -> Live Scouting Questions -> Grades -> Confidence.
"""

from __future__ import annotations

from pathlib import Path

from . import metrics_hitting as mh
from . import metrics_pitching as mp
from . import narrative as nar
from .contradictions import detect_hitter_contradictions, detect_pitcher_contradictions
from .grading import grade_hitter, grade_pitcher
from .io_utils import PlayerBio, load_benchmarks, load_player_data
from .stat_utils import NA_TEXT, fmt, fmt_avg, fmt_pct


def detect_player_type(loaded, explicit: str | None = None) -> str:
    if explicit in ("hitter", "pitcher"):
        return explicit
    pitcher_signal = any("bf" in df.columns or "ip" in df.columns for df in loaded.boxscore)
    pitcher_signal = pitcher_signal or any("pitcher_name" in df.columns and "batter_name" not in df.columns for df in loaded.pitch_level)
    return "pitcher" if pitcher_signal else "hitter"


def _build_hitter_report(name: str, bio: PlayerBio, loaded, benchmarks: dict) -> str:
    counts = mh.aggregate_counts(loaded.boxscore)
    contact = mh.contact_quality(loaded.pitch_level, name, benchmarks)
    discipline = mh.swing_discipline(loaded.pitch_level, name, benchmarks)
    profile = mh.build_hitter_profile(counts, contact, discipline, benchmarks)
    zonal = mh.zonal_profile(loaded.pitch_level, name, benchmarks)
    grades = grade_hitter(profile, benchmarks)
    contradictions = detect_hitter_contradictions(profile, benchmarks)

    strengths = nar.rank_components(grades, nar.HITTER_COMPONENTS, profile, high=True)
    weaknesses = nar.rank_components(grades, nar.HITTER_COMPONENTS, profile, high=False)
    sample_flags = [f for f in contradictions if f.startswith("Small sample")]
    other_flags = [f for f in contradictions if not f.startswith("Small sample")]

    exec_summary = nar.executive_summary(
        name, "hitter", grades, strengths, weaknesses, other_flags,
        sample_flags[0] if sample_flags else None,
    )
    confidence, confidence_reason = nar.confidence_rating(sample_flags, bool(loaded.pitch_level), bool(loaded.boxscore))
    projection = nar.projection_text("hitter", grades)
    priorities = nar.development_priorities(weaknesses)
    questions = nar.live_scouting_questions("hitter", weaknesses)

    metric_rows = [
        ("Traditional", "AVG / OBP / SLG / OPS",
         f"{fmt_avg(profile['avg'])} / {fmt_avg(profile['obp'])} / {fmt_avg(profile['slg'])} / {fmt(profile['ops'], 3)}",
         f"D1 avg approx. .280/.380/.430/.810 ({int(profile['pa']) if profile.get('pa') is not None else 'N/A'} PA)"),
        ("Advanced", "wOBA / wRC+ / ISO / BABIP",
         f"{fmt(profile['woba'], 3)} / {fmt(profile['wrc_plus'], 0) if profile['wrc_plus'] is not None else NA_TEXT} / {fmt(profile['iso'], 3)} / {fmt_avg(profile['babip'])}",
         "wRC+ 100 = D1 league average (see benchmarks.yaml for league constants used)"),
        ("Contact/Shape", "Max EV / Hard-Hit% / Whiff%",
         f"{fmt(profile['max_ev'], 1, ' mph')} / {fmt_pct(profile['hard_hit_pct'])} / {fmt_pct(profile['whiff_pct'])}",
         f"D1 avg approx. 98.0 mph / 32% / 24% ({profile.get('batted_ball_n', 0)} batted balls tracked)"),
        ("Discipline", "BB% / Chase% / Zone-Whiff%",
         f"{fmt_pct(profile['bb_pct'])} / {fmt_pct(profile['chase_pct'])} / {fmt_pct(profile['zone_whiff_pct'])}",
         f"D1 avg approx. 9% / 28% / 15% ({profile.get('pitch_n', 0)} pitches tracked)"),
    ]

    analysis_bullets = [
        f"**Contact quality (EV/Barrel proxy):** {nar.HITTER_COMPONENTS['power']['evidence'](profile)}.",
        f"**Swing decisions (Chase/Zone-Whiff):** {nar.HITTER_COMPONENTS['approach']['evidence'](profile)}, Zone-Whiff% {fmt_pct(profile.get('zone_whiff_pct'))}.",
        "**Pitch-type & velo vulnerabilities:** " + (
            "N/A — Insufficient Data (requires per-pitch-type velocity buckets vs. this batter, not present in the CSVs found)."
        ),
    ]
    if other_flags:
        analysis_bullets.append("**Data contradictions flagged:** " + " ".join(other_flags))

    tool_lines = [
        f"- **Damage Zone:** {zonal['damage_zone'] or NA_TEXT}",
        f"- **Weakness Zone:** {zonal['weakness_zone'] or NA_TEXT}",
        f"- **Hit vs. Power breakdown:** Hit grade {grades['hit'] if grades['hit'] is not None else NA_TEXT} "
        f"({nar.grade_label(grades['hit'])}) vs. Power grade {grades['power'] if grades['power'] is not None else NA_TEXT} "
        f"({nar.grade_label(grades['power'])}).",
    ]

    grades_line = (
        f"Hit: [{_g(grades['hit'])}] | Power: [{_g(grades['power'])}] | Approach: [{_g(grades['approach'])}] | "
        f"Speed: [{_g(grades['speed'])}] | Defense: [{_g(grades['defense'])}] | Overall: [{_g(grades['overall'])}]"
    )

    return _render_template(
        name=name, bio=bio, exec_summary=exec_summary, metric_rows=metric_rows,
        analysis_bullets=analysis_bullets, tool_lines=tool_lines,
        strengths=strengths, weaknesses=weaknesses, projection=projection,
        priorities=priorities, questions=questions, grades_line=grades_line,
        confidence=confidence, confidence_reason=confidence_reason,
        player_type="hitter", overall_grade=grades["overall"],
    )


def _build_pitcher_report(name: str, bio: PlayerBio, loaded, benchmarks: dict) -> str:
    counts = mp.aggregate_pitching_counts(loaded.boxscore)
    arsenal_data = mp.pitch_arsenal(loaded.pitch_level, name, benchmarks)
    profile = mp.build_pitcher_profile(counts, arsenal_data, benchmarks)
    grades = grade_pitcher(profile, benchmarks)
    contradictions = detect_pitcher_contradictions(profile, benchmarks)

    strengths = nar.rank_components(grades, nar.PITCHER_COMPONENTS, profile, high=True)
    weaknesses = nar.rank_components(grades, nar.PITCHER_COMPONENTS, profile, high=False)
    sample_flags = [f for f in contradictions if f.startswith("Small sample")]
    other_flags = [f for f in contradictions if not f.startswith("Small sample")]

    exec_summary = nar.executive_summary(
        name, "pitcher", grades, strengths, weaknesses, other_flags,
        sample_flags[0] if sample_flags else None,
    )
    confidence, confidence_reason = nar.confidence_rating(sample_flags, bool(loaded.pitch_level), bool(loaded.boxscore))
    projection = nar.projection_text("pitcher", grades)
    priorities = nar.development_priorities(weaknesses)
    questions = nar.live_scouting_questions("pitcher", weaknesses)

    fb_ev = nar._fb_evidence(profile)
    if profile["k_pct"] is None and profile["bb_pct"] is None:
        k_bb_display = NA_TEXT
    else:
        k_bb_display = f"{fmt_pct(profile['k_pct'])}-{fmt_pct(profile['bb_pct'])}"
    ip_display = fmt(profile.get("ip_display", profile.get("ip")), 1)
    metric_rows = [
        ("Traditional", "ERA / WHIP / K-BB%",
         f"{fmt(profile['era'], 2)} / {fmt(profile['whip'], 2)} / {k_bb_display}",
         f"IP {ip_display}, BF {int(profile['bf']) if profile.get('bf') is not None else NA_TEXT}"),
        ("Advanced", "K% / BB% / K/9 / BB/9 / K-BB ratio",
         f"{fmt_pct(profile['k_pct'])} / {fmt_pct(profile['bb_pct'])} / {fmt(profile['k_per9'], 2)} / "
         f"{fmt(profile['bb_per9'], 2)} / {fmt(profile['k_bb_ratio'], 2)}",
         "D1 avg approx. K% 22% / BB% 9% / K:BB 2.4 (K/9, BB/9 shown when BF isn't in the source data)"),
        ("Fastball", "Velo / Max Velo / IVB / Whiff%", fb_ev, "D1 FB velo avg approx. 90.5 mph"),
        ("Command/Control", "Zone% / Edge% / Chase%",
         f"{fmt_pct(profile['zone_pct'])} / {fmt_pct(profile['edge_pct'])} / {fmt_pct(profile['chase_pct'])}",
         f"D1 avg approx. Zone% 52% / Edge% 18% / Chase% 28% ({profile.get('pitch_n', 0)} pitches tracked)"),
    ]

    arsenal_ranked = mp.rank_arsenal_by_usage(profile.get("arsenal", {}))
    arsenal_desc = "; ".join(
        f"{p} ({fmt_pct(e.get('usage_pct'), 0)}, Whiff% {fmt_pct(e.get('whiff_pct'))})" for p, e in arsenal_ranked
    ) or NA_TEXT

    analysis_bullets = [
        f"**Fastball architecture:** {fb_ev}.",
        f"**Secondary shape separation:** Arsenal usage/whiff — {arsenal_desc}.",
        f"**Command (Edge%) vs. Control (Zone%):** Edge% {fmt_pct(profile.get('edge_pct'))} vs. Zone% {fmt_pct(profile.get('zone_pct'))}.",
    ]
    if other_flags:
        analysis_bullets.append("**Data contradictions flagged:** " + " ".join(other_flags))

    ranked_names = [p for p, _ in arsenal_ranked]
    best = ranked_names[0] if len(ranked_names) > 0 else NA_TEXT
    secondary = ranked_names[1] if len(ranked_names) > 1 else NA_TEXT
    supporting = ranked_names[2] if len(ranked_names) > 2 else NA_TEXT
    development = ranked_names[3] if len(ranked_names) > 3 else NA_TEXT
    putaway = mp.putaway_pitch(profile.get("arsenal", {})) or NA_TEXT

    tool_lines = [
        f"- **Best Pitch:** {best} | **Secondary:** {secondary} | **Supporting:** {supporting} | **Development:** {development}",
        f"- **Put-away strategy:** {putaway}",
    ]

    grades_line = (
        f"Fastball: [{_g(grades['fastball'])}] | Breaking Ball: [{_g(grades['breaking_ball'])}] | "
        f"Changeup: [{_g(grades['changeup'])}] | Command: [{_g(grades['command'])}] | "
        f"Control: [{_g(grades['control'])}] | Overall: [{_g(grades['overall'])}]"
    )

    return _render_template(
        name=name, bio=bio, exec_summary=exec_summary, metric_rows=metric_rows,
        analysis_bullets=analysis_bullets, tool_lines=tool_lines,
        strengths=strengths, weaknesses=weaknesses, projection=projection,
        priorities=priorities, questions=questions, grades_line=grades_line,
        confidence=confidence, confidence_reason=confidence_reason,
        player_type="pitcher", overall_grade=grades["overall"],
    )


def _g(grade) -> str:
    return str(grade) if grade is not None else "N/A"


def _render_template(*, name, bio: PlayerBio, exec_summary, metric_rows, analysis_bullets, tool_lines,
                      strengths, weaknesses, projection, priorities, questions, grades_line,
                      confidence, confidence_reason, player_type, overall_grade) -> str:
    lines = []
    lines.append(f"# {name.upper()} — ADVANCED SCOUTING REPORT")
    lines.append(
        f"**School:** {bio.school} | **Position:** {bio.position} | **Class:** {bio.year} | "
        f"**Bats/Throws:** {bio.bats_throws} | **Conference:** {bio.conference}"
    )
    lines.append("")
    lines.append("### 1. EXECUTIVE SUMMARY")
    lines.append(exec_summary)
    lines.append("")
    lines.append("### 2. STATISTICAL & ADVANCED METRIC PROFILE")
    lines.append("| Category | Metric | Value | D1 Percentile / Context |")
    lines.append("| :--- | :--- | :--- | :--- |")
    for cat, metric, value, context in metric_rows:
        lines.append(f"| {cat} | {metric} | {value} | {context} |")
    lines.append("")
    lines.append("### 3. ADVANCED DATA ANALYSIS & INTERPRETATION")
    for bullet in analysis_bullets:
        lines.append(f"- {bullet}")
    lines.append("")
    lines.append("### 4. TOOL EVALUATION & ZONAL MAPPING")
    for line in tool_lines:
        lines.append(line)
    lines.append("")
    lines.append("### 5. RANKED STRENGTHS (Top 3-5)")
    if strengths:
        for i, s in enumerate(strengths, 1):
            lines.append(f"{i}. **{s['name']}**")
            lines.append(f"   - *Evidence:* {s['evidence']}")
            lines.append(f"   - *Scouting Interpretation:* {s['interpretation']}")
    else:
        lines.append("No graded tool clears the above-average threshold — profile grades cluster near D1 average, or insufficient data was available to grade any tool.")
    lines.append("")
    lines.append("### 6. RANKED WEAKNESSES & RISKS (Top 3-5)")
    if weaknesses:
        for i, w in enumerate(weaknesses, 1):
            lines.append(f"{i}. **{w['name']}**")
            lines.append(f"   - *Evidence:* {w['evidence']}")
            lines.append(f"   - *Scouting Interpretation:* {w['interpretation']}")
            lines.append(f"   - *Impact on Projection:* Caps the {'offensive' if player_type == 'hitter' else 'pitching'} ceiling until this improves; see Development Priorities.")
    else:
        lines.append("No graded tool falls below the below-average threshold — profile grades cluster near D1 average, or insufficient data was available to grade any tool.")
    lines.append("")
    lines.append("### 7. PROJECTION & DEVELOPMENT PRIORITIES")
    role_label = "D1 Projection"
    lines.append(f"- **{role_label}:** {projection}")
    lines.append("- **Top 3 Priorities:**")
    for i, p in enumerate(priorities, 1):
        lines.append(f"  {i}. {p}")
    lines.append("")
    lines.append("### 8. LIVE SCOUTING QUESTIONS")
    for q in questions:
        lines.append(f"- {q}")
    lines.append("")
    lines.append("### 9. SCOUTING GRADES (20–80 SCALE)")
    label = "*Hitters:*" if player_type == "hitter" else "*Pitchers:*"
    lines.append(f"{label} {grades_line}")
    lines.append("")
    lines.append("### 10. EVALUATION CONFIDENCE & BOTTOM LINE")
    lines.append(f"- **Confidence Rating:** {confidence} — {confidence_reason}")
    bottom_line = (
        f"Overall grade of {overall_grade if overall_grade is not None else NA_TEXT} "
        f"({nar.grade_label(overall_grade)}). {projection}"
    )
    lines.append(f"- **Bottom Line:** {bottom_line}")
    return "\n".join(lines) + "\n"


def generate_report(player_name: str, player_type: str | None = None, data_dir: Path | None = None,
                     bio_overrides: dict | None = None) -> str:
    benchmarks = load_benchmarks()
    loaded = load_player_data(player_name, data_dir)
    bio = _load_bio_with_overrides(player_name, data_dir, bio_overrides)
    ptype = detect_player_type(loaded, player_type)

    if not loaded.has_any():
        return _render_no_data_report(player_name, bio)

    if ptype == "pitcher":
        return _build_pitcher_report(player_name, bio, loaded, benchmarks)
    return _build_hitter_report(player_name, bio, loaded, benchmarks)


def _load_bio_with_overrides(player_name: str, data_dir, overrides: dict | None) -> PlayerBio:
    from .io_utils import load_bio
    bio = load_bio(player_name, data_dir)
    if overrides:
        for k, v in overrides.items():
            if v is not None and hasattr(bio, k):
                setattr(bio, k, v)
    return bio


def _render_no_data_report(name: str, bio: PlayerBio) -> str:
    return (
        f"# {name.upper()} — ADVANCED SCOUTING REPORT\n"
        f"**School:** {bio.school} | **Position:** {bio.position} | **Class:** {bio.year} | "
        f"**Bats/Throws:** {bio.bats_throws} | **Conference:** {bio.conference}\n\n"
        f"### 1. EXECUTIVE SUMMARY\n"
        f"No raw data (CSV, TrackMan export, or box score) matching \"{name}\" was found under the data/ "
        f"directory. Add a file under data/players/<player_slug>/ and re-run — every section below is "
        f"{NA_TEXT} until then.\n\n"
        f"### 2. STATISTICAL & ADVANCED METRIC PROFILE\n{NA_TEXT}\n\n"
        f"### 10. EVALUATION CONFIDENCE & BOTTOM LINE\n"
        f"- **Confidence Rating:** Low — no data found.\n"
        f"- **Bottom Line:** Cannot evaluate without data.\n"
    )
