import pandas as pd

from ncaa_scout.io_utils import apply_column_aliases, load_column_aliases, slugify, classify_csv


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
