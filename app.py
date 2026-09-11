"""NCAA D1 Advanced Scouting Model — web app.

Run with:  streamlit run app.py

Three tabs:
  - Generate Report: upload a player's CSVs, fill in bio info, generate + download the report.
  - Roster: browse everyone already ingested under data/players/, regenerate any report in one click.
  - Benchmarks: view/edit the D1 reference numbers used for grading (writes to
    config/benchmarks.local.yaml — the documented defaults file is never touched).
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import streamlit as st  # noqa: E402

from ncaa_scout.io_utils import (  # noqa: E402
    DATA_DIR, load_benchmarks, load_team_defaults, save_benchmarks_override, slugify,
)
from ncaa_scout.report import generate_report  # noqa: E402

REPORTS_DIR = Path(__file__).resolve().parent / "reports"

st.set_page_config(page_title="NCAA D1 Scouting Model", layout="wide")

TEAM = load_team_defaults()
DEFAULT_SCHOOL = TEAM.get("school", "")
DEFAULT_CONF = TEAM.get("conference", "")


def _player_dirs() -> list[Path]:
    root = DATA_DIR / "players"
    if not root.exists():
        return []
    return sorted([p for p in root.iterdir() if p.is_dir()])


def _save_upload(player_slug: str, uploaded_file) -> None:
    player_dir = DATA_DIR / "players" / player_slug
    player_dir.mkdir(parents=True, exist_ok=True)
    with open(player_dir / uploaded_file.name, "wb") as f:
        f.write(uploaded_file.getbuffer())


def _save_bio(player_slug: str, bio: dict) -> None:
    import json
    player_dir = DATA_DIR / "players" / player_slug
    player_dir.mkdir(parents=True, exist_ok=True)
    with open(player_dir / "bio.json", "w") as f:
        json.dump(bio, f, indent=2)


def _write_report_file(player_slug: str, report_text: str) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / f"{player_slug}_{date.today().isoformat()}.md"
    out_path.write_text(report_text)
    return out_path


st.title("⚾ NCAA D1 Advanced Scouting Model")
st.caption("Upload TrackMan/TruMedia CSVs, generate a full scouting report, and keep every player's data in one place.")

tab_generate, tab_roster, tab_benchmarks = st.tabs(["Generate Report", "Roster", "Benchmarks"])

with tab_generate:
    st.subheader("Player info")
    col1, col2, col3 = st.columns(3)
    with col1:
        player_name = st.text_input("Player name", placeholder="e.g. John Smith")
        school = st.text_input("School", value=DEFAULT_SCHOOL)
    with col2:
        position = st.text_input("Position", placeholder="e.g. SS, RHP")
        conference = st.text_input("Conference", value=DEFAULT_CONF)
    with col3:
        year = st.selectbox("Class", ["", "Fr", "So", "Jr", "Sr", "Gr"])
        bats = st.selectbox("Bats", ["", "R", "L", "S"])
        throws = st.selectbox("Throws", ["", "R", "L"])

    player_type = st.radio("Player type", ["Auto-detect", "Hitter", "Pitcher"], horizontal=True)

    st.subheader("Data")
    st.caption(
        "Upload any combination of a TrackMan/Yakkertech pitch-level export and a TruMedia/box-score "
        "aggregate CSV. Column headers are auto-mapped — see config/column_aliases.yaml if a header "
        "isn't recognized."
    )
    uploaded_files = st.file_uploader("CSV file(s)", type=["csv"], accept_multiple_files=True)

    if st.button("Generate Report", type="primary", disabled=not player_name):
        slug = slugify(player_name)
        for uf in uploaded_files or []:
            _save_upload(slug, uf)

        bio = {
            "name": player_name, "school": school or DEFAULT_SCHOOL, "position": position or "N/A — Insufficient Data",
            "year": year or "N/A — Insufficient Data", "bats": bats or "N/A", "throws": throws or "N/A",
            "conference": conference or DEFAULT_CONF,
        }
        _save_bio(slug, bio)

        ptype = None if player_type == "Auto-detect" else player_type.lower()
        report_text = generate_report(player_name, player_type=ptype, data_dir=DATA_DIR)
        out_path = _write_report_file(slug, report_text)

        st.success(f"Report generated and saved to {out_path.relative_to(Path(__file__).resolve().parent)}")
        st.download_button("Download .md", data=report_text, file_name=out_path.name, mime="text/markdown")
        st.divider()
        st.markdown(report_text)

with tab_roster:
    st.subheader("Everyone currently in data/players/")
    player_dirs = _player_dirs()
    if not player_dirs:
        st.info("No players yet — add one in the Generate Report tab.")
    else:
        for player_dir in player_dirs:
            files = sorted(p.name for p in player_dir.glob("*") if p.is_file())
            with st.expander(f"**{player_dir.name}** — {len(files)} file(s)"):
                st.write(", ".join(files) if files else "No files")
                regen_col1, regen_col2 = st.columns([1, 3])
                with regen_col1:
                    if st.button("Regenerate report", key=f"regen_{player_dir.name}"):
                        report_text = generate_report(player_dir.name, data_dir=DATA_DIR)
                        out_path = _write_report_file(player_dir.name, report_text)
                        st.session_state[f"report_{player_dir.name}"] = report_text
                        st.success(f"Saved to {out_path.name}")
                if st.session_state.get(f"report_{player_dir.name}"):
                    st.download_button(
                        "Download .md", data=st.session_state[f"report_{player_dir.name}"],
                        file_name=f"{player_dir.name}_{date.today().isoformat()}.md",
                        mime="text/markdown", key=f"dl_{player_dir.name}",
                    )
                    st.markdown(st.session_state[f"report_{player_dir.name}"])

with tab_benchmarks:
    st.subheader("D1 reference benchmarks used for grading")
    st.caption(
        "These are calibrated approximations, not an official published percentile table. Update them "
        "with your own conference's real averages whenever you have them — every report generated after "
        "saving picks up the new numbers immediately. Saved to config/benchmarks.local.yaml; delete that "
        "file to fall back to the documented defaults in config/benchmarks.yaml."
    )
    benchmarks = load_benchmarks()

    def _edit_mean_sd_table(section_key: str, section: dict) -> dict:
        updated = {}
        for stat, entry in section.items():
            if not (isinstance(entry, dict) and "mean" in entry and "sd" in entry):
                continue
            c1, c2, c3 = st.columns([2, 1, 1])
            c1.markdown(f"`{stat}`")
            mean = c2.number_input("mean", value=float(entry["mean"]), key=f"{section_key}_{stat}_mean", label_visibility="collapsed")
            sd = c3.number_input("sd", value=float(entry["sd"]), key=f"{section_key}_{stat}_sd", label_visibility="collapsed")
            updated[stat] = {"mean": mean, "sd": sd}
        return updated

    st.markdown("#### Hitting")
    hitting_updated = _edit_mean_sd_table("hitting", benchmarks["hitting"])

    st.markdown("#### Pitching")
    pitching_updated = _edit_mean_sd_table("pitching", benchmarks["pitching"])

    st.markdown("#### Strike zone (feet)")
    sz = benchmarks["strike_zone"]
    z1, z2, z3, z4, z5 = st.columns(5)
    side_min = z1.number_input("side_min", value=float(sz["side_min"]))
    side_max = z2.number_input("side_max", value=float(sz["side_max"]))
    height_min = z3.number_input("height_min", value=float(sz["height_min"]))
    height_max = z4.number_input("height_max", value=float(sz["height_max"]))
    edge_band = z5.number_input("edge_band", value=float(sz["edge_band"]))

    st.markdown("#### Minimum sample sizes")
    ms = benchmarks["min_sample"]
    m1, m2, m3 = st.columns(3)
    pa_min = m1.number_input("pa_for_rate_stats", value=int(ms["pa_for_rate_stats"]), step=1)
    ev_min = m2.number_input("batted_balls_for_ev", value=int(ms["batted_balls_for_ev"]), step=1)
    pitch_min = m3.number_input("pitches_for_pitch_metrics", value=int(ms["pitches_for_pitch_metrics"]), step=1)

    if st.button("Save Benchmarks", type="primary"):
        new_benchmarks = dict(benchmarks)
        new_benchmarks["hitting"] = {**benchmarks["hitting"], **hitting_updated}
        new_benchmarks["pitching"] = {**benchmarks["pitching"], **pitching_updated}
        new_benchmarks["strike_zone"] = {
            "side_min": side_min, "side_max": side_max, "height_min": height_min,
            "height_max": height_max, "edge_band": edge_band,
        }
        new_benchmarks["min_sample"] = {
            "pa_for_rate_stats": pa_min, "batted_balls_for_ev": ev_min, "pitches_for_pitch_metrics": pitch_min,
        }
        path = save_benchmarks_override(new_benchmarks)
        st.success(f"Saved to {path.relative_to(Path(__file__).resolve().parent)}")
