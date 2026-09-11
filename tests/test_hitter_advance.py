import pandas as pd

from ncaa_scout.hitter_advance import (
    approach_by_count, approach_by_situation, performance_vs_pitch_type,
    performance_vs_pitcher_hand, performance_vs_velocity_band, vulnerability_labels,
)
from ncaa_scout.io_utils import load_benchmarks


def _row(pitch_type, hand, call, rel_speed, count, exit_speed=None):
    return {
        "batter_name": "Sample Hitter", "pitch_type": pitch_type, "pitcher_hand": hand,
        "pitch_call": call, "rel_speed": rel_speed, "ball_strike_count": count,
        "exit_speed": exit_speed,
    }


def test_performance_vs_pitcher_hand_splits_correctly():
    df = pd.DataFrame([
        _row("Fastball", "R", "Ball", 92, "0-0"),
        _row("Fastball", "L", "Strike Swinging", 88, "0-1"),
    ])
    table = performance_vs_pitcher_hand(df)
    assert set(table["group"]) == {"R", "L"}
    l_row = table[table["group"] == "L"].iloc[0]
    assert l_row["n_swings"] == 1
    assert l_row["whiff_pct"] == 1.0


def test_performance_vs_pitch_type_whiff_rate():
    df = pd.DataFrame([
        _row("Slider", "R", "Strike Swinging", 84, "0-1"),
        _row("Slider", "R", "Foul", 85, "1-1"),
        _row("Slider", "R", "Ball", 83, "2-1"),  # not a swing
    ])
    table = performance_vs_pitch_type(df)
    row = table[table["group"] == "Slider"].iloc[0]
    assert row["n_swings"] == 2
    assert row["whiff_pct"] == 0.5


def test_performance_vs_velocity_band_buckets_correctly():
    df = pd.DataFrame([
        _row("Fastball", "R", "Foul", 96, "0-0"),
        _row("Fastball", "R", "Ball", 91, "1-0"),
        _row("Fastball", "R", "Ball", 88, "1-1"),
    ])
    table = performance_vs_velocity_band(df)
    groups = set(table["group"])
    assert groups == {"95+ mph", "90-94.9 mph", "< 90 mph"}


def test_approach_by_count_and_situation_no_crash_and_overlap():
    df = pd.DataFrame([_row("Slider", "R", "Foul", 85, "0-2") for _ in range(5)])
    by_count = approach_by_count(df)
    assert not by_count.empty
    by_situation = approach_by_situation(df)
    groups = set(by_situation["group"])
    assert "Pitcher Ahead" in groups
    assert "Two Strikes" in groups


def test_vulnerability_labels_never_forces_a_label_on_tiny_sample():
    df = pd.DataFrame([_row("Fastball", "R", "Ball", 92, "0-0")])
    labels = vulnerability_labels(df, load_benchmarks())
    real_labels = [l for l in labels if "N/A" not in l["label"]]
    assert real_labels == []


def test_vulnerability_labels_no_batted_ball_columns_does_not_crash():
    df = pd.DataFrame([{"batter_name": "X", "pitch_type": "Fastball", "pitch_call": "Ball", "ball_strike_count": "0-0"}])
    labels = vulnerability_labels(df, load_benchmarks())
    assert isinstance(labels, list)
