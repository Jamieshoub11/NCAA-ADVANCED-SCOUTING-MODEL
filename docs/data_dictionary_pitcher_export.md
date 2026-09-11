# Data Dictionary — TruMedia Pitcher Export (Conner Griffin, Binghamton RHP)

Built from the three files actually uploaded, by inspecting real values (dtypes,
null rates, unique values) rather than assuming a schema. All three are **TruMedia**
exports — no TrackMan file has been provided yet, so TrackMan-vs-TruMedia authority
questions (Phase 2) are deferred until one is.

- `C._Griffin_-_Movement.csv` — 1,152 rows, 1 row per **pitch**. This is the pitch-level file.
- `C._Griffin_-_Traditional.csv` — 15 rows, 1 row per **appearance** (game log). This is the correct source for season aggregation.
- `C._Griffin_-_Traditional-2.csv` — a **splits report**: ~10 different breakdowns (Home/Away, LHH/RHH, by month, by inning, by pitch type, by batted-ball type, by zone location, by count, by baserunner state) concatenated into one file, each re-stating close to the same season totals sliced a different way. **Not additive with the game log — summing both double/triple-counts everything.**

---

## 1. Traditional.csv (per-game log) — authoritative for season aggregation

| Column | Represents | Useful for scouting? | Source | Quality notes | Treatment |
|---|---|---|---|---|---|
| Rank | Row order (1=most recent) | No | TruMedia | Clean | Ignore |
| playerId | TruMedia's internal player ID | Yes, as a stable join key | TruMedia | Clean, constant per player | Use as identifier, not a stat |
| abbrevName / playerFullName / player / playerFirstName | Name variants | Identity only | TruMedia | Clean | Use `playerFullName` as display name |
| pos | Position | Context | TruMedia | Clean | Keep as bio field |
| newestTeamName / newestTeamAbbrevName / newestTeamId / newestTeamLocation / newestTeamLevel | Current team info | Context (roster/bio) | TruMedia | Clean | Bio fields, not per-game stats |
| seasonYear | Season | Yes — needed for season boundaries | TruMedia | Clean | Use to scope aggregation |
| gameId | Unique game identifier | **Yes — primary join key to Movement.csv** | TruMedia | Clean, matches `gameId` in Movement.csv | **Use as the game-level join key** |
| date / gameDay | Game date | Yes — needed for recency (Phase 8) | TruMedia | `date` has time-of-day; `gameDay` is short form | Use `date`, parse to datetime |
| teamWithLevel / teamId / teamLevel | Team context | Low | TruMedia | Clean | Ignore unless multi-team |
| home | Home/away flag | Yes — venue splits | TruMedia | Boolean, clean | Use directly |
| win / final | Game outcome flags | Low (team-level, not pitcher-level) | TruMedia | Clean | Ignore for pitcher profile |
| location / team / abbrevName (dup) | Team/location text | Redundant with above | TruMedia | Clean | Ignore |
| opponentId / opponentToken / opponent | Opponent identity | **Yes — needed for the entire advance-scouting use case** | TruMedia | Clean | **Use `opponent` as the opponent join key** |
| result | Game score string ("L 1-10") | Low, human-readable only | TruMedia | Clean but unstructured | Ignore for calculation; fine for display |
| oppOrg | (empty in this file) | No | TruMedia | 100% blank in sample | Ignore |
| **P** | Total pitches thrown in the appearance | **Yes — core volume metric** | TruMedia | Clean | Use directly; also = SUM(pitches) per game in Movement.csv (cross-check) |
| G / GS | Games / games started (always 1/1 per row here) | Low at per-game level | TruMedia | Clean | Only meaningful once summed across games |
| W / L / QS / SV | Decision/quality-start/save flags | Team-context, weak scouting value | TruMedia | Clean | Keep for record but not a scouting metric |
| **IP** | Innings pitched, **baseball notation** (`4.1` = 4⅓ innings, not 4.1 decimal) | **Yes — core volume metric** | TruMedia | ⚠️ Must be summed via outs (3 outs/inning), not as a decimal — see engine fix already shipped | Convert to outs before any aggregation |
| **H, ER, R, BB, K, HR** | Hits/earned runs/runs/walks/strikeouts/HR allowed, that game | **Yes — core counting stats** | TruMedia | Clean | Sum directly across games |
| ER/G, R/G | Rolling per-game rate (cumulative to that point in season) | Low — redundant once we recompute rates from summed counts | TruMedia | Derived by TruMedia | Ignore; recompute ERA ourselves from summed ER/IP for correctness |
| **ERA, FIP, WHIP, K/9, BB/9, K/BB, HR/9** | Rate stats for that single game | Only descriptive for that one outing, not season-level | TruMedia, derived | Single-game rates are noisy (e.g. a 1-out appearance produces absurd ERA) | **Do not average these across games** — recompute from summed raw counts instead (already correct in our engine) |
| IP/G | IP per game (redundant with IP since G=1 per row) | No | TruMedia | Redundant | Ignore |
| scatterName / scatterExtra | Opponent mascot + HTML-formatted result blurb | Display only | TruMedia | Contains `<br>` HTML | Ignore for calculation; could render in a report footer |
| gameDay | Short date | Redundant with `date` | TruMedia | Clean | Ignore |

**Missing from this file, relevant to Phase 3/4:** No `BF` (batters faced) column — cannot compute K% or BB% (per-batters-faced) directly from this file; K/9 and BB/9 (per-inning) ARE computable and are the correct substitute your engine now surfaces. No batter-handedness, pitch-type, count, or location info at all — that all lives only in Movement.csv.

---

## 2. Traditional-2.csv (splits report) — supplementary, NOT for raw aggregation

Same 27 columns as Traditional.csv (P, G, GS, W, L, QS, SV, IP, H, ER, R, ER/G, R/G,
BB, K, HR, ERA, FIP, WHIP, K/9, BB/9, K/BB, HR/9, IP/G) **plus two new ones**:

| Column | Represents | Useful? | Notes |
|---|---|---|---|
| `SplitBy <category>` (first cell of each section) | The split's row label (e.g. "Home", "Lefty", "Feb", pitch-type name) | **Yes — this is exactly Phase 3's "usage/results by situation"** | Value depends on which section it's in |
| `splitByName` | Internal filter-key name for the section (`filterBaseballVenue`, `filterBaseballBatterHand`, `filterBaseballPitchType`, `filterBaseballCount`, ...) | **Yes — this is the detection signal** the engine now uses to route this file away from raw aggregation | Already wired into `classify_csv` |

**Sections present in this file:** Venue (Home/Away), Batter Hand (Lefty/Righty),
Season, Month, Inning (1-9/Extra), Pitch Type (including several *overlapping
composite* rows like "Hard (fast/si/ct)" and "Breaking+Soft+Spec" that double-count
against the individual pitch-type rows — do not sum pitch-type rows together),
Batted Ball type, Zone Location (in/out of zone, on-black, comp/non-comp,
mid-mid), Count (broad buckets AND every individual count 0-0 through 3-2), Men On
(base-out states).

**This is genuinely valuable data for Phase 3/6** (pitch usage by count, by batter
hand, by inning, by baserunner state) — it should be **parsed into its own
structured table** (one row per split-category + split-value + all 27 rate/count
columns) rather than discarded, but it must never be summed into the season box
score. This is exactly the kind of file the engine currently just sets aside
(`loaded.splits`, unused) — turning it into structured per-count/per-handedness
tendency tables is a good candidate for the first real Phase 3 deliverable.

---

## 3. Movement.csv (pitch-level) — the core dataset for Phases 2-5

83 columns. Grouped by function:

### Identifiers (Phase 2 stable IDs)
| Column | Represents | Useful? | Notes |
|---|---|---|---|
| `uniqPitchId` | Unique per-pitch ID | **Yes — use as the pitch-level primary key** | 100% non-null, 100% unique across 1,152 rows |
| `gameId` | Game ID | **Yes — join key to Traditional.csv** | Matches Traditional.csv's `gameId` exactly |
| `abNumInGame` | At-bat number within the game | **Yes — PA-level grouping key** | `gameId` + `abNumInGame` = a stable plate-appearance ID |
| `pitchNumInAB` | Pitch number within the at-bat | **Yes — pitch sequence position** | Needed for Phase 10 sequencing (previous-pitch lookups) |
| `pitchNumInGame` | Pitch number within the game | Yes, secondary sequence key | Clean |
| `playGuid` / `playguid` (duplicate cols) | Alternate play identifier | Redundant with `uniqPitchId` | 10.3% null, not fully unique — **less reliable than uniqPitchId, don't use as the key** |
| `reportId` | Constant `"null-825"` | No | Degenerate (1 value) | Ignore |

### Pitcher/batter/team context
| Column | Represents | Useful? | Notes |
|---|---|---|---|
| `fullName`, `pitcher`, `pitcherAbbrevName` | Pitcher name (redundant x3) | Identity | Constant in this file (one pitcher) — will vary in a team-wide export |
| `pitcherHand` | Pitcher throwing hand | Yes (context) | Constant "R" here |
| `batter`, `batterAbbrevName` | Batter name | **Yes — required for opponent hitter profiles (Phase 4)** | Clean |
| `batterHand` | **Batter handedness (L/R)** | **Yes — required for every LHH/RHH split in Phase 3/4** | Clean, 2 values observed |
| `home`, `opponent`, `team`, `pitchingTeam`/`pitchingTeam.1`, `battingTeam`/`battingTeam.1` (+ Id variants) | Team context, several duplicated columns | Yes for team splits | `pitchingTeam`/`battingTeam` appear twice (`.1` suffix = pandas deduping an actual duplicate header in the source) — **harmless duplicate, use either** |
| `catchingTeam`, `catchingTeamId`, `catcherId`, `catcherAbbrevName` | Catcher identity | Low priority now; potentially useful later for a catcher-framing angle | Clean but out of scope for pitcher/hitter profiles |
| `gameResult`, `gameVenueId`, `level` | Game outcome / venue / level tag | Low | `level` constant ("BBC") — ignore |

### Situation / count / sequence
| Column | Represents | Useful? | Notes |
|---|---|---|---|
| `count` | Ball-strike count as text ("0-0", "1-2", ...) | **Yes — this is Phase 3's "usage by count" directly, no derivation needed** | Clean, 12 values |
| `inn` | Inning + half ("Bot 1", "Top 3") | Yes, situational context | Clean |
| `outs` | Outs when pitch was thrown (0/1/2) | Yes | Clean |
| `abNumInGame`, `pitchNumInAB` | (see Identifiers above) | | |
| `pitchDetails` | Human-readable summary ("1-1 Slider, 86 mph") | QA/spot-check only, redundant with structured fields | Ignore for calculation |
| `date`, `gameDate` (duplicate) | Timestamp of the game | Yes, for recency | Redundant pair, use either |

### Pitch identity / velocity / spin
| Column | Represents | Source-authoritative? | Notes |
|---|---|---|---|
| `pitchType` | Short pitch-type code (FA/SL/FC/CH/CU/UN) | Lower priority than pitchTypeFull | Codes aren't self-explanatory (`UN`=unknown/unclassified — real, not junk) |
| `pitchTypeFull` / `type` (duplicate) | Full pitch name (Fastball/Slider/Cutter/Changeup/Curveball) | **Yes — use this as the canonical pitch type** | Engine now prefers this over the short code |
| `releaseVelocity` / `Vel` (duplicate) | Release velocity, mph | **Yes — core arsenal metric** | Identical values in both columns; stored as text with occasional `-` placeholder, must coerce numeric |
| `Spin` | Spin rate, rpm | **Yes — core arsenal metric** | Clean numeric-as-text |
| `SpinDir` | Spin axis/direction, degrees | **Yes — this is the "spin axis/direction" Phase 3 asks for** | Not yet wired into the engine — real values (0-360°ish), worth adding |
| `BrkLen`, `BrkAng` | Break length/angle (polar movement representation) | **No usable data** | **100% `"-"` placeholder in every row of this file** — not "uncertain," just absent. Do not attempt a trig conversion to IVB/HVB from this file; there's nothing to convert |
| `probSL` | Unlabeled probability-like value (0-1), 25.3% null | **Unknown — do not use until clarified** | No documentation of what this predicts (stuff grade? swing probability? pitch-type-classifier confidence?). Flagging rather than guessing, per your "do not invent data" rule. **Question for you: does TruMedia document this field, or is it worth asking your rep?** |

### Location
| Column | Represents | Usable as TrackMan-style plate location? | Notes |
|---|---|---|---|
| `x`, `y` | Some 2D coordinate | **No — do not treat as feet-based plate location without confirming the convention** | `y` ranges roughly -5.5 to +4.0; a real plate-crossing height is never negative, so this is not simply "height above ground" in the units our strike-zone math (`config/benchmarks.yaml` → `strike_zone`) assumes |
| `PXNorm`, `PZNorm` | "Normalized" x/z, despite the name | **No, same reason** | Confirmed `PXNorm == -x` and `PZNorm == y` exactly — these are a sign-flipped restatement of `x`/`y`, not an independent normalized coordinate. Same unresolved convention problem. |
| `RelSide` | Release point, horizontal (feet) | **Yes** | Values -2.4 to -1.0, consistent with a RHP's arm-side release point in feet — already correctly wired into the engine |
| `RelHeight` | Release point height (feet) | **Yes** | Values 5.9-6.5 ft, a plausible release height — already correctly wired into the engine |

**Bottom line on location: we have release point, but not pitch location at the plate**, from this file. Zone%/Edge%/Chase%/heatmaps (Phase 3's biggest ask) **cannot be built from Movement.csv as currently exported.** This is the single most important gap to close before Phase 3's location-tendency work can happen for real.

**Question for you:** Does your TruMedia account have a "Pitch Location" or "Locations" export type (separate from "Movement") with `PlateLocSide`/`PlateLocHeight`-style feet-based coordinates? Or is a TrackMan CSV the intended source for plate location, with TruMedia only supplying velocity/movement/results? I don't want to guess at `x`/`y`'s meaning and risk silently wrong zone/chase numbers — this needs either your confirmation of the coordinate system or a different export.

### Outcome
| Column | Represents | Useful? | Notes |
|---|---|---|---|
| `pitchResult` | **Rich descriptive outcome** ("Strikeout (Swinging)", "Single on a Ground Ball", "Home Run on a 412.26 ft Fly Ball", "Fielder's Choice", ...) | **Yes — the authoritative outcome field** | 31 distinct values observed; now fully classified into whiff/foul/in-play/no-swing by `src/ncaa_scout/pitch_outcomes.py`, verified against every value actually seen |
| `pitchOutcome` | Cryptic short code (`Ball`, `S`, `B`, `SL`) | **No — too ambiguous, not used** | Only 4 distinct values for what should be a per-pitch call; unclear if `S`/`B`/`SL` distinguish swinging vs. called strikes. Not worth the guess when `pitchResult` already gives us everything reliably. |
| `exitVelocity` | Exit velo on contact, mph | **Yes** | Text with `-` placeholder for no-contact pitches; already wired in |
| Home-run distance (embedded in `pitchResult` text, e.g. "412.26 ft") | Batted-ball distance | Potentially yes, but requires text-parsing | Not currently extracted; low priority vs. the exit-velo/location gaps above |

### Defensive/fielding-model columns — not usable, ignore all
`tarantulaVideoHostedCFURL`, `statcastFieldersInitialFielderPosition`,
`hasKinatraxData`, `SessionType`, `pathEff`, `outProb` are **100% null** in this
file. `hang`, `dist`, `react`, `speed`, `jump`, `wall`, `infieldDist`,
`infieldTime` are **always exactly 0** — template columns from TruMedia's schema
that this export type never populates. None of this is a data-quality problem
with Conner Griffin's data specifically; it's just outside what a pitcher
"Movement" export carries. **Ignore this entire group.**

---

## Overlapping fields / authority recommendation

No TrackMan file has been provided yet, so there's no real TruMedia-vs-TrackMan
conflict to resolve today. Within TruMedia itself, the only overlaps are exact
duplicates (`pitchingTeam`/`pitchingTeam.1`, `releaseVelocity`/`Vel`,
`pitchTypeFull`/`type`, `date`/`gameDate`) — pick either side of each pair, no
authority question involved.

**When a TrackMan file does arrive**, the fields most likely to be contested are
release point (both tools measure it — compare directly), pitch classification
(TrackMan's `TaggedPitchType` vs. TruMedia's `pitchTypeFull` can disagree on
borderline sliders/cutters), and **plate location, which right now only TrackMan
can supply reliably** for this pitcher. I'd recommend TrackMan as authoritative
for location/movement/spin (its native purpose) and TruMedia as authoritative for
play-by-play outcome text and game/season roll-ups (its native purpose) — but this
is a recommendation to confirm with you, not a decision I've made unilaterally.

## What we can build reliably today vs. what's blocked

**Can build now, high confidence:** season/game aggregation (fixed), pitch
arsenal usage/velo/spin by pitch type, whiff% by pitch type, usage by count
(directly from `count`), usage by batter handedness (directly from `batterHand`),
sequencing (pitch-to-pitch within an AB via `abNumInGame`+`pitchNumInAB`), K/9,
BB/9, ERA/WHIP from real counts.

**Blocked until we resolve the location question above:** Zone%, Edge%, Chase%,
CSW%, in-zone%, location heatmaps, "how to attack him" location-based
recommendations — everything in Phase 3 that depends on where the pitch crossed
the plate. This is the single biggest open item before Phase 3 can be considered
complete, not a minor gap.

**Not present in any of the three files:** batters faced (BF) — K%/BB% (as a
share of batters faced) aren't computable; K/9 and BB/9 are the correct
substitute and are already what the engine shows.
