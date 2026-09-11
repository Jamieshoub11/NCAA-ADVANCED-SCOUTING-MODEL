"""Classifies a single pitch-result value into whiff/foul/inplay/no_swing/unknown.

Different export tools describe the same pitch outcome very differently:
  - TrackMan's PitchCall enum: StrikeSwinging, FoulBall, InPlay, StrikeCalled,
    BallCalled, BallinDirt, BallIntentional, HitByPitch.
  - TruMedia's descriptive pitchResult strings: "Ball", "Strike Looking",
    "Strikeout (Swinging)", "Single on a Ground Ball",
    "Home Run on a 412.26 ft Fly Ball", "Fielder's Choice", ...

Rather than merge these into one guessed keyword set, both vocabularies are
matched explicitly from values actually observed in real exports. Anything
that matches neither is classified "unknown" and excluded from swing/whiff
counts rather than silently forced into a bucket — insufficient data stays
insufficient rather than becoming a wrong number.
"""

from __future__ import annotations

import re

# Batted-ball outcome fragments seen in TruMedia's pitchResult strings, plus
# TrackMan's own InPlay tag.
_INPLAY_KEYWORDS = (
    "inplay", "groundout", "flyout", "popout", "lineout", "single", "double",
    "triple", "homerun", "reachedonerror", "fielderschoice", "sacfly",
    "sacbunt", "doubleplay",
)

# Explicit no-swing outcomes: TrackMan's called-ball/called-strike/dead-ball
# tags, plus TruMedia's "Strike Looking" / "Strikeout (Looking)" / "Walk" /
# "Hit By Pitch". Checked as substrings after non-letters are stripped.
_NO_SWING_KEYWORDS = (
    "strikecalled", "ballcalled", "ballindirt", "ballintentional",
    "strikelooking", "strikeoutlooking", "walk", "hitbypitch",
)


def _normalize(raw) -> str:
    return re.sub(r"[^a-z]", "", str(raw).lower())


def classify(raw) -> str:
    """Returns one of: 'whiff', 'foul', 'inplay', 'no_swing', 'unknown'."""
    norm = _normalize(raw)
    if not norm:
        return "unknown"
    if "swinging" in norm:
        return "whiff"
    if "foul" in norm:
        return "foul"
    if norm == "ball":
        return "no_swing"
    if any(k in norm for k in _NO_SWING_KEYWORDS):
        return "no_swing"
    if any(k in norm for k in _INPLAY_KEYWORDS):
        return "inplay"
    return "unknown"


def is_swing(raw) -> bool:
    return classify(raw) in ("whiff", "foul", "inplay")


def is_whiff(raw) -> bool:
    return classify(raw) == "whiff"


def is_inplay(raw) -> bool:
    return classify(raw) == "inplay"


_CALLED_STRIKE_KEYWORDS = ("strikecalled", "strikelooking", "strikeoutlooking")
_CALLED_BALL_KEYWORDS = ("ballcalled", "ballindirt", "ballintentional", "walk")


def no_swing_detail(raw) -> str | None:
    """For pitches classify() marks 'no_swing', distinguishes a called
    strike from a called ball/take (needed to calibrate a zone boundary from
    umpire ground truth — see zone_calibration.py). Returns 'called_strike',
    'called_ball', 'hbp', or None (not a no-swing pitch, or an unrecognized
    no-swing value that shouldn't be guessed into either bucket).
    """
    if classify(raw) != "no_swing":
        return None
    norm = _normalize(raw)
    if "hitbypitch" in norm:
        return "hbp"
    if norm == "ball" or any(k in norm for k in _CALLED_BALL_KEYWORDS):
        return "called_ball"
    if any(k in norm for k in _CALLED_STRIKE_KEYWORDS):
        return "called_strike"
    return None
