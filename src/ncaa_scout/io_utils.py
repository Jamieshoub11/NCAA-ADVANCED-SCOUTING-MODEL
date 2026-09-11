"""Config loading, CSV discovery, and header normalization.

Real exports from TruMedia/TrackMan/Synergy never agree on header spelling.
Everything downstream works on *canonical* column names; this module is the
only place that has to know about the messy real-world aliases, via
config/column_aliases.yaml.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"
DATA_DIR = REPO_ROOT / "data"


def load_yaml(path: Path) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def load_column_aliases() -> dict[str, list[str]]:
    return load_yaml(CONFIG_DIR / "column_aliases.yaml")


def load_benchmarks() -> dict:
    return load_yaml(CONFIG_DIR / "benchmarks.yaml")


def _normalize_header(name: str) -> str:
    name = str(name).strip().lower()
    name = re.sub(r"[\s\-]+", "_", name)
    name = re.sub(r"[^a-z0-9_]", "", name)
    return name


def _alias_lookup(aliases: dict[str, list[str]]) -> dict[str, str]:
    """alias-header -> canonical-name, including the canonical name itself."""
    lookup = {}
    for canonical, variants in aliases.items():
        lookup[_normalize_header(canonical)] = canonical
        for v in variants:
            lookup[_normalize_header(v)] = canonical
    return lookup


def apply_column_aliases(df: pd.DataFrame, aliases: dict[str, list[str]] | None = None) -> pd.DataFrame:
    """Rename df's columns to canonical names wherever an alias matches.

    Columns with no known alias are kept as-is (normalized) rather than dropped,
    so nothing is silently lost.
    """
    if aliases is None:
        aliases = load_column_aliases()
    lookup = _alias_lookup(aliases)
    rename_map = {}
    for col in df.columns:
        norm = _normalize_header(col)
        rename_map[col] = lookup.get(norm, norm)
    return df.rename(columns=rename_map)


def slugify(name: str) -> str:
    slug = _normalize_header(name).strip("_")
    return re.sub(r"_+", "_", slug)


@dataclass
class PlayerBio:
    name: str
    school: str = "N/A — Insufficient Data"
    position: str = "N/A — Insufficient Data"
    year: str = "N/A — Insufficient Data"
    bats: str = "N/A"
    throws: str = "N/A"
    conference: str = "N/A — Insufficient Data"

    @property
    def bats_throws(self) -> str:
        return f"{self.bats}/{self.throws}"


def load_bio(player_name: str, data_dir: Path | None = None) -> PlayerBio:
    data_dir = data_dir or DATA_DIR
    slug = slugify(player_name)
    bio_path = data_dir / "players" / slug / "bio.json"
    if bio_path.exists():
        with open(bio_path, "r") as f:
            raw = json.load(f)
        return PlayerBio(
            name=raw.get("name", player_name),
            school=raw.get("school", PlayerBio.school),
            position=raw.get("position", PlayerBio.position),
            year=raw.get("year", PlayerBio.year),
            bats=raw.get("bats", PlayerBio.bats),
            throws=raw.get("throws", PlayerBio.throws),
            conference=raw.get("conference", PlayerBio.conference),
        )
    return PlayerBio(name=player_name)


def find_player_files(player_name: str, data_dir: Path | None = None) -> list[Path]:
    """Find CSVs relevant to a player.

    Search order:
      1. data/players/<slug>/*.csv  (the canonical per-player folder)
      2. any *.csv anywhere under data/ whose filename contains the player's slug
      3. any *.csv anywhere under data/ that has a batter/pitcher column containing
         the player's name (slow path, used as a fallback for dumped raw exports)
    """
    data_dir = data_dir or DATA_DIR
    slug = slugify(player_name)
    found: list[Path] = []

    player_dir = data_dir / "players" / slug
    if player_dir.exists():
        found.extend(sorted(player_dir.glob("*.csv")))

    if found:
        return found

    for csv_path in data_dir.rglob("*.csv"):
        if slug in slugify(csv_path.stem):
            found.append(csv_path)

    if found:
        return sorted(set(found))

    name_lower = player_name.strip().lower()
    for csv_path in data_dir.rglob("*.csv"):
        try:
            df = pd.read_csv(csv_path, nrows=5)
        except Exception:
            continue
        df = apply_column_aliases(df)
        for col in ("batter_name", "pitcher_name"):
            if col in df.columns and df[col].astype(str).str.lower().str.contains(name_lower, na=False).any():
                found.append(csv_path)
                break

    return sorted(set(found))


CSV_KIND_PITCH_LEVEL_COLS = {"rel_speed", "plate_loc_height", "plate_loc_side", "exit_speed", "pitch_call"}
CSV_KIND_BOXSCORE_COLS = {"ab", "h", "pa"}


def classify_csv(df: pd.DataFrame) -> str:
    """Best-effort guess at what kind of export this dataframe is."""
    cols = set(df.columns)
    if cols & CSV_KIND_PITCH_LEVEL_COLS:
        return "pitch_level"
    if cols & CSV_KIND_BOXSCORE_COLS:
        return "boxscore"
    return "unknown"


@dataclass
class LoadedData:
    pitch_level: list[pd.DataFrame] = field(default_factory=list)
    boxscore: list[pd.DataFrame] = field(default_factory=list)
    unknown: list[pd.DataFrame] = field(default_factory=list)
    source_paths: list[Path] = field(default_factory=list)

    def has_any(self) -> bool:
        return bool(self.pitch_level or self.boxscore or self.unknown)


def load_player_data(player_name: str, data_dir: Path | None = None) -> LoadedData:
    aliases = load_column_aliases()
    paths = find_player_files(player_name, data_dir)
    loaded = LoadedData(source_paths=paths)
    for path in paths:
        try:
            df = pd.read_csv(path)
        except Exception:
            continue
        df = apply_column_aliases(df, aliases)
        kind = classify_csv(df)
        if kind == "pitch_level":
            loaded.pitch_level.append(df)
        elif kind == "boxscore":
            loaded.boxscore.append(df)
        else:
            loaded.unknown.append(df)
    return loaded
