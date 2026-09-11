from ncaa_scout.grading import grade_from_value


def test_grade_at_mean_is_50():
    assert grade_from_value(100, mean=100, sd=10) == 50


def test_grade_one_sd_above_is_60():
    assert grade_from_value(110, mean=100, sd=10) == 60


def test_grade_one_sd_below_is_40():
    assert grade_from_value(90, mean=100, sd=10) == 40


def test_grade_clips_at_80():
    assert grade_from_value(1000, mean=100, sd=10) == 80


def test_grade_clips_at_20():
    assert grade_from_value(-1000, mean=100, sd=10) == 20


def test_lower_is_better_inverts_direction():
    # a below-mean value should grade as a plus tool when lower is better (e.g. K% or Whiff%)
    assert grade_from_value(90, mean=100, sd=10, lower_is_better=True) == 60
    assert grade_from_value(110, mean=100, sd=10, lower_is_better=True) == 40


def test_grade_none_when_value_missing():
    assert grade_from_value(None, mean=100, sd=10) is None


def test_grade_none_when_sd_zero():
    assert grade_from_value(100, mean=100, sd=0) is None
