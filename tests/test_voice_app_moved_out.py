"""Voice Training left the health app on 2026-10-19 (rebuild Phase 1).

It runs as its own Streamlit app from B-macs/health-voice-training. These keep
it out: no route, no nav tab, no page file, no submodule, no voice-only library,
and an old ?page=sync link lands on Home rather than on a page that is gone.
Static checks only: app.py is never imported (it runs the Home page), and
nav.py is read as source so the engine's Python 3.12 run needs no Streamlit.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")


def _assigned(source: str, name: str):
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} is not assigned")


def test_the_nav_bar_has_three_tabs_and_no_voice_tab():
    items = _assigned((ROOT / "nav.py").read_text(encoding="utf-8"), "_ITEMS")
    assert [key for _icon, _label, key in items] == ["home", "training", "insights"]


def test_every_tab_routes_somewhere_and_an_unknown_page_falls_back_to_home():
    # The routing moved to services/navigation.py (move INS-8, 2026-10-19).
    from services import navigation
    assert set(navigation.PAGES) == {"home", "training", "insights", "checkin"}
    assert navigation.resolve_page(None, "sync") == "home"
    assert "_page = navigation.resolve_page(" in APP


def test_no_route_or_file_loads_the_voice_page():
    assert "views import sync" not in APP
    assert not (ROOT / "views" / "sync.py").exists()


def test_the_submodule_and_the_voice_libraries_are_gone():
    assert not (ROOT / ".gitmodules").exists()
    names = {line.split(">")[0].split("=")[0].split("<")[0].strip().lower()
             for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()}
    assert not names & {"praat-parselmouth", "scipy", "soundfile", "imageio-ffmpeg"}
