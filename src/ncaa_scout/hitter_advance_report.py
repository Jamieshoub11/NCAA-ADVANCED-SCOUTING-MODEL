"""Assembles the Phase-4 opposing-hitter advance report: performance vs.
pitcher handedness, vs. pitch type, vs. velocity band, approach by count/
situation, and evidence-gated vulnerability labels.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import hitter_advance as ha
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

    lines.append(f"*Based on {len(df)} tracked pitches seen. Chase%, damage zones, and pull/center/oppo "
                 f"direction are not included — they require plate-location and batted-ball-direction "
                 f"fields not present in this data source. See docs/data_dictionary_pitcher_export.md.*")
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
