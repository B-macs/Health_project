"""
services/clients/notion.py — Notion API client + generic primitives.

Raw Notion access only: page-shaped dicts in and out, pagination with
rate-limit retry, and the property (de)serializers — generic to any Notion
property of a given type (title/rich_text/number/select/multi_select/date/
checkbox), not specific to any one column name. Column names live only in
services/repository.py.

Moved verbatim from the former db.py's _client/_title/_text/_num/_sel/_msel/
_date/_check/_get/_query_all — same requests, same pagination/retry behavior,
just parameterized by an injected Config instead of reading st.secrets.
"""

from __future__ import annotations

import time
from typing import Any

from notion_client import Client
from notion_client.errors import APIResponseError

from services.config import Config


def make_client(config: Config) -> Client:
    return Client(auth=config.notion_api_key)


# ─── Property builders (generic — any Notion property of this type) ──────────

def title(text: str) -> dict:
    return {"title": [{"text": {"content": str(text or "")[:2000]}}]}


def rich_text(text: str) -> dict:
    return {"rich_text": [{"text": {"content": str(text or "")[:2000]}}]}


def number(val) -> dict:
    return {"number": float(val) if val is not None else None}


def select(name: str) -> dict:
    return {"select": {"name": str(name)}} if name else {"select": None}


def multi_select(names: list) -> dict:
    return {"multi_select": [{"name": str(n)[:100]} for n in (names or [])]}


def date_prop(d) -> dict:
    return {"date": {"start": str(d)}} if d else {"date": None}


def checkbox(val: bool) -> dict:
    return {"checkbox": bool(val)}


# ─── Property extractor ───────────────────────────────────────────────────

def get_property(page: dict, name: str, kind: str) -> Any:
    """Extract a typed value from a Notion page property."""
    prop = page.get("properties", {}).get(name)
    if not prop:
        return None
    if kind == "title":
        return "".join(t.get("plain_text", "") for t in prop.get("title", []))
    if kind == "rich_text":
        return "".join(t.get("plain_text", "") for t in prop.get("rich_text", []))
    if kind == "number":
        return prop.get("number")
    if kind == "select":
        s = prop.get("select")
        return s.get("name") if s else None
    if kind == "multi_select":
        return [o.get("name") for o in prop.get("multi_select", [])]
    if kind == "date":
        d = prop.get("date")
        return d.get("start") if d else None
    if kind == "checkbox":
        return prop.get("checkbox", False)
    return None


# ─── Query / write primitives ─────────────────────────────────────────────

def query_database(
    client: Client,
    database_id: str,
    filter_: dict | None = None,
    sorts: list | None = None,
    page_size: int = 100,
) -> list[dict]:
    """Fetch ALL pages from a Notion database, following pagination cursors."""
    results: list[dict] = []
    kwargs: dict = {"database_id": database_id, "page_size": page_size}
    if filter_:
        kwargs["filter"] = filter_
    if sorts:
        kwargs["sorts"] = sorts

    while True:
        try:
            resp = client.databases.query(**kwargs)
        except APIResponseError as exc:
            if exc.status == 429:          # rate-limited
                time.sleep(1)
                resp = client.databases.query(**kwargs)
            else:
                raise
        results.extend(resp.get("results", []))
        if not resp.get("has_more"):
            break
        kwargs["start_cursor"] = resp["next_cursor"]

    return results


def create_page(client: Client, database_id: str, properties: dict) -> dict:
    return client.pages.create(parent={"database_id": database_id}, properties=properties)


def update_page(client: Client, page_id: str, properties: dict) -> dict:
    return client.pages.update(page_id=page_id, properties=properties)


def ensure_properties(client: Client, database_id: str, properties: dict[str, dict]) -> list[str]:
    """Adds any property in `properties` (name -> Notion property-type
    payload, e.g. {"number": {}}, {"checkbox": {}}, or
    {"select": {"options": [{"name": "Sweet"}, ...]}}) that doesn't already
    exist on the database (Notion's schema-update API only adds/overwrites
    the keys you pass — existing properties not named here are untouched).
    Returns the names actually created; already-present ones are skipped, so
    this is safe to call repeatedly. This is a schema change (unlike
    create_page/update_page, which only touch rows) — callers should treat
    it as a one-time setup step, not part of a normal write path."""
    existing = client.databases.retrieve(database_id=database_id).get("properties", {})
    missing = {n: spec for n, spec in properties.items() if n not in existing}
    if missing:
        client.databases.update(database_id=database_id, properties=missing)
    return list(missing)


def ensure_number_properties(client: Client, database_id: str, names: list[str]) -> list[str]:
    """Number-only convenience wrapper over ensure_properties — kept for the
    existing Repository.ensure_garmin_activity_columns call site."""
    return ensure_properties(client, database_id, {n: {"number": {}} for n in names})
