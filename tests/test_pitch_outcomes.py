from ncaa_scout.pitch_outcomes import classify, is_swing, is_whiff, is_inplay

# TrackMan's PitchCall enum
TRACKMAN_CASES = {
    "StrikeSwinging": "whiff", "FoulBall": "foul", "InPlay": "inplay",
    "StrikeCalled": "no_swing", "BallCalled": "no_swing",
    "BallinDirt": "no_swing", "BallIntentional": "no_swing",
}

# Every distinct value actually observed in a real TruMedia pitchResult export
TRUMEDIA_CASES = {
    "Ball": "no_swing", "Foul": "foul",
    "Ground Out": "inplay", "Strike Looking": "no_swing",
    "Strikeout (Looking)": "no_swing", "Single on a Line Drive": "inplay",
    "Strike Swinging": "whiff", "Strikeout (Swinging)": "whiff",
    "Fly Out": "inplay", "Walk": "no_swing", "Hit By Pitch": "no_swing",
    "Home Run on a 412.26 ft Fly Ball": "inplay",
    "Double on a Fly Ball": "inplay", "Pop Out": "inplay",
    "Single on a Ground Ball": "inplay", "Line Out": "inplay",
    "Double on a Line Drive": "inplay", "Single on a Fly Ball": "inplay",
    "Double on a Ground Ball": "inplay", "Sac Fly": "inplay",
    "Reached on Error on a Ground Ball": "inplay", "Sac Bunt": "inplay",
    "Single on a Bunt Ground Ball": "inplay", "Double Play": "inplay",
    "Fielder's Choice": "inplay", "Double on a Pop Up": "inplay",
}


def test_trackman_vocabulary():
    for raw, expected in TRACKMAN_CASES.items():
        assert classify(raw) == expected, raw


def test_trumedia_vocabulary():
    for raw, expected in TRUMEDIA_CASES.items():
        assert classify(raw) == expected, raw


def test_unrecognized_value_is_unknown_not_guessed():
    assert classify("Some Totally New Export Tool's Weird Tag") == "unknown"
    assert classify(None) == "unknown"
    assert classify(float("nan")) == "unknown"


def test_is_swing_helpers():
    assert is_swing("Strikeout (Swinging)") is True
    assert is_whiff("Strikeout (Swinging)") is True
    assert is_inplay("Strikeout (Swinging)") is False
    assert is_swing("Ball") is False
    assert is_swing("Strike Looking") is False
    assert is_inplay("Ground Out") is True
