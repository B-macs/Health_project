"""
flexibility_baselines.py — the gym flexibility scan, transcribed.

Same reason `strength_baselines.py` and `body_composition_baselines.py` exist:
the source is not machine-readable and cannot be re-derived from anything the
app can reach. This one is worse than either — the source is a **phone
screenshot of a vendor app**, with no export, no PDF and no print-out. Lose this
file and the only instrumented range-of-motion measurements ever taken on this
athlete are gone.

Source: gym flexibility scan, five isolated regions measured 2025-01-17,
screenshotted and read 2026-08-05.

THE PROTOCOL IS UNRECORDED, AND THAT IS THE HEIGHT DEFECT ALL OVER AGAIN
-----------------------------------------------------------------------
`body_composition_baselines.py` records that the InBody sheet never prints the
height it was told, so four of five scans are wrong in every kilogram. The same
class of defect is here: the screen prints a number of degrees per region and
never says WHICH MOVEMENT produced it.

"Hip 33 deg" means something different, and corroborates a different clinical
finding, depending on whether it is internal rotation (normal 35-45), abduction
(normal ~45) or a Thomas-test hip extension (normal 10-20, where 33 would be
excellent rather than the "Low" the vendor printed). A reference band cannot be
chosen without knowing which.

So every entry carries `protocol`, and every entry currently carries
`protocol=None`. `reference_band` holds a PROVISIONAL band chosen from the most
likely protocol, and `provisional=True` propagates all the way to the score, to
the confidence weighting and to the screen. Nothing here silently defaults. The
athlete is asking the gym for the movement list (2026-08-05); when it arrives,
set `protocol` and confirm or replace each band, and the provisional penalty
disappears on its own.

LAT_FLEX IS DELIBERATELY LEFT UNSCOREABLE
-----------------------------------------
Its `reference_band` is None, not a guess. The vendor calls 20-21 deg "Normal",
which is incompatible with the obvious reading of the label — trunk lateral
flexion is normally 35-45 deg, where 20 would be markedly low, not normal. So
either the label does not mean trunk side-bend or the vendor's norms are not
population norms. Guessing a band here would invent a number out of a
contradiction. `services.flexibility` reports it as UNSCOREABLE and excludes it
from the Range axis; the region still scores off its Control axis.

THE PERFECT-SYMMETRY QUESTION, TO BE ANSWERED AT THE NEXT SCAN
--------------------------------------------------------------
Three regions differ left-to-right by 1-3 deg (lat flex 20/21, hip 33/32,
hamstrings 89/86). Two are EXACTLY equal (neck 30/30, chest 106/106).

Chest 106/106 is the least likely result on the sheet. This athlete has three
right anterior dislocations, a failed capsular repair and a Latarjet coracoid
transfer (patient_profile.py finding #6); a post-Latarjet shoulder
characteristically loses external rotation and horizontal abduction on the
operated side. Exact bilateral equality there is either one measurement mirrored
into both columns, or a protocol that does not isolate the shoulder.

Not asserted either way — `symmetry_suspect` flags the two, and one visit
settles it. Same discipline as keeping both 2025-05-21 InBody scans rather than
deduplicating the one that looked wrong.

THE VENDOR'S BIOAGE IS NOT STORED, AND ITS DEFECT IS WHY
--------------------------------------------------------
The screen reads "Flexibility BioAge 28 years" against "Real age: 31 years".
The measurement is from 2025-01-17, when this athlete was **30** (DOB
1994-10-19) — the vendor compares a Jan-2025 measurement against a LIVE
chronological age, so the displayed gap was -2 at measurement and is shown as
-3, and it widens every birthday without anybody moving. That is a console value
contaminating a derived number, exactly as the typed height was.

`services/body_composition.py` already refuses "body composition expressed as an
age in years"; the same refusal applies here and is enforced by a test. The
vendor's verdicts ARE kept, verbatim, as provenance — see `vendor_verdict` — but
nothing computes from them: converting a verdict to a score would import the
vendor's undisclosed norm table into ours and then double-count it against our
own reference band.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

#: The one date on which any instrumented ROM was recorded for this athlete.
SCAN_DATE: date = date(2025, 1, 17)

#: Chronological age ON THE SCAN DATE, not today. Recorded because the vendor
#: screen gets exactly this wrong. DOB 1994-10-19.
AGE_AT_SCAN_YEARS: int = 30

#: What the vendor's own screen displayed, kept only so the defect above stays
#: auditable. Nothing reads these two for any computation, and a test enforces
#: that no flexibility age in years is ever produced from them.
VENDOR_BIOAGE_YEARS: int = 28
VENDOR_BIOAGE_COMPARED_AGAINST_AGE: int = 31


@dataclass(frozen=True)
class RegionBaseline:
    """One isolated-ROM row off the vendor screen.

    left_deg/right_deg are as printed. `protocol` is the movement that produced
    them and is None until the gym supplies the list. `reference_band` is
    (lo, hi) in degrees of the IDEAL range — full marks inside it, penalised
    below it, and penalised above it too, because for a hypermobile athlete
    more range is not automatically better. None means UNSCOREABLE.
    """
    key: str
    label: str
    left_deg: float | None
    right_deg: float | None
    vendor_verdict: str | None          # "Low" | "Normal" | None — provenance only
    protocol: str | None                # None = unrecorded
    assumed_protocol: str | None        # what reference_band was chosen for
    reference_band: tuple[float, float] | None
    provisional: bool                   # True while protocol is None
    symmetry_suspect: bool = False
    note: str = ""

    @property
    def mean_deg(self) -> float | None:
        sides = [s for s in (self.left_deg, self.right_deg) if s is not None]
        return sum(sides) / len(sides) if sides else None

    @property
    def asymmetry_deg(self) -> float | None:
        if self.left_deg is None or self.right_deg is None:
            return None
        return abs(self.left_deg - self.right_deg)


#: The eight regions the vendor screen lays out, in its own order. Three carry
#: no instrumented reading at all — they are the "Functional flexibility
#: results" rows, all of which read "No data yet". They are kept as entries
#: rather than omitted so that coverage is visible instead of invisible.
REGION_BASELINES: dict[str, RegionBaseline] = {
    "neck": RegionBaseline(
        key="neck", label="Neck",
        left_deg=30.0, right_deg=30.0, vendor_verdict="Low",
        protocol=None, assumed_protocol="cervical lateral flexion",
        reference_band=(40.0, 50.0), provisional=True, symmetry_suspect=True,
        note="30 deg is low for lateral flexion (normal ~45) and severely low for "
             "rotation (normal ~80), so the verdict is consistent with either. "
             "Independently, symptom_log 2026-07-31 records ASYMMETRIC cervical "
             "flexion tightness, left-dominant — which the exactly-equal 30/30 "
             "does not show. That assessment is 18 months later, so this is not "
             "necessarily a contradiction, but it is the second reason to doubt "
             "the perfect symmetry.",
    ),
    "chest": RegionBaseline(
        key="chest", label="Chest",
        left_deg=106.0, right_deg=106.0, vendor_verdict="Low",
        protocol=None, assumed_protocol="supine shoulder flexion",
        reference_band=(160.0, 180.0), provisional=True, symmetry_suspect=True,
        note="See the module docstring — exact bilateral equality is least "
             "plausible here of anywhere on the sheet, given finding #6.",
    ),
    "lat_flex": RegionBaseline(
        key="lat_flex", label="Lat Flex",
        left_deg=20.0, right_deg=21.0, vendor_verdict="Normal",
        protocol=None, assumed_protocol=None,
        reference_band=None, provisional=True,
        note="UNSCOREABLE by design. 'Normal' at 20-21 deg contradicts the "
             "obvious reading of the label (trunk lateral flexion, normal "
             "35-45). Do not guess a band out of a contradiction.",
    ),
    "hip": RegionBaseline(
        key="hip", label="Hip",
        left_deg=33.0, right_deg=32.0, vendor_verdict="Low",
        protocol=None, assumed_protocol="hip internal rotation",
        reference_band=(35.0, 45.0), provisional=True,
        note="Internal rotation assumed because the vendor called it Low, which "
             "rules out a Thomas-test reading (normal 10-20, where 33 would be "
             "excellent). If it IS internal rotation, low bilaterally "
             "corroborates the tight posterior capsule and piriformis in "
             "imbalances.overactive_tight.",
    ),
    "hamstrings": RegionBaseline(
        key="hamstrings", label="Hamstrings",
        left_deg=89.0, right_deg=86.0, vendor_verdict="Normal",
        protocol=None, assumed_protocol="passive straight-leg raise",
        reference_band=(80.0, 90.0), provisional=True,
        note="Best-supported of the five assumptions: SLR normal is 80-90 and "
             "the vendor's 'Normal' agrees. This is the reading that reconciles "
             "with the 25/100 straddle fold — see patient_profile.py symptom_log "
             "2026-08-05. Normal length with NO RESERVE, not shortness: "
             "long-sitting upright is already ~90 deg of hip flexion with the "
             "knee straight, so at 86-89 he is at the limit merely sitting up. "
             "If this is actually a popliteal-angle test, that reconciliation "
             "needs redoing.",
    ),
    "squat_depth": RegionBaseline(
        key="squat_depth", label="Squat Depth",
        left_deg=None, right_deg=None, vendor_verdict=None,
        protocol=None, assumed_protocol=None, reference_band=None,
        provisional=False,
        note="'No data yet' on the device. NOT to be filled from the 2025 "
             "training log's 'mobility excellent, hits depth easily' — that is "
             "a qualitative note, not a measurement, and writing it here would "
             "be the same error as fusing the scale's body fat with the "
             "InBody's. The yoga flow has no squat pose either, so this region "
             "is genuinely uncovered on both axes.",
    ),
    "back": RegionBaseline(
        key="back", label="Back",
        left_deg=None, right_deg=None, vendor_verdict=None,
        protocol=None, assumed_protocol=None, reference_band=None,
        provisional=False,
        note="'No data yet' on the device. Covered on the Control axis by the "
             "yoga flow's twists and folds.",
    ),
    "shoulders": RegionBaseline(
        key="shoulders", label="Shoulders",
        left_deg=None, right_deg=None, vendor_verdict=None,
        protocol=None, assumed_protocol=None, reference_band=None,
        provisional=False,
        note="'No data yet' on the device. Covered on the Control axis by Down "
             "Dog, Walk the Dog and the two hip openers.",
    ),
}

#: Display order, as the vendor lays it out: functional block first, then
#: isolated. Kept so our screen can mirror the one the athlete already reads.
FUNCTIONAL_REGIONS: tuple[str, ...] = ("squat_depth", "back", "shoulders")
ISOLATED_REGIONS: tuple[str, ...] = ("neck", "chest", "lat_flex", "hip", "hamstrings")


#: Share of the overall score each region carries. Documented prior, not fitted
#: — there is one instrumented date, so nothing could be fitted. Weighted toward
#: this athlete's clinical centre: lumbar spine (L3-S1 protrusions, activated
#: L5/S1 osteochondrosis) and hips (Coxa Saltans, tight posterior capsule,
#: upper-glute gripping) carry the most, and both are where symptoms actually
#: appear. Revisit only with a reason, and record the reason.
REGION_WEIGHT: dict[str, float] = {
    "hip":         0.20,
    "back":        0.20,
    "hamstrings":  0.15,
    "shoulders":   0.15,
    "neck":        0.10,
    "chest":       0.08,
    "lat_flex":    0.07,
    "squat_depth": 0.05,
}


#: Which yoga poses inform which region's CONTROL axis, and how strongly.
#: Weights per pose sum to 1.0 so no pose counts more than once in total.
#:
#: Same pattern as training_constants.EXERCISE_BODY_REGION — and the SAME
#: failure mode: a pose missing from this dict is silently excluded from every
#: region total. services.flexibility.control_axis returns the unmapped pose
#: names as part of its result for exactly that reason, which is the cheapest
#: way to notice. Savasana is deliberately absent: it is not a stretch.
POSE_REGION_WEIGHT: dict[str, dict[str, float]] = {
    "Seated Cross-Legged Side Bend (Shoulder Drop)": {"lat_flex": 0.6, "back": 0.3, "neck": 0.1},
    "Seated Side Stretch (Right)":                   {"lat_flex": 0.7, "back": 0.3},
    "Seated Side Stretch (Left)":                    {"lat_flex": 0.7, "back": 0.3},
    "90/90 Hip Rotation":                            {"hip": 1.0},
    "Butterfly Forward Fold":                        {"hip": 0.5, "back": 0.5},
    "Walk the Dog (Down Dog pedaling)":              {"hamstrings": 0.6, "shoulders": 0.4},
    "Deep Lunge (Right)":                            {"hip": 1.0},
    "Deep Lunge Hip Opener (Right)":                 {"hip": 0.6, "back": 0.2, "shoulders": 0.2},
    "Half Pigeon Pose (Right)":                      {"hip": 1.0},
    "Seated Twist (Left)":                           {"back": 1.0},
    "Down Dog":                                      {"shoulders": 0.5, "hamstrings": 0.3, "back": 0.2},
    "Deep Lunge (Left)":                             {"hip": 1.0},
    "Deep Lunge Hip Opener (Left)":                  {"hip": 0.6, "back": 0.2, "shoulders": 0.2},
    "Half Pigeon Pose (Left)":                       {"hip": 1.0},
    "Seated Twist (Right)":                          {"back": 1.0},
    "Straddle Forward Fold":                         {"hamstrings": 0.5, "hip": 0.3, "back": 0.2},
    "Knee to Chest (Right)":                         {"hip": 0.7, "back": 0.3},
    "Lying Twist (Right)":                           {"back": 0.7, "hip": 0.3},
    "Knee to Chest (Left)":                          {"hip": 0.7, "back": 0.3},
    "Lying Twist (Left)":                            {"back": 0.7, "hip": 0.3},
    "Happy Baby":                                    {"hip": 0.8, "back": 0.2},
}

#: Poses with no region mapping, stated rather than left implicit.
UNMAPPED_POSES: frozenset[str] = frozenset({"Deep Relaxation (Savasana)"})


#: The 2026-08-05 self-rated depth ratings, 1-100, one per pose. 1 = can barely
#: enter the position, 100 = at the physical limit with no stretch sensation
#: left. Athlete's own scale and own numbers; full table with his verbatim
#: reasons in docs/training/Yoga_Library.md.
#:
#: NOTE the scale's 100 is NOT the overall score's 100. On this scale 100 means
#: "at the end of what is physically possible"; on the overall it means "ideal".
#: services.flexibility.control_score is the transform between them, and it is
#: the whole reason the two axes exist.
POSE_DEPTH_RATING_2026_08_05: dict[str, int] = {
    "Seated Cross-Legged Side Bend (Shoulder Drop)": 40,
    "Seated Side Stretch (Right)":                   60,
    "Seated Side Stretch (Left)":                    65,
    "90/90 Hip Rotation":                            85,
    "Butterfly Forward Fold":                        82,
    "Walk the Dog (Down Dog pedaling)":              76,
    "Deep Lunge (Right)":                            57,
    "Deep Lunge Hip Opener (Right)":                 46,
    "Half Pigeon Pose (Right)":                      40,
    "Seated Twist (Left)":                           66,
    "Down Dog":                                      64,
    "Deep Lunge (Left)":                             57,
    "Deep Lunge Hip Opener (Left)":                  46,
    "Half Pigeon Pose (Left)":                       40,
    "Seated Twist (Right)":                          68,
    "Straddle Forward Fold":                         25,
    "Knee to Chest (Right)":                         85,
    "Lying Twist (Right)":                           85,
    "Knee to Chest (Left)":                          88,
    "Lying Twist (Left)":                            88,
    "Happy Baby":                                    80,
    "Deep Relaxation (Savasana)":                   100,
}

#: When the depth ratings above were taken.
DEPTH_RATING_DATE: date = date(2026, 8, 5)
