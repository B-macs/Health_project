"""services/strain_regions.py — strain, localised to upper body / core / lower body.

Pure functions. No I/O, no Streamlit, explicit `today` — the services/engine.py
contract.

WHAT THIS ADDS, AND WHAT IT MUST NEVER TOUCH
════════════════════════════════════════════
The overall strain number is unchanged by everything here, bit for bit. This
module is additive information beside the headline, never a re-derivation of
it. tests/test_strain_overall_unchanged.py is the acceptance criterion, and it
was written against the tree before any of this existed.

Nothing here can cap volume. services/engine.py's acwr(), traffic_light() and
volume_recommendation() do not import this module, and a source-level test in
tests/test_strain_regions_acwr.py fails if they ever do. That makes "a regional
number can never gate a decision" a property of the import graph rather than a
promise in a docstring.


THE ONE THING TO UNDERSTAND: THE SHARE IS THE ANSWER, THE STRAIN IS THE SCALE
════════════════════════════════════════════════════════════════════════════
engine.load_to_strain is 21·ln(x+1)/ln(601) — a LOG curve. So three regional
strains DO NOT SUM to the overall strain, and no amount of care makes them.

Worked example, the athlete's own founding case. A 120-minute hike at RPE 5:
raw AU 600, "Outdoor Hike" weighted 0.5 → 300 weighted AU, stage 2 CLF 0.40.

    region        share      AU     strain
    lower body     80%      240      15.0
    core           15%       45       9.7
    upper body      5%       15       6.4
    ─────────────────────────────────────
    overall       100%      300      15.7      ← the three total 31.1

Two consequences, and the whole design follows from them:

1. THE SHARE IS WHAT HE ASKED FOR. His words were "adds PROPORTIONALLY more to
   the lowerbody". An intended 16:1 lower:upper localisation shows up as 2.34:1
   once through the curve — the log compresses away the very thing the feature
   exists to show. The AU share does not: it is exact, it is additive, and it
   is the quantity the sentence is about. So callers lead with the share.

2. THE STRAIN TRIPLE IS SECONDARY, AND IS NEVER SUMMED. Each value is that
   region's own load read on the same familiar 0-21 scale. No function in this
   module returns a total of them; additivity_gap() returns the size of the
   discrepancy so a screen can STATE it rather than hand-wave it, and
   NON_ADDITIVE_NOTE is the sentence to state.

   One property makes the pair readable rather than broken-looking: every
   regional value is bounded above by the overall, necessarily — regional AU is
   at most total AU and the curve is monotonic. A region can never read higher
   than the headline.


ATTRIBUTION: AN UNMAPPED NAME IS UNATTRIBUTED, NEVER SPREAD AND NEVER ZEROED
═══════════════════════════════════════════════════════════════════════════
The identity is

    upper + core + lower + unattributed == the day's whole weighted AU

exactly, at one decimal place, via services.strength.split_parts' residual
rounding.

A name absent from training_constants.EXERCISE_REGION_SHARES goes to the
UNATTRIBUTED bucket and is NAMED in `unmapped_names`. Two alternatives were
considered and rejected:

  * Spreading it evenly across the three. That asserts the drill loaded upper
    body, which for a yoga pose or a self-assessment is a fabrication, and it
    would quietly inflate every region's ACWR denominator.
  * Returning None for all three. That is right when NOTHING maps (a pure yoga
    session — `regions_known` is False and callers must render "—", never
    0.0, following the flexibility ladder's rule that an unmeasured muscle has
    no number). But it throws away a perfectly good split on the far more
    common case of a mostly-mapped session with one unknown name in it.

The bucket does both: it asserts nothing, keeps the identity, and makes the
gap visible instead of absorbing it. Yoga poses are in neither region map —
a documented scope boundary, not a bug — so a yoga day reads 100% unattributed
with its pose names listed, which is also the cheapest way to notice the gap.

MASS IS WEIGHTED BY seconds × movement_weight, NOT BY SECONDS. That product is
exactly content_weighting.day_content_multiplier's numerator, and it has to be:
the quantity being split IS that numerator's output. Ten minutes of Goblet
Squat (1.3) and ten minutes of Cat-Cow (0.25) do not contribute equally to the
day's AU, so they must not contribute equally to its split. Bare seconds would
hand a mixed Session A most of its strain to core purely because release work
occupies more clock. Pinned by test, both as behaviour and as the identity
sum(mass) == day_content_multiplier(...)["weighted_seconds"].

HOW MUCH OF THE SESSION THIS ACTUALLY SEES. Reconstructed exercise time covers
about half of elapsed session time — measured across all 23 logged sessions:
50% overall, ranging 6% to 565%. day_content_multiplier is immune because it is
a ratio, numerator and denominator scaling together. A SPLIT is not: it
allocates 100% of the AU on a proxy covering half the session. Distributing
setup and inter-set rest pro-rata is defensible; a 6% day is not. So
`attributed_fraction` is returned and callers show it, in the idiom of
session HR's `hr_coverage`.


THE HEART-RATE TERM
═══════════════════
Edwards' TRIMP is one number for one body and has no region in it. Where a
day's strain is HR-derived, the regional split is applied to the RPE-and-
content share only, and `hr_basis` says so rather than implying the watch knew
which muscles were working.

Per-exercise HR is deliberately NOT used as the attribution basis even when it
becomes available. services/hr_load.py's own record of 2026-08-06 is the
reason: Lat Pulldown and Single-Arm DB Row peaked higher (159, 163) than a
heavier Hip Thrust (149) because of rest density and relative effort, not load.
Attributing regions by per-exercise heart rate would read a well-programmed
heavy lower-body day as an upper-body day. It is a rest-density meter wearing a
regional label.

Note also that as of 2026-08-10 the HR path writes nothing at all —
Repository.sync_session_hr_for_date raises AttributeError on `ex.sets`
(models.ExerciseEntry has no such field), so the Session HR tab is empty and
every day's strain is RPE-derived. That is a separate bug, recorded here
because it is why HR_BASIS_AU_SHARES is the only basis this module has ever
returned in practice.


THE INVENTED CONSTANTS
══════════════════════
training_constants.EXERCISE_REGION_SHARES is 83 entries of invented numbers,
flagged REGION_SHARES_BASIS = "provisional" and surfaced as such on screen.
The two ACWR floors below are invented too. Both carry revert conditions in the
biometrics.HRV_GARMIN_HOLD idiom — lift on a measurement or a review, never on
a date.
"""

from __future__ import annotations

from datetime import date, timedelta

import training_constants as tc
from services import content_weighting
from services import engine as _engine
from services import hr_load as _hr_load
from services.strength import split_parts

#: Third copy after tonnage.REGIONS and strength.REGIONS. Duplicated rather
#: than imported so this module does not depend on either; a test pins all
#: three equal, which is cheaper than the coupling.
REGIONS: tuple[str, ...] = ("upper_body", "core", "lower_body")

#: The fourth bucket. Load whose exercise name is in no region map — it is
#: reported, never spread across the three and never silently dropped.
UNATTRIBUTED: str = "unattributed"

# ── why a given exercise's shares are what they are ──────────────────────────
BASIS_MAPPED = "mapped"                # a real EXERCISE_REGION_SHARES entry
BASIS_UNMAPPED = "unmapped"            # no entry — goes to UNATTRIBUTED
BASIS_RENORMALISED = "renormalised"    # entry did not sum to 1.0; scaled, named

# ── which method produced a regional HR figure ───────────────────────────────
HR_BASIS_AU_SHARES = "au_shares"
HR_BASIS_NONE = "none"

#: Below this the panel should say the split rests on a thin sample of the
#: session. Measured median coverage is ~50%, so this is not a failure
#: threshold — it is the point at which the caveat stops being pedantic.
ATTRIBUTED_FRACTION_LOW: float = 0.70

# ── regional ACWR floors. INVENTED. ──────────────────────────────────────────
#
# engine.acwr's ratio is scale-free, and ACWR_MIN_IN_STAGE_DAYS counts CALENDAR
# days in the stage rather than days THIS REGION was loaded. Measured directly
# against engine.acwr with stage_start = today-20:
#
#     region's entire in-stage load          ACWR    status
#     one 300 AU session today               3.00    overreach_risk
#     one 1.5 AU wall slide today            3.00    overreach_risk
#     two loaded days inside the last 7      3.00    overreach_risk
#
# All three report baseline_established=True. A 90-second scapular slide and a
# 300 AU session are indistinguishable, because if all of a region's in-stage
# load lands in the acute window the ratio is exactly N/7 for an N-day in-stage
# window, independent of AU entirely.
#
# So a regional ratio needs a floor the global one does not. Below either of
# these the ratio is WITHHELD — status "insufficient_regional_load" — while
# acute_avg, chronic_avg, loaded_days and chronic_share are still reported.
# Same shape as baseline_establishing: report the fact, withhold the number.
#
# REVERT CONDITION, in the HRV_GARMIN_HOLD idiom: revisit once a full stage of
# per-region history exists and the ratio's actual distribution per region can
# be looked at — on that measurement, not on a date. For reference, over the 28
# days to 2026-07-31 the athlete's regions were loaded on 19 (lower), 18 (core)
# and 13 (upper) days, so this floor does not bite his current pattern; it bites
# the first week of a block and the week after a deload, which is exactly when
# the degenerate cases above fire.
REGION_ACWR_MIN_LOADED_DAYS: int = 8
REGION_ACWR_MIN_CHRONIC_SHARE: float = 0.10

STATUS_INSUFFICIENT_REGIONAL_LOAD = "insufficient_regional_load"

#: The sentence a screen shows beside the strain triple. States the mechanism,
#: not the inequality: "the three are always larger" is false in the degenerate
#: case where one region holds all the load, and a claim a pure leg day can
#: falsify is worse than no claim.
NON_ADDITIVE_NOTE = (
    "Each region is its own load put through the same 0-21 curve. The curve "
    "is logarithmic, so these three never sum to the overall — read them "
    "against each other, not as slices of it."
)


# ─── shares ──────────────────────────────────────────────────────────────────

def region_shares_for(name: str) -> tuple[dict[str, float] | None, str]:
    """(shares, basis) for one exercise name. Never raises.

    None shares means the name is in no region map and its load belongs in
    UNATTRIBUTED.

    A stored entry that does not sum to 1.0 is RENORMALISED here and its name
    reported, rather than raised on. That split is deliberate and already this
    codebase's habit: the test enforces exactness so a typo cannot live
    forever, while the runtime degrades so a data-completeness gap can never
    crash a page that shows health numbers (content_weighting's docstring makes
    the same trade for the same reason).
    """
    raw = tc.EXERCISE_REGION_SHARES.get(name)
    if not raw:
        return None, BASIS_UNMAPPED
    total = sum(raw.get(r, 0.0) for r in REGIONS)
    if total <= 0:
        return None, BASIS_UNMAPPED
    if abs(total - 1.0) > 1e-9:
        return {r: raw.get(r, 0.0) / total for r in REGIONS}, BASIS_RENORMALISED
    return {r: raw.get(r, 0.0) for r in REGIONS}, BASIS_MAPPED


def session_region_mass(exercise_seconds: list[dict]) -> dict:
    """One session's regional mass, UNROUNDED.

        mass[r] = Σ over exercises of  seconds × movement_weight × shares[r]

    `exercise_seconds` is content_weighting.day_content_multiplier's own input
    shape, [{"name": str, "seconds": int}, ...].

    Returns {"mass": {region: float}, "unattributed_mass": float,
             "total_mass": float, "shares": {region: float},
             "unattributed_share": float, "regions_known": bool,
             "unmapped_names": [...], "renormalised_names": [...],
             "plain_seconds": int}

    `total_mass` is exactly day_content_multiplier's `weighted_seconds`, which
    is what makes the split a decomposition of the AU rather than a second
    opinion about it. `regions_known` is False when nothing mapped — callers
    must render "—" for the three regions in that case, never 0.0.
    """
    mass = {r: 0.0 for r in REGIONS}
    unattributed = 0.0
    plain_seconds = 0
    unmapped: list[str] = []
    renormalised: list[str] = []

    for entry in exercise_seconds or []:
        name = entry.get("name") or ""
        seconds = float(entry.get("seconds") or 0)
        plain_seconds += int(entry.get("seconds") or 0)
        weight_entry = tc.EXERCISE_MOVEMENT_WEIGHT.get(name)
        weight = (weight_entry[1] if weight_entry
                  else content_weighting.UNMAPPED_EXERCISE_WEIGHT)
        weighted = seconds * weight
        if weighted <= 0:
            # Still worth naming: a zero-second row cannot be attributed
            # either, and silence about it is what makes a gap invisible.
            if name and name not in tc.EXERCISE_REGION_SHARES and name not in unmapped:
                unmapped.append(name)
            continue

        shares, basis = region_shares_for(name)
        if shares is None:
            unattributed += weighted
            if name and name not in unmapped:
                unmapped.append(name)
            continue
        if basis == BASIS_RENORMALISED and name not in renormalised:
            renormalised.append(name)
        for r in REGIONS:
            mass[r] += weighted * shares[r]

    total = sum(mass.values()) + unattributed
    if total > 0:
        shares_out = {r: mass[r] / total for r in REGIONS}
        unattributed_share = unattributed / total
    else:
        shares_out = {r: 0.0 for r in REGIONS}
        unattributed_share = 0.0

    return {
        "mass": mass,
        "unattributed_mass": unattributed,
        "total_mass": total,
        "shares": shares_out,
        "unattributed_share": unattributed_share,
        "regions_known": sum(mass.values()) > 0,
        "unmapped_names": sorted(unmapped),
        "renormalised_names": sorted(renormalised),
        "plain_seconds": plain_seconds,
    }


def split_session_au(session_au: float, mass: dict) -> dict:
    """`session_au` divided by `mass`'s shares, rounded so the four parts sum
    to it EXACTLY at one decimal place.

    The unattributed bucket absorbs the rounding remainder against the total,
    and services.strength.split_parts absorbs it within the three regions —
    reused rather than reimplemented, because a second copy of that residual
    rule is exactly the drift its own docstring warns about.
    """
    total = round(float(session_au or 0.0), 1)
    if total <= 0 or mass["total_mass"] <= 0:
        return {**{r: 0.0 for r in REGIONS}, UNATTRIBUTED: total}
    attributed_share = sum(mass["shares"][r] for r in REGIONS)
    attributed = round(total * attributed_share, 1)
    parts = split_parts(
        # Renormalised WITHIN the attributed portion, so split_parts' own
        # residual absorption lands inside it rather than leaking into the
        # unattributed bucket.
        {r: (mass["shares"][r] / attributed_share if attributed_share > 0 else 0.0)
         for r in REGIONS},
        attributed,
    )
    parts[UNATTRIBUTED] = round(total - attributed, 1)
    return parts


# ─── daily series ────────────────────────────────────────────────────────────

def daily_region_au(sessions: list[dict]) -> dict:
    """Per-date regional AU from per-SESSION rows.

    `sessions`: [{"date": iso, "au": float (already content-weighted),
                  "exercise_seconds": [...], "elapsed_seconds": float|None}]
    — one entry per Session ID, so a gym session and a same-day yoga session
    are split independently and only then summed. Splitting a merged day would
    let one session's exercise mix redistribute the other's load.

    Returns {"rows": [{"date", "upper_body", "core", "lower_body",
                       "unattributed", "total_au", "regions_known"}],
             "unmapped_names", "renormalised_names", "attributed_fraction"}

    Rounding happens ONCE per session and the date total is the sum of those,
    which keeps every row's four parts summing to its own total_au exactly.
    """
    by_date: dict[str, dict[str, float]] = {}
    known: dict[str, bool] = {}
    unmapped: set[str] = set()
    renormalised: set[str] = set()
    recon_seconds = 0.0
    elapsed_seconds = 0.0

    for s in sessions or []:
        d = s.get("date") or ""
        if not d:
            continue
        mass = session_region_mass(s.get("exercise_seconds") or [])
        parts = split_session_au(s.get("au") or 0.0, mass)
        bucket = by_date.setdefault(
            d, {**{r: 0.0 for r in REGIONS}, UNATTRIBUTED: 0.0},
        )
        for key, value in parts.items():
            bucket[key] += value
        known[d] = known.get(d, False) or mass["regions_known"]
        unmapped.update(mass["unmapped_names"])
        renormalised.update(mass["renormalised_names"])
        recon_seconds += mass["plain_seconds"]
        elapsed_seconds += float(s.get("elapsed_seconds") or 0.0)

    rows = []
    for d in sorted(by_date):
        b = by_date[d]
        rows.append({
            "date": d,
            **{r: round(b[r], 1) for r in REGIONS},
            UNATTRIBUTED: round(b[UNATTRIBUTED], 1),
            "total_au": round(sum(b.values()), 1),
            "regions_known": known.get(d, False),
        })

    return {
        "rows": rows,
        "unmapped_names": sorted(unmapped),
        "renormalised_names": sorted(renormalised),
        "attributed_fraction": (round(recon_seconds / elapsed_seconds, 3)
                                if elapsed_seconds > 0 else None),
    }


def region_au_for_date(rows: list[dict], d: date) -> dict | None:
    """The one row for `d`, or None. Rows without regional keys (a caller that
    hand-built [{"date", "total_au"}]) return None rather than three zeros —
    absent is not the same claim as zero."""
    iso = d.isoformat()
    for row in rows or []:
        if row.get("date") == iso and all(r in row for r in REGIONS):
            return row
    return None


# ─── strain ──────────────────────────────────────────────────────────────────

def region_strain(region_au: dict | None, stage: int) -> dict[str, float | None]:
    """Each region's own AU through engine.au_to_strain.

    None for every region when there is no session at all, or when nothing in
    the session mapped (`regions_known` False — a pure yoga day). Otherwise
    every region gets a number, possibly 0.0.

    That divergence from dashboard.au_to_strain_or_none is deliberate. On the
    overall metric None means "no session". On a regional breakdown a 0.0
    beside a 14.2 means "you did no upper-body work today", which is true and
    worth saying; a "—" there would read as missing data, which is false.
    """
    if not region_au or not region_au.get("regions_known"):
        return {r: None for r in REGIONS}
    return {r: _engine.au_to_strain(float(region_au.get(r) or 0.0), stage)
            for r in REGIONS}


def additivity_gap(region_strains: dict[str, float | None],
                   overall_strain: float | None) -> float | None:
    """sum(regions) − overall, so a screen can state the size of the
    discrepancy rather than gesture at it.

    This is the ONLY place the three are added, and the result is explicitly a
    measure of the gap — never presented as a total. Positive on any day whose
    load is spread across more than one region.
    """
    values = [v for v in region_strains.values() if v is not None]
    if not values or overall_strain is None:
        return None
    return round(sum(values) - overall_strain, 1)


def rolling_prior_region_strain(
    rows: list[dict], stage: int, today: date | None = None,
) -> dict[str, float | None]:
    """The regional analogue of dashboard.rolling_prior_strain: mean AU per
    region over the 7 days BEFORE today (rest days count as 0), each through
    the curve.

    All three are None when every region's 7-day mean is zero — matching the
    overall's own None, so a screen never shows 0.0/0.0/0.0 under a headline
    reading "No Readings".
    """
    today = today or date.today()
    by_date = {row.get("date"): row for row in rows or []}
    means = {}
    for r in REGIONS:
        total = 0.0
        for offset in range(1, 8):
            row = by_date.get((today - timedelta(days=offset)).isoformat())
            total += float((row or {}).get(r) or 0.0)
        means[r] = total / 7
    if sum(means.values()) <= 0:
        return {r: None for r in REGIONS}
    return {r: _engine.au_to_strain(means[r], stage) for r in REGIONS}


# ─── the heart-rate term ─────────────────────────────────────────────────────

def region_hr_load(hr_row: dict | None, region_au: dict | None) -> tuple[dict, str]:
    """(regional Edwards' load, basis).

    Edwards' TRIMP is one number for one body, so there is nothing in it that
    knows which muscles worked. The only defensible thing to do with it is
    divide it the way the AU divided — and then SAY that is what happened, so
    the screen never implies the watch supplied the regions.

    Σ over regions == hr_row["edwards_load"] exactly (split_parts).
    """
    if not hr_row or not region_au or not region_au.get("regions_known"):
        return {r: 0.0 for r in REGIONS}, HR_BASIS_NONE
    load = float(hr_row.get("edwards_load") or 0.0)
    attributed = sum(float(region_au.get(r) or 0.0) for r in REGIONS)
    if load <= 0 or attributed <= 0:
        return {r: 0.0 for r in REGIONS}, HR_BASIS_NONE
    shares = {r: float(region_au.get(r) or 0.0) / attributed for r in REGIONS}
    return split_parts(shares, round(load, 1)), HR_BASIS_AU_SHARES


def blend_region_strain(
    hr_region_load: dict, rpe_region_strain: dict[str, float | None],
    hr_basis: str,
) -> dict[str, tuple[float | None, str]]:
    """Per region, hr_load.blend_strain of its own HR-derived and RPE-derived
    strain. Uses hr_load.HR_BLEND_WEIGHT by reference, never a literal."""
    out = {}
    for r in REGIONS:
        hr_value = (_hr_load.hr_strain(hr_region_load.get(r, 0.0))
                    if hr_basis != HR_BASIS_NONE else None)
        out[r] = _hr_load.blend_strain(hr_value, rpe_region_strain.get(r))
    return out


# ─── regional ACWR ───────────────────────────────────────────────────────────

def region_acwr(
    rows: list[dict],
    stage: int = 1,
    today: date | None = None,
    stage_start: date | None = None,
) -> dict[str, dict]:
    """Three DELEGATED engine.acwr calls, then the floors above.

    Delegated rather than reimplemented because the stage-scoped chronic
    window, the ceiling table, ACWR_MIN_IN_STAGE_DAYS and hard_locked are
    safety-relevant behaviour that must have exactly one implementation. A
    parallel copy would be a second place to get the prior-stage-exclusion
    decision wrong — and that one was already measured moving ACWR the WRONG
    way when down-weighted (1.32 → 1.50 against an intended 0.93).

    No regional ceiling table exists: each region reports against
    rules.STAGE_CONSTRAINTS[stage]["acwr_ceiling"], inherited from the
    delegated call.

    Each result carries `hard_locked=False` and `advisory_only=True`
    UNCONDITIONALLY — not "because engine.ACWR_ADVISORY_MODE is True". That
    flag is expected to be flipped one day (it is a dated hold in CLAUDE.md's
    Known Open Issues), and a regional ratio built on invented weights is not
    the thing that should start capping volume on that day.
    """
    today = today or date.today()
    results: dict[str, dict] = {}
    chronic: dict[str, float] = {}

    for r in REGIONS:
        au_rows = [
            {"date": row["date"], "total_au": float(row.get(r) or 0.0)}
            for row in rows or [] if row.get("date") and r in row
        ]
        res = dict(_engine.acwr(au_rows, stage, today=today, stage_start=stage_start))
        res["loaded_days"] = sum(1 for v in res.get("daily_au_28") or [] if v > 0)
        chronic[r] = float(res.get("chronic_avg") or 0.0)
        results[r] = res

    chronic_total = sum(chronic.values())
    for r in REGIONS:
        res = results[r]
        res["chronic_share"] = (round(chronic[r] / chronic_total, 3)
                                if chronic_total > 0 else 0.0)
        thin = (res["loaded_days"] < REGION_ACWR_MIN_LOADED_DAYS
                or res["chronic_share"] < REGION_ACWR_MIN_CHRONIC_SHARE)
        if thin and res.get("acwr") is not None:
            # Withhold the RATIO, keep every fact that produced it.
            res["acwr"] = None
            res["status"] = STATUS_INSUFFICIENT_REGIONAL_LOAD
            res["exceeds_ceiling"] = False
        res["min_loaded_days"] = REGION_ACWR_MIN_LOADED_DAYS
        # Unconditional, and last, so nothing above can re-enable it.
        res["hard_locked"] = False
        res["advisory_only"] = True

    return results
