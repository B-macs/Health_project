"""today.py — the ONE cached read of today's decision, for BOTH screens.

⚠ WHY THIS IS A MODULE AND NOT A HELPER IN EACH VIEW. Two identically-coded
@st.cache_data functions are TWO INDEPENDENT CACHE ENTRIES with independent
TTLs. Home fills at 09:00, Training fills at 09:31 after a sync lands, and the
two screens then disagree with byte-identical source. The cached reader has to
be one function OBJECT, not one algorithm — which is why _engine_directive moved
out of views/training.py rather than being copied into app.py.

This sits at the root beside nav.py / repo.py / styles.py because it is a
Streamlit-layer module: it holds the CACHING, and nothing else. The reads and
the composition are services/decision.py (moved there on 2026-10-19, so the
phone's API reads the same decision for the phone's date), the pure verdict is
services/verdict.py, and the decision itself is services.sessions.load_policy,
untouched. services/decision.py is also where the ring's HRV run crosses onto a
screen that carries a load decision, as one string.
"""

from datetime import date

import streamlit as st

import repo
from services import decision, verdict


@st.cache_data(ttl=1800, show_spinner=False)
def today_directive() -> dict:
    """Traffic light + ACWR + injury weight, as one directive
    (decision.directive). A failed read is "no opinion"."""
    try:
        r = repo.get_repository()
    except Exception:
        return dict(decision.NO_OPINION)
    return decision.directive(r, date.today())


@st.cache_data(ttl=1800, show_spinner=False)
def _bio_for_readiness() -> list[dict]:
    return decision.readiness_rows(repo.get_repository(), date.today())


@st.cache_data(ttl=1800, show_spinner=False)
def today_readiness_modifier() -> dict:
    try:
        rows = _bio_for_readiness()
    except Exception:
        return {}
    return decision.readiness_modifier(rows)


@st.cache_data(ttl=1800, show_spinner=False)
def today_readiness_raw() -> float | None:
    """The score the engine actually buckets — NOT the EMA on Home's card
    (decision.readiness_raw)."""
    try:
        rows = _bio_for_readiness()
    except Exception:
        return None
    return decision.readiness_raw(rows, date.today())


@st.cache_data(ttl=1800, show_spinner=False)
def _ring_hrv_series() -> dict:
    """The RAW ring series, keyed by date (decision.ring_hrv_series)."""
    return decision.ring_hrv_series(repo.get_repository(), date.today())


def today_hrv_note(directive: dict | None = None) -> str:
    """The ring's downward-run sentence, or "" (decision.hrv_note: its own
    try/except, so a failed caption never greys the directive, and suppressed
    when the light already names HRV)."""
    return decision.hrv_note(directive, date.today(), _ring_hrv_series)


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
