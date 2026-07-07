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
WEEKLY_ROLLUP_WORKSHEET = "Weekly Rollup"


def make_client(config: Config):
    return gspread.service_account_from_dict(config.google_service_account)


def get_all_records(client, sheet_id: str) -> list[dict]:
    """Every row in the worksheet, gspread's own dict-per-row parsing, unmapped."""
    return client.open_by_key(sheet_id).worksheet(WORKSHEET).get_all_records()


# ─── Weekly Rollup — raw worksheet primitives, no column-name knowledge ─────
# (that lives in services/repository.py). This is the only writable
# worksheet in the app so far; everything else is Sheets-as-read-only-source.


def get_or_create_weekly_rollup_worksheet(client, sheet_id: str, header: list[str]):
    """Opens the "Weekly Rollup" tab, creating it with the given header row
    on first use if it doesn't exist yet."""
    spreadsheet = client.open_by_key(sheet_id)
    try:
        return spreadsheet.worksheet(WEEKLY_ROLLUP_WORKSHEET)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(
            title=WEEKLY_ROLLUP_WORKSHEET, rows=200, cols=max(10, len(header)),
        )
        ws.update([header], "A1")
        return ws


def get_weekly_rollup_records(worksheet) -> list[dict]:
    return worksheet.get_all_records()


def upsert_weekly_rollup_row(worksheet, key_col: int, key_value: str, row_values: list) -> None:
    """Update-in-place if a row with `key_value` already exists in `key_col`
    (1-indexed); otherwise append a new row. Only overwrites the first
    len(row_values) columns, so any extra columns to the right stay
    untouched on update."""
    cell = worksheet.find(key_value, in_column=key_col)
    if cell is not None:
        end_col_letter = gspread.utils.rowcol_to_a1(1, len(row_values)).rstrip("0123456789")
        worksheet.update([row_values], f"A{cell.row}:{end_col_letter}{cell.row}")
    else:
        worksheet.append_row(row_values)
