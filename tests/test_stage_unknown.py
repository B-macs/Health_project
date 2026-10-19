"""Fault F23 (rebuild Phase 2, fixed 2026-10-19): Repository.get_current_stage
read a missing or unreadable stage as stage 1, a silent guess inherited by
every reader. It now raises StageUnknownError, and each caller decides in the
open: the day's decision has no opinion, Home does not score strain (F7), the
yoga cautions use the strictest stage and say so.
"""

from __future__ import annotations

from datetime import date

from services import decision
from services import rules
from services import yoga
from services.repository import StageUnknownError


class _Repo:
    def __getattr__(self, name):
        return lambda *a, **k: []

    def get_current_stage(self):
        raise StageUnknownError("the stored stage is missing")


def test_an_unknown_stage_leaves_the_day_without_an_opinion():
    assert decision.directive(_Repo(), date(2026, 10, 19)) == decision.NO_OPINION


def test_the_yoga_fallback_is_the_strictest_stage():
    assert yoga.STAGE_WHEN_UNKNOWN == min(rules.STAGE_CONSTRAINTS) == 1
