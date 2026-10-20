"""The switch-over's one write and its undo (rebuild Phase 9, switch step 3;
scripts/set_background_writer.py). Through a Repository over a fake store; the
command line is checked only where it refuses before any store is built."""

from __future__ import annotations

from datetime import date

import pytest

from scripts import set_background_writer as sbw
from services import background_writer as bw
from tests._record_store import FakeStore, new_local_copy, record_repo

DAY = date(2026, 10, 20)


def test_the_dry_run_says_what_it_would_write():
    assert sbw.plan(bw.STREAMLIT, bw.ENGINE) == "Would set background_writer from streamlit to engine."
    assert sbw.plan(None, bw.ENGINE) == "Would set background_writer from unreadable to engine."
    assert "already names engine" in sbw.plan(bw.ENGINE, bw.ENGINE)


def test_apply_writes_and_reads_back_and_the_undo_restores(tmp_path):
    repo = record_repo(new_local_copy(tmp_path), FakeStore())
    assert bw.current(repo) == bw.STREAMLIT, "absent reads as the old app"
    assert sbw.apply(repo, bw.ENGINE, DAY) == bw.ENGINE
    assert sbw.apply(repo, bw.STREAMLIT, DAY) == bw.STREAMLIT


def test_an_unknown_writer_is_refused(tmp_path):
    repo = record_repo(new_local_copy(tmp_path), FakeStore())
    with pytest.raises(ValueError):
        sbw.apply(repo, "both", DAY)
    with pytest.raises(SystemExit):
        sbw.main(["--to", "both"])
