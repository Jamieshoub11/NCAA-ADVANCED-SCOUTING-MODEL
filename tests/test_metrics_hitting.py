import pytest

from ncaa_scout.metrics_hitting import slash_line, woba, wrc_plus
from ncaa_scout.io_utils import load_benchmarks

COUNTS = {
    "pa": 215, "ab": 180, "h": 58, "b1": 35, "b2": 12, "b3": 2, "hr": 9,
    "bb": 28, "ibb": 0, "hbp": 4, "so": 38, "sf": 3, "sh": 0,
}


def test_slash_line_matches_hand_calculation():
    line = slash_line(COUNTS)
    assert line["avg"] == pytest.approx(58 / 180, abs=1e-6)
    assert line["obp"] == pytest.approx((58 + 28 + 4) / (180 + 28 + 4 + 3), abs=1e-6)
    assert line["slg"] == pytest.approx((35 + 24 + 6 + 36) / 180, abs=1e-6)
    assert line["ops"] == pytest.approx(line["obp"] + line["slg"], abs=1e-9)
    assert line["iso"] == pytest.approx(line["slg"] - line["avg"], abs=1e-9)
    assert line["babip"] == pytest.approx((58 - 9) / (180 - 38 - 9 + 3), abs=1e-6)
    assert line["k_pct"] == pytest.approx(38 / 215, abs=1e-6)
    assert line["bb_pct"] == pytest.approx(28 / 215, abs=1e-6)


def test_slash_line_returns_none_when_missing_ab():
    line = slash_line({f: None for f in COUNTS})
    assert line["avg"] is None
    assert line["obp"] is None
    assert line["slg"] is None


def test_woba_matches_hand_calculation():
    weights = load_benchmarks()["hitting"]["linear_weights"]
    value = woba(COUNTS, weights)
    expected_num = weights["bb"] * 28 + weights["hbp"] * 4 + weights["b1"] * 35 + weights["b2"] * 12 + weights["b3"] * 2 + weights["hr"] * 9
    expected_den = 180 + 28 + 3 + 4
    assert value == pytest.approx(expected_num / expected_den, abs=1e-6)


def test_woba_none_when_component_missing():
    incomplete = {**COUNTS, "hbp": None}
    assert woba(incomplete, load_benchmarks()["hitting"]["linear_weights"]) is None


def test_wrc_plus_increases_with_woba():
    hb = load_benchmarks()["hitting"]
    low = wrc_plus(0.300, 200, hb)
    high = wrc_plus(0.450, 200, hb)
    assert high > low


def test_wrc_plus_none_without_pa():
    hb = load_benchmarks()["hitting"]
    assert wrc_plus(0.350, None, hb) is None
    assert wrc_plus(None, 200, hb) is None
