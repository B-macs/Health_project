"""
services/clients/sheets.py — Google Sheets client + raw read.

Raw access only: gspread client init from Config, and a plain read of every
row in the worksheet, exactly as gspread parses them (header row -> dict per
row, no renaming/coercion). Column names and unit conversions live in
services/repository.py.

Moved from sync_sheets.py's _gc()/_open() — same worksheet, same call shape,
just parameterized by an injected Config instead of reading st.secrets.
"""

from __future__ import annotations

import gspread

from services.config import Config

WORKSHEET = "Sheet1"


def make_client(config: Config):
    return gspread.service_account_from_dict(config.google_service_account)


def get_all_records(client, sheet_id: str) -> list[dict]:
    """Every row in the worksheet, gspread's own dict-per-row parsing, unmapped."""
    return client.open_by_key(sheet_id).worksheet(WORKSHEET).get_all_records()
