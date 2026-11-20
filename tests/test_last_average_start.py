"""The reverse crunch and the side plank with hip raises start at the average of
last time's sets (Update 5, WP-55).

The athlete, 2026-11-19: "Reverse crunch should start what the average of the
reps I performed the previous time not always 12"; his answer "Agree" to both
exercises (the two to-failure exercises with no rep range), rounded to the
nearest whole rep: 14, 14, 12 gives 13. Every other unloaded exercise keeps
today's planned reps.
"""
from __future__ import annotations

from datetime import date

import goal_block as gb
from services import prescription
from services import sessions as sess

TWO = {"Reverse Crunch (Ab Mat)", "Side Plank with Hip Raises"}


def _block(name):
    return next(e for d in gb.SESSIONS.values() for e in d if e["name"] == name)


def _sets(*reps, left=None):
    out = [{"set_num": i + 1, "reps": r, "weight": 0.0} for i, r in enumerate(reps)]
    for i, value in enumerate(left or []):
        if value != reps[i]:
            out[i]["reps_left"] = value
    return out


def test_only_the_two_exercises_start_at_last_times_average():
    marked = {e["name"] for d in gb.SESSIONS.values() for e in d if e.get("start_from_last_average")}
    assert marked == TWO


def test_the_average_is_rounded_to_the_nearest_rep():
    crunch = _block("Reverse Crunch (Ab Mat)")
    assert sess.bodyweight_entry(crunch, _sets(14, 14, 12), "2026-11-11")["reps"] == 13
    assert sess.bodyweight_entry(crunch, _sets(15, 15, 15), "2026-11-19")["reps"] == 15
    assert sess.bodyweight_entry(crunch, _sets(15, 14, 14, 14), None)["reps"] == 14   # 14.25
    assert sess.bodyweight_entry(crunch, _sets(15, 14), None)["reps"] == 15           # 14.5 up


def test_a_one_side_exercise_counts_both_sides():
    plank = _block("Side Plank with Hip Raises")
    entry = sess.bodyweight_entry(plank, _sets(12, 12, 12, left=[10, 10, 10]), "2026-11-13")
    assert (entry["reps"], entry["source"], entry["last_seen_date"]) == (11, sess.LAST_AVERAGE_SOURCE, "2026-11-13")


def test_no_history_starts_at_the_plan_and_warm_up_sets_never_count():
    crunch = _block("Reverse Crunch (Ab Mat)")
    assert sess.bodyweight_entry(crunch, None, None) == sess.bodyweight_entry(crunch)
    assert sess.bodyweight_entry(crunch)["reps"] == crunch["reps"] == 12
    warm = [{"reps": 30, "is_warmup": True}] + _sets(13, 13, 13)
    assert sess.bodyweight_entry(crunch, warm, None)["reps"] == 13


def test_another_unloaded_exercise_keeps_its_planned_reps():
    march = _block("Standing Psoas March")
    assert sess.bodyweight_entry(march, _sets(30, 30), "2026-11-11") == sess.bodyweight_entry(march)


class _Repo:
    def get_last_performance(self, name):
        return {"session_date": "2026-11-11", "reps": 12, "weight_kg": 0.0, "band_tier": None}

    def get_last_session_all_sets(self, name):
        return _sets(14, 14, 12)


def test_the_seed_starts_the_reverse_crunch_at_13_after_14_14_12():
    crunch = _block("Reverse Crunch (Ab Mat)")
    seed = prescription.seed_exercise(_Repo(), crunch, streak_label="normal",
                                      policy=sess.load_policy(None, None), today=date(2026, 11, 20))
    assert seed.entry["reps"] == 13 and seed.entry["source"] == sess.LAST_AVERAGE_SOURCE
    assert sess.actual_caption(seed.entry) == (
        "The average of your sets last time (2026-11-11). Change them if you do a different number.")
