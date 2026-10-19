"""The body-composition readings in the store (rebuild Phase 2, fault F15,
2026-10-19). The Metabolism screen read a local, git-ignored CSV and a Python
tuple, so on a server it showed no weight at all. The readings now live in
two Supabase tables, written through Supabase first and read from the local
copy like every other table. Made-up readings only; a fake Supabase.
"""

from __future__ import annotations

from datetime import datetime

import pytest

import body_composition_baselines as bcb
from services import body_composition as bc
from services import record_cache
from tests._record_store import FakeStore, new_local_copy, record_repo

READINGS = [
    bc.ScaleReading(taken_at=datetime(2026, 9, 1, 7, 30), weight_kg=80.0, bmi=24.2,
                    body_fat_pct=17.0),
    bc.ScaleReading(taken_at=datetime(2026, 9, 3, 7, 41), weight_kg=79.6, bmi=None,
                    body_fat_pct=None),
]
SCANS = [
    bc.InBodyScan(taken_at=datetime(2026, 5, 2, 12, 0), weight_kg=80.0, bmi=24.0,
                  total_body_water_l=48.0, skeletal_muscle_kg=37.0, ecw_tbw=0.377,
                  phase_angle_deg=6.0, note="first", device="Model A"),
    bc.InBodyScan(taken_at=datetime(2026, 9, 2, 12, 0), weight_kg=79.0, bmi=23.9,
                  total_body_water_l=48.5, skeletal_muscle_kg=37.4, ecw_tbw=0.376,
                  phase_angle_deg=None, device="Model B"),
]


@pytest.fixture
def repo(tmp_path):
    db = new_local_copy(tmp_path)
    store = FakeStore()
    yield record_repo(db, store), store
    record_cache.forget(db)


def test_a_reading_and_a_scan_survive_their_row():
    assert bc.scale_readings_from_rows([bc.scale_reading_row(r) for r in READINGS]) == READINGS
    assert bc.inbody_scans_from_rows([bc.inbody_scan_row(s) for s in SCANS]) == SCANS
    assert bc.scale_reading_row(READINGS[0])["taken_at"] == "2026-09-01T07:30:00"


def test_a_scan_is_stored_with_its_machine():
    with pytest.raises(ValueError):
        bc.inbody_scan_row(SCANS[0].__class__(**{**SCANS[0].__dict__, "device": ""}))
    assert {s.device for s in bcb.SCANS} == {bcb.DEVICE}


def test_a_new_machine_starts_its_own_series():
    assert bc.latest_device_scans(SCANS) == [SCANS[1]]
    assert bc.latest_device_scans([]) == []


def test_the_store_writes_supabase_first_and_reads_back_from_the_copy(repo):
    r, store = repo
    assert r.save_scale_readings(READINGS) == 2
    assert r.save_inbody_scans(SCANS) == 2
    assert [row["taken_at"] for row in store.tables["scale_readings"]] == [
        "2026-09-01T07:30:00", "2026-09-03T07:41:00"]
    assert r.get_scale_readings() == READINGS
    assert r.get_inbody_scans() == SCANS


def test_a_second_import_overwrites_and_never_duplicates(repo):
    r, store = repo
    r.save_scale_readings(READINGS)
    r.save_scale_readings(READINGS)
    assert len(store.tables["scale_readings"]) == 2
    assert len(r.get_scale_readings()) == 2


def test_a_failed_supabase_write_keeps_nothing_in_the_copy(tmp_path):
    db = new_local_copy(tmp_path)
    try:
        r = record_repo(db, FakeStore(fail_on="scale_readings"))
        with pytest.raises(Exception):
            r.save_scale_readings(READINGS)
        assert r.get_scale_readings() == []
    finally:
        record_cache.forget(db)
