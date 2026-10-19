"""The day's training decision, read and composed for a given day.

Home and the Training page show ONE decision: today.py caches it once per
process, so the two screens cannot disagree. The phone's API must show the
same decision for the phone's own date (rebuild rule 3). So the reads and the
composition live here, with the day as a parameter, and today.py keeps only
the caching around them.

⚠ THE RING'S HRV RUN CROSSES INTO THE DECISION HERE, AS ONE STRING. hrv_note
is the only place this module touches services/hrv_trend.py, and what leaves
it is a sentence for the verdict to show beside the decision, never a number
any rule reads. No guardrail may import this module, which is what keeps the
device-dependent combined HRV figure out of their reach
(tests/test_decision.py, tests/test_hrv_trend.py). Until 2026-10-19 this
composition sat in today.py, outside services/, for the same reason.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Callable

from services import engine, hrv_trend, readiness, verdict, week_repeat
from services import plan as _plan
from services import sessions as _sess

#: What a failed engine read degrades to. Grey means "no opinion", which
#: load_policy turns into no banner on either screen — so the two go quiet
#: TOGETHER and still cannot disagree.
NO_OPINION = {"signal_color": "grey", "label": "", "action": "", "multiplier": 1.0}

#: The rows the readiness modifier and the engine's daily readiness read.
READINESS_WINDOW_DAYS = 14


def engine_state(repo, day: date, *, with_stage_status: bool = False) -> dict:
    """The reads and the arithmetic behind the directive for `day`, every part
    kept: the rows, the traffic light (its metrics and baseline drift), ACWR
    with its windows, the injury weight, and the recommendation they make.
    The directive is this state's recommendation; Insights › Engine Data
    shows the rest. A failed read raises (directive() turns it into
    NO_OPINION).

    `for_date` is what stops a stale row being graded as this morning
    (engine.traffic_light's _row_can_be_judged note), and ACWR's chronic
    baseline is scoped to the current stage (engine.ACWR_MIN_IN_STAGE_DAYS).
    `with_stage_status` adds engine.stage_status, which needs one more read,
    the average tightness, that the directive does not."""
    bio = [asdict(b) for b in repo.get_biometric_rolling(days=28, today=day)]
    # Separate, deliberately wide fetch feeding ONLY the baseline-drift guard —
    # see engine.traffic_light's drift_rows docstring for why this can't just
    # be a longer `bio`.
    drift = [asdict(b) for b in repo.get_biometric_rolling(
        days=engine.DRIFT_RECOMMENDED_FETCH_DAYS, today=day)]
    au = repo.get_daily_session_au_weighted(28, today=day)
    diag = repo.get_diagnostic_profile()
    stage = repo.get_current_stage()
    streak = repo.get_pain_free_streak(today=day)
    lam = float(diag.get("injury_weight_decay_lambda") or 0.05)
    tl = engine.traffic_light(bio, drift_rows=drift, for_date=day)
    acwr_r = engine.acwr(au, stage,
                         stage_start=_plan.current_stage_start(repo.get_phases(), day))
    inj_w = engine.injury_weight(lam, streak)
    obs_rem = engine.observation_days_remaining(tl["data_days"])
    state = {
        "bio_rows": bio,
        "stage": stage,
        "pain_free_streak": streak,
        "traffic_light": tl,
        "acwr": acwr_r,
        "injury_weight": inj_w,
        "recommendation": engine.volume_recommendation(tl, acwr_r, stage, obs_rem, inj_w),
    }
    if with_stage_status:
        state["stage_status"] = engine.stage_status(
            stage, streak, repo.get_avg_tightness(14, today=day))
    return state


def directive(repo, day: date) -> dict:
    """Traffic light + ACWR + injury weight, as one directive for `day`
    (engine_state's recommendation). A failed read degrades to NO_OPINION."""
    try:
        state = engine_state(repo, day)
    except Exception:
        return dict(NO_OPINION)
    rec = state["recommendation"]
    # Carried so the HRV note can be suppressed when the light ALREADY names
    # HRV. Not read by any decision.
    rec["_traffic_drivers"] = tuple(state["traffic_light"].get("drivers") or ())
    return rec


def readiness_rows(repo, day: date) -> list[dict]:
    """The READINESS_WINDOW_DAYS rows ending on `day`, as engine-shaped dicts."""
    return [asdict(b) for b in repo.get_biometric_rolling(days=READINESS_WINDOW_DAYS, today=day)]


def readiness_modifier(rows: list[dict]) -> dict:
    try:
        return engine.readiness_training_modifier(rows)
    except Exception:
        return {}


def readiness_raw(rows: list[dict], day: date) -> float | None:
    """The score the engine actually buckets — NOT the trend on Home's card.
    Both are shown, because the gap between them is what produced the
    2026-08-23 report and hiding it would not close it."""
    try:
        score = readiness.compute_readiness(for_date=day, bio_rows=rows)
        return None if isinstance(score, str) else float(score)
    except Exception:
        return None


def ring_hrv_series(repo, day: date) -> dict:
    """The RAW ring series, keyed by date.

    ⚠ hrv_trend_series()["oura"], never `hrv_ms` off get_biometric_rolling.
    Those are the same numbers only while biometrics.HRV_GARMIN_HOLD is on; the
    day it lifts, hrv_ms becomes a 70/30 mixture and the sentence would start
    describing a blend while claiming to describe the ring."""
    raw = repo.hrv_trend_series(days=120, today=day)
    return {date.fromisoformat(k): v for k, v in raw["oura"].items()}


def hrv_note(directive_: dict | None, day: date, read_series: Callable[[], dict]) -> str:
    """The ring's downward-run sentence, or "".

    ⚠ ITS OWN try/except, separate from directive()'s. Folding this read into
    that one would mean a failure in a DISPLAY-ONLY feature silently degrading
    the whole directive to grey — losing the traffic light, the ACWR advisory
    and the injury cap because an HRV query timed out. A guardrail must not be
    taken down by a caption. `read_series` is called only when the note can
    show, so a day HRV already drives the light costs no read.

    SUPPRESSED when the traffic light already names HRV as what it acted on:
    otherwise a day HRV drives the light yellow shows two warnings about one
    reading. Same rule engine.acwr_advisory_note already applies."""
    try:
        drivers = (directive_ or {}).get("_traffic_drivers") or ()
        if "hrv_ms" in drivers:
            return ""
        return hrv_trend.ring_run_advisory(read_series(), day) or ""
    except Exception:
        return ""


def day_verdict(repo, day: date, readiness_display: float | None = None,
                readiness_band: str = "") -> verdict.Verdict:
    """The verdict for `day`, everything read through `repo`: what the phone's
    API returns, and what today.py composes from its cached reads."""
    directive_ = directive(repo, day)
    try:
        rows = readiness_rows(repo, day)
    except Exception:
        rows = []
    return verdict.today_verdict(
        directive_,
        readiness_modifier(rows),
        readiness_display=readiness_display,
        readiness_raw=readiness_raw(rows, day) if rows else None,
        readiness_band=readiness_band,
        hrv_note=hrv_note(directive_, day, lambda: ring_hrv_series(repo, day)),
    )


def training_policy(policy: dict, phases: list, day: date) -> dict:
    """The day's load policy as the training screen applies it: the verdict's
    policy, with the failed-week hold folded in BEFORE anything reads it
    (Key Rule 22, athlete 2026-09-16: "if there is a failed week then no
    increases in the weights during that week"), so the volume factor, the
    seeded numbers and the accessory session all see one decision. A failed
    check leaves the policy as it was; the + button adds load either way."""
    try:
        if phases and week_repeat.failed_week_holds_load(phases, day):
            return _sess.hold_for_failed_week(policy)
    except Exception:
        pass
    return policy
