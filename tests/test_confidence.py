from ncaa_scout.confidence import HIGH, INSUFFICIENT, LOW, MODERATE, confidence_tier


def test_thresholds():
    assert confidence_tier(5) == INSUFFICIENT
    assert confidence_tier(9) == INSUFFICIENT
    assert confidence_tier(10) == LOW
    assert confidence_tier(29) == LOW
    assert confidence_tier(30) == MODERATE
    assert confidence_tier(74) == MODERATE
    assert confidence_tier(75) == HIGH
    assert confidence_tier(1000) == HIGH


def test_zero_n_is_insufficient():
    assert confidence_tier(0) == INSUFFICIENT
