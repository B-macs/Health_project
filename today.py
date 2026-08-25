"""today.py — the ONE cached read of today's decision, for BOTH screens.

⚠ WHY THIS IS A MODULE AND NOT A HELPER IN EACH VIEW. Two identically-coded
@st.cache_data functions are TWO INDEPENDENT CACHE ENTRIES with independent
TTLs. Home fills at 09:00, Training fills at 09:31 after a sync lands, and the
two screens then disagree with byte-identical source. The cached reader has to
be one function OBJECT, not one algorithm — which is why _engine_directive moved
out of views/training.py rather than being copied into app.py.

This sits at the root beside nav.py / repo.py / styles.py because it is a
Streamlit-layer module: it holds the caching and the I/O. The pure composition
it hands off to is services/verdict.py, and the decision itself is
services.sessions.load_policy, untouched.

It is also the file where hrv_trend crosses onto a screen that carries a load
decision — deliberately HERE, outside services/, so that neither engine.py nor
sessions.py nor verdict.py ever gains a name through which the device-dependent
60/40 combined figure could be reached. What crosses is one string.
"""

from dataclasses import asdict
from datetime import date

import streamlit as st

import repo
from services import engine, hrv_trend, plan as ph, readiness, verdict

#: What a failed engine read degrades to. Grey means "no opinion", which
#: load_policy turns into no banner on either screen — so the two go quiet
#: TOGETHER and still cannot disagree.
_NO_OPINION = {"signal_color": "grey", "label": "", "action": "", "multiplier": 1.0}


@st.cache_data(ttl=1800, show_spinner=False)
def today_directive() -> dict:
    """Traffic light + ACWR + injury weight, as one directive.

    Moved verbatim from views/training.py::_engine_directive on 2026-08-23 so
    Home can read the same object. One read dropped on the way: the previous
    body assigned `tight = r.get_avg_tightness(14)` and never used it, which
    was a whole Notion query per cache fill.
    """
    try:
        r = repo.get_repository()
        bio = [asdict(b) for b in r.get_biometric_rolling(days=28)]
        # Separate, deliberately wide fetch feeding ONLY the baseline-drift
        # guard — see engine.traffic_light's drift_rows docstring for why this
        # can't just be a longer `bio`.
        drift = [asdict(b) for b in
                 r.get_biometric_rolling(days=engine.DRIFT_RECOMMENDED_FETCH_DAYS)]
        au = r.get_daily_session_au_weighted(28)
        diag = r.get_diagnostic_profile()
        stage = r.get_current_stage()
        streak = r.get_pain_free_streak()
        lam = float(diag.get("injury_weight_decay_lambda") or 0.05)
        # for_date is what stops a stale row being graded as this morning
        # -- see engine.traffic_light's _row_can_be_judged note.
        tl = engine.traffic_light(bio, drift_rows=drift, for_date=date.today())
        # Scope ACWR's chronic baseline to the current stage — see
        # engine.ACWR_MIN_IN_STAGE_DAYS.
        acwr_r = engine.acwr(au, stage,
                             stage_start=ph.current_stage_start(r.get_phases(),
                                                                date.today()))
        inj_w = engine.injury_weight(lam, streak)
        obs_rem = engine.observation_days_remaining(tl["data_days"])
        rec = engine.volume_recommendation(tl, acwr_r, stage, obs_rem, inj_w)
        # Carried so the HRV note can be suppressed when the light ALREADY
        # names HRV — see today_hrv_note. Not read by any decision.
        rec["_traffic_drivers"] = tuple(tl.get("drivers") or ())
        return rec
    except Exception:
        return dict(_NO_OPINION)


@st.cache_data(ttl=1800, show_spinner=False)
def _bio_for_readiness() -> list[dict]:
    return [asdict(b) for b in repo.get_repository().get_biometric_rolling(days=14)]


@st.cache_data(ttl=1800, show_spinner=False)
def today_readiness_modifier() -> dict:
    try:
        return engine.readiness_training_modifier(_bio_for_readiness())
    except Exception:
        return {}


@st.cache_data(ttl=1800, show_spinner=False)
def today_readiness_raw() -> float | None:
    """The score the engine actually buckets — NOT the EMA on Home's card.

    Both are shown, because the gap between them is what produced the
    2026-08-23 report and hiding it would not close it.
    """
    try:
        rows = _bio_for_readiness()
        score = readiness.compute_readiness(bio_rows=rows)
        return None if isinstance(score, str) else float(score)
    except Exception:
        return None


@st.cache_data(ttl=1800, show_spinner=False)
def _ring_hrv_series() -> dict:
    """The RAW ring series, keyed by date.

    ⚠ hrv_trend_series()["oura"], never `hrv_ms` off get_biometric_rolling.
    Those are the same numbers only while biometrics.HRV_GARMIN_HOLD is on; the
    day it lifts, hrv_ms becomes a 70/30 mixture and the sentence would start
    describing a blend while claiming to describe the ring.
    """
    raw = repo.get_repository().hrv_trend_series(days=120)
    return {date.fromisoformat(k): v for k, v in raw["oura"].items()}


def today_hrv_note(directive: dict | None = None) -> str:
    """The ring's downward-run sentence, or "".

    ⚠ ITS OWN try/except, separate from today_directive's. Folding this read
    into that one would mean a failure in a DISPLAY-ONLY feature silently
    degrading the whole directive to grey — losing the traffic light, the ACWR
    advisory and the injury cap because an HRV query timed out. A guardrail
    must not be taken down by a caption.

    SUPPRESSED when the traffic light already names HRV as what it acted on:
    otherwise a day HRV drives the light yellow shows two warnings about one
    reading. Same rule engine.acwr_advisory_note already applies — nothing is
    emitted when the recommendation already carries the message.
    """
    try:
        drivers = (directive or {}).get("_traffic_drivers") or ()
        if "hrv_ms" in drivers:
            return ""
        return hrv_trend.ring_run_advisory(_ring_hrv_series(), date.today()) or ""
    except Exception:
        return ""


def today_verdict(readiness_display: float | None = None,
                  readiness_band: str = "") -> verdict.Verdict:
    """The object both screens render from. Uncached — it is arithmetic over
    three cached reads, and caching it would add a fourth TTL to fall out of
    step with the other three."""
    directive = today_directive()
    return verdict.today_verdict(
        directive,
        today_readiness_modifier(),
        readiness_display=readiness_display,
        readiness_raw=today_readiness_raw(),
        readiness_band=readiness_band,
        hrv_note=today_hrv_note(directive),
    )
