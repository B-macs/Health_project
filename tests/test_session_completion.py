"""The completion screen's rules, moved out of views/training.py on
2026-10-19 (move TRN-16), and inventory fault F16: the save's "Estimated AU"
preview read RPE 5 whatever rating was chosen, because the rating sat inside
a Streamlit form, where a widget's value arrives only on submit.
"""

from __future__ import annotations

from pathlib import Path

from services import sessions as sess

ROOT = Path(__file__).resolve().parents[1]

_EXERCISES = [
    {"name": "Goblet Squat", "type": "reps", "sets": 3, "reps": 10, "weight_kg": 22.5,
     "equipment_type": "dumbbell", "rest_seconds": 90},
]


def test_the_clock_gives_whole_minutes_and_never_less_than_five():
    start = 1_000_000.0
    assert sess.elapsed_minutes(start, start + 52 * 60 + 59, _EXERCISES) == 52
    assert sess.elapsed_minutes(start, start + 60, _EXERCISES) == sess.MIN_SESSION_MINUTES
    assert sess.elapsed_minutes(start, start + 60, _EXERCISES,
                                floor=sess.MIN_ACCESSORY_MINUTES) == 3, "the accessory session"


def test_a_session_without_a_clock_saves_its_modelled_length():
    assert sess.elapsed_minutes(0, 1_000_000.0, _EXERCISES) == sess.estimate_duration(_EXERCISES)


def test_the_load_is_the_chosen_rating_times_the_minutes():
    assert sess.session_au(8, 45) == 360.0
    assert sess.session_au(5, 45) != sess.session_au(8, 45), "F16: the rating moves the AU"


def _hr(rpe=6.0, au=300.0, coverage=0.95):
    return {"hr_rpe": rpe, "hr_au": au, "hr_coverage": coverage, "hr_active_minutes": 48,
            "activity_name": "Strength", "hr_covered_exercises": 5, "hr_total_exercises": 6}


def test_no_heart_rate_figure_means_no_comparison():
    assert sess.hr_comparison(None, 6, 300) is None
    assert sess.hr_comparison({"needs_choice": True, "reason": "clocks"}, 6, 300) is None
    assert sess.hr_comparison({"hr_au": None}, 6, 300) is None


def test_the_verdict_reads_the_difference_in_rating():
    assert sess.hr_comparison(_hr(rpe=6.3), 6, 300)["verdict"] == "exact"
    assert sess.hr_comparison(_hr(rpe=7.0), 6, 300)["verdict"] == "under"
    assert sess.hr_comparison(_hr(rpe=5.0), 6, 300)["verdict"] == "over"
    cmp = sess.hr_comparison(_hr(rpe=7.0, au=350.0), 6, 300)
    assert cmp["rpe_delta"] == 1.0 and cmp["au_delta"] == 50.0


def test_without_a_rating_there_is_no_verdict_and_no_difference():
    cmp = sess.hr_comparison(_hr(), None, None)
    assert cmp["verdict"] is None and cmp["rpe_delta"] is None and cmp["au_delta"] is None
    assert cmp["measured_rpe"] == 6.0 and cmp["measured_au"] == 300.0


def test_a_paused_watch_is_said_out_loud():
    assert not sess.hr_comparison(_hr(coverage=0.85), 6, 300)["low_coverage"]
    assert sess.hr_comparison(_hr(coverage=0.84), 6, 300)["low_coverage"]
    assert sess.hr_comparison(_hr(coverage=None), 6, 300)["low_coverage"]


def test_the_rating_sits_outside_the_save_form_and_drives_the_preview():
    """F16. Inside st.form the slider's value reaches the script only on
    submit, so the preview could not follow it. The rating and the length
    choice render before the form; the form holds the notes and Save."""
    src = (ROOT / "views" / "training.py").read_text(encoding="utf-8")
    form = src.index('with st.form("log_session_form")')
    slider = src.index('key="tp_save_rpe"')
    length = src.index('key="tp_length_choice"')
    preview = src.index("sess.session_au(session_rpe, _save_minutes)")
    assert slider < form and length < form and preview < form
    assert "5 * _save_minutes" not in src
    assert "sess.elapsed_minutes(" in src and "sess.hr_comparison(" in src
