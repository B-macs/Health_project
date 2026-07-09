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
GARMIN_DAILY_WORKSHEET = "Garmin Daily"
GARMIN_ACTIVITIES_WORKSHEET = "Garmin Activities"
OURA_DAILY_WORKSHEET = "Oura Daily"
OURA_WORKOUTS_WORKSHEET = "Oura Workouts"
OURA_SLEEP_PERIODS_WORKSHEET = "Oura Sleep Periods"
OURA_SESSIONS_WORKSHEET = "Oura Sessions"
OURA_REST_MODE_WORKSHEET = "Oura Rest Mode"


def make_client(config: Config):
    return gspread.service_account_from_dict(config.google_service_account)


def get_all_records(client, sheet_id: str) -> list[dict]:
    """Every row in the worksheet, gspread's own dict-per-row parsing, unmapped."""
    return client.open_by_key(sheet_id).worksheet(WORKSHEET).get_all_records()


# ─── Writable worksheets — raw primitives, no column-name knowledge ─────────
# (that lives in services/repository.py). Weekly Rollup was the first
# writable tab; Garmin Daily/Activities (services/repository.py) reuse the
# same generic get_or_create_worksheet()/upsert_row_by_key() underneath.


def get_or_create_worksheet(client, sheet_id: str, title: str, header: list[str]):
    """Opens the given tab, creating it with the given header row on first
    use if it doesn't exist yet."""
    spreadsheet = client.open_by_key(sheet_id)
    try:
        return spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(
            title=title, rows=200, cols=max(10, len(header)),
        )
        ws.update([header], "A1")
        return ws


def upsert_row_by_key(worksheet, key_col: int, key_value: str, row_values: list) -> None:
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


def get_or_create_weekly_rollup_worksheet(client, sheet_id: str, header: list[str]):
    """Opens the "Weekly Rollup" tab, creating it with the given header row
    on first use if it doesn't exist yet."""
    return get_or_create_worksheet(client, sheet_id, WEEKLY_ROLLUP_WORKSHEET, header)


def get_weekly_rollup_records(worksheet) -> list[dict]:
    return worksheet.get_all_records()


def upsert_weekly_rollup_row(worksheet, key_col: int, key_value: str, row_values: list) -> None:
    upsert_row_by_key(worksheet, key_col, key_value, row_values)
