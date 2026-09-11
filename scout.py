#!/usr/bin/env python3
"""/scout [Player Name] — generate an NCAA D1 advanced scouting report from
whatever CSV data is sitting in the data/ directory for that player.

Usage:
    python scout.py "John Smith"
    python scout.py "Jane Doe" --type pitcher
    python scout.py "Jane Doe" --school "Vanderbilt" --pos SS --year Jr --bats R --throws R --conf SEC
    python scout.py "Jane Doe" --data-dir data --out reports --print

See README.md for the data folder convention and column-alias config.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from ncaa_scout.io_utils import DATA_DIR, slugify  # noqa: E402
from ncaa_scout.report import generate_report  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Generate an NCAA D1 advanced scouting report for one player.")
    parser.add_argument("player", help="Player name, e.g. \"John Smith\"")
    parser.add_argument("--type", choices=["hitter", "pitcher"], default=None,
                         help="Force hitter or pitcher (auto-detected from data if omitted)")
    parser.add_argument("--data-dir", default=None, help="Root data directory (default: ./data)")
    parser.add_argument("--out", default="reports", help="Directory to write the .md report to (default: ./reports)")
    parser.add_argument("--school", default=None)
    parser.add_argument("--pos", dest="position", default=None)
    parser.add_argument("--year", default=None, help="Class, e.g. Fr/So/Jr/Sr")
    parser.add_argument("--bats", default=None)
    parser.add_argument("--throws", default=None)
    parser.add_argument("--conf", dest="conference", default=None)
    parser.add_argument("--print", dest="print_only", action="store_true", help="Print to stdout instead of writing a file")
    args = parser.parse_args()

    data_dir = Path(args.data_dir) if args.data_dir else DATA_DIR
    overrides = {
        "school": args.school, "position": args.position, "year": args.year,
        "bats": args.bats, "throws": args.throws, "conference": args.conference,
    }

    report_text = generate_report(args.player, player_type=args.type, data_dir=data_dir, bio_overrides=overrides)

    if args.print_only:
        print(report_text)
        return

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{slugify(args.player)}_{date.today().isoformat()}.md"
    out_path.write_text(report_text)
    print(f"Report written to {out_path}")
    print()
    print(report_text)


if __name__ == "__main__":
    main()
