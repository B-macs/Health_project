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

#: The three Notion databases, as Repository names them. Repository._db_kind
#: maps a configured database id onto one of these.
READINESS = "readiness"
TRAINING = "training"
CONFIG = "config"

#: Notion property name -> (datastore column, property kind).
#:
#: A column of None is SYNTHESIZED — see _synthesize below. This map is the
#: exact inverse of the Repository getters that populate the datastore
#: (get_all_readiness_checkins_raw, get_all_training_exercises_raw,
#: get_all_config_rows); a test walks both
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
    CONFIG: "config",
}

#: Set fields that are integers by construction in services.sessions —
#: set_num is a counter, reps a rep count, rest and tut whole seconds. SQLite
#: stores them REAL and hands them back as floats; restoring the int keeps a
#: seeded stepper reading "10" rather than "10.0". `weight` is absent on
#: purpose: make_sets_data emits a float there.
_INTEGRAL_SET_FIELDS = ("set_num", "reps", "rest", "tut", "rest_taken_seconds", "reps_left")

#: Written into a synthesized page id. Not a valid Notion UUID, so a write
#: that somehow reached one fails at the API naming this string, instead of
#: quietly updating a real page.
#:
#: ⚠ "somehow reached one" turned out to be the NORMAL case in cache mode,
#: which reads locally and writes live — see Repository._live_page_id. Only
#: READINESS and CONFIG synthesize; a TRAINING page id IS its exercise_id, the
#: real Notion UUID, which is why the training write paths were never bitten.
ID_PREFIX = "offline:"


def is_synthesized_page_id(page_id) -> bool:
    """True for a page id this module invented rather than read from Notion."""
    return isinstance(page_id, str) and page_id.startswith(ID_PREFIX)


def synthesized_page_key(page_id: str) -> tuple[str, str]:
    """('config', 'phases') out of 'offline:config:phases'.

    Split on the first two colons only: a CONFIG key or a READINESS date is
    the whole remainder, so a key that itself contained a colon still comes
    back whole.
    """
    if not is_synthesized_page_id(page_id):
        raise ValueError(f"{page_id!r} is not a synthesized page id")
    kind, _, key = page_id[len(ID_PREFIX):].partition(":")
    if kind not in PROPERTIES:
        raise ValueError(f"{page_id!r} names no known database")
    return kind, key


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
    key = {READINESS: "date", CONFIG: "key"}[kind]
    return f"{ID_PREFIX}{kind}:{row.get(key)}"


def page_from_row(kind: str, row: dict) -> dict:
    """One datastore row as the Notion page the callers already parse."""
    props = {}
    for name, (column, prop_kind) in PROPERTIES[kind].items():
        raw = _synthesize(kind, name, row) if column is None else row.get(column)
        props[name] = _payload(prop_kind, raw)
    return {"id": _page_id(kind, row), "properties": props, "object": "page"}


# ─── page -> row (the inverse, for the Supabase mirror) ──────────────────
#
# PROPERTIES is used in BOTH directions and that is the point: one map, so a
# column cannot be read from one place and written to another. Above turns a
# datastore row into a Notion page (for offline reads); below turns a Notion
# property payload back into a datastore row (so a Notion WRITE can be
# mirrored into Postgres without re-reading the page).
#
# ⚠ THE TWO NOTION SHAPES ARE NOT THE SAME. services/clients/notion.py's
# BUILDERS produce what the API ACCEPTS -- {"text": {"content": ...}} -- while
# get_property reads what the API SENDS -- {"plain_text": ...}. A decoder
# written against the wrong one returns "" for every title and every note,
# with no error anywhere. Both are accepted below, so a payload decodes
# whether it came from a builder or from a live page.

def _text_of(elements) -> str:
    """Join a title/rich_text element list, from either shape.

    Joining rather than taking [0] is required, not tidy: notion.rich_text
    CHUNKS a value over 2000 chars into up to 100 elements, so the phases
    JSON blob and a long note both arrive in pieces. get_property already
    joins on the way in; this is the same rule on the way out.
    """
    out = []
    for el in elements or []:
        if not isinstance(el, dict):
            continue
        if "plain_text" in el:                      # API response shape
            out.append(el.get("plain_text") or "")
        else:                                       # builder / request shape
            out.append((el.get("text") or {}).get("content") or "")
    return "".join(out)


def value_from_payload(prop_kind: str, payload: dict):
    """One Notion property payload as the datastore stores that column.

    The storage conventions are NOT arbitrary and are copied from the
    Repository getters that populate these tables
    (get_all_readiness_checkins_raw, get_all_training_exercises_raw):
    a multi_select is stored as a JSON ARRAY STRING and a checkbox as 1/0,
    not as a list and not as a bool. Getting either wrong produces a row that
    looks right and compares unequal to every row built by the other path.
    """
    if prop_kind == "title" or prop_kind == "rich_text":
        return _text_of(payload.get(prop_kind))
    if prop_kind == "number":
        return payload.get("number")
    if prop_kind == "select":
        sel = payload.get("select")
        return sel.get("name") if isinstance(sel, dict) else None
    if prop_kind == "multi_select":
        names = [o.get("name") for o in (payload.get("multi_select") or [])
                 if isinstance(o, dict)]
        return json.dumps(names)
    if prop_kind == "date":
        d = payload.get("date")
        return d.get("start") if isinstance(d, dict) else None
    if prop_kind == "checkbox":
        return 1 if payload.get("checkbox") else 0
    raise NotionQueryUnsupportedError(f"unknown property kind {prop_kind!r}")


def row_from_properties(kind: str, properties: dict) -> dict:
    """A Notion write's property payload as a partial datastore row.

    PARTIAL BY DESIGN. A Notion update_page sends only the properties it is
    changing, and the mirror upserts only those columns —
    `resolution=merge-duplicates` leaves the rest of the row alone (verified
    against the live project). Inventing defaults for the absent columns would
    blank real data on every partial update.

    Properties with no datastore column (and the synthesized "Entry" title)
    are skipped rather than raising: a Notion database may carry columns this
    app does not mirror, and a write is not the place to discover that.
    """
    known = PROPERTIES[kind]
    row = {}
    for name, payload in (properties or {}).items():
        mapped = known.get(name)
        if mapped is None:
            continue
        column, prop_kind = mapped
        if column is None:            # synthesized on read, nothing to store
            continue
        if not isinstance(payload, dict):
            continue
        row[column] = value_from_payload(prop_kind, payload)
    return row


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
    """One training_sets row as the dict the Sets JSON originally held.

    Column reads go through `_col` rather than row[...] because a datastore.db
    built before a column existed simply does not have it, and indexing a
    missing key on a sqlite3.Row raises IndexError. That file is a cache the
    athlete may not have rebuilt yet, and the whole point of the offline lane is
    that it degrades to "this field wasn't recorded", not to a crash on every
    read. Rebuild with scripts/build_datastore.py to populate the newer ones."""
    def _col(name):
        return row[name] if name in row.keys() else None

    out = {}
    for field in ("set_num", "reps", "weight", "rest", "tut", "velocity"):
        v = _col(field)
        if field in _INTEGRAL_SET_FIELDS and isinstance(v, float) and v.is_integer():
            v = int(v)
        out[field] = v
    for optional in ("band_tier", "ts", "rest_taken_seconds", "reps_left", "weight_left"):
        v = _col(optional)
        if v is not None:
            if optional in _INTEGRAL_SET_FIELDS and isinstance(v, float) and v.is_integer():
                v = int(v)
            out[optional] = v
    # SQLite has no boolean: is_warmup comes back 0/1 and has a DEFAULT of 0, so
    # unlike the fields above it is never NULL. Restore it as the bool the Sets
    # JSON held, and only when True — build_set_record omits it otherwise, and a
    # round-trip that added `is_warmup: False` to every historical set would not
    # be the same document.
    if _col("is_warmup"):
        out["is_warmup"] = True
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
