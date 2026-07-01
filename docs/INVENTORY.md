# docs/INVENTORY.md

*Phase 1 snapshot — 2026-06-30 — read-only codebase audit, no behaviour changed*

---

## File Inventory

Confidence key: 🟢 fully read, high confidence · 🟠 partially read or contains stale/unused content · 🔴 requires immediate attention

| # | Path | Purpose | Key Functions / Constants | Internal Imports | Imported By | Conf |
|---|------|---------|--------------------------|-----------------|-------------|------|
| 1 | `app.py` | SPA entry point + home dashboard. Routes based on `st.session_state["_nav_page"]`. Renders home cards inline; delegates all other views to `views/*.py`. | `_arc_svg`, `_sparkline`, `_readiness_meta`, `_strain_meta`, `_sleep_meta`, `_card_html`, `_strain_detail`; `_SLEEP_NEED_HOURS=8.0`; `_CARD_BG` bg-image map | `db`, `engine`, `nav`, `readiness` (as `readiness_model`), `styles`, `sync_sheets`, `views.checkin`, `views.training`, `views.insights`, `views.sync` | — (entry point) | 🟢 |
| 2 | `db.py` | Notion API backend — all reads and writes. Manages 4 databases: Readiness, Training, Biometrics, Config. Secrets via `_secret()` (OS env → `st.secrets`). | `save_daily_readiness`, `create_training_session`, `get_daily_session_au`, `get_biometric_rolling`, `get_current_stage`, `get_pain_free_streak`, `get_avg_tightness`, `get_diagnostic_profile`, `get_macro_trend_data`; `_query_all` (pagination + 429 retry); `_get`, `_title`, `_text`, `_num`, `_sel`, `_msel`, `_date` | — | `app.py`, `views/checkin.py`, `views/training.py`, `views/insights.py` | 🟢 |
| 3 | `engine.py` | Pure deterministic math. No DB access, no Streamlit. Computes all load metrics and recommendations. | `au_to_strain`, `traffic_light`, `acwr`, `volume_recommendation`, `apply_volume_recommendation`, `stage_status`, `check_auto_stage_advance`, `injury_weight`, `injury_weight_signal`, `compute_session_au`, `observation_days_remaining`; `STAGE_CLF={1:0.04,2:0.40,3:1.0}`, `YELLOW_THRESHOLD=0.10`, `RED_THRESHOLD=0.25`, `MIN_OBSERVATION_DAYS=14` | — | `app.py`, `views/training.py`, `views/insights.py`, `tests.py` | 🟢 |
| 4 | `readiness.py` | Adaptive readiness score from HRV + sleep + RHR. Progressive sleep baseline (7→14→28→56 nights). | `compute_readiness`, `sleep_baseline`, `hrv_baseline`, `rhr_baseline`; `NOT_COMPUTED="NOT_COMPUTED"`, `_SLEEP_WINDOWS=(7,14,28,56)`, `_SLEEP_MIN_H=4.0`, `_SLEEP_MAX_H=11.0`, `_MIN_DAYS=14`, `_MIN_SLEEP=7` | — | `app.py` (as `readiness_model`) | 🟢 |
| 5 | `stats.py` | Deterministic statistical engine — lag correlation, trend slopes, recovery direction, symptom detection. | `lag_correlation`, `trend_slope`, `recovery_direction`, `session_tonnage`, `detect_neural_symptoms`, `detect_urgent_symptoms`, `auto_warning_level`, `compute_all_correlations`; `NEURAL_KEYWORDS` (17 items), `URGENT_KEYWORDS` (12 items) | — | `ai.py` (as `_stats`), `views/insights.py` (as `stats_mod`), `tests.py` | 🟢 |
| 6 | `rules.py` | Movement safety rules + stage constraints. Single source of truth for ACWR ceilings, RPE ceilings, volume caps per stage. | `check_movement`, `get_contraindicated_always`, `get_cleared_for_stage`, `get_caution_movements`, `get_stage_constraints`, `movement_safety_summary`; `MovementRule` dataclass; `MOVEMENT_RULES` (35 entries); `STAGE_CONSTRAINTS` dict (stages 1-3) | — | `ai.py` (as `_rules`), `tests.py` | 🟢 |
| 7 | `ai.py` | Deterministic rule-based text parsers. No LLM calls. `MODEL_FAST = MODEL_SMART = "rules-based"` for API compatibility. | `parse_session_note`, `parse_tightness`, `analyze_macro_trends`, `assess_movement_risk`; `_SEVERITY_TABLE` (38), `_SENSATION_MAP` (35), `_BODY_PART_MAP` (23), `_POSITIVE_WORDS` (20), `_NEGATIVE_WORDS` (18), `_HEADLINES`, `_LOAD_NOTES`, `_RECOMMENDATIONS`, `_CORR_TEMPLATES` (18) | `stats` (as `_stats`), `rules` (as `_rules`) | `views/insights.py` | 🟢 |
| 8 | `nav.py` | Bottom navigation bar + JS bridge (URL-based nav via `?page=X`). No hidden trigger buttons. | `inject`, `bottom_nav_html`; `CHROME_CSS`, `_ITEMS` (4 nav items), `_JS_BRIDGE_TMPL` | — | `app.py` | 🟢 |
| 9 | `styles.py` | Dual-theme CSS (Oura palette ≤768px / Whoop palette ≥769px). Component helpers for SVG rings, stat blocks, cards. | `inject_css`, `oura_ring`, `oura_card`, `whoop_stat`, `whoop_panel`, `dual_layout`; `OURA` dict, `WHOOP` dict; `_build_css()` | — | `app.py` (and via views as needed) | 🟢 |
| 10 | `sync_sheets.py` | Google Sheets biometrics reader (gspread, service account). Returns same row format as `db.get_biometric_rolling()`. | `get_biometric_rolling`, `fetch_all_rows`; column mappings for HRV, RHR, sleep, steps, weight | — | `app.py`, `views/training.py`, `views/insights.py`, `views/sync.py` | 🟢 |
| 11 | `training_constants.py` | Exercise catalogue + enum lists. Intended single source for ANATOMICAL_LOCATIONS and SENSATION_TAGS. | `EXERCISES` (4 categories), `ALL_EXERCISES`, `MOVEMENT_TYPES`, `VELOCITY_OPTIONS`, `ANATOMICAL_LOCATIONS` (21 items), `SENSATION_TAGS` (9 items) | — | ⚠️ Nothing imports it — `ANATOMICAL_LOCATIONS` and `SENSATION_TAGS` duplicated in `views/checkin.py` without import | 🟠 |
| 12 | `training_plan.py` | 14-day bodyweight rehab exercise data. All exercise objects with mechanics, biomechanical focus, progressions, regressions. | `PLAN` dict (days 1–14); `UPPER_GLUTE_RELEASE`, `RIGHT_HIP_CAPSULE`, `PIRIFORMIS_PNF`, `ISCHIAL_RELEASE`, `COXA_SALTANS_DRILL` (shared release exercises); `_ex()` helper | — | `views/training.py` (as `tp`) | 🟢 |
| 13 | `patient_profile.py` | Clinical reference data: MRI findings, biomechanical assessment, imbalances, pre-session release protocol. | `PROFILE` dict; `current_stage=1`, `mri` (primary + secondary + constraints), `biomechanical_findings` (5 items), `imbalances`, `pre_session_release`, `stage_1_exit_criteria` | — | ⚠️ Not imported by any active code — `init_db.py` seed data mirrors its content; `training_plan.py` docstring references it | 🟠 |
| 14 | `views/checkin.py` | Morning check-in form. Collects tightness/pain/locations/sensations/lifestyle and saves via `db.save_daily_readiness()`. | `render()`; `ANATOMICAL_LOCATIONS` (21 items ⚠️ dup), `SENSATION_TAGS` (9 items ⚠️ dup), `CONDITION_OPTIONS` | `db` | `app.py` (SPA router) | 🟢 |
| 15 | `views/training.py` | Interactive 14-day session guide. LocalStorage-persisted timers (hold/rest/duration). Session state preserved across SPA navigation. Auto-logs completed sessions to Notion. | `render()`; `_hold_timer`, `_rest_timer`, `_duration_timer` (JS components) | `db`, `engine`, `sync_sheets`, `training_plan` (as `tp`) | `app.py` (SPA router) | 🟢 |
| 16 | `views/insights.py` | 6-tab insights page: Training Directive, Engine Data, Processing Queue, Tightness Map, Macro Trends, MRI Intelligence. Module-level `@st.cache_data(ttl=1800)` fetchers. | `render()`; cached `_bio()`, `_au()`, `_streak()`, `_tight()`, `_diag()`, `_stage()` | `db`, `ai`, `engine`, `sync_sheets`, `stats` (as `stats_mod`) | `app.py` (SPA router) | 🟢 |
| 17 | `views/sync.py` | Raw biometric data viewer from Google Sheets. Cache-busting refresh button. | `render()`, `_load()` | `sync_sheets` | `app.py` (SPA router) | 🟢 |
| 18 | `views/__init__.py` | Empty package init | — | — | — | 🟢 |
| 19 | `_pages/0_Training_Plan.py` | Redirect stub → `app.py` via `st.switch_page` | `st.switch_page("app.py")` | — | Streamlit multi-page router (suppressed) | 🟢 |
| 20 | `_pages/1_Home.py` | Redirect stub → `app.py` | `st.switch_page("app.py")` | — | Streamlit multi-page router (suppressed) | 🟢 |
| 21 | `_pages/2_Check_In.py` | Redirect stub → `app.py` | `st.switch_page("app.py")` | — | Streamlit multi-page router (suppressed) | 🟢 |
| 22 | `_pages/3_Autoregulation.py` | Redirect stub → `app.py` | `st.switch_page("app.py")` | — | Streamlit multi-page router (suppressed) | 🟢 |
| 23 | `_pages/4_AI_Insights.py` | Redirect stub → `app.py` | `st.switch_page("app.py")` | — | Streamlit multi-page router (suppressed) | 🟢 |
| 24 | `_pages/6_Sync.py` | Redirect stub → `app.py` | `st.switch_page("app.py")` | — | Streamlit multi-page router (suppressed) | 🟢 |
| 25 | `init_notion.py` | One-shot Notion backend setup + DB connectivity verification. Seeds `current_stage=1` and `diagnostic_profile` into Config DB. | `main()`, `_check_db()`, `_seed_config()`; `DIAGNOSTIC_PROFILE` seed dict | — | — (CLI, run once) | 🟢 |
| 26 | `init_db.py` | One-shot SQLite schema init + migration. Seeds diagnostic profile + biomechanical assessment. | `init_db()`, `_migrate()`, `_seed_diagnostic_profile()`, `_seed_biomechanical_profile()`, `_seed_user_config()`; full biomechanical seed data (2026-06-28 assessment) | — | — (CLI, run once; ⚠️ orphaned — app runs on Notion) | 🟠 |
| 27 | `schema.sql` | SQLite DDL: 9 tables + indexes (legacy). Equivalent data model to Notion DBs. | Tables: `diagnostic_profile`, `daily_readiness`, `training_sessions`, `training_log`, `training_set_log`, `session_notes`, `daily_biometrics`, `ai_movement_risk`, `biomechanical_assessment`, `user_config` | — | `init_db.py` (⚠️ orphaned) | 🟠 |
| 28 | `tests.py` | Deterministic regression test suite. Run with `py tests.py`. Covers engine, stats, rules with boundary conditions. | `section()`, `check()`; 70+ test cases across: constants, injury_weight, traffic_light, acwr, volume_recommendation, apply_volume_recommendation, stage_status, check_auto_stage_advance, symptom detection, trend_slope, recovery_direction, session_tonnage, lag_correlation, check_movement, stage_constraints | `engine`, `stats`, `rules` | — (test runner) | 🟢 |
| 29 | `requirements.txt` | Python dependencies (6 packages). | `streamlit>=1.58`, `pandas>=3.0`, `numpy>=2.0`, `notion-client==2.2.1`, `streamlit-aggrid>=1.2`, `gspread>=6.0` | — | — | 🟠 |
| 30 | `resume.md` | Full architecture specification, development philosophy, stage machine, biometric pipeline, Notion schema, agile roadmap, keyword library. | Living document — 400 lines. Last updated 2026-06-29. | — | Read by developers; all new code should comply with rules section | 🟢 |
| 31 | `README.md` | Empty (project name only — encoding issue) | — | — | — | 🟠 |
| 32 | `.streamlit/secrets.toml` | All production secrets: Notion API key + 5 DB IDs, Google Sheets ID, full Google service account JSON (private key included). | Real credentials — Notion key `ntn_520514...`, GCP project `[REDACTED-GCP-PROJECT]` | — | Streamlit runtime → `db.py` (via `st.secrets`), `sync_sheets.py` | 🔴 |
| 33 | `Training plan/Training_System.md` | Human-readable methodology overview: load formulas, CLF table, ACWR, readiness score, sleep baseline, data sources, file index. | Reference doc — mirrors `engine.py` + `readiness.py` formulas | — | — (human reference) | 🟢 |
| 34 | `Training plan/Stage_1_14_Day_Plan.md` | Day-by-day exercise plan in readable form. Maps to `training_plan.py` PLAN dict. | 14 days / 2 weeks; exercises, mechanics, biomechanical cues, progressions | — | — (human reference) | 🟢 |

---

## Implicit Architecture

```
Streamlit URL-nav (each nav tap reloads to ?page=X, Streamlit reconnects)
══════════════════════════════════════════════════════════════

  app.py  ──────────────────────────────────┐
  (SPA router)                              │ home dashboard
       │ reads st.query_params["page"]      │ rendered inline
       ├── "checkin"  → views/checkin.py    │
       ├── "training" → views/training.py   │
       ├── "insights" → views/insights.py   │
       └── "sync"     → views/sync.py       │
  
  nav.py ← injected by app.py               │
    JS bridge: stNav(page) sets ?page=X     │

  ── Pure logic (no I/O) ────────────────────────────────────
  engine.py      ← zero internal imports
  readiness.py   ← zero internal imports
  stats.py       ← zero internal imports
  rules.py       ← zero internal imports
  nav.py         ← zero internal imports
  styles.py      ← zero internal imports

  ai.py          ← stats.py, rules.py

  ── Data layer ─────────────────────────────────────────────
  db.py          → Notion API (4 DBs: Readiness, Training, Biometrics, Config)
  sync_sheets.py → Google Sheets (gspread service account, read-only)

  ── Reference data ─────────────────────────────────────────
  training_plan.py       → PLAN dict (14 exercise days)
  training_constants.py  → EXERCISES catalogue (⚠️ not wired into checkin)
  patient_profile.py     → PROFILE dict (⚠️ not imported by any module)

  ── Legacy / setup ─────────────────────────────────────────
  init_notion.py  ← CLI one-shot (Notion setup)
  init_db.py      ← CLI one-shot (SQLite — ORPHANED, app uses Notion)
  schema.sql      ← read by init_db.py only (ORPHANED)

  ── Secrets ────────────────────────────────────────────────
  .streamlit/secrets.toml ← gitignored ✅ — NOT committed
```

---

## Problems

Severity: 🔴 bug/data-loss risk · 🟠 silent drift risk · 🟡 quality/clarity

---

### P1 — ACWR ceiling wrong for Stage 3 🔴

**File:** `engine.py`, `acwr()` function  
**Code:** `ceiling = 1.2 if stage == 1 else 1.3`  
**Problem:** Stage 3 gets ceiling `1.3` from `engine.acwr()`, but `rules.STAGE_CONSTRAINTS[3]["acwr_ceiling"] = 1.5`. The two authoritative values disagree. This is a real behavioural divergence right now, not a future drift risk.  
**Impact:** Stage 3 hard-locks too early — at 1.3× instead of 1.5×. Stage 2 is correct (1.3).  
**Test gap:** `tests.py` only verifies Stage 1 (1.2) and Stage 2 (1.3) ceilings from `engine.acwr()`. Stage 3 is not tested.  
**Proposed fix (Phase 2 — needs approval):** Import `STAGE_CONSTRAINTS` from `rules.py` in `engine.py`; derive ceiling as `rules.STAGE_CONSTRAINTS.get(stage, {}).get("acwr_ceiling", 1.3)`.

---

### P2 — `ANATOMICAL_LOCATIONS` duplicated 🟠

**Files:** `training_constants.py:69–90` and `views/checkin.py:11–33`  
**Problem:** Identical 21-item list defined in both places. `views/checkin.py` does not import from `training_constants.py`. Any edit to one will not propagate to the other.  
**Proposed fix (Phase 2):** Delete the local copy from `views/checkin.py`; add `from training_constants import ANATOMICAL_LOCATIONS, SENSATION_TAGS`.

---

### P3 — `SENSATION_TAGS` duplicated 🟠

**Files:** `training_constants.py:94–105` and `views/checkin.py:35–45`  
Same issue as P2. 9-item list defined twice with no import link.

---

### P4 — `training_constants.py` not wired in 🟠

**File:** `training_constants.py`  
**Problem:** `EXERCISES`, `ALL_EXERCISES`, `MOVEMENT_TYPES`, `VELOCITY_OPTIONS` are defined but nothing in the active codebase imports them. The file appears to be the intended catalogue for the training UI, but `views/training.py` reads exercise data from `training_plan.py` directly.  
**Risk:** If training UI ever needs to validate an exercise name or offer a dropdown, developers may re-define the list inline again rather than finding this file.

---

### P5 — `patient_profile.py` not imported by any module 🟠

**File:** `patient_profile.py`  
**Problem:** `PROFILE` dict (MRI findings, biomechanical assessment) is defined but not imported by any active module. The `training_plan.py` docstring says "Biomechanical profile integrated (from patient_profile.py)" but the module does not `import patient_profile` — it embeds the data inline via the shared exercise objects.  
**Risk:** Updating `patient_profile.py` does not affect any running code. It is currently a human-readable reference file only, not a live code dependency.  
**Note:** `init_db.py` seeds similar but more verbose data; `init_notion.py` seeds diagnostic profile. None reference `patient_profile.py`.

---

### P6 — `patient_profile.py` hardcodes `current_stage = 1` 🟡

**File:** `patient_profile.py`, `PROFILE["current_stage"]`  
**Problem:** `current_stage = 1` is hardcoded. The live stage value comes from `db.get_current_stage()` which reads Notion. These are separate values. Since nothing imports `patient_profile.py`, this causes no runtime bug today, but could mislead if the file is wired in later.

---

### P7 — `ai.py` redundant inline import 🟡

**File:** `ai.py`, `analyze_macro_trends()` body  
**Problem:** `import stats as _s` appears inside the function body, but `stats` is already imported at module level as `_stats`. The inline import shadows the module-level alias within the function scope.  
**Impact:** Harmless (Python deduplicates the import), but confusing. The function should use `_stats` consistently.

---

### P8 — `MIN_DAYS=7` vs `MIN_OBSERVATION_DAYS=14` naming confusion 🟡

**File:** `engine.py`  
**Problem:** `traffic_light()` uses a local constant `MIN_DAYS = 7` (minimum observations for traffic light to produce a colour). The module-level `MIN_OBSERVATION_DAYS = 14` governs the observation lock in `volume_recommendation()`. Both are correct values but the similar names and different scopes create a readability trap.

---

### P9 — `_SLEEP_NEED_HOURS = 8.0` magic constant in `app.py` 🟡

**File:** `app.py`  
**Problem:** Sleep fallback `8.0` is defined inline. `readiness.py` computes a personal sleep baseline (falling back to 8.0 there too via a similar sentinel), but the two are independent constants. If the default sleep need is adjusted, both files must be updated.

---

### P10 — `init_db.py` + `schema.sql` orphaned 🟠

**Files:** `init_db.py`, `schema.sql`  
**Problem:** The app backend is Notion. SQLite is not used at runtime. These files are not in any module's import chain. They contain useful schema documentation and migration patterns, but running them would create a `health_engine.db` file that the app never reads.  
**Risk:** Low (orphaned, not harmful), but adds confusion about which backend is active.

---

### P11 — `requirements.txt` has unused dep + missing transitive deps 🟠

**File:** `requirements.txt`  
**Problems:**  
1. `streamlit-aggrid>=1.2.0` listed — `resume.md` notes "AG Grid not in active use" and no import of `st_aggrid` appears in any source file.  
2. `gspread>=6.0.0` requires `google-auth` and `google-auth-oauthlib` at runtime but these are not explicitly pinned. They install as transitive deps of gspread so the app works, but they are invisible to anyone reading `requirements.txt`.

---

### P12 — Staged git changes uncommitted 🟡

**Status:** `git status` shows:
- Modified: `app.py`, `engine.py`, `training_plan.py` (staged changes)
- Staged deletions: `pages/0_Training_Plan.py`, `pages/3_Autoregulation.py`, `pages/4_AI_Insights.py`, `pages/6_Sync.py`
- Untracked: `Training plan/`, `Oura_template.jpg`

All active code lives in `_pages/` (stubs). The `pages/` deletions are staged but not yet committed. The `Training plan/` docs directory is untracked.

---

### P13 — `resume.md` architecture table outdated 🟡

**File:** `resume.md`, table under "CURRENT APPLICATION STRUCTURE"  
**Problem:** Table references `pages/0_Training_Plan.py`, `pages/3_Autoregulation.py`, etc. Actual layout is `_pages/*.py` (stubs) + `views/*.py` (rendering). Bucket 11 status shows "IN PROGRESS 🔄 (agent running)" — stale.

---

### P14 — `secrets.toml` contains real credentials 🔴

**File:** `.streamlit/secrets.toml`  
**Status:** Gitignored ✅ — confirmed NOT in git history.  
**Risk:** File contains Notion API key (`ntn_[REDACTED]...`), 4 Notion DB UUIDs, Google Sheets ID, and a full GCP service account private key (RSA). If this file is ever accidentally staged (e.g. `git add .`), all credentials will be committed in plaintext.  
**Recommendation (Phase 2, out-of-scope for refiling):** Rotate credentials if `.streamlit/secrets.toml` has ever been shared. Ensure `.gitignore` entry is preserved in any future reorg. No change needed for Phase 3 refiling — this is flagged for awareness only.

---

## Summary counts

| Category | Count |
|----------|-------|
| Source modules (root) | 14 |
| View modules (`views/`) | 5 |
| Page stubs (`_pages/`) | 6 |
| Setup / CLI scripts | 3 |
| Test files | 1 |
| Config / secrets | 1 |
| Documentation | 4 |
| **Total files inventoried** | **34** |

| Confidence | Count |
|-----------|-------|
| 🟢 Fully read, well-understood | 26 |
| 🟠 Partial read or orphaned/stale | 8 |
| 🔴 Requires immediate attention | 2 |

| Problem severity | Count |
|----------------|-------|
| 🔴 Bug / data-loss risk | 2 (P1, P14) |
| 🟠 Silent drift risk | 6 (P2, P3, P4, P5, P10, P11) |
| 🟡 Quality / clarity | 6 (P6, P7, P8, P9, P12, P13) |

---

*End of Phase 1 inventory. Awaiting go-ahead for Phase 2 (target directory tree proposal).*
