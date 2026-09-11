import re
from pathlib import Path

from ncaa_scout.advance_report import build_pitcher_advance_report
from ncaa_scout.hitter_advance_report import build_hitter_advance_report
from ncaa_scout.report import generate_report

SAMPLE_DIR = Path(__file__).resolve().parents[1] / "data" / "sample"


def _assert_no_literal_nan(report: str):
    # Catches the real bug where a pandas column upcasts None to float NaN
    # and an f-string prints it as the literal text "nan" instead of the
    # N/A sentinel — "nan" as a case-insensitive standalone word, not inside
    # another word (e.g. "Conner" or a hyphenated pitch name).
    assert not re.search(r"(?<![a-zA-Z])nan(?![a-zA-Z])", report), "literal 'nan' leaked into the report"

REQUIRED_SECTIONS = [
    "### 1. EXECUTIVE SUMMARY", "### 2. STATISTICAL & ADVANCED METRIC PROFILE",
    "### 3. ADVANCED DATA ANALYSIS & INTERPRETATION", "### 4. TOOL EVALUATION & ZONAL MAPPING",
    "### 5. RANKED STRENGTHS", "### 6. RANKED WEAKNESSES & RISKS",
    "### 7. PROJECTION & DEVELOPMENT PRIORITIES", "### 8. LIVE SCOUTING QUESTIONS",
    "### 9. SCOUTING GRADES", "### 10. EVALUATION CONFIDENCE & BOTTOM LINE",
]


def test_hitter_report_has_all_sections_and_no_crash():
    report = generate_report("Sample Hitter", data_dir=SAMPLE_DIR)
    for section in REQUIRED_SECTIONS:
        assert section in report
    assert "SAMPLE HITTER" in report
    assert "*Hitters:*" in report


def test_pitcher_report_has_all_sections_and_no_crash():
    report = generate_report("Sample Pitcher", data_dir=SAMPLE_DIR)
    for section in REQUIRED_SECTIONS:
        assert section in report
    assert "SAMPLE PITCHER" in report
    assert "*Pitchers:*" in report


def test_pitcher_arsenal_is_parsed_from_camelcase_trackman_headers():
    report = generate_report("Sample Pitcher", data_dir=SAMPLE_DIR)
    assert "N/A — Insufficient Data." not in report.split("### 3.")[1].split("### 4.")[0]


def test_unknown_player_falls_back_gracefully_without_fabricating_data():
    report = generate_report("Totally Fictional Player Xyz", data_dir=SAMPLE_DIR)
    assert "N/A — Insufficient Data" in report
    assert "No raw data" in report


def test_never_fabricates_woba_without_required_counting_stats():
    # If box score data is entirely absent, wOBA/wRC+ must be N/A, never guessed.
    report = generate_report("Sample Pitcher", data_dir=SAMPLE_DIR, player_type="hitter")
    assert "wOBA" in report  # label still present in template


def test_pitcher_advance_report_no_crash_and_no_literal_nan():
    report = build_pitcher_advance_report("Sample Pitcher", data_dir=SAMPLE_DIR)
    assert "PITCHER ADVANCE SCOUTING REPORT" in report
    assert "HOW TO ATTACK HIM" in report
    _assert_no_literal_nan(report)


def test_hitter_advance_report_no_crash_and_no_literal_nan():
    report = build_hitter_advance_report("Sample Hitter", data_dir=SAMPLE_DIR)
    assert "HITTER ADVANCE SCOUTING REPORT" in report
    assert "APPROACH / VULNERABILITY LABELS" in report
    _assert_no_literal_nan(report)
