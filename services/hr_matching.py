"""
services/hr_matching.py — associate Garmin activities with logged sessions.

Pure functions, no I/O. Two jobs:

  1. Decide which Garmin activity (if any) IS a given logged training
     session, by wall-clock overlap.
  2. Split that activity's heart-rate series across the session's individual
     exercises, using the per-set timestamps the guided flow records.

Why overlap rather than "most recent activity"
──────────────────────────────────────────────
The pre-existing hook for run/walk days (Repository.
get_recent_garmin_activity_minutes) matches on the activity's own DURATION
being close to the planned duration, because that flow knows what it's
looking for and only ever runs immediately after the walk.

That approach cannot work here. A gym session's Garmin activity has no
predictable duration to match against, several activities can exist on the
same day, and the session may be logged well after it finished. So this
matches the way the request describes it: the activity whose time span
actually overlaps the session's, taking the largest overlap when more than
one qualifies.

Clock skew between the watch and the phone, plus the gap between finishing
the last set and tapping "Save Session", mean the two spans rarely align
exactly — hence MATCH_TOLERANCE_SECONDS, which pads the session window
before testing for overlap.
"""

from __future__ import annotations

from datetime import datetime, timedelta

# Padding applied to each end of the logged session window before testing
# overlap. Covers watch-vs-phone clock skew and the lag between the final set
# and actually saving the session.
MATCH_TOLERANCE_SECONDS: float = 15 * 60.0

# An overlap shorter than this is treated as coincidence rather than a match —
# stops a short walk that happens to butt up against the session from being
# claimed as the gym activity.
MIN_OVERLAP_SECONDS: float = 5 * 60.0

# Activity types that are never a gym session, even on a perfect overlap.
# Kept deliberately small: anything not listed is allowed to match, because
# Garmin's typeKey for indoor strength work varies by device and firmware
# ("strength_training", "indoor_cardio", "fitness_equipment", ...) and an
# allow-list would silently drop real matches.
NON_SESSION_ACTIVITY_TYPES: frozenset[str] = frozenset({
    "sleep", "rest",
})


def _to_dt(value) -> datetime | None:
    """Parse the timestamp shapes that reach this module: ISO strings (per-set
    "ts" records), Garmin's "%Y-%m-%d %H:%M:%S" local strings, and datetimes
    passed straight through."""
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _comparable(*dts: datetime) -> tuple[datetime, ...]:
    """Make a set of datetimes safe to compare with each other.

    The two sides of a match come from different worlds and always have:
    our per-set "ts" is TIMEZONE-AWARE (services.sessions.set_timestamp
    stamps an explicit offset), while Garmin's "startTimeLocal" is a NAIVE
    local string. Python refuses to order an aware datetime against a naive
    one, and the resulting TypeError propagates out of match_activity into a
    caller that treats any failure as "no activity matched" — so the whole
    HR feature would have gone quietly dark on the first session logged after
    timezones were introduced, reporting no match rather than an error.

    When every bound is aware they are compared as INSTANTS, which is
    strictly correct. When the set is mixed, all are reduced to WALL CLOCK,
    which is the right reading here: our aware timestamp is rendered in the
    athlete's own zone, and Garmin's local string is the wall clock where the
    activity happened, so the two describe the same clock face.

    (The one case that reads wrong is training abroad while HEALTH_TIMEZONE
    still names home — then the athlete's rendered clock and the watch's
    local clock genuinely differ. That is a configuration limit, not a
    comparison bug, and it fails toward "no match" rather than a wrong one.)
    """
    if all(d.tzinfo is not None for d in dts):
        return dts
    return tuple(d.replace(tzinfo=None) if d.tzinfo is not None else d for d in dts)


def overlap_seconds(a_start, a_end, b_start, b_end) -> float:
    """Seconds two time spans share. 0.0 if they don't intersect or any bound
    is unparseable."""
    a0, a1, b0, b1 = _to_dt(a_start), _to_dt(a_end), _to_dt(b_start), _to_dt(b_end)
    if None in (a0, a1, b0, b1):
        return 0.0
    a0, a1, b0, b1 = _comparable(a0, a1, b0, b1)
    if a1 < a0:
        a0, a1 = a1, a0
    if b1 < b0:
        b0, b1 = b1, b0
    latest_start, earliest_end = max(a0, b0), min(a1, b1)
    return max(0.0, (earliest_end - latest_start).total_seconds())


def session_window(set_records: list[dict], fallback_date: str | None = None,
                    duration_minutes: float = 0.0) -> tuple[datetime, datetime] | None:
    """The session's real wall-clock span, from the per-set "ts" timestamps
    the guided flow captures (services.sessions.build_set_record).

    Returns None when no set carries a timestamp — which is the case for
    every session logged before per-set capture existed. Those sessions
    cannot be time-matched at all and correctly fall through to RPE-only
    strain; there is no way to recover a start time that was never recorded.

    The window runs from the FIRST set's timestamp to the last, then extends
    by `duration_minutes` only if that would widen it (a session whose sets
    all landed inside a couple of minutes still occupied its full duration —
    warm-up and rest before the first logged set aren't timestamped).
    """
    stamps = sorted(
        dt for dt in (_to_dt(r.get("ts")) for r in (set_records or [])) if dt is not None
    )
    if not stamps:
        return None
    start, end = stamps[0], stamps[-1]
    if duration_minutes > 0:
        implied_end = start + timedelta(minutes=duration_minutes)
        if implied_end > end:
            end = implied_end
    return start, end


def match_activity(
    activities: list[dict], window: tuple[datetime, datetime] | None,
    tolerance_seconds: float = MATCH_TOLERANCE_SECONDS,
    min_overlap_seconds: float = MIN_OVERLAP_SECONDS,
) -> tuple[dict | None, float]:
    """Pick the Garmin activity that best overlaps the session window.

    `activities`: normalised rows (Repository._garmin_activity_row's shape) —
    "start_time_local", "duration_minutes", "type".

    Returns (activity, overlap_seconds); (None, 0.0) when nothing qualifies.
    Ties break toward the LARGER overlap, then the longer activity, so a full
    gym session wins over a short walk nested inside the same window.
    """
    if not window or not activities:
        return None, 0.0
    padded_start = window[0] - timedelta(seconds=tolerance_seconds)
    padded_end = window[1] + timedelta(seconds=tolerance_seconds)

    best, best_overlap = None, 0.0
    for act in activities:
        if str(act.get("type", "")).lower() in NON_SESSION_ACTIVITY_TYPES:
            continue
        start = _to_dt(act.get("start_time_local"))
        if start is None:
            continue
        try:
            minutes = float(act.get("duration_minutes") or 0)
        except (TypeError, ValueError):
            continue
        if minutes <= 0:
            continue
        end = start + timedelta(minutes=minutes)
        ov = overlap_seconds(padded_start, padded_end, start, end)
        if ov < min_overlap_seconds:
            continue
        if ov > best_overlap or (
            ov == best_overlap and best is not None
            and minutes > float(best.get("duration_minutes") or 0)
        ):
            best, best_overlap = act, ov
    return best, best_overlap


def exercise_blocks(set_records_by_exercise: dict[int, list[dict]]) -> list[dict]:
    """Turn each exercise's captured sets into a time block.

    {exercise_idx: [set records]} → [{"exercise_idx", "start", "end"}], sorted
    by start. A block spans its exercise's first to last set timestamp, so the
    rest AFTER the final set belongs to whatever exercise came next rather
    than being attributed here — the block covers work actually done under
    this movement.

    Exercises whose sets carry no timestamps are omitted.
    """
    blocks = []
    for idx, rows in (set_records_by_exercise or {}).items():
        stamps = sorted(
            dt for dt in (_to_dt(r.get("ts")) for r in (rows or [])) if dt is not None
        )
        if not stamps:
            continue
        blocks.append({"exercise_idx": idx, "start": stamps[0], "end": stamps[-1]})
    return sorted(blocks, key=lambda b: b["start"])


def samples_for_block(
    samples: list[tuple[float, float]], start: datetime, end: datetime,
) -> list[tuple[float, float]]:
    """The (epoch_seconds, bpm) samples falling inside one exercise block.

    A block whose sets were all logged within the same second (fast bodyweight
    work) would otherwise capture nothing, so a zero-length block is widened
    to the single sample nearest its instant.
    """
    if not samples:
        return []
    t0, t1 = start.timestamp(), end.timestamp()
    inside = [s for s in samples if t0 <= s[0] <= t1]
    if inside or t1 > t0:
        return inside
    nearest = min(samples, key=lambda s: abs(s[0] - t0))
    return [nearest] if abs(nearest[0] - t0) <= 60 else []
