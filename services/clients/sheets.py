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
BIOMETRIC_BLEND_WORKSHEET = "Biometric Blend"
METRICS_HISTORY_WORKSHEET = "Metrics History"
WAKE_TIME_ADJUSTMENTS_WORKSHEET = "Wake Time Adjustments"
SESSION_HR_WORKSHEET = "Session HR"


def make_client(config: Config):
    return gspread.service_account_from_dict(config.google_service_account)


def get_all_records(client, sheet_id: str) -> list[dict]:
    """Every row in the worksheet, gspread's own dict-per-row parsing, unmapped."""
    return client.open_by_key(sheet_id).worksheet(WORKSHEET).get_all_records()


# ─── Writable worksheets — raw primitives, no column-name knowledge ─────────
# (that lives in services/repository.py). Weekly Rollup was the first
# writable tab; Garmin Daily/Activities (services/repository.py) reuse the
# same generic get_or_create_worksheet()/upsert_row_by_key() underneath.


def get_worksheet_records(worksheet) -> list[dict]:
    """Every row in an arbitrary already-opened worksheet, gspread's own
    dict-per-row parsing, unmapped — the generic counterpart to
    get_all_records() (which is hardcoded to Sheet1) for the Oura/Garmin
    tabs, which until now were write-only from the app's perspective."""
    return worksheet.get_all_records()


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


APPEND_CHUNK_SIZE = 500


def append_rows(worksheet, rows: list[list], chunk_size: int = APPEND_CHUNK_SIZE) -> int:
    """Batch-append `rows` in chunks — one API call per chunk, versus the two
    (find + update/append) that upsert_row_by_key spends on every single row.
    For a bulk historical backfill of ~1,300 rows that's the difference
    between ~3 calls and ~2,600, i.e. between seconds and blowing through
    Sheets' 60-writes-per-minute quota.

    No key checking: the caller is responsible for having established that
    every row is new (see Repository.backfill_oura_history, which diffs
    against the tab's existing keys first). Returns rows written.

    INSERT_ROWS rather than the API's default OVERWRITE: a tab created by
    get_or_create_worksheet() starts at 200 rows, and a backfill of several
    hundred would otherwise run past the end of the grid."""
    for i in range(0, len(rows), chunk_size):
        worksheet.append_rows(rows[i:i + chunk_size], insert_data_option="INSERT_ROWS")
    return len(rows)


def rewrite_worksheet(worksheet, header: list[str], rows: list[list],
                      chunk_size: int = APPEND_CHUNK_SIZE) -> int:
    """Replaces the tab's header row and every data row in one batched pass.

    The only way to widen a tab: adding a column means rewriting the header
    AND every existing row, which upsert_row_by_key can't express (it only
    overwrites the first len(row_values) columns of one row at a time).

    Deliberately does NOT clear() first — a clear-then-write pairing would
    leave the tab empty if the write half failed. Instead every cell in the
    block is overwritten in place, which is equivalent as long as the caller
    passes back at least as many rows as the tab already had (see
    Repository.rebuild_oura_tabs, which carries unmatched existing rows
    through rather than dropping them). Grows the grid first when the new
    block is taller or wider than the current one."""
    needed_rows, needed_cols = len(rows) + 1, len(header)
    if worksheet.row_count < needed_rows or worksheet.col_count < needed_cols:
        worksheet.resize(
            rows=max(worksheet.row_count, needed_rows),
            cols=max(worksheet.col_count, needed_cols),
        )
    end_col = gspread.utils.rowcol_to_a1(1, len(header)).rstrip("0123456789")
    worksheet.update([header], f"A1:{end_col}1")
    for i in range(0, len(rows), chunk_size):
        block = rows[i:i + chunk_size]
        first = i + 2  # +1 for the header row, +1 for 1-indexing
        worksheet.update(block, f"A{first}:{end_col}{first + len(block) - 1}")
    return len(rows)


def get_or_create_weekly_rollup_worksheet(client, sheet_id: str, header: list[str]):
    """Opens the "Weekly Rollup" tab, creating it with the given header row
    on first use if it doesn't exist yet."""
    return get_or_create_worksheet(client, sheet_id, WEEKLY_ROLLUP_WORKSHEET, header)


def get_weekly_rollup_records(worksheet) -> list[dict]:
    return worksheet.get_all_records()


def upsert_weekly_rollup_row(worksheet, key_col: int, key_value: str, row_values: list) -> None:
    upsert_row_by_key(worksheet, key_col, key_value, row_values)
