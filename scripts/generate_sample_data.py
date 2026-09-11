#!/usr/bin/env python3
"""Generates the synthetic demo data under data/sample/. Not real player data —
purely for exercising the pipeline end-to-end. Re-run any time to regenerate.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = REPO_ROOT / "data" / "sample" / "players"

rng = np.random.default_rng(42)


def make_hitter_data():
    player_dir = SAMPLE_DIR / "sample_hitter"
    player_dir.mkdir(parents=True, exist_ok=True)

    bio = {
        "name": "Sample Hitter", "school": "Demo State University", "position": "SS",
        "year": "Jr", "bats": "R", "throws": "R", "conference": "Demo Conference",
    }
    (player_dir / "bio.json").write_text(json.dumps(bio, indent=2))

    ab, bb, hbp, sf, so = 180, 28, 4, 3, 38
    b2, b3, hr = 12, 2, 9
    h = 58
    pa = ab + bb + hbp + sf
    boxscore = pd.DataFrame([{
        "PA": pa, "AB": ab, "H": h, "2B": b2, "3B": b3, "HR": hr,
        "BB": bb, "HBP": hbp, "SO": so, "SF": sf, "R": 34, "RBI": 31, "SB": 9, "CS": 3,
    }])
    boxscore.to_csv(player_dir / "boxscore.csv", index=False)

    n_pitches = 260
    pitch_types = rng.choice(["Fastball", "Slider", "Changeup", "Curveball"], size=n_pitches, p=[0.55, 0.22, 0.13, 0.10])
    loc_side = rng.normal(0, 0.7, n_pitches)
    loc_height = rng.normal(2.5, 0.7, n_pitches)
    in_zone = (np.abs(loc_side) <= 0.83) & (loc_height >= 1.5) & (loc_height <= 3.5)

    swing_prob = np.where(in_zone, 0.68, 0.28)
    is_swing = rng.random(n_pitches) < swing_prob
    whiff_prob = np.where(pitch_types == "Slider", 0.34, np.where(pitch_types == "Curveball", 0.30, 0.20))
    is_whiff = is_swing & (rng.random(n_pitches) < whiff_prob)
    is_foul = is_swing & ~is_whiff & (rng.random(n_pitches) < 0.45)
    is_inplay = is_swing & ~is_whiff & ~is_foul

    pitch_call = np.select(
        [is_whiff, is_foul, is_inplay, in_zone & ~is_swing, ~in_zone & ~is_swing],
        ["StrikeSwinging", "FoulBall", "InPlay", "StrikeCalled", "BallCalled"],
        default="BallCalled",
    )

    exit_speed = np.where(is_inplay, np.clip(rng.normal(93, 9, n_pitches), 55, 112), np.nan)
    angle = np.where(is_inplay, rng.normal(14, 12, n_pitches), np.nan)

    df = pd.DataFrame({
        "Batter": "Sample Hitter",
        "PitchType": pitch_types,
        "PlateLocSide": loc_side,
        "PlateLocHeight": loc_height,
        "PitchCall": pitch_call,
        "ExitSpeed": exit_speed,
        "Angle": angle,
    })
    df.to_csv(player_dir / "trackman.csv", index=False)


def make_pitcher_data():
    player_dir = SAMPLE_DIR / "sample_pitcher"
    player_dir.mkdir(parents=True, exist_ok=True)

    bio = {
        "name": "Sample Pitcher", "school": "Demo State University", "position": "RHP",
        "year": "So", "bats": "R", "throws": "R", "conference": "Demo Conference",
    }
    (player_dir / "bio.json").write_text(json.dumps(bio, indent=2))

    ip, bf, h, er, bb, so, hr_allowed = 62.0, 260, 51, 24, 22, 74, 6
    boxscore = pd.DataFrame([{
        "IP": ip, "BF": bf, "H": h, "ER": er, "BB": bb, "SO": so, "HR": hr_allowed, "R": 27,
    }])
    boxscore.to_csv(player_dir / "boxscore.csv", index=False)

    n_pitches = 420
    pitch_types = rng.choice(["Fastball", "Slider", "Changeup"], size=n_pitches, p=[0.58, 0.27, 0.15])

    rel_speed = np.select(
        [pitch_types == "Fastball", pitch_types == "Slider", pitch_types == "Changeup"],
        [rng.normal(92.5, 1.4, n_pitches), rng.normal(83.5, 1.6, n_pitches), rng.normal(84.0, 1.7, n_pitches)],
    )
    spin_rate = np.select(
        [pitch_types == "Fastball", pitch_types == "Slider", pitch_types == "Changeup"],
        [rng.normal(2280, 90, n_pitches), rng.normal(2450, 110, n_pitches), rng.normal(1750, 100, n_pitches)],
    )
    ivb = np.select(
        [pitch_types == "Fastball", pitch_types == "Slider", pitch_types == "Changeup"],
        [rng.normal(16, 1.5, n_pitches), rng.normal(2, 2.0, n_pitches), rng.normal(7, 1.8, n_pitches)],
    )
    hvb = np.select(
        [pitch_types == "Fastball", pitch_types == "Slider", pitch_types == "Changeup"],
        [rng.normal(8, 1.5, n_pitches), rng.normal(-4, 2.0, n_pitches), rng.normal(12, 1.8, n_pitches)],
    )
    rel_height = rng.normal(5.9, 0.15, n_pitches)
    rel_side = rng.normal(1.8, 0.15, n_pitches)
    extension = rng.normal(6.1, 0.2, n_pitches)

    loc_side = rng.normal(0, 0.75, n_pitches)
    loc_height = rng.normal(2.4, 0.75, n_pitches)
    in_zone = (np.abs(loc_side) <= 0.83) & (loc_height >= 1.5) & (loc_height <= 3.5)

    swing_prob = np.where(in_zone, 0.62, 0.30)
    is_swing = rng.random(n_pitches) < swing_prob
    whiff_prob = np.select(
        [pitch_types == "Slider", pitch_types == "Changeup"],
        [0.38, 0.30], default=0.18,
    )
    is_whiff = is_swing & (rng.random(n_pitches) < whiff_prob)
    is_foul = is_swing & ~is_whiff & (rng.random(n_pitches) < 0.45)
    is_inplay = is_swing & ~is_whiff & ~is_foul

    pitch_call = np.select(
        [is_whiff, is_foul, is_inplay, in_zone & ~is_swing, ~in_zone & ~is_swing],
        ["StrikeSwinging", "FoulBall", "InPlay", "StrikeCalled", "BallCalled"],
        default="BallCalled",
    )

    df = pd.DataFrame({
        "Pitcher": "Sample Pitcher",
        "PitchType": pitch_types,
        "RelSpeed": rel_speed,
        "SpinRate": spin_rate,
        "InducedVertBreak": ivb,
        "HorzBreak": hvb,
        "RelHeight": rel_height,
        "RelSide": rel_side,
        "Extension": extension,
        "PlateLocSide": loc_side,
        "PlateLocHeight": loc_height,
        "PitchCall": pitch_call,
    })
    df.to_csv(player_dir / "trackman.csv", index=False)


if __name__ == "__main__":
    make_hitter_data()
    make_pitcher_data()
    print(f"Sample data written under {SAMPLE_DIR}")
