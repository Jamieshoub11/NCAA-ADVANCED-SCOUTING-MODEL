"""Assembles the Phase-4 opposing-hitter advance report: performance vs.
pitcher handedness, vs. pitch type, vs. velocity band, approach by count/
situation, and evidence-gated vulnerability labels.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import hitter_advance as ha
from . import metrics_hitting as mh
from .io_utils import load_benchmarks, load_player_data
from .stat_utils import NA_TEXT, fmt, fmt_pct


def _stats_table(title: str, table: pd.DataFrame) -> list[str]:
    lines = [f"## {title}"]
    if table.empty:
        lines.append(NA_TEXT)
        return lines
    lines.append("| Group | Swing% | Whiff% | Contact% | Avg EV | Hard-Hit% | Sample | Confidence |")
    lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    for _, row in table.iterrows():
        lines.append(
            f"| {row['group']} | {fmt_pct(row['swing_pct'])} | {fmt_pct(row['whiff_pct'])} | "
            f"{fmt_pct(row['contact_pct'])} | {fmt(row['avg_ev'], 1, ' mph')} | {fmt_pct(row['hard_hit_pct'])} | "
            f"N={row['n_pitches']} pitches / {row['n_batted']} batted | {row['confidence']} |"
        )
    return lines


def build_hitter_advance_report(player_name: str, data_dir: Path | None = None) -> str:
    benchmarks = load_benchmarks()
    loaded = load_player_data(player_name, data_dir)
    df = ha.prepare_hitter_pitch_data(loaded.pitch_level, player_name)

    lines = [f"# {player_name.upper()} — HITTER ADVANCE SCOUTING REPORT", ""]

    if df.empty:
        lines.append(f"No pitch-level data found for {player_name}. {NA_TEXT}")
        return "\n".join(lines)

    lines.append(f"*Based on {len(df)} tracked pitches seen. Pull/center/oppo direction is not included — "
                 f"it requires a batted-ball-direction field not present in this data source. "
                 f"See docs/data_dictionary_pitcher_export.md.*")
    lines.append("")

    # --- Chase% / Zone Contact ---
    discipline = mh.swing_discipline(loaded.pitch_level, player_name, benchmarks)
    lines.append("## Chase% & Zone Contact")
    if discipline.get("zone_pct") is not None:
        lines.append(f"Zone% seen {fmt_pct(discipline['zone_pct'])} | Chase% {fmt_pct(discipline['chase_pct'])} | "
                     f"Zone-Whiff% {fmt_pct(discipline['zone_whiff_pct'])} | Whiff% {fmt_pct(discipline['whiff_pct'])} "
                     f"(D1 avg approx. Chase% 28% / Zone-Whiff% 15%) — N={discipline.get('pitch_n', 0)} pitches")
        calibration = discipline.get("zone_calibration")
        if calibration:
            v = calibration["validation"]
            method = "held-out" if v["held_out"] else "in-sample (too few called pitches for a held-out split)"
            lines.append(
                f"\n*Zone boundary self-calibrated from this hitter's own {calibration['n_called_strikes']} called "
                f"strikes and {calibration['n_called_balls']} called balls seen — {method} accuracy "
                f"{fmt_pct(v['accuracy'])} vs. a {fmt_pct(v['baseline_accuracy'])} majority-class baseline.*"
            )
    else:
        lines.append(f"{NA_TEXT} — no usable plate-location field, and not enough called pitches "
                     f"(need 50+, with 10+ of each call) to self-calibrate one.")
    lines.append("")

    # --- Damage / Weakness Zone ---
    zonal = mh.zonal_profile(loaded.pitch_level, player_name, benchmarks)
    lines.append("## Damage Zone / Weakness Zone")
    lines.append(f"- **Damage Zone:** {zonal.get('damage_zone') or NA_TEXT}")
    lines.append(f"- **Weakness Zone:** {zonal.get('weakness_zone') or NA_TEXT}")
    lines.append("")

    lines.extend(_stats_table("vs. RHP / LHP", ha.performance_vs_pitcher_hand(df)))
    lines.append("")
    lines.extend(_stats_table("vs. Pitch Type", ha.performance_vs_pitch_type(df)))
    lines.append("")
    lines.extend(_stats_table("vs. Velocity Band", ha.performance_vs_velocity_band(df)))
    lines.append("")
    lines.extend(_stats_table("Approach by Count", ha.approach_by_count(df)))
    lines.append("")
    lines.extend(_stats_table("Approach by Situation", ha.approach_by_situation(df)))
    lines.append("")

    labels = ha.vulnerability_labels(df, benchmarks)
    lines.append("## APPROACH / VULNERABILITY LABELS")
    if labels:
        for i, lab in enumerate(labels, 1):
            lines.append(f"{i}. **{lab['label']}**")
            lines.append(f"   - *Evidence:* {lab['evidence']}")
            if lab["confidence"]:
                lines.append(f"   - *Confidence:* {lab['confidence']}")
    else:
        lines.append("No label cleared the confidence bar (MODERATE, N>=30) — treat this hitter's profile as unresolved rather than force a label.")
    lines.append("")

    return "\n".join(lines)
