"""
sync_sheets.py — Google Sheets biometrics reader.

Reads directly from Sheet1 of the daily_biometrics_master spreadsheet.
No Notion sync — biometrics stay in Google Sheets.
Notion stores only: training sessions, morning check-ins, app config.

get_biometric_rolling() returns data in the same format as
db.get_biometric_rolling() so the engine works unchanged.
"""

from __future__ import annotations

from datetime import date as _date_cls, timedelta

WORKSHEET = "Sheet1"


# ─────────────────────────────────────────────────────────────────────────────
#  Auth
# ─────────────────────────────────────────────────────────────────────────────

def _gc():
    import gspread
    import streamlit as st
    return gspread.service_account_from_dict(dict(st.secrets["google_service_account"]))


def _open(sheet_id: str):
    return _gc().open_by_key(sheet_id).worksheet(WORKSHEET)


# ─────────────────────────────────────────────────────────────────────────────
#  Value coercers
# ─────────────────────────────────────────────────────────────────────────────

def _date(val) -> str | None:
    try:
        return str(val).split(" ")[0].strip() or None
    except Exception:
        return None


def _flt(val) -> float | None:
    try:
        v = float(val)
        return v if v != 0.0 else None
    except (TypeError, ValueError):
        return None


def _nt(val) -> int | None:
    try:
        v = int(float(val))
        return v if v != 0 else None
    except (TypeError, ValueError):
        return None


def _kj_to_kcal(val) -> int | None:
    v = _flt(val)
    return round(v / 4.184) if v else None


# ─────────────────────────────────────────────────────────────────────────────
#  Primary API — used by Autoregulation engine
# ─────────────────────────────────────────────────────────────────────────────

def get_biometric_rolling(sheet_id: str, days: int = 28) -> list[dict]:
    """
    Read the last `days` days of biometric data from Google Sheets.
    Returns rows sorted ascending by date — identical format to
    db.get_biometric_rolling() so the traffic_light() engine needs no changes.
    """
    ws      = _open(sheet_id)
    records = ws.get_all_records()

    cutoff   = (_date_cls.today() - timedelta(days=days)).isoformat()
    today_str = str(_date_cls.today())
    out = []

    for row in records:
        d = _date(row.get("Date/Time", ""))
        if not d or d < cutoff or d > today_str:
            continue
        out.append({
            "date":                 d,
            "hrv_ms":               _flt(row.get("Heart Rate Variability (ms)")),
            "resting_heart_rate":   _nt(row.get("Resting Heart Rate (count/min)")),
            "sleep_duration_hours": _flt(row.get("Sleep Analysis [Total] (hr)")),
            "sleep_deep_hours":     _flt(row.get("Sleep Analysis [Deep] (hr)")),
            "active_kcal":          _kj_to_kcal(row.get("Active Energy (kJ)")),
            "weight_kg":            _flt(row.get("Weight (kg)")),
            "steps":                _nt(row.get("Step Count (count)")),
        })

    return sorted(out, key=lambda r: r["date"])


# ─────────────────────────────────────────────────────────────────────────────
#  Status / preview — used by the Sync page
# ─────────────────────────────────────────────────────────────────────────────

def fetch_all_rows(sheet_id: str) -> list[dict]:
    """Return every row in Sheet1 as raw dicts — for the status page."""
    return _open(sheet_id).get_all_records()
