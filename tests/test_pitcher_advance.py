import pandas as pd

from ncaa_scout.pitcher_advance import (
    build_attack_findings, sequencing_transitions, usage_by_count,
    usage_by_handedness, usage_by_situation, whiff_pct_by_group,
)


def _row(game_id, ab, pitch_num, pitch_type, count, hand, call):
    return {
        "game_id": game_id, "ab_num_in_game": ab, "pitch_num_in_ab": pitch_num,
        "pitch_type": pitch_type, "ball_strike_count": count,
        "batter_hand": hand, "pitch_call": call,
    }


def test_usage_by_count_basic():
    df = pd.DataFrame([
        _row(1, 1, 1, "Fastball", "0-0", "R", "Ball"),
        _row(1, 1, 2, "Fastball", "1-0", "R", "Ball"),
        _row(1, 2, 1, "Slider", "0-0", "R", "Ball"),
    ])
    table = usage_by_count(df)
    first_pitch = table[table["group"] == "0-0"]
    assert set(first_pitch["pitch_type"]) == {"Fastball", "Slider"}
    assert first_pitch[first_pitch["pitch_type"] == "Fastball"]["n_pitch"].iloc[0] == 1


def test_usage_by_handedness_basic():
    df = pd.DataFrame([
        _row(1, 1, 1, "Fastball", "0-0", "L", "Ball"),
        _row(1, 2, 1, "Fastball", "0-0", "R", "Ball"),
        _row(1, 3, 1, "Slider", "0-0", "R", "Ball"),
    ])
    table = usage_by_handedness(df)
    vs_r = table[table["group"] == "R"]
    assert vs_r["n_group"].iloc[0] == 2


def test_situations_overlap_correctly():
    """A 0-2 count is both 'Pitcher Ahead' and 'Two Strikes' — both buckets
    must see it (this was a real bug: first-match-wins logic made 'Two
    Strikes' unreachable since every 2-strike count also matches an earlier
    bucket)."""
    df = pd.DataFrame([_row(1, i, 1, "Slider", "0-2", "R", "Foul") for i in range(5)])
    table = usage_by_situation(df)
    groups_present = set(table["group"])
    assert "Pitcher Ahead" in groups_present
    assert "Two Strikes" in groups_present


def test_sequencing_transitions():
    df = pd.DataFrame([
        _row(1, 1, 1, "Fastball", "0-0", "R", "Ball"),
        _row(1, 1, 2, "Slider", "1-0", "R", "Foul"),
        _row(1, 1, 3, "Fastball", "1-1", "R", "InPlay"),
        _row(1, 2, 1, "Fastball", "0-0", "R", "Ball"),
        _row(1, 2, 2, "Slider", "1-0", "R", "InPlay"),
    ])
    seq = sequencing_transitions(df)
    from_fastball = seq[seq["prev_pitch"] == "Fastball"]
    assert set(from_fastball["next_pitch"]) == {"Slider"}
    assert from_fastball["n_prev_total"].iloc[0] == 2


def test_whiff_pct_by_group():
    df = pd.DataFrame([
        _row(1, 1, 1, "Slider", "0-0", "R", "Strike Swinging"),
        _row(1, 1, 2, "Slider", "0-1", "R", "Foul"),
        _row(1, 2, 1, "Slider", "0-0", "R", "Ball"),  # not a swing, excluded from swing denominator
    ])
    table = whiff_pct_by_group(df, [], min_swings=1)
    row = table[table["pitch_type"] == "Slider"].iloc[0]
    assert row["n_swings"] == 2  # Strike Swinging + Foul, Ball excluded
    assert row["whiff_pct"] == 0.5


def test_build_attack_findings_does_not_crash_on_small_sample():
    df = pd.DataFrame([_row(1, 1, 1, "Fastball", "0-0", "R", "Ball")])
    findings = build_attack_findings(df)
    assert isinstance(findings, list)


def test_build_attack_findings_empty_df():
    assert build_attack_findings(pd.DataFrame()) == []
