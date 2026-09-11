"""Assembles the Phase-3 pitcher advance report: arsenal, usage by count,
batter-handedness splits, two-strike tendencies, sequencing, and evidence-backed
"How to Attack" findings — every number carries its N and confidence tier.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import metrics_pitching as mp
from . import pitcher_advance as pa
from .io_utils import load_benchmarks, load_player_data
from .stat_utils import NA_TEXT, fmt, fmt_pct


def _fmt_row(pitch_type, n, pct, confidence) -> str:
    return f"| {pitch_type} | {fmt_pct(pct)} | N={n} | {confidence} |"


def _usage_section(title: str, table: pd.DataFrame, group_value) -> list[str]:
    lines = [f"**{title}**"]
    subset = table[table["group"] == group_value] if not table.empty else table
    if subset.empty:
        lines.append(NA_TEXT)
        return lines
    subset = subset.sort_values("usage_pct", ascending=False)
    lines.append("| Pitch | Usage | Sample | Confidence |")
    lines.append("| :--- | :--- | :--- | :--- |")
    for _, row in subset.iterrows():
        lines.append(_fmt_row(row["pitch_type"], row["n_pitch"], row["usage_pct"], row["confidence"]))
    return lines


def build_pitcher_advance_report(player_name: str, data_dir: Path | None = None) -> str:
    benchmarks = load_benchmarks()
    loaded = load_player_data(player_name, data_dir)
    df = pa.prepare_pitch_data(loaded.pitch_level, player_name)

    lines = [f"# {player_name.upper()} — PITCHER ADVANCE SCOUTING REPORT", ""]

    if df.empty:
        lines.append(f"No pitch-level data found for {player_name}. {NA_TEXT}")
        return "\n".join(lines)

    total_n = len(df)
    lines.append(f"*Based on {total_n} tracked pitches. Every tendency below shows its own sample size (N) "
                 f"and confidence tier — see confidence.py for the CI-based thresholds.*")
    lines.append("")

    # --- Arsenal ---
    arsenal_data = mp.pitch_arsenal(loaded.pitch_level, player_name, benchmarks)
    arsenal = arsenal_data.get("arsenal", {})
    lines.append("## Arsenal")
    if arsenal:
        lines.append("| Pitch | Usage | Velo (avg/max) | Spin | Whiff% | Sample |")
        lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
        for pitch_name, e in sorted(arsenal.items(), key=lambda kv: kv[1].get("usage_pct") or 0, reverse=True):
            n_pitch = round((e.get("usage_pct") or 0) * total_n)
            lines.append(
                f"| {pitch_name} | {fmt_pct(e.get('usage_pct'), 0)} | "
                f"{fmt(e.get('velo'), 1)} / {fmt(e.get('velo_max'), 1)} mph | {fmt(e.get('spin_rate'), 0)} rpm | "
                f"{fmt_pct(e.get('whiff_pct'))} | N={n_pitch} |"
            )
    else:
        lines.append(NA_TEXT)
    lines.append("")

    # --- Command & Control ---
    lines.append("## Command & Control")
    calibration = arsenal_data.get("zone_calibration")
    if arsenal_data.get("zone_pct") is not None:
        lines.append(f"Zone% {fmt_pct(arsenal_data['zone_pct'])} | Edge% {fmt_pct(arsenal_data['edge_pct'])} | "
                     f"Chase% {fmt_pct(arsenal_data['chase_pct'])} (D1 avg approx. Zone% 52% / Edge% 18% / Chase% 28%)")
        if calibration:
            v = calibration["validation"]
            method = "held-out" if v["held_out"] else "in-sample (too few called pitches for a held-out split)"
            lines.append(
                f"\n*Zone boundary self-calibrated from this pitcher's own {calibration['n_called_strikes']} called "
                f"strikes and {calibration['n_called_balls']} called balls (no TrackMan-style plate-location field "
                f"was present) — {method} accuracy {fmt_pct(v['accuracy'])} vs. a {fmt_pct(v['baseline_accuracy'])} "
                f"majority-class baseline. See zone_calibration.py.*"
            )
        else:
            lines.append("\n*From TrackMan-style plate-location data (plate_loc_side/plate_loc_height).*")
    else:
        lines.append(f"{NA_TEXT} — no usable plate-location field, and not enough called pitches "
                     f"(need 50+, with 10+ of each call) to self-calibrate one.")
    lines.append("")

    # --- Usage by count ---
    count_table = pa.usage_by_count(df)
    lines.append("## Usage by Count")
    if not count_table.empty:
        counts_present = sorted(count_table["group"].unique(), key=lambda c: (int(c.split("-")[0]), int(c.split("-")[1])))
        lines.append("| Count | Pitch | Usage | Sample | Confidence |")
        lines.append("| :--- | :--- | :--- | :--- | :--- |")
        for count in counts_present:
            subset = count_table[count_table["group"] == count].sort_values("usage_pct", ascending=False)
            for _, row in subset.iterrows():
                lines.append(f"| {count} | {row['pitch_type']} | {fmt_pct(row['usage_pct'])} | N={row['n_group']} | {row['confidence']} |")
    else:
        lines.append(NA_TEXT)
    lines.append("")

    # --- Situational usage ---
    situation_table = pa.usage_by_situation(df)
    lines.append("## Usage by Situation")
    for situation in ("First Pitch", "Even", "Pitcher Ahead", "Hitter Ahead", "Two Strikes"):
        lines.extend(_usage_section(situation, situation_table, situation))
        lines.append("")

    # --- Handedness splits ---
    hand_table = pa.usage_by_handedness(df)
    lines.append("## LHH / RHH Usage Splits")
    if not hand_table.empty:
        for hand, label in (("L", "vs LHH"), ("R", "vs RHH")):
            lines.extend(_usage_section(label, hand_table, hand))
            lines.append("")
    else:
        lines.append(NA_TEXT)
        lines.append("")

    # --- Sequencing ---
    seq_table = pa.sequencing_transitions(df)
    lines.append("## Sequencing (previous pitch -> next pitch)")
    if not seq_table.empty:
        lines.append("| After... | Next pitch | Probability | Sample | Confidence |")
        lines.append("| :--- | :--- | :--- | :--- | :--- |")
        for prev_pitch in sorted(seq_table["prev_pitch"].unique()):
            subset = seq_table[seq_table["prev_pitch"] == prev_pitch].sort_values("prob", ascending=False)
            for _, row in subset.iterrows():
                lines.append(f"| {prev_pitch} | {row['next_pitch']} | {fmt_pct(row['prob'])} | N={row['n_prev_total']} | {row['confidence']} |")
    else:
        lines.append(NA_TEXT)
    lines.append("")

    # --- How to Attack ---
    findings = pa.build_attack_findings(df, zone_info=arsenal_data, benchmarks=benchmarks)
    lines.append("## HOW TO ATTACK HIM")
    if findings:
        for i, f in enumerate(findings, 1):
            lines.append(f"{i}. **{f['finding']}**")
            lines.append(f"   - *Evidence:* {f['evidence']}")
            lines.append(f"   - *Confidence:* {f['confidence']}")
    else:
        lines.append("No finding cleared the confidence bar required for an actionable recommendation "
                      "(MODERATE, N>=30) — treat this pitcher's tendencies as unresolved rather than force a claim.")
    lines.append("")

    return "\n".join(lines)
