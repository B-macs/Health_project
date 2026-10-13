"""
services/metrics.py — Weekly Rollup sync orchestration.

The one module in services/ that both computes (via metrics_logic.py's pure
functions) and does I/O (via repository.py) — kept separate from
metrics_logic.py so the pure scoring functions need zero mocking to test.
Still zero Streamlit imports: Repository itself never touches st.secrets or
st.cache_*, so importing it here doesn't violate that rule.
"""

from __future__ import annotations

import dataclasses
from datetime import date, datetime

from services import metrics_logic
from services.models import WeekScore
from services.repository import Repository


@dataclasses.dataclass(frozen=True)
class SyncResult:
    ok: bool
    synced_week_starts: list[str]
    error: str | None = None


def sync_weekly_rollup(repository: Repository, today: date | None = None) -> SyncResult:
    """Computes the full week history and upserts every ENDED week to the
    Weekly Rollup Sheet tab (idempotent, keyed on week_start — see
    Repository.upsert_weekly_rollup). Never writes the current in-progress
    week. On any failure (phases/sessions read, or the Sheets write itself),
    returns a failed SyncResult instead of raising, so callers can degrade
    gracefully to in-memory-only display."""
    today = today or date.today()
    try:
        phases = repository.get_phases()
        if not phases:
            return SyncResult(ok=True, synced_week_starts=[])

        earliest = min(date.fromisoformat(p.start_date) for p in phases)
        sessions = [{"date": d} for d in repository.get_logged_session_dates(earliest, today)]

        history = metrics_logic.compute_week_history(today, phases, sessions)
        ended = [w for w in history if w.status != "in_progress"]

        # ONLY THE WEEKS WHOSE VERDICT CHANGED (2026-10-13). Every ended week
        # was re-stamped and rewritten on each refresh, so every row looked
        # changed. With Supabase as the record each row is one waited write
        # (~136 ms), and this runs inside the Training page's render: fifteen
        # unchanged weeks stalled it about two seconds every half hour. An
        # unreadable table writes every week, as before.
        try:
            stored = {w.week_start: w for w in repository.get_weekly_rollup_history()}
        except Exception:
            stored = {}
        changed = [w for w in ended if not _same_verdict(w, stored.get(w.week_start))]

        now_iso = datetime.now().isoformat(timespec="seconds")
        stamped: list[WeekScore] = [dataclasses.replace(w, computed_at=now_iso) for w in changed]

        written = repository.upsert_weekly_rollup(stamped) if stamped else []
        return SyncResult(ok=True, synced_week_starts=written)
    except Exception as exc:
        return SyncResult(ok=False, synced_week_starts=[], error=str(exc))


def _same_verdict(week: WeekScore, stored: WeekScore | None) -> bool:
    """A stored row says the same thing as a fresh one — everything but the
    time it was computed."""
    if stored is None:
        return False
    fields = ("week_end", "phase_number", "scheduled", "completed", "status")
    return all(str(getattr(week, f)) == str(getattr(stored, f)) for f in fields)
