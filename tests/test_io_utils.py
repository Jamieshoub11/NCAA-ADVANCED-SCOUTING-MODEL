import pandas as pd
import pytest

from ncaa_scout.io_utils import (
    apply_column_aliases, load_column_aliases, slugify, classify_csv,
    load_bio, load_benchmarks, save_benchmarks_override, CONFIG_DIR,
)


def test_camelcase_trackman_headers_map_to_canonical_names():
    df = pd.DataFrame([{
        "Pitcher": "Jane Doe", "PitchType": "Fastball", "RelSpeed": 92.1,
        "PlateLocSide": 0.1, "PlateLocHeight": 2.4, "PitchCall": "InPlay", "ExitSpeed": 98.0,
    }])
    aliases = load_column_aliases()
    mapped = apply_column_aliases(df, aliases)
    assert set(["pitcher_name", "pitch_type", "rel_speed", "plate_loc_side",
                "plate_loc_height", "pitch_call", "exit_speed"]) <= set(mapped.columns)


def test_slugify():
    assert slugify("John Smith Jr.") == "john_smith_jr"
    assert slugify("  Jane   Doe  ") == "jane_doe"


def test_classify_csv_pitch_level():
    df = pd.DataFrame([{"rel_speed": 90.0, "plate_loc_side": 0.0}])
    assert classify_csv(df) == "pitch_level"


def test_classify_csv_boxscore():
    df = pd.DataFrame([{"ab": 4, "h": 2}])
    assert classify_csv(df) == "boxscore"


def test_classify_csv_unknown():
    df = pd.DataFrame([{"some_note": "text"}])
    assert classify_csv(df) == "unknown"


def test_load_bio_falls_back_to_team_defaults_without_bio_json(tmp_path):
    bio = load_bio("Totally New Player Nobody Has A Folder For", data_dir=tmp_path)
    assert bio.school == "Binghamton University"
    assert bio.conference == "America East"


@pytest.fixture
def clean_benchmarks_override():
    override_path = CONFIG_DIR / "benchmarks.local.yaml"
    assert not override_path.exists(), "a stray benchmarks.local.yaml would make this test invalid"
    yield override_path
    if override_path.exists():
        override_path.unlink()


def test_benchmarks_override_round_trip(clean_benchmarks_override):
    base = load_benchmarks()
    edited = dict(base)
    edited["hitting"] = {**base["hitting"], "avg": {"mean": 0.999, "sd": 0.111}}

    saved_path = save_benchmarks_override(edited)
    assert saved_path == clean_benchmarks_override
    assert saved_path.exists()

    reloaded = load_benchmarks()
    assert reloaded["hitting"]["avg"]["mean"] == 0.999
    assert reloaded["hitting"]["avg"]["sd"] == 0.111
    # untouched sections still come through from the documented defaults
    assert reloaded["strike_zone"]["side_min"] == base["strike_zone"]["side_min"]
