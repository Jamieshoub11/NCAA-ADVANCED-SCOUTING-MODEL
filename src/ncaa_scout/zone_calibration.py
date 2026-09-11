"""Derives a strike-zone boundary from whichever location convention a file
actually provides, rather than assuming one.

TrackMan-style exports give plate_loc_side/plate_loc_height in feet, centered
at the plate — the fixed rectangle in config/benchmarks.yaml's strike_zone
applies directly.

TruMedia's "Movement" export instead gives x/y (aka PXNorm/PZNorm) in some
normalized, evidently per-batter-adjusted unit — not feet, and not something
to guess at. Instead, this calibrates a zone rectangle empirically from that
SAME file's own umpire ball/strike calls: a called strike is objective
ground truth that the pitch was in the zone regardless of what unit x/y are
in, and a called ball (excluding borderline take calls) is ground truth it
wasn't. Validated on Conner Griffin's real data: an 88% held-out accuracy
zone classifier vs. a 74% majority-class baseline (see the commit introducing
this file for the full train/test evaluation). Every calibration is re-fit
per file/player rather than hardcoded, and refuses to run below a minimum
sample size rather than fit noise.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import pitch_outcomes as po

MIN_N_TO_CALIBRATE = 50
MIN_N_FOR_HELDOUT_VALIDATION = 100
PERCENTILE = 5.0


def _labeled_called_pitches(df: pd.DataFrame, x_col: str, y_col: str) -> pd.DataFrame:
    if not {x_col, y_col, "pitch_call"} <= set(df.columns):
        return pd.DataFrame()
    detail = df["pitch_call"].map(po.no_swing_detail)
    labeled = df[detail.isin(("called_strike", "called_ball"))].copy()
    labeled["is_strike"] = (detail[labeled.index] == "called_strike").astype(int)
    labeled[x_col] = pd.to_numeric(labeled[x_col], errors="coerce")
    labeled[y_col] = pd.to_numeric(labeled[y_col], errors="coerce")
    return labeled.dropna(subset=[x_col, y_col])


def _fit_rectangle(strikes: pd.DataFrame, x_col: str, y_col: str, percentile: float = PERCENTILE) -> dict:
    x_lo, x_hi = np.percentile(strikes[x_col], [percentile, 100 - percentile])
    y_lo, y_hi = np.percentile(strikes[y_col], [percentile, 100 - percentile])
    return {"x_lo": float(x_lo), "x_hi": float(x_hi), "y_lo": float(y_lo), "y_hi": float(y_hi)}


def _evaluate(rect: dict, data: pd.DataFrame, x_col: str, y_col: str) -> dict:
    pred = data[x_col].between(rect["x_lo"], rect["x_hi"]) & data[y_col].between(rect["y_lo"], rect["y_hi"])
    truth = data["is_strike"].astype(bool)
    tp = int((pred & truth).sum())
    tn = int((~pred & ~truth).sum())
    fp = int((pred & ~truth).sum())
    fn = int((~pred & truth).sum())
    n = len(data)
    return {
        "n": n, "accuracy": (tp + tn) / n if n else None,
        "precision": tp / (tp + fp) if (tp + fp) else None,
        "recall": tp / (tp + fn) if (tp + fn) else None,
        "baseline_accuracy": float((~truth).mean()) if n else None,
    }


def calibrate_trumedia_zone(df: pd.DataFrame, x_col: str = "trumedia_loc_x", y_col: str = "trumedia_loc_y",
                             seed: int = 42) -> dict | None:
    """Returns a calibration dict with the fitted rectangle and (when there
    was enough data for a held-out split) validation metrics, or None if
    there weren't enough called pitches to calibrate at all.
    """
    labeled = _labeled_called_pitches(df, x_col, y_col)
    n_labeled = len(labeled)
    if n_labeled < MIN_N_TO_CALIBRATE or labeled["is_strike"].sum() < 10 or (labeled["is_strike"] == 0).sum() < 10:
        return None

    if n_labeled >= MIN_N_FOR_HELDOUT_VALIDATION:
        rng = np.random.default_rng(seed)
        idx = rng.permutation(n_labeled)
        n_train = int(n_labeled * 0.7)
        train, test = labeled.iloc[idx[:n_train]], labeled.iloc[idx[n_train:]]
        train_strikes = train[train["is_strike"] == 1]
        if len(train_strikes) < 10:
            train_strikes, test = labeled[labeled["is_strike"] == 1], labeled
        rect = _fit_rectangle(train_strikes, x_col, y_col)
        validation = _evaluate(rect, test, x_col, y_col)
        validation["held_out"] = True
    else:
        rect = _fit_rectangle(labeled[labeled["is_strike"] == 1], x_col, y_col)
        validation = _evaluate(rect, labeled, x_col, y_col)
        validation["held_out"] = False

    return {"rect": rect, "validation": validation, "n_called_strikes": int(labeled["is_strike"].sum()),
            "n_called_balls": int((labeled["is_strike"] == 0).sum()), "x_col": x_col, "y_col": y_col}


def _trackman_in_zone(row, sz: dict) -> bool | None:
    side, height = row.get("plate_loc_side"), row.get("plate_loc_height")
    if pd.isna(side) or pd.isna(height):
        return None
    return (sz["side_min"] <= side <= sz["side_max"]) and (sz["height_min"] <= height <= sz["height_max"])


def _trackman_is_edge(row, sz: dict) -> bool | None:
    side, height = row.get("plate_loc_side"), row.get("plate_loc_height")
    if pd.isna(side) or pd.isna(height):
        return None
    band = sz.get("edge_band", 0.25)
    in_outer = (sz["side_min"] - band <= side <= sz["side_max"] + band) and (sz["height_min"] - band <= height <= sz["height_max"] + band)
    in_inner = (sz["side_min"] + band <= side <= sz["side_max"] - band) and (sz["height_min"] + band <= height <= sz["height_max"] - band)
    return in_outer and not in_inner


def get_zone_columns(df: pd.DataFrame, benchmarks: dict) -> tuple[pd.Series | None, pd.Series | None, dict | None]:
    """Returns (in_zone, is_edge, calibration_meta) using whichever location
    convention is available:
      - TrackMan feet (plate_loc_side/height): fixed config rectangle,
        calibration_meta is None (no calibration needed/performed).
      - TruMedia normalized (trumedia_loc_x/y): self-calibrated from this
        file's own called pitches; calibration_meta carries the fit + any
        held-out validation metrics for transparency in the report.
      - Neither present, or too little data to calibrate: (None, None, None).
    """
    if {"plate_loc_side", "plate_loc_height"} <= set(df.columns):
        sz = benchmarks["strike_zone"] if "strike_zone" in benchmarks else benchmarks
        # dtype="boolean" (pandas' nullable extension type, not plain object)
        # is required here: any row with missing location makes the raw
        # apply() result mix True/False/None into an *object*-dtype Series,
        # and `~` on an object-dtype column of Python bools does bitwise
        # complement (~True == -2), not logical negation — silently corrupting
        # every "out of zone" mask downstream. "boolean" dtype implements `~`
        # correctly and still carries NA through for unlocated pitches.
        in_zone = df.apply(lambda r: _trackman_in_zone(r, sz), axis=1).astype("boolean")
        is_edge = df.apply(lambda r: _trackman_is_edge(r, sz), axis=1).astype("boolean")
        return in_zone, is_edge, None

    if {"trumedia_loc_x", "trumedia_loc_y"} <= set(df.columns):
        calibration = calibrate_trumedia_zone(df)
        if calibration is None:
            return None, None, None
        return in_zone_mask(df, calibration), edge_mask(df, calibration), calibration

    return None, None, None


def in_zone_mask(df: pd.DataFrame, calibration: dict) -> pd.Series:
    rect, x_col, y_col = calibration["rect"], calibration["x_col"], calibration["y_col"]
    x = pd.to_numeric(df[x_col], errors="coerce")
    y = pd.to_numeric(df[y_col], errors="coerce")
    # "boolean" (nullable) dtype before .where(), not plain bool: a plain-bool
    # Series can't hold NaN, so introducing it via .where() silently upcasts
    # to object dtype — and `~` on an object column of Python bools does
    # bitwise complement, not logical negation (see get_zone_columns).
    result = (x.between(rect["x_lo"], rect["x_hi"]) & y.between(rect["y_lo"], rect["y_hi"])).astype("boolean")
    return result.where(x.notna() & y.notna())


def edge_mask(df: pd.DataFrame, calibration: dict, edge_frac: float = 0.15) -> pd.Series:
    """'Edge' pitches: within a band straddling the rectangle boundary, sized
    as a fraction of the rectangle's own half-width/half-height rather than a
    fixed feet value (this coordinate system isn't feet)."""
    rect, x_col, y_col = calibration["rect"], calibration["x_col"], calibration["y_col"]
    x_band = (rect["x_hi"] - rect["x_lo"]) / 2 * edge_frac
    y_band = (rect["y_hi"] - rect["y_lo"]) / 2 * edge_frac
    x = pd.to_numeric(df[x_col], errors="coerce")
    y = pd.to_numeric(df[y_col], errors="coerce")
    in_outer = x.between(rect["x_lo"] - x_band, rect["x_hi"] + x_band) & y.between(rect["y_lo"] - y_band, rect["y_hi"] + y_band)
    in_inner = x.between(rect["x_lo"] + x_band, rect["x_hi"] - x_band) & y.between(rect["y_lo"] + y_band, rect["y_hi"] - y_band)
    result = (in_outer & ~in_inner).astype("boolean")
    return result.where(x.notna() & y.notna())
