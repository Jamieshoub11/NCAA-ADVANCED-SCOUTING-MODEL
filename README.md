# NCAA D1 Advanced Scouting Model

Turns raw CSV exports (TrackMan/Yakkertech pitch-level data, TruMedia/box-score
aggregates) into a full NCAA D1 advanced scouting report — no fabricated
numbers, ever. Anything that can't be computed from what you gave it comes
back as `N/A — Insufficient Data`, and the tool automatically flags
statistical contradictions (e.g. a plus SLG paired with a below-average
Hard-Hit%) instead of quietly reporting a misleading grade.

Built for Binghamton's analytics office: `config/team.yaml` defaults every
new player's school/conference to Binghamton University / America East, so
you're not retyping it for every roster entry. Override it per-player
(opponent scouting, transfers) with the School/Conference fields or a
`bio.json`.

## Quick start

```bash
pip install -r requirements.txt

# try it on the bundled synthetic demo data first
python scout.py "Sample Hitter" --data-dir data/sample --print
python scout.py "Sample Pitcher" --data-dir data/sample --print
```

## Web app (recommended for daily use)

```bash
streamlit run app.py
```

Opens a browser UI with three tabs:

- **Generate Report** — enter a player's name/bio, drag in their CSV(s), hit
  Generate. Renders the report on the page, saves it to `reports/`, and gives
  you a download button. Every upload is saved to `data/players/<slug>/`
  under the hood, so it's available next time (in the app or the CLI) too.
- **Roster** — everyone already ingested, one click to regenerate any report
  and download it.
- **Benchmarks** — view and edit the D1 reference means/SDs used for grading,
  right in the browser. Saves to `config/benchmarks.local.yaml`, which
  overrides (but never overwrites) the documented defaults in
  `config/benchmarks.yaml` — delete the local file any time to reset.

This runs locally on your machine (`localhost:8501` by default) — it isn't
hosted anywhere. To put it on a URL your assistants/coaches can hit without
you running it, the easiest options are [Streamlit Community Cloud](https://streamlit.io/cloud)
(free, point it at this repo/branch) or standing up the container on
Binghamton's own infrastructure if IT allows it. Either way, treat
`data/players/` as containing real athlete performance data — keep the
deployment access-restricted to your staff, not public.

## Daily workflow — scouting a real player (CLI)

1. **Drop the player's data in.** Create a folder under `data/players/<name>/`
   (any spelling — it gets slugified) and put whatever CSVs you have in it:
   a TrackMan/Yakkertech pitch-level export, a TruMedia box-score export, or
   both. File names don't matter; the tool sniffs each CSV's columns to figure
   out what it is.

   ```
   data/players/john_smith/
     trackman_2026.csv
     boxscore_2026.csv
     bio.json          # optional — see below
   ```

2. **(Optional) add a `bio.json`** so the report header is filled in instead
   of showing `N/A`:

   ```json
   {
     "name": "John Smith", "school": "Vanderbilt", "position": "SS",
     "year": "Jr", "bats": "R", "throws": "R", "conference": "SEC"
   }
   ```

   You can also pass these as flags instead: `--school`, `--pos`, `--year`,
   `--bats`, `--throws`, `--conf`.

3. **Run it:**

   ```bash
   python scout.py "John Smith"
   ```

   This writes `reports/john_smith_<today>.md` and prints it to the terminal.
   Add `--print` to skip the file and only print. Add `--type pitcher` (or
   `hitter`) if auto-detection guesses wrong — auto-detection looks for
   pitching-shaped columns (`IP`/`BF`) or a `pitcher_name`-only pitch-level file.

`data/players/` is gitignored by default (real player exports often carry
data-license restrictions), so your actual scouting data stays local unless
you deliberately commit it.

## What it computes

- **Traditional/advanced hitting:** AVG/OBP/SLG/OPS, ISO, BABIP, wOBA, a
  simplified wRC+, K%/BB%.
- **Contact quality:** Max EV, avg EV, Hard-Hit% (≥95 mph), all from
  pitch-level `ExitSpeed` on batted balls.
- **Swing decisions:** Whiff%, Chase%, Zone-Whiff%, Zone%, computed from
  `PitchCall` + `PlateLocSide`/`PlateLocHeight` against a configurable strike
  zone.
- **Zonal mapping:** a 3x3 zone grid identifies the "damage zone" (highest
  avg EV on balls in play) and "weakness zone" (highest whiff rate on
  swings), each gated behind a minimum-sample check.
- **Pitching:** per-pitch-type velo/spin/movement/release/usage/whiff from
  TrackMan, plus Zone%/Edge%/Chase%, ERA/WHIP/K%/BB%/K:BB from box scores.
- **20-80 scouting grades**, both offense and pitching, as a z-score against
  the D1 benchmarks in `config/benchmarks.yaml`.
- **Automatic contradiction flags** (see `src/ncaa_scout/contradictions.py`)
  and small-sample warnings so you never get a confident-sounding grade off
  15 pitches.

## Making it match *your* exports

Real export tools never agree on column headers. Everything the model reads
goes through `config/column_aliases.yaml`, which maps a canonical field name
(`exit_speed`, `plate_loc_side`, …) to every header spelling it should
recognize. If your CSV uses a header the tool doesn't already know, add it to
the right list in that file — no code changes needed.

`config/benchmarks.yaml` holds the D1 reference means/SDs used for grading
and the league constants used for wRC+. **These are calibrated
approximations, not an official published percentile table** — swap in your
own conference's real averages whenever you have them (e.g. from a TruMedia
leaderboard) and every future report immediately uses the better numbers.

## Project layout

```
app.py                         Streamlit web app — streamlit run app.py
scout.py                       CLI entrypoint — python scout.py "Player Name"
src/ncaa_scout/
  io_utils.py                  CSV discovery, header-alias normalization, bio/team-defaults loading
  metrics_hitting.py           slash line, wOBA/wRC+, contact quality, swing discipline, zonal mapping
  metrics_pitching.py          pitch arsenal, command/control, rate stats
  grading.py                   z-score -> 20-80 scale
  contradictions.py            rule-based contradiction/small-sample detector
  narrative.py                 turns grades/flags into the report's prose sections
  report.py                    assembles the final markdown from the fixed template
config/
  column_aliases.yaml          header-spelling -> canonical field name
  benchmarks.yaml               D1 reference means/SDs, strike zone bounds, sample-size thresholds
  benchmarks.local.yaml         optional overrides written by the app's Benchmarks tab (gitignored-safe to commit if you want to share tuned numbers)
  team.yaml                    your program's default school/conference
data/sample/                   synthetic demo data (regenerate with scripts/generate_sample_data.py)
data/players/                  your real per-player data goes here (gitignored)
tests/                         pytest suite (arithmetic, aliasing, end-to-end report generation)
```

## Running tests

```bash
python -m pytest tests/ -v
```
