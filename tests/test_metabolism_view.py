"""The Metabolism page rendered alone in Streamlit's test runtime (move INS-2,
faults F11 and F15, 2026-10-19): it reads the readings from the repository,
never from a local file, prints no "Normal" pill, and colours a rise in
fat-free mass as good. Made-up readings; no network and no secrets.
"""

from __future__ import annotations

import os

from streamlit.testing.v1 import AppTest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_SCRIPT = '''
import sys
sys.path.insert(0, r"{root}")
from datetime import date, datetime, timedelta
import repo
import streamlit as st
from services import body_composition as bc

today = date.today()


def _r(days_back, weight, pct):
    d = today - timedelta(days=days_back)
    return bc.ScaleReading(taken_at=datetime(d.year, d.month, d.day, 7, 30),
                           weight_kg=weight, bmi=None, body_fat_pct=pct)


class _Repo:
    def get_scale_readings(self):
        # fat-free mass rises from 64.0 kg (80 x 0.80) to 66.4 kg (82 x 0.81)
        return [_r(20, 80.0, 20.0), _r(5, 82.0, 19.0)]

    def get_inbody_scans(self):
        return [bc.InBodyScan(taken_at=datetime(2026, 6, 1, 12, 0), weight_kg=80.0,
                              bmi=80.0 / 1.82 ** 2, total_body_water_l=48.0,
                              skeletal_muscle_kg=37.0, ecw_tbw=0.377, phase_angle_deg=6.0,
                              device="Model A")]

    def get_seca_scans(self):
        return []


repo.get_repository = lambda: _Repo()
from views import insights as V
V._metabolism_screen_data.clear()
st.session_state.setdefault("metab_metric", "{metric}")
V._render_metabolism_detail()
'''


def _run(metric: str) -> AppTest:
    at = AppTest.from_string(_SCRIPT.format(root=_ROOT, metric=metric), default_timeout=120)
    at.run()
    assert not at.exception, at.exception
    return at


def test_the_page_reads_the_store_and_prints_no_normal_pill():
    at = _run("Weight")
    page = "\n".join(m.value for m in at.markdown)
    assert "kg fat" in page and "Model A" in page
    assert "Normal" not in page
    assert not at.warning, "a read that worked raises no warning"


def test_a_rise_in_fat_free_mass_reads_as_good():
    from views import insights as V
    page = "\n".join(m.value for m in _run("Fat-free mass").markdown)
    assert f'<span style="color:{V._GOOD}">+' in page
