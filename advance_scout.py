#!/usr/bin/env python3
"""Advance-scouting report from pitch-level data — pitcher side (usage by
count, handedness splits, sequencing, "How to Attack" findings) or hitter
side (performance vs. pitcher hand/pitch type/velocity, approach by count,
vulnerability labels), auto-detected from which identity column the name
matches more often.

Usage:
    python advance_scout.py "Player Name"
    python advance_scout.py "Player Name" --role hitter
    python advance_scout.py "Player Name" --data-dir data --out reports --print
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from ncaa_scout.advance_report import build_pitcher_advance_report  # noqa: E402
from ncaa_scout.hitter_advance_report import build_hitter_advance_report  # noqa: E402
from ncaa_scout.io_utils import DATA_DIR, detect_advance_role, load_player_data, slugify  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Generate an advance-scouting report from pitch-level data.")
    parser.add_argument("player", help="Player name, e.g. \"Conner Griffin\"")
    parser.add_argument("--role", choices=["pitcher", "hitter"], default=None,
                         help="Force pitcher or hitter (auto-detected from the data if omitted)")
    parser.add_argument("--data-dir", default=None, help="Root data directory (default: ./data)")
    parser.add_argument("--out", default="reports", help="Directory to write the .md report to (default: ./reports)")
    parser.add_argument("--print", dest="print_only", action="store_true", help="Print to stdout instead of writing a file")
    args = parser.parse_args()

    data_dir = Path(args.data_dir) if args.data_dir else DATA_DIR

    role = args.role
    if role is None:
        loaded = load_player_data(args.player, data_dir)
        role = detect_advance_role(loaded, args.player)

    if role == "hitter":
        report_text = build_hitter_advance_report(args.player, data_dir=data_dir)
        suffix = "hitter_advance"
    else:
        report_text = build_pitcher_advance_report(args.player, data_dir=data_dir)
        suffix = "advance"

    if args.print_only:
        print(report_text)
        return

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{slugify(args.player)}_{suffix}_{date.today().isoformat()}.md"
    out_path.write_text(report_text)
    print(f"Report written to {out_path}")
    print()
    print(report_text)


if __name__ == "__main__":
    main()
