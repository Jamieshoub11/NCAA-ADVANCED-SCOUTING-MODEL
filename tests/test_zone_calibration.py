import numpy as np
import pandas as pd

from ncaa_scout.zone_calibration import calibrate_trumedia_zone, edge_mask, get_zone_columns, in_zone_mask
from ncaa_scout.io_utils import load_benchmarks


def _synthetic_trumedia_df(n=300, seed=1):
    """Called strikes cluster tightly near (0,0); called balls scatter more
    widely — the same signature validated against real Conner Griffin data."""
    rng = np.random.default_rng(seed)
    n_strikes = n // 3
    n_balls = n - n_strikes
    strike_x = rng.normal(0, 0.7, n_strikes)
    strike_y = rng.normal(0, 0.5, n_strikes)
    ball_x = rng.normal(0, 1.6, n_balls)
    ball_y = rng.normal(0, 1.6, n_balls)
    return pd.DataFrame({
        "trumedia_loc_x": np.concatenate([strike_x, ball_x]),
        "trumedia_loc_y": np.concatenate([strike_y, ball_y]),
        "pitch_call": ["Strike Looking"] * n_strikes + ["Ball"] * n_balls,
    })


def test_calibration_beats_majority_baseline():
    df = _synthetic_trumedia_df()
    calibration = calibrate_trumedia_zone(df)
    assert calibration is not None
    v = calibration["validation"]
    assert v["held_out"] is True
    assert v["accuracy"] > v["baseline_accuracy"]


def test_calibration_returns_none_below_min_sample():
    df = _synthetic_trumedia_df(n=20)
    assert calibrate_trumedia_zone(df) is None


def test_calibration_returns_none_without_both_classes():
    df = pd.DataFrame({
        "trumedia_loc_x": np.zeros(60), "trumedia_loc_y": np.zeros(60),
        "pitch_call": ["Ball"] * 60,  # no called strikes at all
    })
    assert calibrate_trumedia_zone(df) is None


def test_in_zone_mask_is_nullable_boolean_dtype_not_object():
    """Regression test for the real bug: an object-dtype column of Python
    True/False/NaN makes `~` do bitwise complement (~True == -2) instead of
    logical negation, corrupting every downstream 'out of zone' filter."""
    df = _synthetic_trumedia_df()
    df.loc[0, "trumedia_loc_y"] = np.nan  # force a missing-location row
    calibration = calibrate_trumedia_zone(df)
    mask = in_zone_mask(df, calibration)
    assert str(mask.dtype) == "boolean"
    # ~ must behave as logical negation on the located subset, not bitwise complement
    located = mask[mask.notna()]
    inverted = ~located
    assert set(inverted.unique()) <= {True, False}


def test_edge_mask_is_nullable_boolean_dtype():
    df = _synthetic_trumedia_df()
    calibration = calibrate_trumedia_zone(df)
    mask = edge_mask(df, calibration)
    assert str(mask.dtype) == "boolean"


def test_get_zone_columns_trackman_path_handles_missing_location_rows():
    """Same regression, via the TrackMan feet-based path with some rows
    missing plate_loc_side/height (common in real exports)."""
    df = pd.DataFrame({
        "plate_loc_side": [0.0, 0.5, np.nan, -2.0, 0.1],
        "plate_loc_height": [2.5, 2.0, 2.5, np.nan, 2.5],
        "pitch_call": ["Ball", "StrikeCalled", "Ball", "BallCalled", "InPlay"],
    })
    in_zone, is_edge, calibration = get_zone_columns(df, load_benchmarks())
    assert calibration is None
    assert str(in_zone.dtype) == "boolean"
    located = in_zone[in_zone.notna()]
    assert len(located) == 3  # two rows have missing location and stay NA
    inverted = ~located  # must not raise / must not produce ints
    assert set(inverted.unique()) <= {True, False}


def test_get_zone_columns_none_when_no_location_present():
    df = pd.DataFrame({"pitch_call": ["Ball", "StrikeCalled"]})
    in_zone, is_edge, calibration = get_zone_columns(df, load_benchmarks())
    assert in_zone is None and is_edge is None and calibration is None
