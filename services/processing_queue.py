"""Insights › Processing Queue's rules (move INS-5, rebuild Phase 2,
2026-10-19): the keyword parse of session notes and check-in notes as one
job, and the grouping behind the warnings calendar and the warning-level
lists, so the engine can run the parse and the phone can draw the same
calendar.

The parse is keyword matching (services/ai.py), never a model, and it is
advisory only (Key Rule 2): nothing here reaches a guardrail.
"""

from __future__ import annotations

import calendar
import json
from datetime import date

from services import ai

#: The warning levels, quietest first.
LEVELS: tuple[str, ...] = ("none", "monitor", "flag")


def pending(repo) -> dict:
    """{"notes": [...], "readiness": [...]}: what still waits for the parse."""
    return {"notes": repo.get_unparsed_session_notes(),
            "readiness": repo.get_unparsed_readiness()}


def parse_note(repo, note: dict, injury_profile: dict) -> None:
    """Parse one session note and store what it found."""
    result = ai.parse_session_note(note["raw_text"], injury_profile)
    repo.update_session_note_ai(
        note_id=note["id"], summary=result["summary"],
        sentiment_score=result["sentiment_score"],
        flagged_body_parts=result["flagged_body_parts"],
        warning_level=result["warning_level"])


def parse_readiness(repo, entry: dict, injury_profile: dict) -> None:
    """Parse one check-in's sensation note and store what it found. The
    check-in table is keyed by DATE, so the entry's date goes with the write."""
    result = ai.parse_tightness(entry["subjective_tightness"], injury_profile)
    repo.update_readiness_ai(
        row_id=entry["id"], severity=result["severity"], body_parts=result["body_parts"],
        sensation_type=result["sensation_type"], warning_level=result["warning_level"],
        entry_date=entry.get("timestamp"))


def process_all(repo, injury_profile: dict, queue: dict | None = None,
                on_progress=None) -> dict:
    """Parse every pending note and check-in; one failure never stops the
    rest. {"total", "errors"}: each error names its item. `on_progress(done,
    total)` is called after each item."""
    queue = pending(repo) if queue is None else queue
    items = ([("Note", parse_note, n) for n in queue["notes"]]
             + [("Readiness", parse_readiness, e) for e in queue["readiness"]])
    errors: list[str] = []
    for done, (kind, parse, item) in enumerate(items, start=1):
        try:
            parse(repo, item, injury_profile)
        except Exception as exc:
            errors.append(f"{kind} {item['id']}: {exc}")
        if on_progress is not None:
            on_progress(done, len(items))
    return {"total": len(items), "errors": errors}


def parse_after_save(repo) -> dict | None:
    """The keyword parse right after a save: the approved move for the
    Processing Queue (inventory I63, "parse on save"), so a note never waits
    for a button press. It never fails the save that ran it: the save is
    already stored, and an item it could not parse stays pending, on the
    queue, which runs the same job (process_all) on demand. None when the
    job itself could not start.

    Every save that can store a note runs it: the check-in, a session, yoga,
    in the engine and in the old app alike. Until 2026-10-21 the old app's
    saves did not, so every note it stored after the Processing Queue's
    button was last pressed (early August) waited unread, and the warnings
    calendar showed nothing after 6 August until the first check-in saved
    from the phone read the backlog."""
    try:
        return process_all(repo, repo.get_diagnostic_profile())
    except Exception:
        return None


# ─── The warnings calendar ──────────────────────────────────────────────────

def entry_date(entry: dict) -> str:
    """The ISO day a flagged entry belongs to: its session's, or its check-in's."""
    return str(entry.get("session_date") or entry.get("timestamp") or "")[:10]


def warnings_by_date(flagged: list[dict]) -> dict[str, list[dict]]:
    by_date: dict[str, list[dict]] = {}
    for entry in flagged:
        by_date.setdefault(entry_date(entry), []).append(entry)
    return by_date


def day_level(entries: list[dict]) -> str:
    """A day's marker: "flag" when any entry flags, else "monitor"."""
    return "flag" if any(e.get("warning_level") == "flag" for e in entries) else "monitor"


def calendar_anchor(today: date) -> tuple[int, int]:
    """(year, month) the calendar opens on: today's (the owner, 2026-10-21: "When I go
    to warnings it should open on the current day"). Until then it opened on the latest
    warning's month, which read as a calendar stuck in the past."""
    return today.year, today.month


def step_month(year: int, month: int, delta: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def month_weeks(year: int, month: int) -> list[list[date]]:
    """The month's weeks, Monday first, padded with the days around it."""
    return calendar.Calendar(firstweekday=0).monthdatescalendar(year, month)


def names(value) -> str:
    """Body areas or sensations stored as a JSON list, as "a, b"; plain text
    unchanged; an unreadable list left as it was stored."""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    if isinstance(value, str) and value.startswith("["):
        try:
            return ", ".join(str(v) for v in json.loads(value))
        except (TypeError, ValueError):
            return value
    return "" if value is None else str(value)


def entry_view(entry: dict) -> dict:
    """One flagged entry for the day detail: level (monitor when unset),
    source, body areas, summary (200 characters at most) and movement."""
    return {"level": entry.get("warning_level") or "monitor",
            "source": entry.get("source", "?"),
            "parts": names(entry.get("body_parts", "")),
            "summary": str(entry.get("summary") or "")[:200],
            "movement": entry.get("movement_name") or ""}


def rows_by_warning_level(parsed_rows: list[dict]) -> dict[str, list[dict]]:
    """The parsed check-ins grouped by warning level; every level present,
    an unset level read as "none"."""
    groups: dict[str, list[dict]] = {level: [] for level in LEVELS}
    for row in parsed_rows:
        groups.setdefault(row.get("ai_warning_level") or "none", []).append(row)
    return groups
