# Tests that need Streamlit (rebuild Phase 0 → mapped in Phase 10)

These test files import `streamlit` or a screen module (`app`, `views`, `nav`,
`styles`, `repo`), so they cannot run in the engine's venv, which has no
Streamlit. `scripts/rebuild_gate.py` reads this list (the lines that start with
"- `tests/") and passes each file as `--ignore` and each single test (`file::test`) as `--deselect` to the engine-venv run.
Phase 10 maps every one to a replacement, or to a retirement that the owner
approves. Found 2026-10-07 by an import scan of `tests/`.

- `tests/test_checkin_view_edits.py` — the check-in page opens a saved day filled in (added 2026-10-19, fault F3)
- `tests/test_chart_axes.py` — chart axis rendering in app.py/styles.py
- `tests/test_flexibility_screen.py` — the flexibility (Cluster A) screen
- `tests/test_hold_timer_endings.py` — the guided flow's hold-timer endings
- `tests/test_home_and_training_agree.py` — Home and Training show one readiness
- `tests/test_nav_survives_a_failing_view.py` — the nav bar survives a broken view
- `tests/test_no_replay_unsafe_cached_elements.py` — Streamlit cache replay hazard
- `tests/test_previous_session_display.py` — the previous-session line
- `tests/test_sleep_screen_is_all_or_nothing.py` — the Sleep screen rule
- `tests/test_strain_screen.py` — the strain screen
- `tests/test_strength_screen.py` — the strength screen
- `tests/test_training_guided_flow_fragment.py` — the guided training flow
- `tests/test_training_save_view.py` — the Training page's own save, run in Streamlit's test runtime (added 2026-10-19)
- `tests/test_engine_data_screen.py` — Insights › Engine Data rendered alone (added 2026-10-19)
- `tests/test_gate1_view.py` — the training page's gate-1 card rendered alone (added 2026-10-19)
- `tests/test_metabolism_view.py` — the Metabolism page rendered alone (added 2026-10-19)
- `tests/test_core_hold_score.py::test_core_s_card_shows_the_hold_time_marked_provisional` — ONE test (added 2026-10-16): it renders the strength card with views/insights.py; the rest of the file is engine-only and stays in the engine run

## Tests that only READ the screen files as text
These run in any venv (they parse source, they do not import it), so the
engine run keeps them. Phase 10 still maps them, because the files they read
are removed then:

test_accessory, test_begin_next_phase_reachable, test_datastore_cache_mode,
test_directive_no_contradiction, test_exercise_notes, test_exercise_rpe_from_hr,
test_failed_week_rule, test_manual_sync_serialised, test_no_stage_one_on_screen,
test_plan, test_plan_text_is_instructions_only, test_profile_is_position_not_programme,
test_scheduling, test_session_hr_sync, test_session_save_resumes, test_spa_navigation,
test_supabase_mirror, test_supabase_mirror_notion, test_supplementary_save_once,
test_traffic_light_awaits_today, test_training_checkpoint_mirror.

## Measured
2026-10-07, `.venv-engine` (Python 3.12.9, requirements-engine-dev.txt), these
11 ignored: **3895 passed, 1 skipped, 0 failed** in 72 s. The main gate in
`venv/` (Python 3.11.9) is 4226 at the floor, so the 11 files hold about 330 tests.

2026-10-16, the same venv on the current code (the 12-week block and Supabase as the only store had landed), the 11 files ignored and the one test deselected: **4588 passed, 1 skipped, 1 deselected, 0 failed** in 99 s. The main gate in `venv/` read 4929 passed, 1 skipped.
