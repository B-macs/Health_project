"""
services/clients/notion_reader.py — a read-only stand-in for a Notion
database, served from the local datastore.

The sibling of clients/datastore_reader.py, and built the same way: that one
is duck-typed against a gspread Worksheet so every Sheets read works
unmodified; this one is duck-typed against notion.query_database, so every
Notion read works unmodified. Repository._query is the single seam — all 29
Notion reads already went through it, which is the only reason this is one
module rather than a rewrite of forty getters.

WHY PAGE-SHAPED, not row-shaped. The obvious design is to return flat rows
and teach the getters to read them. That is ~40 rewrites of working,
tested code, each an opportunity to change behaviour by accident. Returning
the shape the callers already parse means the diff is this file plus a
two-line branch, and `notion.get_property` stays the one place a Notion
property is decoded — live or offline, the same function, so the two cannot
drift.

THE FILTER IS EVALUATED AGAINST THE SYNTHESIZED PAGE, deliberately, using
get_property itself rather than against the SQL row. A filter that read the
column directly would be a second mapping from property name to value, and
the first time one of them changed it would silently return the wrong rows —
the failure that looks exactly like missing data. Filtering the page means
the filter sees precisely what the caller will see.

Notion's query language is enormous; the four databases here use five
operators (equals, on_or_after, on_or_before, is_empty, is_not_empty) over
five property kinds, combined with and/or. That closed set is implemented
exactly. Anything outside it RAISES rather than being ignored — a filter
that silently does nothing returns every row, which reads as "the query
matched everything" and is far worse than a crash.

WHAT IS RECONSTRUCTED, and what that costs:

  Sets      training_sets is normalized back into the `Sets` rich_text JSON
            the callers parse. SQLite has no int/float distinction to
            preserve, so set_num/reps/rest/tut come back as floats; they are
            integers by construction in BOTH writers
            (services.sessions.build_set_record and make_sets_data) and are
            restored as such. `weight` is deliberately NOT restored that
            way — make_sets_data emits `ex.get("weight_kg") or 0.0`, so a
            float is the faithful value there, not a rounding artefact.
            A NULL band_tier/ts is DROPPED rather than emitted as null,
            because both writers omit the key entirely when absent.

  Page ids  Only training_exercises stores one (it is that table's primary
            key). Readiness/config/biometrics rows are keyed by date or
            name, so their ids are synthesized with an "offline:" prefix —
            not a valid Notion id, so a write that reached one would fail
            loudly at the API instead of updating some arbitrary page.
            Repository._nc raises offline, so nothing gets that far.

  Titles    "Entry" is write-only in this codebase (never read back), and is
            f"{date} Morning Check-In" / the date string by construction. It
            is regenerated rather than stored, so a page carries every
            property the live one does — a missing property reads as None
            where the live value would be False, which is the kind of gap
            that only shows up in a checkbox branch months later.
"""

from __future__ import annotations

import json
import sqlite3

from services.clients.notion import get_property

#: The four Notion databases, as Repository names them. Repository._db_kind
#: maps a configured database id onto one of these.
READINESS = "readiness"
TRAINING = "training"
BIOMETRICS = "biometrics"
CONFIG = "config"

#: Notion property name -> (datastore column, property kind).
#:
#: A column of None is SYNTHESIZED — see _synthesize below. This map is the
#: exact inverse of the Repository getters that populate the datastore
#: (get_all_readiness_checkins_raw, get_all_training_exercises_raw,
#: get_all_notion_biometrics_rows, get_all_config_rows); a test walks both
#: directions so neither side can gain a field alone.
PROPERTIES: dict[str, dict[str, tuple[str | None, str]]] = {
    READINESS: {
        "Entry":                (None, "title"),
        "Date":                 ("date", "date"),
        "Condition":            ("current_condition", "select"),
        "Tightness":            ("tightness_score", "number"),
        "Pain":                 ("pain_score", "number"),
        "Body Areas":           ("anatomical_locations", "multi_select"),
        "Sensations":           ("sensation_tags", "multi_select"),
        "Note":                 ("subjective_tightness", "rich_text"),
        "Alcohol Units":        ("alcohol_units", "number"),
        "Travel":               ("travel_flag", "checkbox"),
        "Stress Level":         ("psych_stress_score", "number"),
        "Instability Events":   ("instability_events", "number"),
        "Bristol Type":         ("bristol_type", "number"),
        "Unusual Stool Colour": ("unusual_stool_colour", "checkbox"),
        "Hunger Deviation":     ("hunger_deviation", "number"),
        "Thirst Intensity":     ("thirst_intensity", "number"),
        "Electrolytes Taken":   ("electrolytes_taken", "checkbox"),
        "Meditation Done":      ("meditation_done", "checkbox"),
        "Meditation Minutes":   ("meditation_minutes", "number"),
        "Relaxation Depth":     ("relaxation_depth", "number"),
        "Parsed":               ("parsed", "checkbox"),
        "Parsed Severity":      ("parsed_severity", "number"),
        "Parsed Areas":         ("parsed_areas", "rich_text"),
        "Parsed Sensations":    ("parsed_sensations", "rich_text"),
        "Warning":              ("warning_level", "select"),
    },
    TRAINING: {
        "Movement":               ("movement_name", "title"),
        "Session Date":           ("session_date", "date"),
        "Session ID":             ("session_id", "rich_text"),
        "Type":                   ("movement_type", "select"),
        "Planned Sets":           ("planned_sets", "number"),
        "Planned Reps":           ("planned_reps", "number"),
        "Exercise RPE":           ("exercise_rpe", "number"),
        "Sets":                   ("_sets_json", "rich_text"),
        "Notes":                  ("notes", "rich_text"),
        "Session Duration":       ("session_duration_minutes", "number"),
        "Session RPE":            ("session_rpe", "number"),
        "Session AU":             ("session_au", "number"),
        "Note Summary":           ("note_summary", "rich_text"),
        "Sentiment":              ("sentiment_score", "number"),
        "Flagged Areas":          ("flagged_body_parts", "rich_text"),
        "Warning":                ("warning_level", "select"),
        "Activity Avg HR":        ("garmin_avg_hr", "number"),
        "Activity Max HR":        ("garmin_max_hr", "number"),
        "Activity Distance (km)": ("garmin_distance_km", "number"),
        "Activity Calories":      ("garmin_calories", "number"),
    },
    BIOMETRICS: {
        "Entry":             (None, "title"),
        "Log Date":          ("date", "date"),
        "RHR":               ("resting_heart_rate", "number"),
        "HR Average":        ("hr_average", "number"),
        "HRV":               ("hrv_ms", "number"),
        "Sleep Hours":       ("sleep_duration_hours", "number"),
        "Deep Sleep Hours":  ("sleep_deep_hours", "number"),
        "Active kcal":       ("active_kcal", "number"),
        "Weight kg":         ("weight_kg", "number"),
        "Steps":             ("steps", "number"),
    },
    CONFIG: {
        "Key":     ("key", "title"),
        "Value":   ("value", "rich_text"),
        "Updated": ("updated", "date"),
    },
}

#: The datastore table (or, for training, the driving table) behind each.
TABLES = {
    READINESS: "readiness_checkins",
    TRAINING: "training_exercises",
    BIOMETRICS: "notion_biometrics",
    CONFIG: "config",
}

#: Set fields that are integers by construction in services.sessions —
#: set_num is a counter, reps a rep count, rest and tut whole seconds. SQLite
#: stores them REAL and hands them back as floats; restoring the int keeps a
#: seeded stepper reading "10" rather than "10.0". `weight` is absent on
#: purpose: make_sets_data emits a float there.
_INTEGRAL_SET_FIELDS = ("set_num", "reps", "rest", "tut")

#: Written into a synthesized page id. Not a valid Notion UUID, so a write
#: that somehow reached one fails at the API naming this string, instead of
#: quietly updating a real page.
ID_PREFIX = "offline:"


class NotionQueryUnsupportedError(RuntimeError):
    """A filter or sort this reader cannot honour exactly.

    Never caught internally. Degrading to "return everything" would look
    like a successful query over a wider window, which is indistinguishable
    from correct output right up until a decision is made on it.
    """


# ─── row -> page ─────────────────────────────────────────────────────────

def _synthesize(kind: str, name: str, row: dict):
    """The value of a property that has no column of its own."""
    if name == "Entry" and kind == READINESS:
        return f"{row.get('date') or ''} Morning Check-In"
    if name == "Entry" and kind == BIOMETRICS:
        return str(row.get("date") or "")
    raise NotionQueryUnsupportedError(
        f"{kind}.{name!r} is mapped to no column and has no synthesizer"
    )


def _payload(prop_kind: str, value):
    """One property, in the shape the Notion API returns it.

    Note `plain_text`, not `text.content`: get_property reads what the API
    SENDS, while services/clients/notion.py's builders produce what it
    ACCEPTS, and the two shapes differ. Building the wrong one here would
    make every title and note read back empty.
    """
    if prop_kind == "title":
        s = "" if value is None else str(value)
        return {"title": [{"plain_text": s}] if s else []}
    if prop_kind == "rich_text":
        s = "" if value is None else str(value)
        return {"rich_text": [{"plain_text": s}] if s else []}
    if prop_kind == "number":
        return {"number": None if value is None or value == "" else float(value)}
    if prop_kind == "select":
        s = "" if value is None else str(value)
        return {"select": {"name": s} if s else None}
    if prop_kind == "multi_select":
        names = []
        if value:
            try:
                names = [str(n) for n in json.loads(value)]
            except (ValueError, TypeError):
                names = []
        return {"multi_select": [{"name": n} for n in names]}
    if prop_kind == "date":
        s = "" if value is None else str(value)
        return {"date": {"start": s} if s else None}
    if prop_kind == "checkbox":
        return {"checkbox": bool(value)}
    raise NotionQueryUnsupportedError(f"unknown property kind {prop_kind!r}")


def _page_id(kind: str, row: dict) -> str:
    if kind == TRAINING:
        return row.get("exercise_id") or f"{ID_PREFIX}training:?"
    key = {READINESS: "date", BIOMETRICS: "date", CONFIG: "key"}[kind]
    return f"{ID_PREFIX}{kind}:{row.get(key)}"


def page_from_row(kind: str, row: dict) -> dict:
    """One datastore row as the Notion page the callers already parse."""
    props = {}
    for name, (column, prop_kind) in PROPERTIES[kind].items():
        raw = _synthesize(kind, name, row) if column is None else row.get(column)
        props[name] = _payload(prop_kind, raw)
    return {"id": _page_id(kind, row), "properties": props, "object": "page"}


# ─── filtering ───────────────────────────────────────────────────────────

def _test(value, prop_kind: str, condition: dict) -> bool:
    """One leaf condition, against the value get_property already returned."""
    if len(condition) != 1:
        raise NotionQueryUnsupportedError(
            f"expected exactly one operator, got {sorted(condition)}"
        )
    (op, wanted), = condition.items()

    if op == "is_empty":
        return (not value) == bool(wanted)
    if op == "is_not_empty":
        return bool(value) == bool(wanted)
    if op == "equals":
        if prop_kind == "checkbox":
            return bool(value) == bool(wanted)
        if prop_kind == "date":
            # Notion compares the DAY. Stored values are date-only, but a
            # live one can carry a time, so both sides are cut to 10 chars
            # rather than compared whole.
            return bool(value) and str(value)[:10] == str(wanted)[:10]
        return value == wanted
    if op in ("on_or_after", "on_or_before"):
        if not value:
            # Notion excludes an empty date from a range filter rather than
            # sorting it to one end.
            return False
        left, right = str(value)[:10], str(wanted)[:10]
        return left >= right if op == "on_or_after" else left <= right
    raise NotionQueryUnsupportedError(
        f"filter operator {op!r} is not implemented — implement it rather "
        f"than letting the query silently match every row"
    )


def matches(kind: str, page: dict, filter_: dict | None) -> bool:
    if not filter_:
        return True
    if "and" in filter_:
        return all(matches(kind, page, f) for f in filter_["and"])
    if "or" in filter_:
        return any(matches(kind, page, f) for f in filter_["or"])
    name = filter_.get("property")
    if name is None:
        raise NotionQueryUnsupportedError(f"filter has no property: {filter_}")
    known = PROPERTIES[kind]
    if name not in known:
        raise NotionQueryUnsupportedError(
            f"{kind} has no property {name!r} in the datastore mapping"
        )
    prop_kind = known[name][1]
    condition = filter_.get(prop_kind)
    if condition is None:
        raise NotionQueryUnsupportedError(
            f"filter on {name!r} is keyed {sorted(set(filter_) - {'property'})}, "
            f"but that property is a {prop_kind}"
        )
    return _test(get_property(page, name, prop_kind), prop_kind, condition)


# ─── sorting ─────────────────────────────────────────────────────────────

_TEXTUAL = ("title", "rich_text", "select", "date")


def sort_pages(kind: str, pages: list[dict], sorts: list) -> list[dict]:
    """Applied last key first, leaning on Python's stable sort for multi-key
    ordering — the same result Notion gives for its own sort list."""
    out = list(pages)
    for spec in reversed(sorts or []):
        name = spec.get("property")
        known = PROPERTIES[kind]
        if name not in known:
            raise NotionQueryUnsupportedError(
                f"cannot sort {kind} by {name!r} — not in the datastore mapping"
            )
        prop_kind = known[name][1]
        empty = "" if prop_kind in _TEXTUAL else float("-inf")
        descending = spec.get("direction", "ascending") == "descending"
        out.sort(
            key=lambda p: (lambda v: empty if v is None else v)(
                get_property(p, name, prop_kind)),
            reverse=descending,
        )
    return out


# ─── reading the datastore ───────────────────────────────────────────────

def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _restore_set(row: sqlite3.Row) -> dict:
    """One training_sets row as the dict the Sets JSON originally held."""
    out = {}
    for field in ("set_num", "reps", "weight", "rest", "tut", "velocity"):
        v = row[field]
        if field in _INTEGRAL_SET_FIELDS and isinstance(v, float) and v.is_integer():
            v = int(v)
        out[field] = v
    for optional in ("band_tier", "ts"):
        if row[optional] is not None:
            out[optional] = row[optional]
    return out


def _sets_by_exercise(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    """Every set, grouped — one query for the whole table rather than one per
    exercise, which is the N+1 this whole cutover exists to stop repeating.

    Ordered by the surrogate `id`, i.e. INSERT order, which is the order the
    original JSON array held. Ordering by set_num instead would silently
    re-sort a session where a set was redone out of order (upsert_set_record
    replaces in place, so the list is not necessarily set_num-ascending).
    """
    out: dict[str, list[dict]] = {}
    if not _table_exists(conn, "training_sets"):
        return out
    for row in conn.execute("SELECT * FROM training_sets ORDER BY id"):
        out.setdefault(row["exercise_id"], []).append(_restore_set(row))
    return out


def _rows(conn: sqlite3.Connection, kind: str) -> list[dict]:
    table = TABLES[kind]
    if not _table_exists(conn, table):
        # Same tolerance as OfflineWorksheet: a datastore built before this
        # table existed reads as "no rows yet", which is what an empty
        # Notion database returns too.
        return []

    if kind != TRAINING:
        return [dict(r) for r in conn.execute(f'SELECT * FROM "{table}"')]

    sets = _sets_by_exercise(conn)
    sql = "SELECT e.* FROM training_exercises e"
    session_cols = ("session_duration_minutes", "session_rpe", "session_au")
    if _table_exists(conn, "training_sessions"):
        sql = (
            "SELECT e.*, s.session_duration_minutes, s.session_rpe, s.session_au "
            "FROM training_exercises e "
            "LEFT JOIN training_sessions s ON s.session_id = e.session_id"
        )
    rows = []
    for r in conn.execute(sql):
        row = dict(r)
        for c in session_cols:
            row.setdefault(c, None)
        row["_sets_json"] = json.dumps(sets.get(row.get("exercise_id"), []))
        rows.append(row)
    return rows


def query(conn: sqlite3.Connection, kind: str, filter_: dict | None = None,
          sorts: list | None = None) -> list[dict]:
    """Every page of one Notion database, filtered and sorted — the same
    contract as notion.query_database, which is what lets Repository._query
    swap one for the other with a two-line branch."""
    if kind not in PROPERTIES:
        raise NotionQueryUnsupportedError(f"unknown Notion database {kind!r}")
    pages = [page_from_row(kind, row) for row in _rows(conn, kind)]
    if filter_:
        pages = [p for p in pages if matches(kind, p, filter_)]
    if sorts:
        pages = sort_pages(kind, pages, sorts)
    return pages
