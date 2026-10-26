"""The SECA scans (WP-37, the owner, 2026-10-26: "the new metabolism update is
coming from the new SECA machine in the gym ... ill be doing this every 12
weeks"). Its own lane: never pooled with the scale or the InBody. The export
below has the machine's German layout and made-up numbers."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from services import body_composition as bc
from services import metabolism_screen as ms

EXPORT = '''"Wert","Einheit","Mar 3, 2026, 7:05 AM"
"Fettmasse-Index","kg/m²","5.0"
"Fettfreie-Masse-Index","kg/m²","19.0"
"Prozentuale Fettmasse","%","20.0"
"Skelettmuskelmasse","kg","30.00"
"Phasenwinkel","°","5.0"
"Wasserverhältnis","%","40"
"Viszerales Fett","",""
"Taillenumfang","",""
"Fettmasse","kg","16.00"
"Segmentale Skelettmuskelmasse","",""
"Torso","kg","14.00"
"Linker Arm","kg","2.00"
"Linkes Bein","kg","6.00"
"Rechter Arm","kg","1.80"
"Rechtes Bein","kg","6.30"
"Skelettmuskelmasse in Abhängigkeit vom Alter","kg","30.00"
"Segmentale Skelettmuskelmasse","",""
"Torso","kg","99.00"
"Linker Arm","kg","99.00"
"Ruheenergieverbrauch","kcal/Tag","1800"
"Ruheenergieverbrauch","MJ/Tag","7.53"
"Body-Mass-Index","kg/m²","24.0"
"Gewicht","kg","80.00"
'''


def test_the_export_is_read_figure_by_figure():
    scan = bc.parse_seca_csv("﻿" + EXPORT)
    assert scan.taken_at == datetime(2026, 3, 3, 7, 5) and scan.device == "SECA"
    assert (scan.weight_kg, scan.fat_pct, scan.fat_mass_kg, scan.skeletal_muscle_kg) == (80.0, 20.0, 16.0, 30.0)
    assert scan.fat_free_mass_kg == 64.0
    assert (scan.phase_angle_deg, scan.water_ratio_pct, scan.resting_kcal) == (5.0, 40.0, 1800.0)
    assert scan.visceral_fat is None and scan.waist_cm is None, "blank is not measured, never 0"
    assert dict(scan.segments) == {"torso": 14.0, "left_arm": 2.0, "left_leg": 6.0,
                                   "right_arm": 1.8, "right_leg": 6.3}, "the first block only"
    assert scan.height_m == pytest.approx(1.826, abs=0.001)


def test_a_file_that_is_not_a_seca_export_is_refused():
    with pytest.raises(ValueError):
        bc.parse_seca_csv('"Date","Weight"\n"2026-03-03","80"\n')
    with pytest.raises(ValueError):
        bc.parse_seca_csv(EXPORT.replace('"Gewicht","kg","80.00"\n', ""))


def test_a_stored_scan_reads_back_the_same():
    scan = bc.parse_seca_csv(EXPORT)
    assert bc.seca_scans_from_rows([bc.seca_scan_row(scan)]) == [scan]


def test_the_section_shows_each_figure_and_each_side():
    first = bc.parse_seca_csv(EXPORT)
    later = bc.parse_seca_csv(EXPORT.replace("Mar 3, 2026", "Jun 2, 2026")
                              .replace('"Gewicht","kg","80.00"', '"Gewicht","kg","81.00"'))
    out = ms.seca([first, later], date(2026, 6, 9))
    assert (out["date"], out["count"], out["days_old"]) == (date(2026, 6, 2), 2, 7)
    figures = {f["key"]: f for f in out["figures"]}
    assert figures["weight_kg"]["value"] == 81.0 and figures["weight_kg"]["change"] == 1.0
    assert figures["visceral_fat"]["value"] is None
    arms = next(s for s in out["sides"] if s["label"] == "Arms")
    assert (arms["left_kg"], arms["right_kg"], arms["right_vs_left_pct"]) == (2.0, 1.8, -10.0)
    assert ms.seca([first], date(2026, 3, 3))["figures"][0]["change"] is None
    assert ms.seca([], date(2026, 3, 3)) is None


def test_the_tile_shows_the_newest_weight_with_its_device():
    scan = bc.parse_seca_csv(EXPORT)
    older = bc.ScaleReading(taken_at=datetime(2026, 2, 1, 7, 0), weight_kg=79.0, bmi=None,
                            body_fat_pct=None)
    newer = bc.ScaleReading(taken_at=datetime(2026, 3, 9, 7, 0), weight_kg=79.5, bmi=None,
                            body_fat_pct=None)
    assert ms.headline([older], [scan]) == {"date": date(2026, 3, 3), "weight_kg": 80.0, "source": "seca"}
    assert ms.headline([newer], [scan])["source"] == "scale"
    assert ms.headline([], []) is None


def test_the_import_script_finds_the_newest_export(tmp_path):
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location(
        "import_seca_scan", Path(__file__).resolve().parents[1] / "scripts" / "import_seca_scan.py")
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    assert script.newest_export(tmp_path) is None
    for name in ("Made_Up_TableView_2026-03-03_SECA.csv", "Made_Up_TableView_2026-06-02_SECA.csv",
                 "Fitdays.csv"):
        (tmp_path / name).write_text(EXPORT, encoding="utf-8")
    assert script.newest_export(tmp_path).name == "Made_Up_TableView_2026-06-02_SECA.csv"
