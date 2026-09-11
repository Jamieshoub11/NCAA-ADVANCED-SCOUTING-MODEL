#!/usr/bin/env python3
"""Pitcher advance-scouting report: usage by count, batter-handedness splits,
sequencing, two-strike tendencies, and evidence-backed "How to Attack"
findings — built from pitch-level data only.

Usage:
    python advance_scout.py "Pitcher Name"
    python advance_scout.py "Pitcher Name" --data-dir data --out reports --print
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from ncaa_scout.advance_report import build_pitcher_advance_report  # noqa: E402
from ncaa_scout.io_utils import DATA_DIR, slugify  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Generate a pitcher advance-scouting report from pitch-level data.")
    parser.add_argument("pitcher", help="Pitcher name, e.g. \"Conner Griffin\"")
    parser.add_argument("--data-dir", default=None, help="Root data directory (default: ./data)")
    parser.add_argument("--out", default="reports", help="Directory to write the .md report to (default: ./reports)")
    parser.add_argument("--print", dest="print_only", action="store_true", help="Print to stdout instead of writing a file")
    args = parser.parse_args()

    data_dir = Path(args.data_dir) if args.data_dir else DATA_DIR
    report_text = build_pitcher_advance_report(args.pitcher, data_dir=data_dir)

    if args.print_only:
        print(report_text)
        return

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{slugify(args.pitcher)}_advance_{date.today().isoformat()}.md"
    out_path.write_text(report_text)
    print(f"Report written to {out_path}")
    print()
    print(report_text)


if __name__ == "__main__":
    main()
