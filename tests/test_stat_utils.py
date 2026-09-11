from ncaa_scout.stat_utils import safe_div, fmt, fmt_avg, fmt_pct, NA_TEXT


def test_safe_div_basic():
    assert safe_div(10, 4) == 2.5


def test_safe_div_none_inputs():
    assert safe_div(None, 4) is None
    assert safe_div(10, None) is None


def test_safe_div_zero_denominator():
    assert safe_div(10, 0) is None


def test_fmt_none_is_na():
    assert fmt(None) == NA_TEXT


def test_fmt_avg_strips_leading_zero():
    assert fmt_avg(0.322) == ".322"


def test_fmt_avg_none_is_na():
    assert fmt_avg(None) == NA_TEXT


def test_fmt_pct():
    assert fmt_pct(0.245) == "24.5%"
    assert fmt_pct(None) == NA_TEXT
