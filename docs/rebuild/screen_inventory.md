# Screen inventory — rebuild Phase 2 (2026-10-19)

Every feature of the Streamlit health app, what sits behind it, what the view computes itself, what it writes, and a proposal: **KEEP** (same screen in the new app), **MOVE** (another screen, for example Settings › Data) or **DROP** (only with the owner's approval). Three read-only walks of the code made it on 2026-10-19: Home (`app.py`), Training (`views/training.py`), and Insights, Check-in and the shell (`views/insights.py`, `views/checkin.py`, `nav.py`, `styles.py`). Row ids: **H** = Home, **T** = Training, **I** = Insights, Check-in and the shell.

The owner wants the whole app transformed now and will remove parts himself once the new app runs (2026-10-19), so almost everything is KEEP. **DROP is proposed only for code that is dead, unreachable or a placeholder.** No safety or training rule is proposed for DROP.

**Status: decided by the owner on 2026-10-19** (*"Keep the cardio coming soon as I do want to add this at some point but for now the rest can be dropped. Yes. Yes fix the faults. Yes to all"*): 13 drops approved and the Cardio placeholder kept; every move approved; every fault fixed in the move, and F1 and F3 in the live app now as well; the scale and InBody readings get Supabase tables. The decisions are in the "Decision" column of D1-D3.

---

## D1. DROP proposals — dead, unreachable or a placeholder

| Id | Screen | Feature | Why it can go | Decision |
|---|---|---|---|---|
| H3 | Shell | "Rebuilt the local read cache" toast | Cannot appear: the notice is set only when Supabase is not the record (repo.py:74-79). | **DROP** — approved 2026-10-19 |
| H59 | Home | Durable Home snapshot (`services/home_snapshot.py`) | Never called by the app; the phone's own offline cache replaces it. Keep its one rule: show today's stored values only once readiness and sleep are both scored, with the "as of" time. | **DROP** — approved 2026-10-19 |
| H60 | Home | `_wake_adjustment_sources` reader | Defined, never called. The API still returns which wake correction applied. | **DROP** — approved 2026-10-19 |
| T3 | Training | "Your last save is in Notion, but its copy in Supabase did not send" warning | Cannot appear with Supabase as the record: a failed write raises and the save says "press Save again". | **DROP** — approved 2026-10-19 |
| T15 | Training | Block B → 12-week block changeover | Ran on 2026-10-16 (stored and verified); it does nothing once phase 5 is stored. | **DROP** — approved 2026-10-19 |
| T49 | Training | "Your plan starts in n day(s)" screen | Unreachable: an active phase always covers today. | **DROP** — approved 2026-10-19 |
| I4 | Insights › BioAge | Cardio card and its "coming soon" detail | A placeholder with no metric behind it. | **KEEP** — the owner, 2026-10-19: "Keep the cardio coming soon as I do want to add this at some point" |
| I14 | Insights › Strength | "View All ›" | Plain text that does nothing; the list below already shows everything. | **DROP** — approved 2026-10-19 |
| I25 | Insights › Metabolism | "+ Foryond weigh-in" and "+ Tape baseline" | Disabled buttons with no write path. | **DROP** — approved 2026-10-19 |
| I80 | Insights › Sync | "Supabase mirror failing" warning | Cannot show: the mirror ended when Supabase became the record. | **DROP** — approved 2026-10-19 |
| I81 | Insights › Sync | Sheet1 raw table | Cannot show: Sheets is a frozen archive. | **DROP** — approved 2026-10-19 |
| I113 | Check-in | "Its copy in Supabase did not send" warning | Cannot fire with Supabase as the record; the text also names Notion. | **DROP** — approved 2026-10-19 |
| I119 | Shell | Unused desktop/phone component kit in `styles.py` | Nothing in the repo calls any of it. | **DROP** — approved 2026-10-19 |
| I121 | Shell | Same-tab chart-link script | Streamlit-only workaround; the phone app has real taps. | **DROP** — approved 2026-10-19 |

## D2. MOVE proposals

| Id | From | Feature | Proposed new place | Decision |
|---|---|---|---|---|
| H2 | Shell | Offline-datastore banner | App-wide status in the shell (the engine reports its mode and the copy's age) | **MOVE** — approved 2026-10-19 |
| H57 | Home | Device sync at the foot of Home | The engine, run at the first open of the day on any screen, retried at most hourly while last night is missing (the owner's rule of 2026-10-19), with the screen updated when it ends | **MOVE** — approved 2026-10-19 |
| T5 | Training | Weekly rollup sync on open | The engine (same chain) | **MOVE** — approved 2026-10-19 |
| T6 | Training | Garmin daily sync on open | The engine (same chain) | **MOVE** — approved 2026-10-19 |
| T29 | Training | Plan start setup (first run; "Begin 14-Day Plan") | Settings / first run, without the Stage 1 wording | **MOVE** — approved 2026-10-19 |
| I62–I63 | Insights | Processing Queue (pending counts, "Process All") | Run on save in the engine; counts on Settings › Data | **MOVE** — approved 2026-10-19 |
| I78 | Insights › Sleep Architecture | Sleep-fusion shadow report | Settings › Data (an engineering check, not a daily reading) | **MOVE** — approved 2026-10-19 |
| I79, I82–I93 | Insights › Sync | Store caption, Engine View, Blend history and backfill, Metrics History, session checks, auto-sync caption, Garmin / Sleep Fusion / Oura sync buttons | Settings › Data (captions corrected: Garmin daily runs every 2 h, Oura needs the OAuth login) | **MOVE** — approved 2026-10-19 |

## D3. Faults found — the proposal is to fix each in the move into `services/`, so the new app has it right

The owner decided on 2026-10-19 that the live Streamlit app gets no more fixes. The new app reads the moved services, so a fault fixed in the move is fixed there. **Where a fault touches a training or safety rule, the live app can also get the fix: the owner decides.**

| Id | Where | Fault | Effect | Decision |
|---|---|---|---|---|
| F1 | T32 (live fix done 2026-10-19) | **The readiness auto-shift has not run since 2026-08-23.** It reads `_rm_bio`, which commit e43f59e removed; the error is caught and ignored (training.py L3655, L3694-3695). | No "Readiness suggests moving today's session" proposal has been shown or written for two months. Tests only check the source text. | **Fix in the move, and in the live app now** — approved 2026-10-19 |
| F2 | T22, T30, T32 | The three `date_overrides` writers merge every shift reason, even for moves `reject_violating_overrides` refused; the rejection warning disappears on the rerun. | The day banner can say "Session moved" for a day that did not move. | **Fix in the move** — approved 2026-10-19 |
| F3 | I96, I112 (live fix done 2026-10-19) | A second check-in the same day cannot set a field back to its default (the form's defaults double as "not filled in"). | Pain cannot be corrected from, say, 4 back to 0, and the pain gate (above 5 blocks a weight step) keeps reading the old value. | **Fix in the move, and in the live app now** — approved 2026-10-19 |
| F4 | I53 | Insights › Engine Data calls `load_policy(rec, {})` without the readiness signal Home passes. | On a day only readiness asks for less, Home says REDUCED LOAD and Engine Data says NO CHANGE TO LOAD. | **Fix in the move** — approved 2026-10-19 |
| F5 | H47 | The wake-time stepper writes a manual value, but on a fused night the fusion figure wins; the caption credits Oura's pattern. | On fused nights the − / + buttons change nothing. | **Fix in the move** — approved 2026-10-19 |
| F6 | H26–H27 | The Readiness drill-down's contributors use the 60-day raw score; today's card uses the 14-day one. | On today the card and its breakdown can disagree. | **Fix in the move** — approved 2026-10-19 |
| F7 | H16 | A failed stage read becomes stage 1. | It changes the strain number (STAGE_CLF) and can print "Stage 1 ceiling" (rebuild rule 9 bans Stage 1 text). | **Fix in the move** — approved 2026-10-19 |
| F8 | H16, H54 | Read windows and the rest-day 7-day strain count back from the server's today, not the day shown. | Older days can show "not scored" and blame the ring; a past day's card can differ from its own point on the 30-day trend. | **Fix in the move** — approved 2026-10-19 |
| F9 | Home caches | No cached read is keyed by date. | Up to 30 minutes after midnight the windows still end yesterday. | **Fix in the move** — approved 2026-10-19 |
| F10 | I43, I48 | Flexibility prints "of 4 slots" and "N slots not measured" with 4 typed in; the battery has 3. | A full run says "3 of 4 slots run" and claims a slot was skipped. | **Fix in the move** — approved 2026-10-19 |
| F11 | I21, I24 | Metabolism colours every rise amber and every fall green, and shows "Normal" on every derived value. | Wrong for fat-free mass and phase angle (up is good); "Normal" is not a check. | **Fix in the move** — approved 2026-10-19 |
| F12 | I75 | Sleep Architecture's "Oura only" count includes watch-only nights. | The count is too high. | **Fix in the move** — approved 2026-10-19 |
| F13 | I27–I40 | A flexibility assessment in progress lives only in the local `.sync_state.json`. | A hosted restart loses an unfinished assessment. | **Fix in the move** — approved 2026-10-19 |
| F14 | I90 | "Sync Garmin Activities" is the only writer of `garmin_activities`, and nothing runs it automatically. | The HR-max estimate behind session heart rate goes stale unless the button is pressed. | **Fix in the move** — approved 2026-10-19 |
| F15 | I7, I16–I17 | Metabolism reads `Input_files/Fitdays.csv` (a local, git-ignored file) and hard-coded InBody scans. | On a server, and so through the API, the screen is empty: the readings need a store. | **Fix: the scale and InBody readings get Supabase tables** — approved 2026-10-19 |
| F16 | T94 | The "Estimated AU" caption always uses RPE 5. | The preview does not follow the slider. | **Fix in the move** — approved 2026-10-19 |
| F17 | T84 | The activity timer has no staleness guard and its key is the same every day. | A timer left running on an earlier day shows DONE at once. | **Fix in the move** — approved 2026-10-19 |
| F18 | T103 | The "+" menu is drawn during a session; only the accessory start is guarded. | Yoga and Hike can be opened mid-session. | **Fix in the move** — approved 2026-10-19 |
| F19 | T75 | Garmin-verified walk minutes and the heart-rate panel are not checkpointed. | After a dropped connection the walk logs its planned minutes. | **Fix in the move** — approved 2026-10-19 |
| F20 | T40, T90 | The overview, the duration estimate, "Planned Reps" and the review's Weight show plan values, while the flow uses the readiness-dosed values. | Small mismatches on a reduced-load day. | **Fix in the move** — approved 2026-10-19 |
| F21 | Text | Out-of-date text: "not Google Sheets" (H2), "Garmin once a day" (I87–I88), "Add OURA_TOKEN" (I92), "14-Day Plan" (T29), Notion in docstrings and warnings (T3, T110, I113). | Misleading captions. | **Fix in the move** — approved 2026-10-19 |

---

## Home (`app.py`) — 61 rows

| Id | Feature | What the owner sees or does | services/ or Repository calls | Computation inside app.py | Writes | Proposal |
|---|---|---|---|---|---|---|
| H1 | Shell: page layout | Dark phone-width column (480 px), fixed date bar and bottom bar; Streamlit chrome hidden | nav.CHROME_CSS, styles.inject_css | CSS only (40-48, 2377-2395, 2504-2508) | — | KEEP (becomes the phone shell; the CSS is not ported) |
| H2 | Shell: offline-datastore banner | "Offline — reading the local datastore…" on every page | Repository.offline, datastore_built_at | Shown when offline; "unknown" with no build time (74-81) | — | MOVE (app-wide status; "not Google Sheets" is out of date) |
| H3 | Shell: cache-rebuilt toast | "Rebuilt the local read cache from Supabase" once per process | ensure_local_cache; repo.pop_cache_hydration_notice | 68-72 | (the rebuild writes datastore.db) | DROP (cannot appear in production) |
| H4 | Shell: page router | Home by default; Training, Insights, Check-in from nav state or ?page=; an unknown page → Home | views.*.render; nav.start_run, nav.inject | 87-93, 119-120, 149-169 | ?page | KEEP (carry over: a failing screen keeps its nav; unknown route → Home) |
| H5 | Shell: bottom nav | Home · Training · Insights, Home highlighted | nav.inject("home") | Drawn after the whole Home body (2608); a Home error leaves no nav | _nav_page | KEEP (without that gap) |
| H6 | Header: date label | "TODAY" or the date; drill-down titles with the date on the right | — | 371-372, 2303-2321, 2354-2362 | — | KEEP |
| H7 | Header: day Home opens on | Opens on today; a picked past day survives only a same-day reconnect; an old ?d= opens on today | dashboard.home_date_on_open, home_date_params | 190-206 | _home_date_opened; URL d/ds | KEEP (open on the device's today) |
| H8 | Header: day arrows ‹ › | Step one day; › disabled on today | dashboard.home_date_params | 373-375, 2349-2352, 227-256 | URL d/ds | KEEP |
| H9 | Drill-down back ← and ‹ › | ← back to the cards; ‹ › change the night | dashboard.home_date_params | 2330-2331, 2343-2347 | URL view/pt/rw/d/ds | KEEP |
| H10 | "Back to today" pill | Under the bar whenever a past day is shown | dashboard.home_date_params | 2512-2516 | URL d/ds/pt | KEEP |
| H11 | Check-in FAB (+) | White round + opens Morning Check-in | — | 2372-2373, 2510-2511 | _nav_page | KEEP |
| H12 | Readiness card, DAILY and TREND | Arc 0-100, DAILY and TREND (or "--"), band word at 85/70/50; "No Readings" with no score | today.today_readiness_raw; readiness.compute_readiness, compute_readiness_trend; dashboard.readiness_meta | DAILY window: 14-day rows on today, 60-day on a past day (2432-2441); arc follows DAILY else TREND (2444-2445); arc fill (698-725) | — | KEEP (move the window choice into services) |
| H13 | Readiness badge | VOLUME HELD / REDUCED LOAD / REST ADVISED, today only | today.today_verdict → verdict.today_verdict → sessions.load_policy | 2470-2476, 2482-2483 | — | KEEP (training/safety rule) |
| H14 | Verdict line under the card | The reading the engine named, the banner text and the HRV note; today only | today.today_directive, today_readiness_modifier; Verdict.has_something_to_say | Order cause → banner → HRV (862-893, 2566-2573) | — | KEEP (training/safety rule) |
| H15 | HRV downward-run note | One neutral sentence after a 4-night downward run, silent when the light already acted | today.today_hrv_note → hrv_trend.ring_run_advisory | Styling (887-889) | — | KEEP (warning only) |
| H16 | Strain card | Arc 0-21; Light/Moderate/Hard/Strenuous at 8/12/16; "STRAIN · 7D AVG" on a rest day; "No Readings" | dashboard.compute_daily_metrics_snapshot (+ hr_load.blend_strain, …), strain_meta | 7-day figure and step modifier use the server's today (663-674); a failed stage read becomes stage 1 (642-645) | — | KEEP (see F7, F8) |
| H17 | Sleep card | Arc 0-100; bands at 85/70/50; description names the baseline or "target (8 h)" | compute_daily_metrics_snapshot → sleep_score.compute_sleep_score; readiness.sleep_baseline; dashboard.sleep_meta | Sleep need = baseline else 8.0 h (182, 656-661) | — | KEEP |
| H18 | Card tap → drill-down | Tap opens the Readiness, Strain or Sleep detail | dashboard.home_date_params | Invisible button over the card (270-292, 2557-2571) | URL view | KEEP |
| H19 | Card background photos | A fixed photo per card | — | 173-180, 685-694 | — | KEEP (static assets) |
| H20 | Biometric read failed | "Could not load your biometric readings… the read failed, not missing data" | Repository.get_biometric_rolling | 516-532, 2518-2529 | — | KEEP (a failed read never looks like missing data) |
| H21 | Oura not authorised | Red error naming `scripts/authorize_oura.py` | Repository.oura_auth_status | Every render; a failed check counts as authorised (2574-2597) | May copy the token into the local cache | KEEP (the phone needs its own re-authorise path) |
| H22 | "Oura sync unavailable — will retry next visit." | Grey caption | _sync_status_oura from the runner | 2598-2599; read at the top of the run, so one run late (513) | — | KEEP (one status line; reword for the hourly retry) |
| H23 | "Garmin sync unavailable — will retry next visit." | Grey caption | _sync_status_garmin | 514, 2600-2601 | — | KEEP |
| H24 | "Device sync failed to run — will retry next visit." | Grey caption when the chain raised | runner.last_error() | 2602-2607 | — | KEEP |
| H25 | Readiness drill-down masthead | "READINESS · date", number, band | dashboard.readiness_meta | 2120-2123, 2015-2039 | — | KEEP |
| H26 | Readiness contributors | Nine rows: raw value or "not scored", weight %, coloured bar; unscored rows dimmed | readiness.readiness_breakdown (60-day rows), dashboard.readiness_breakdown_rows | 1041-1071, 1145-1157 | — | KEEP (see F6) |
| H27 | Contributors caption | Trend vs last night, "Scored on X of 9…", alcohol not deducted | verdict.readiness_scale_caption, dashboard.readiness_coverage_caption, readiness_alcohol_caption | 1158-1170 (compares TREND with the 60-day raw score) | — | KEEP |
| H28 | Reason when not scored | Read failed / night not through yet / no readings | dashboard.readiness_unscored_reason | 527-532, 589-604, 1151-1156 | — | KEEP |
| H29 | Readiness key metrics 2×2 | RHR, HRV, body temperature (signed °C), respiratory rate; "—" when missing | get_sleep_night_details + the day's row | Fields, units, formatting (1173-1191) | — | KEEP (move into services like sleep_key_metrics) |
| H30 | Overnight HR and HRV panels | Lowest HR with average; average HRV with max; line over the night with an average line | dashboard.overnight_series, value_axis, overnight_axis_labels; styles.overnight_chart_svg | 1603-1610, 2132-2142, 1674-1681, 1662-1672 | — | KEEP |
| H31 | Overnight point tap | Time, reading, difference from average, night's low and high | dashboard.hit_bands, overnight_point_detail | 1652-1661, 1688-1703 | URL pt (reload) | KEEP |
| H32 | Sleep masthead "· ADJUSTED" | Shown when the night has a wake correction | dashboard.sleep_meta; get_effective_wake_adjustments | 2144-2147 | — | KEEP (say which correction applied) |
| H33 | Sleep contributors | Seven rows with raw values; "Scored on X of 7…"; wake-correction note | sleep_score.sleep_score_breakdown, dashboard.sleep_breakdown_rows, sleep_coverage_caption | 1074-1097, 1122-1134 | — | KEEP |
| H34 | Sleep reason when not scored | Read failed / not through yet / no sleep period; "Tap ‹ to see an earlier night." | dashboard.sleep_unscored_reason | 1106-1118 | — | KEEP |
| H35 | Sleep all-or-nothing rule | No score → no night panels and no wake stepper | sleep_score.sleep_score_breakdown | 1094-1097, 1524-1540, 2545-2549 | — | KEEP (rebuild rule 9) |
| H36 | Watch-only night | "Time asleep" panel: no Sleep Score, ring not worn; the watch's stages still shown | get_sleep_fusion_history | Stage minutes and % (1476-1504) | — | KEEP (move the arithmetic) |
| H37 | Night detail failed to load | "Could not load this night's detail — try again shortly." | get_sleep_night_details | 1545-1557 | — | KEEP |
| H38 | Fused key metrics and caption | Total sleep, time in bed, efficiency, RHR; "Fused with Garmin: N min…" | dashboard.sleep_night_figures, sleep_key_metrics, sleep_fusion_caption | 1559-1572 | — | KEEP |
| H39 | Sleep debt | Hours, band, four-segment bar, "Rest is triggered at 9.5 h." | readiness.sleep_debt_hours, dashboard.sleep_debt_display | 1219-1240, 1574-1576 | — | KEEP (training rule) |
| H40 | Time asleep | Total, time in bed, hypnogram, stage rows with duration and % | dashboard.format_duration, sleep_stage_legend, sleep_stage_minutes | 1578-1599 | — | KEEP |
| H41 | Hypnogram and source line | Four-row strip on a clock axis; source Fused / Oura / Garmin; notes and caveats | get_sleep_fusion_history, get_sleep_night_details; dashboard.minutes_between, clock_axis_labels; styles.hypnogram_svg | 1286-1338, 1340-1355 | — | KEEP |
| H42 | Movement strip | Strip on the same axis with source, caption and position shifts | fusion row; styles.movement_svg, movement_legend_html | 1434-1473 | — | KEEP |
| H43 | Strip point tap | Stage or movement class, from–to, duration, night total, share | dashboard.hit_bands, run_at, segment_point_detail | 1396-1431, 1373-1393 | URL pt (reload) | KEEP |
| H44 | Day total (naps) | Day total, night plus naps, one row per nap | dashboard.sleep_naps_display | 1243-1270 | — | KEEP |
| H45 | Vitals while asleep | Average/lowest HR, HRV, respiration, SpO2, breathing disturbance, temperature | dashboard.sleep_vitals_rows; get_oura_daily_sleep_context | 1612-1614 | — | KEEP |
| H46 | "⚡ N nights wake-time adjusted" | Count under the 30-day Sleep Score trend | get_effective_wake_adjustments | 2207-2218 | — | KEEP |
| H47 | Wake-time − / + stepper | 5-minute steps 0-120; "−N min" or "No adjustment"; caption; scored nights only | dashboard.step_wake_time_adjustment; set_wake_time_adjustment | Effective value (2260); buttons, cache clear, rerun (2267-2293) | wake-time adjustment row; clears every cache | KEEP (Key Rule 4's one manual correction; fix F5 first) |
| H48 | Strain masthead | "STRAIN · 7D AVG" or the date; value and band | dashboard.strain_meta | 2153-2155 | — | KEEP |
| H49 | Strain split by body area | Load share bar, upper/core/lower rows with strain, AU, %, ACWR and reason, faceplates; "They total X against Y"; advisory caption with the stage ceiling | get_daily_region_au(31), get_phases; plan.current_stage_start; strain_regions.region_acwr; dashboard.compute_region_strain_snapshot | Heading, fills, gap, caveat, unmapped list, ceiling lookup (1795-2012) | — | KEEP (advisory rule; move the texts and the ceiling into services). The unmapped list is off both apps' screens since 2026-10-20 (the owner: it "doesn't give me any details about strain") |
| H50 | Strain split empty states | No session / no split / not in the region map | dashboard.compute_region_strain_snapshot | 1934-1957 | — | KEEP |
| H51 | Rest-day week toggle | "Show the week's shape" / "Hide the week"; week note; title "— last 7 days" | strain_regions.rolling_prior_region_row | 2170-2181, 1901-1919, 1973-1984, 2000 | URL rw | KEEP |
| H52 | Strain source | ● Garmin HR / ● HR + RPE / ○ RPE only; Edwards' load, HR, HRmax, TRIMP, zones; blend line (since 2026-10-20 in plain words, the owner: "a better title and more user friendly": strain_screen.SOURCE_WORDS, each zone with its heart rates, no TRIMP) | hr_load.blend_strain, SOURCE_LABELS; get_session_hr_history | 1706-1754 | — | KEEP |
| H53 | 7-day HRV and RHR charts | Latest value and seven weekday points; tap for change, average and range | dashboard.fill_7day, value_axis, hit_bands, x_axis_labels, trend_point_detail | 647-652, 680-681, 2062-2078, 2197-2200 | URL pt (reload) | KEEP |
| H54 | 30-day trend in every drill-down | Readiness / Sleep / Strain trend; tap a day for value, change, average, range, other metrics, "Open {date} →" | get_metrics_history; dashboard.value_axis, hit_bands, x_axis_labels, trend_point_detail, metrics_history_rows | 2203-2205, 2092-2095, 2116-2126, 2148-2150, 2188-2194, 2097-2104 | URL pt (reload) | KEEP (plots stored values; see F8) |
| H55 | Chart point panel controls | ✕ closes; "Open {date} →" moves the drill-down | dashboard.point_selection_key, parse_point_selection; styles.chart_hits, enable_chart_links | 743-807, 2542-2544 | URL (full page load) | KEEP (behaviour; the links are Streamlit-only) |
| H56 | Empty-chart message | "No historical readings available for this period." | — | 772-775, 828-829 | — | KEEP |
| H57 | Device sync at the foot of Home | Nothing visible apart from H22-H24 | BackgroundSyncRunner.run_now/start/results; Repository.run_home_syncs | Runs only if Home reaches its last line; inline when today is not settled, else a worker (2611-2690) | see the write list | MOVE (to the engine, the owner's rule) |
| H58 | Re-read of stale biometric rows | Stops "No Readings" above a night the drill-down draws | dashboard.has_night_without_biometric_row | 573-604 | _bio_rolling.clear() | KEEP the outcome (a fresh API read makes the re-read unnecessary) |
| H59 | Durable Home snapshot | Never shown | services/home_snapshot.py; get/save/invalidate_home_snapshot | Never called (`git log -S` finds no caller) | — | DROP (dead code; keep its one rule) |
| H60 | `_wake_adjustment_sources` | Never called | get_effective_wake_adjustments | 450-457 | — | DROP (dead function) |
| H61 | Training summary on Home | Not on Home (the badge, verdict, strain card and drill-down carry training) | — | — | — | Nothing to inventory |

## Training (`views/training.py`) — 114 rows

### Page shell and background work
| Id | Feature | What the owner sees or does | services/ or Repository calls | Computation inside the view | Writes | Proposal |
|---|---|---|---|---|---|---|
| T1 | Page styling | White pill buttons, centred column, fixed action bar and "+" | — | CSS L1501-1513, L2496-2530, L2685-2762 | — | KEEP (restyle natively) |
| T2 | Audio unlock and notification permission | First tap unlocks sound; the browser may ask for notifications | — | `_audio_unlock_component` L222-284 | browser globals | KEEP |
| T3 | Supabase copy warning | "Your last save is in Notion, but its copy in Supabase did not send…" | send_mirror_now | L1147-1154 | session_state | DROP (cannot appear with Supabase as the record) |
| T4 | Phases unreadable | "Couldn't read your training phases…"; page stops, yoga still works | get_phases → PhasesCorruptError | L3387-3398 | — | KEEP |
| T5 | Weekly rollup sync on open | "Weekly rollup sync unavailable — showing live data only." | metrics.sync_weekly_rollup | 30-min throttle L1565-1575; caption L3774-3775 | weekly rollup rows | MOVE (engine) |
| T6 | Garmin daily sync on open | "Garmin daily sync unavailable — will retry next visit." | exclusive(timeout=0), sync_garmin_daily_if_due | L1578-1603, L3776-3777 | Garmin daily rows | MOVE (engine) |
| T7 | Navigation | Bottom nav; "Back to Home" buttons | nav.inject | L3885-3887, L4246-4248 | _nav_page | KEEP |

### Weekly banners and the failed-week rule
| Id | Feature | What the owner sees or does | services/ or Repository calls | Computation inside the view | Writes | Proposal |
|---|---|---|---|---|---|---|
| T8 | Weekly rollup banner | STREAK; "THIS WEEK: x/y SESSIONS" with a tier line; "n perfect · m ultimate" | metrics_logic.compute_week_history, compute_streak, current_streak_is_all_ultimate; get_logged_session_dates | `_current_week_tier` re-codes the score_week thresholds (L1711-1727); `_streak_label` L1703-1708 | — | KEEP |
| T9 | "Last week:" line | Every day; a failed week's line on Monday only | week_repeat.last_week_line_is_due | L1762-1774, L1687-1700 | — | KEEP |
| T10 | Past-week badge | "Week of {date}: {verdict}" | — | L1930-1950 | — | KEEP |
| T11 | Repeat-week notice (Monday) | "Last week had n of 7 days logged, so it failed…" | repeat_notice_is_due, repeat_notice | L1875-1883 | — | KEEP |
| T12 | Redo this week (Monday after 0-2 days) | Two-step confirm with what moves | redo_is_offered, redo_this_week, consequences; get_phases_live, set_phases | L1884-1927 (the re-check reads cached dates, not _live) | phases | KEEP |
| T13 | Failed-week load hold | Numbers start at the last session; "nothing goes up this week"; "held at 100%" | week_repeat.failed_week_holds_load, sessions.hold_for_failed_week | Folded into the policy L3428-3432 | — | KEEP |
| T14 | Failed-week rule (automatic) | Nothing to press; the page shows the repeated week | apply_failed_week_rule; get_phases_live, get_logged_session_dates_live, set_phases | L3492-3514 | phases | KEEP (rule; the trigger moves to the engine) |
| T15 | Block changeover | Nothing to press; ran once | block_changeover.due; get_phases_live, set_phases | L3456-3474 | phases | DROP (ran 2026-10-16; does nothing now) |

### Week strip and day views
| Id | Feature | What the owner sees or does | services/ or Repository calls | Computation inside the view | Writes | Proposal |
|---|---|---|---|---|---|---|
| T16 | Week strip | ✓ done, ● today, ○ missed, ● planned, ○ rest; tap a day | plan.get_week_view; get_logged_session_dates | L1667-1676, L2015-2063 | tp_selected_date | KEEP |
| T17 | Week toggle and "Today" | ‹ › one week within the block; "Today" when elsewhere | plan.clamp_week_start, phase_week_bounds | L1981-2069 | tp_week_start | KEEP |
| T18 | Schedule note banner | "Session moved — {reason}" or the plain note | scheduling.shift_note | L1964-1973 | — | KEEP (see F2) |
| T19 | Day-detail router | Another day opens its rest, done, missed or future view | has_logged_session; sessions.day_view_state, is_planned_rest, calendar_plan | L2448-2450 | — | KEEP |
| T20 | Past completed day | "SESSION LOGGED", RPE · min · AU, exercises | get_recent_sessions | L2176-2180 | — | KEEP |
| T21 | Past missed day | "NOT COMPLETED", planned content | calendar_plan, prescription_label | L2217-2239 | — | KEEP |
| T22 | Manual swap | "Swap with today's session" / "Do this session today", blockers, warnings | manual_swap_blockers/warnings/entries; reject_violating_overrides; set_phases | L2261-2315 | phases | KEEP (see F2) |
| T23 | Future day preview | Objective, RPE target, date, exercises, at-home items, swap offer | calendar_plan | L2318-2351 | — | KEEP |
| T24 | Rest day | "Rest day."; optional yoga; "To train anyway, open any other day…" | yoga.suggest_for_day | L2354-2379 | tp_yoga_* | KEEP |
| T25 | Forced or planned rest today | Rest screen, never an empty Start | is_planned_rest, calendar_plan | L3797-3807 | — | KEEP |
| T26 | Reassessment gap | "Reassessment — no phase active"; next block and when it starts | — | L2389-2401 | — | KEEP |
| T27 | Stranded-days warning | "{block} ended before its last days were reached…" | plan.stranded_override_days, phase_end_date | L2422-2437 | — | KEEP |
| T28 | "Begin next block" offer | Removed 2026-08-18; blocks start by date | — | — | — | Nothing to port |
| T29 | Plan start setup (first run) | "Set Your Plan Start Date", "Begin 14-Day Plan" | set_config("plan_start_date"), seed_default_phase, set_phases | L3727-3754 | config, phases | MOVE (Settings / first run; Stage 1 wording) |

### Scheduling prompts (ask-first)
| Id | Feature | What the owner sees or does | services/ or Repository calls | Computation inside the view | Writes | Proposal |
|---|---|---|---|---|---|---|
| T30 | Missed-session carry | "Missed session — proposed reschedule…"; "Apply reschedule" / "Leave as missed" | missed_reschedules, has_real_move, declined_entries; reject_violating_overrides; set_phases | L3530-3622 | phases | KEEP (see F2) |
| T31 | Missed-session carry, in order (12-week block) | "The sessions run in order, so the rest move along…"; "Run in order" / "Keep as planned" | runs_in_order, in_order_reschedules, in_order_summary | L3539-3545, L3589-3596 | phases | KEEP |
| T32 | Readiness auto-shift | Should show "Readiness suggests moving today's session…" | should_evaluate_shift, should_shift_session, swap_pairs_for_shift, … | L3637-3697 — broken since 2026-08-23 | phases (never reached) | KEEP (fix F1) |

### Gate 1 and the flexibility retest
| Id | Feature | What the owner sees or does | services/ or Repository calls | Computation inside the view | Writes | Proposal |
|---|---|---|---|---|---|---|
| T33 | Gate-1 reason prompt | "The week of {date} ran n of 3 core sessions. What was the reason?" | gate1.applies, read_reasons, week_mondays, core_sessions_done, count, with_reason | L1795-1821 | config gate1_week_reasons | KEEP |
| T34 | Gate-1 card | "Gate 1 — the first run · r of 6 weeks · m of 4 lifts" | gate1.strength_rows, lift_weights; get_recent_session_sets | L1822-1838 | — | KEEP |
| T35 | Gate-1 flare-up | "A session this week was shortened or changed because of the hips or back" → confirm | with_reason(REASON_FLARE); set_config | L1839-1855 | config | KEEP |
| T36 | Flexibility retest banner | Tomorrow / due / due-but | get_flexibility_assessments, get_recent_sessions(3); flexibility.retest_readiness | L3707-3720 | — | KEEP |

### Today's overview (before Start)
| Id | Feature | What the owner sees or does | services/ or Repository calls | Computation inside the view | Writes | Proposal |
|---|---|---|---|---|---|---|
| T37 | Load verdict banner | Red rest / amber reduced / blue injury cap / blue no reading; ACWR advisory caption | today.today_verdict, today_directive | L2550-2572, L3894-3895 | — | KEEP |
| T38 | Coach header | Date, headline, subtitle | sessions.coach_message | L2589-2600 | — | KEEP |
| T39 | Workout card | Block, DAY n, minutes, RPE target, focus, "n of N sessions" bar | estimate_duration, focus_areas | L2074-2115 (the bar counts rest days as sessions) | — | KEEP |
| T40 | Release / Workout lists | Two expanders with prescriptions | split_release_and_main, prescription_label | L2125-2144, L2604-2611 (plan values, not dosed) | — | KEEP (see F20) |
| T41 | At home today | Name, prescription, how-to; not logged | prescription_label | L2147-2162 | — | KEEP |
| T42 | Garmin pre-start prompt | "Start a workout on your Garmin now…" + checkbox | — | L2629-2645 | session_state | KEEP |
| T43 | First-side note | "Start each of those exercises on the {side} side today." | sessions.first_side_note | L2647-2649 | — | KEEP |
| T44 | Adapt session dialog | "No adaptation today…" / volume held / changed; how it works | load_policy | L2466-2491 | — | KEEP |
| T45 | Start | Starts the guided flow; fixes today's first side | sessions.first_side | L2658-2672 | checkpoint | KEEP |

### In-session chrome
| Id | Feature | What the owner sees or does | services/ or Repository calls | Computation inside the view | Writes | Proposal |
|---|---|---|---|---|---|---|
| T46 | "SESSION ADAPTED" badge | Coloured by the verdict | policy | L4258-4264 | — | KEEP |
| T47 | Status strip | Plan Start / Today / Day n/N; progress bar | get_config_value("plan_start_date") | L3846-3851 (first plan's start) | — | KEEP |
| T48 | Session in progress / Exit | "Navigate freely — your place is saved."; Exit → confirm → Discard | — | L3840-3865, L3903-3928 | clears tp_*; checkpoint | KEEP |
| T49 | Before plan start | "Your plan starts in n day(s)…" | — | L3870-3873 | — | DROP (unreachable) |
| T50 | Plan complete | Balloons, "{N}-Day {name} Complete." | — | L3876-3889 | — | KEEP (safety net) |
| T51 | Day header | "Day n of N", objective, RPE target | — | L3931-3937 | — | KEEP |

### Guided session flow
| Id | Feature | What the owner sees or does | services/ or Repository calls | Computation inside the view | Writes | Proposal |
|---|---|---|---|---|---|---|
| T52 | Guided flow shell | "Today's session k/N", list (✓ / current / next), one exercise per screen | — | L4280, L762-787, L4309-4324 | — | KEEP |
| T53 | Hand-off to the save screen | After the last exercise | — | L4327-4330 | tp_done_today; checkpoint | KEEP |
| T54 | Readiness-scaled dose | Working sets shortened on a low day; warm-up, prep, release, tests at full dose | readiness_dose, readiness_scales, engine.apply_exercise_volume_modifier | L4334-4345, L3433 | — | KEEP |
| T55 | Exercise header and prescription | "Exercise n of N", "sets × reps each side (range a-b) Tempo … rest" | displayed_prescription, prescription_label | L4364-4377 | — | KEEP |
| T56 | Prescription seeding | Today's numbers on the first view of a lift | get_last_performance, get_recent_session_sets, get_recent_readiness(1); resolve_prescription | L1351-1467 | tp_actuals; checkpoint | KEEP |
| T57 | Ramp set | About 60% of the next lift | ramp_lift_index, ramp_entry | L4340-4349 | tp_actuals | KEEP |
| T58 | Pain gate on a weight step | "The weight is ready to go up, but it stays the same today: …" | todays_check_in, step_block_reason | L1434-1440 | — | KEEP (safety) |
| T59 | Prescription contradiction | "Prescription contradiction — …"; falls back to the last session | PrescriptionContradiction, last_completed_ceiling | L1450-1465 | tp_actuals | KEEP |
| T60 | Previous session box | "Last: … · vs prescribed +2.5 kg" | previous_caption, prescription_delta, delta_direction | L4396-4415 | — | KEEP |
| T61 | Where today's numbers came from | Range aim, held amount, when the weight goes up next | actual_caption; next_step_caption | L4483 | — | KEEP |
| T62 | Mechanics | "MECHANICS" how-to box | — | L4417-4425 | — | KEEP |
| T63 | Safety warning gate | Red warning only when the exercise's body area strain is over 16 | strain_regions.warning_is_due; get_daily_region_au(31) | `_warning_strains` L2824-2848, L4442-4446 | — | KEEP (safety) |
| T64 | Note per exercise | "Add a note for this exercise" | — | L1157-1196, L4453-4470 | tp_notes → the exercise row | KEEP |
| T65 | Reps stepper | − n + | step_reps | L4537-4559 | tp_actuals | KEEP |
| T66 | Weight stepper | "WEIGHT (KG)" or "WEIGHT"; − n + | step_weight_kg | L4587-4619 | tp_actuals | KEEP |
| T67 | Band tier stepper | "BAND" tier | step_band_tier, BAND_TIER_LABELS | L4561-4586 | tp_actuals | KEEP |
| T68 | Second side, "Edit {side} side" | Mirrored or edited second side | ready_side, side_keys, other_side | L4494-4535 | reps_left / weight_kg_left | KEEP |
| T69 | First-side alternation | SIDE RIGHT / LEFT; "✓ {First} Side Done" | first_side, other_side | L4352-4354, L4647-4655, … | tp_side | KEEP |
| T70 | Set, rep and tempo readouts | SET n/N, REP n/N, TEMPO | — | L4668-4682 | — | KEEP |
| T71 | Reps exercise completion | "✓ Set n Complete" | build_set_record, upsert_set_record, set_timestamp | L4752-4785, L1199-1227 | tp_set_log; checkpoint | KEEP |
| T72 | Hold exercise completion | HOLD timer, side swap, "✓ Set n Complete" | hold_ending, is_timed_test | L4800-4853 | tp_set_log | KEEP |
| T73 | Hold-reps completion | "REP n of N — SIDE"; "✓ Rep n Done" | hold_ending | L4856-4913 | tp_set_log | KEEP |
| T74 | Duration exercise | ACTIVITY TIMER, "✓ Activity Complete" | is_run_or_walk; garmin_configured | L4692-4705 | checkpoint | KEEP |
| T75 | Garmin pull for a run or walk | "Start {name} on your Garmin…"; "Pulled n min from Garmin…" | get_recent_garmin_activity_minutes; summarize_garmin_activities | L4695-4729 | tp_garmin_minutes (not checkpointed) | KEEP (see F19) |
| T76 | Plank test (timed hold) | Count-up stopwatch; "Seconds held — {side} side"; done disabled until typed | is_timed_test, timed_hold_entry, build_set_record | L4804-4838 | training_sets.tut / tut_left | KEEP |
| T77 | Rest phase | REST timer, "→ Next Set" (pressed at zero) | — | L1239-1275, L4740-4869 | rest_taken_seconds | KEEP |
| T78 | ← Back (undo) | Undo up to 30 steps | — | L1306-1348, L4922-4929 | checkpoint | KEEP |
| T79 | Skip exercise | "Only skip if pain prevents performance…" | — | L4952-4962 | checkpoint | KEEP |
| T80 | Resume after a drop or reload | Place, numbers, notes and a part-finished save come back; a logged plan day cannot start again | save/get_training_checkpoint_local, set_config("training_progress"), has_logged_session | L790-958 | .sync_state.json; config training_progress | KEEP (the phone keeps the session; the engine keeps the "already logged" lock) |

### Timers and sounds
| Id | Feature | What the owner sees or does | services/ or Repository calls | Computation inside the view | Writes | Proposal |
|---|---|---|---|---|---|---|
| T81 | Hold countdown timer | Start/Pause/Resume/Reset; last 3 s red; ticks; ✓; presses done after 0.7 s; next rep or side starts by itself | hold_ending | `_hold_timer` L310-479 | localStorage | KEEP |
| T82 | Hold endings (count the strikes) | 1 strike = another rep; 2 falling = swap sides; 3 = set over; 4 = exercise over; notifications | hold_ending, HOLD_ENDING_* | L171-198, L356-372 | — | KEEP |
| T83 | Rest countdown timer | Starts by itself; MM:SS; ticks; "GO" with a rising two-strike bell; presses "→ Next Set" after 0.9 s | — | `_rest_timer` L482-618 | localStorage | KEEP |
| T84 | Activity timer | "Start n min Timer"; colour change in the last 30 s; four-strike bell; DONE | — | `_duration_timer` L686-755 | localStorage | KEEP (see F17) |
| T85 | Count-up stopwatch | Start/Stop/Reset; never rings | — | `_stopwatch` L621-683 | localStorage | KEEP |
| T86 | Countdown ticks | 880 Hz tick at 3, 2, 1 | — | L91-103 | — | KEEP |
| T87 | Background notifications | Only when hidden and allowed | — | L208-218 | — | KEEP |
| T88 | Screen stays awake | Not built; a locked phone stops the timers | — | — | — | KEEP as a new phone requirement |

### Completion and save
| Id | Feature | What the owner sees or does | services/ or Repository calls | Computation inside the view | Writes | Proposal |
|---|---|---|---|---|---|---|
| T89 | Day complete banner | "DAY n COMPLETE — save your session." | — | L3946-3962 | — | KEEP |
| T90 | Review an exercise | Time (Garmin or estimated), sets, weight | exercise_duration_seconds | L3968-3989 (shows the plan's weight) | — | KEEP (see F20) |
| T91 | Garmin check before save | "Garmin workout found…" / "Stop your Garmin…" / "No Garmin workout was started…" | find_open_garmin_activity | L4007-4039 | tp_garmin_check | KEEP |
| T92 | Session RPE | Slider 1-10, default 5 | — | L4047-4049 | — | KEEP |
| T93 | Session length question | "The clock says x min… Which length do you save?" | duration_needs_a_check, estimate_duration | L3991-3994, L4044-4061 | — | KEEP |
| T94 | Duration and AU caption | "Session duration… · Estimated AU…" | — | L4062-4066 (RPE fixed at 5) | — | KEEP (see F16) |
| T95 | Session notes | "Session Notes (optional)" | save_session_notes | L4067-4071 | last exercise row | KEEP |
| T96 | "Save Session to Log" (resumable) | Saves; on failure "press Save again and it continues…" | create_training_session, save_training_exercise, save_session_notes | `_auto_log_session` L991-1124, L4074-4118 | session, exercise and set rows | KEEP (becomes one idempotent save) |
| T97 | Heart-rate match | "Matching heart rate to exercises…" | compute_session_hr | L1278-1302, L4098-4099 | tp_hr_au | KEEP |
| T98 | Congratulations | "Congratulations — session logged…" | — | L4121-4134 | — | KEEP |
| T99 | Watch/timezone mismatch picker | "Couldn't line this session up with your watch…"; "Use this activity" | compute_session_hr(force_activity_id, shift_hours) | L4146-4184 | tp_hr_au | KEEP |
| T100 | Measured vs reported | Measured RPE and AU vs yours; cover line | — | L4186-4225 | — | KEEP |
| T101 | No heart-rate captions | "No heart-rate match… Load is from your own rating…" | — | L4230-4240 | — | KEEP |
| T102 | Tomorrow's preview | "Preview: Day n+1 — {objective}" | type_icon, prescription_label | L4241-4245 | — | KEEP |

### "+" menu, accessory, yoga, outdoor
| Id | Feature | What the owner sees or does | services/ or Repository calls | Computation inside the view | Writes | Proposal |
|---|---|---|---|---|---|---|
| T103 | "+" menu | Yoga, Hike / Walk, Accessory | — | L2765-2806 (drawn mid-session too) | tp_fab_open | KEEP (see F18) |
| T104 | Accessory blocked | "There's a session in progress…" | — | L2781-2787, L2914-2916 | — | KEEP |
| T105 | Start an accessory session | A short second session chosen from regional strain | accessory.choose, build_day; region_acwr; … | L2851-2927 | tp_accessory_plan | KEEP |
| T106 | Accessory overview | Objective, RPE target, items, minutes, "Why this session", Start / Cancel | estimate_duration, first_side | L2977-3041 | checkpoint key −1 | KEEP |
| T107 | Accessory in progress | "Exit accessory session" + the guided flow | — | L3043-3047 | checkpoint | KEEP |
| T108 | Accessory save | RPE slider; duration; notes; resumable save; Discard | `_auto_log_session(movement_type_override="Accessory")` | L2935-3020 | Type=Accessory rows | KEEP |
| T109 | Yoga picker | "Select Yoga"; one button per flow | yoga.YOGA_LIBRARY | L3187-3214 | tp_yoga_* | KEEP |
| T110 | Yoga detail and Complete | Name, minutes, RPE, YouTube, form notes, Complete → logged / already logged | get_current_stage, get_supplementary_sessions_live, …; yoga_save_plan | L3058-3184 | Type=Yoga rows | KEEP |
| T111 | Hike / Walk search | "Add outdoor training", day picker, "Search Garmin" | exclusive(), get_garmin_activities_for_date | L3275-3314 | tp_hike_results | KEEP |
| T112 | Pick, rate and log an outdoor activity | List, "How hard was it?", AU preview, "Log to training" | outdoor_exercise_name, outdoor_activity_logged, make_sets_data; … | L3241-3348 | Type=Outdoor row | KEEP |
| T113 | AI note | Not on Training (the parse is on Insights) | — | — | — | (see I62-I63) |
| T114 | Core hold score | Not on Training (shown on Insights; Training records the seconds) | strength.core_hold_index | — | — | (see I13) |

## Insights, Check-in and the shell — 124 rows

| Id | Screen | Feature | What the owner sees or does | services/ or Repository calls | Computation inside the view (file:line) | Writes | Proposal |
|---|---|---|---|---|---|---|---|
| I1 | Insights | Title and 6-tab bar | BioAge, Engine Data, Processing Queue, Macro Trends, Sleep Architecture, Sync | get_diagnostic_profile | All six tabs run on every rerun (2326-2342) | — | KEEP (regroup for the phone) |
| I2 | BioAge | Category cards | Four image cards (Strength, Flexibility, Metabolism, Cardio) | `_bioage_b64` | 158-203 | `_bioage_detail` | KEEP |
| I3 | BioAge | Detail navigation | "← Back"; the open card survives a reconnect | — | 123-151 | session, ?bioage= | KEEP (native routing) |
| I4 | BioAge › Cardio | Cardio detail | "coming soon" | — | 2367-2368 | — | KEEP (the owner will add Cardio later; 2026-10-19) |
| I5 | Strength | Overall Strength hero | Score or "—"; "Calibrating" pill | strength.screen() | 559-586, 743-746 | — | KEEP |
| I6 | Strength | History read failure | Warning with the exception | get_all_training_exercises_raw | 2268-2272, 747-753 | — | KEEP |
| I7 | Strength | Progress metric picker | Five series; "Updated on" | — | 261-267, 758-780 | widget | KEEP |
| I8 | Strength | Weekly readout | This week, last week, change | tonnage.change | 589-619, 369-377, 782-793 | — | KEEP |
| I9 | Strength | Score chart (6 weeks) | Modelled level, measured series, haloed last point | strength.screen()["score_series"] | 478-556 | — | KEEP |
| I10 | Strength | Tonnage chart (6 weeks) | Bars per week, zero-week stub, tooltip | tonnage.weekly_tonnage, nice_axis_max, unloaded_text | 404-455 | — | KEEP |
| I11 | Strength | Work without load | Held time and reps, never added | tonnage.unloaded_text | 458-475, 801-804 | — | KEEP |
| I12 | Strength | Body-parts split bar | Points and % per region | strength.screen() regions | 677-691 | — | KEEP |
| I13 | Strength | Region cards and plates | Points, %, index or "—", confidence bar; Core's provisional hold index | strength.displayed_index, CALIBRATION_EXIT, core_hold_index | 622-674 | — | KEEP |
| I14 | Strength | "View All ›" | Text that does nothing | — | 816-826 | — | DROP (keep the header) |
| I15 | Strength | Imbalance card and list | "Muscle imbalances N"; two groups | bioage.muscle_imbalance_count; PROFILE["imbalances"] | 694-733 | — | KEEP |
| I16 | Metabolism | Composition hero | kg fat · kg fat-free, "Measured · date" | bc.parse_fitdays_csv | 965-1014, 1222-1230 | — | KEEP (see F15) |
| I17 | Metabolism | Scale-export read failure | Warning | — (reads Input_files/Fitdays.csv) | 2229-2236, 1231-1236 | — | KEEP (see F15) |
| I18 | Metabolism | Fat / fat-free split bar | kg, %, total | — | 1017-1034 | — | KEEP |
| I19 | Metabolism | Progress metric picker | Six series incl. phase angle, ECW/TBW | — | 854-867 | widget | KEEP |
| I20 | Metabolism | Range and stepper | Week / Month / Year / All; ‹ › | bc.period_window, can_step | 1255-1281 | metab_range, metab_offset | KEEP |
| I21 | Metabolism | Readout | Latest; change first → last | — (bc.window_change unused) | 1037-1062, 1283-1290, 1339-1354 | — | KEEP (see F11) |
| I22 | Metabolism | Series chart | Line and dots, broken across gaps | bc.readings_in, split_runs | 1065-1129 | — | KEEP |
| I23 | Metabolism | Cellular health (InBody) | Phase angle and ECW/TBW with age pill | bcb.SCANS → at_height() | 1146-1162, 1316 | — | KEEP |
| I24 | Metabolism | Body analysis cards | MASS / ENERGY / WATER / RISK; "Normal" pills | bc.TRUE_HEIGHT_M | All arithmetic in the view (1165-1212) | — | KEEP (move the formulas; see F11) |
| I25 | Metabolism | "Add measurement" | Two disabled buttons | — | 1328-1336 | — | DROP (placeholder) |
| I26 | Flexibility | Read failure | "Could not read the flexibility record…" | get_flexibility_assessments | 2182-2186 | — | KEEP |
| I27 | Flexibility | Resume banner | "Assessment in progress — X of Y tests…" | get_flexibility_draft; fx.capture_progress | 2188-2201 | fx_mode | KEEP (see F13) |
| I28 | Flexibility (empty) | Standing-goal card and Start | "Not measured"; cold, every twelve weeks | fx.CLUSTERS | 1539-1555 | fx_mode | KEEP |
| I29 | Flexibility (empty) | "What this produces" | One label, not a score | — | 1557-1565 | — | KEEP |
| I30 | Flexibility (empty) | The slots and why in order | Per slot: question, "Decides:" | btry.SLOT_* | 1573-1574 | — | KEEP |
| I31 | Flexibility (empty) | "Held back for now" | Deferred tests with conditions | cba.DEFERRED_TESTS | 1585-1595 | — | KEEP |
| I32 | Capture | Cold gate | "Measure cold"; Cold / Warm | — | 1628-1630, 1679 | — | KEEP (measurement rule) |
| I33 | Capture | Leg day yesterday | Warning, never a block | get_recent_sessions(3); fx.leg_loading_days | 1636-1645 | — | KEEP (training rule) |
| I34 | Capture | Protocol expanders | The three numbers, LOCK, measure once, record but never chase | flexibility_baselines.* | 1524-1534, 1647-1673 | — | KEEP |
| I35 | Capture | Begin / Cancel | Begin creates the draft | btry.Assessment | 1675-1685 | save_flexibility_draft (local only) | KEEP |
| I36 | Capture | Early stop | "That is your answer — stop here"; Save / Keep going | btry.run; cba.PATTERNS | 1693-1718 | save_flexibility_assessment | KEEP |
| I37 | Capture | Step header and ticks | "test · n of N · slot k"; skip notes | applicable_tests, SKIP_NOTES | 1724-1736, 1600-1606 | — | KEEP |
| I38 | Capture | LOCK, setup, how to read it | Safety text | test.lock, setup, measurement, safety | 1744-1759 | — | KEEP (safety) |
| I39 | Capture | Reading form | Values per side; load field; setup carried over; void; Save & next | fx.merge_reading, btry.Reading | 1789-1852 | draft each step; assessment at the end | KEEP |
| I40 | Capture | Skip / Back / Pause | Step navigation | — | 1854-1863 | session | KEEP |
| I41 | Populated | No pattern | "No pattern reached"; "A missing measurement is not a pass…" | fx.assess | 2011-2024 | — | KEEP |
| I42 | Populated | Fill in what is missing | Form for 1-2 readings; "Add and re-run" | missing_inputs; fx.merge_reading | 1930-2005 | save_flexibility_assessment | KEEP |
| I43 | Populated | Pattern card | Label, "stopped at · n of 4 slots" | report fields | "of 4" typed in (2036) | — | KEEP (see F10) |
| I44 | Populated | Trust warning | "hypothesis, not a verdict… 3 baseline mornings" | btry.BASELINE_SESSIONS_REQUIRED | 2045-2052, 2169 | — | KEEP |
| I45 | Populated | The ladder | Rungs with measured/target, state | ladder via fx.assess | 1868-1927 | — | KEEP |
| I46 | Populated | Your stack | Numbered exercises with how-to | fx.prescribe; cluster_a_mechanics.exercise | 2063-2099 | — | KEEP |
| I47 | Populated | Held-back items and outro | "Until …" | stack items | 2101-2111 | — | KEEP |
| I48 | Populated | How that was reached | Per slot pass/undecided/fail; "N slots not measured" | btry.SLOT_* | 2114-2127 (4 − len(slots)) | — | KEEP (see F10) |
| I49 | Populated | Every reading | Test, side, value, load, setup | result readings | 2129-2134 | — | KEEP |
| I50 | Populated | Retest status | Next retest / blocked / ready | fx.retest_readiness, leg_loading_days | 2136-2150 | — | KEEP (training rule) |
| I51 | Populated | Re-assess | Button and caption | — | 2152-2158 | session | KEEP |
| I52 | Engine Data | Freshness and Refresh | "Data as of …"; "Refresh engine data" | — | 2388-2392 | clears every cache | KEEP (pull-to-refresh) |
| I53 | Engine Data | DIRECTIVE banner | Home's words and tone, the action sentence | engine chain; sessions.load_policy; verdict.* | Chain rebuilt with the view's caches (2394-2410); load_policy(rec, {}) (2417) | — | KEEP (read the same verdict as Home; see F4) |
| I54 | Engine Data | ACWR advisory | Note under the banner | rec["acwr_advisory"] | 2435-2436 | — | KEEP |
| I55 | Engine Data | Stage progression | Stage, pain-free days, tightness target | engine.stage_status; get_pain_free_streak, get_avg_tightness | 2443-2453 | — | KEEP (training rule) |
| I56 | Engine Data | Traffic light | "Overall: COLOUR — message" | engine.traffic_light | 2458-2468 | — | KEEP |
| I57 | Engine Data | HRV / RHR / sleep / temperature cards | Value, 28-day average, change; temperature signals | insights.metric_delta_str | 2474-2516 | — | KEEP |
| I58 | Engine Data | Baseline drift | "BASELINE DRIFT — severity"; light downgraded | drift result | 2527-2556 | — | KEEP (safety) |
| I59 | Engine Data | Workload numbers | ACWR, acute, chronic, ceiling; hard lock / establishing / advisory | engine.acwr(stage_start) | 2564-2585 | — | KEEP (training/safety) |
| I60 | Engine Data | Daily AU chart | 28 days, chronic vs acute | insights.acwr_chart_data | 2587-2601 | — | KEEP |
| I61 | Engine Data | Weekly volume load | Σ reps × weight per week, 8 weeks | volume.weekly_volume_load | 2613-2629 | — | KEEP |
| I62 | Processing Queue | Pending counts | Notes and entries pending | get_unparsed_session_notes, get_unparsed_readiness | 2636-2651 | — | MOVE |
| I63 | Processing Queue | "Process All" | Parsed n/N, errors | ai.parse_session_note, parse_tightness (keyword rules) | 2653-2702 | update_session_note_ai, update_readiness_ai | MOVE (parse on save) |
| I64 | Processing Queue | Active warnings calendar | Month grid, day detail | get_flagged_entries | 2704-2811 | session | KEEP |
| I65 | Macro Trends | Empty state | "No parsed readiness entries yet…" | get_parsed_readiness(90) | 2818-2821 | — | KEEP |
| I66 | Macro Trends | Body areas selected most (until 2026-10-20 "Most flagged body regions", a keyword count of the note text, which did not match the areas he selects; the owner) | Bar chart | insights.selected_area_frequency | 2823-2851 | — | KEEP |
| I67 | Macro Trends | Tightness severity timeline (since 2026-10-20 every check-in of the last 90 days, with the parsed severity where the note was read; until then only the parsed check-ins; the owner's choice) | Self-reported, parsed, pain | insights_screens.checkin_trend | 2853-2864 | — | KEEP |
| I68 | Macro Trends | Warning level history | Clear / Monitor / Flag buttons with lists | — | 2866-2920 | session | KEEP |
| I69 | Macro Trends | Data gate | Days available; "Need at least 14 days…" | get_macro_trend_data(90) | 2924-2938 | — | KEEP |
| I70 | Macro Trends | Recovery direction and slopes | Table | stats.compute_all_correlations; insights.slope_direction_rows | 2940-2953 | — | KEEP |
| I71 | Macro Trends | Notable correlations | Pairs with r | compute_all_correlations | 2955-2964 | — | KEEP |
| I72 | Macro Trends | "Generate Trend Interpretation" | Template text (not a model) | ai.analyze_macro_trends | 2982-2992, 2972 | session | KEEP (compute on load) |
| I73 | Sleep Architecture | Method caption | Oura stages, Garmin's Awake | — | 3018-3024 | — | KEEP |
| I74 | Sleep Architecture | Read failure vs empty | Two messages | get_sleep_fusion_history | 3030-3046 | — | KEEP |
| I75 | Sleep Architecture | Summary metrics | Nights fused, Oura only, median phantom wake | — | 3048-3054 | — | KEEP (see F12) |
| I76 | Sleep Architecture | Nightly hypnograms | Picker; Oura, Master, Garmin bands | styles.hypnogram_svg | 3061-3078 | widget | KEEP |
| I77 | Sleep Architecture | Per-night metrics | Agreement %, Cohen's κ, minutes | fusion row | 3080-3092 | — | KEEP |
| I78 | Sleep Architecture | Shadow report | Why fusion stays display-only; what would change | dash.sleep_fusion_shadow_report | 3094-3128 | — | MOVE (Settings › Data) |
| I79 | Sync | Store caption | "Supabase holds all data…" | R.supabase_record | 3139-3148 | — | MOVE |
| I80 | Sync | Mirror-failure warning | — | mirror_last_error | 3149-3161 | — | DROP (cannot show) |
| I81 | Sync | Sheet1 raw table | — | get_raw_sheet_rows | 3163-3205 | — | DROP (cannot show) |
| I82 | Sync | Engine View, last 28 days | Blend caption; table | get_biometric_rolling(28) | 3207-3220 | — | MOVE |
| I83 | Sync | Biometric Blend History | From/To; table | get_biometric_blend_history | 3245-3266 | — | MOVE |
| I84 | Sync | "Backfill full history now" | Persisted N days | sync_biometric_blend(400) under the lock | 3231-3243 | biometric_blend | MOVE |
| I85 | Sync | Metrics History | From/To; table | get_metrics_history | 3278-3296 | — | MOVE |
| I86 | Sync | Session checks | Two sessions on one date; AU over 1.5× | sessions.session_log_warnings | 3298-3313 | — | MOVE (keep the rule) |
| I87 | Sync | Auto-sync caption | "Garmin once a day" (out of date) | — | 3315-3320 | — | MOVE (fix text) |
| I88 | Sync › Garmin | Setup and description | — | garmin_configured | 3322-3337 | — | MOVE |
| I89 | Sync › Garmin | "Sync Garmin Daily Metrics" | Synced N days | sync_garmin_daily(7) under the lock | 3341-3351 | garmin_daily, garmin_sleep_stages | MOVE |
| I90 | Sync › Garmin | "Sync Garmin Activities" | Synced N activities | sync_garmin_activities(20) under the lock | 3352-3365 | garmin_activities (only writer) | MOVE (and add to the automatic chain; F14) |
| I91 | Sync › Sleep Fusion | "Rebuild Sleep Fusion" | Fused N nights | sync_sleep_fusion(1200) under the lock | 3367-3393 | sleep_fusion | MOVE |
| I92 | Sync › Oura | Setup | "Add OURA_TOKEN…" (out of date) | oura_configured | 3395-3412 | — | MOVE (fix text) |
| I93 | Sync › Oura | "Sync Weekly Oura Details" | Synced N days, workouts, … | sync_oura_all(7) under the lock | 3413-3429 | five oura_* tables | MOVE |
| I94 | Check-in | Date selector | Today / Yesterday / dated, up to 3 days back | — | checkin.py:56-85 | — | KEEP |
| I95 | Check-in | Tightness | Slider 0-10 | readiness_checkins | 93-96 | via I112 | KEEP |
| I96 | Check-in | Pain | Slider 0-10 | readiness_checkins | 97-100 | via I112 | KEEP (safety; see F3) |
| I97 | Check-in | General readiness | Excellent … Poor | | 101-103 | via I112 | KEEP |
| I98 | Check-in | Affected areas | Multi-select | | 106-111 | via I112 | KEEP |
| I99 | Check-in | Sensation tags | Multi-select | | 112-116 | via I112 | KEEP |
| I100 | Check-in | Sensation note | One line | | 117-122 | via I112 | KEEP |
| I101 | Check-in | Psychological stress | 1-5 | | 126-143 | via I112 | KEEP |
| I102 | Check-in | Alcohol units (24 h) | 0-20, step 0.5 | (feeds the shift rule) | 144-149 | via I112 | KEEP |
| I103 | Check-in | Travel / location change | Toggle | | 150-154 | via I112 | KEEP |
| I104 | Check-in | Instability events | 0-20 | | 161-165 | via I112 | KEEP |
| I105 | Check-in | Bristol stool type | 0-7 | | 166-171 | via I112 | KEEP |
| I106 | Check-in | Unusual colour? | Toggle | | 172-174 | via I112 | KEEP |
| I107 | Check-in | Hunger vs baseline | −2 to +2 | | 178-182 | via I112 | KEEP |
| I108 | Check-in | Morning thirst | 1-5 | | 183-186 | via I112 | KEEP |
| I109 | Check-in | Salt / electrolytes | Toggle | | 187-189 | via I112 | KEEP |
| I110 | Check-in | Meditation minutes | 0-120; "done" inferred | | 211-212 | via I112 | KEEP |
| I111 | Check-in | Relaxation depth | 1-5 | | 199-203 | via I112 | KEEP |
| I112 | Check-in | "Save Morning Check-In" | One submit; "Check-in saved…" | save_check_in(CheckInRecord) | 206-244 | readiness_checkins (merge per date) | KEEP (see F3) |
| I113 | Check-in | Supabase-send warning | — | send_mirror_now | 245-254 | — | DROP (cannot fire) |
| I114 | Check-in | Scale reference | Tightness and pain bands | — | 19-50, 256-268 | — | KEEP |
| I115 | Shell | Bottom nav bar | Three tabs, active green | — | nav.py:22-241 | _nav_page | KEEP |
| I116 | Shell | Nav survives a failing screen | Bar drawn even after an error | — | app.py:149-169; nav.py:202-214 | run flag | KEEP |
| I117 | Home | Check-in FAB | "+" top right | — | app.py:336-353, 2372-2373 | _nav_page | KEEP |
| I118 | Shell | Dual theme | Desktop Whoop look; phone Oura look | styles.inject_css | styles.py:13-46, 170-319 | — | KEEP (the phone uses the Oura palette) |
| I119 | Shell | Desktop/phone component kit | — | — | styles.py:49-165 | — | DROP (never called) |
| I120 | Home | Tappable chart points | Tap bands, outlined selection, point detail | styles.chart_frame, chart_hits, chart_points; dashboard.hit_bands | styles.py:321-337, 421-494 | URL pt (reload) | KEEP (native selection) |
| I121 | Home | Same-tab chart links | — | — | styles.py:523-587 | — | DROP (Streamlit-only) |
| I122 | Home | Axes, trend and overnight charts | Gap rules, pinned labels | axis_gutter_labels, trend_chart_svg, overnight_chart_svg | styles.py:356-412, 599-656, 822-891 | — | KEEP (the gap rules are behaviour) |
| I123 | Sleep | Hypnogram and legend | Deep/Light/REM/Awake bands | STAGE_BAND, hypnogram_svg, stage_legend_html | styles.py:670-745 | — | KEEP |
| I124 | Sleep | Movement strip and legend | Four strengths; unmeasured slots blank | movement_svg, movement_legend_html | styles.py:755-819 | — | KEEP |

---

## Computations that must move into `services/` (milestone 3)

Each line is a rule or calculation that today lives only in a view and that an API must return. Every move is one commit with its test; the Streamlit view then calls the moved function.

**Home**
1. Readiness DAILY and its window (14 days on the caller's today, 60 on a past day); arc and band follow DAILY else TREND; one raw score with its own breakdown (F6).
2. The verdict only for the caller's today.
3. An explicit failure for an unreadable stage, never stage 1 (F7).
4. Sleep need (baseline else 8.0 h) — a second copy of `dashboard.SLEEP_NEED_HOURS_DEFAULT`.
5. The rest-day strain's reference date, chosen explicitly (F8).
6. Read windows counted back from the requested day (F8).
7. The read-failure and staleness flags that pick the "not scored" reason.
8. The Sleep screen's all-or-nothing rule (and its test, `tests/test_sleep_screen_is_all_or_nothing.py`).
9. Watch-only stage rows. 10. Hypnogram source and notes. 11. Strip time window and tap bands. 12. Movement caption. 13. Overnight panel choices. 14. Readiness key metrics. 15. Contributor captions. 16. Wake-correction display with its source. 17. The wake stepper's rule (F5). 18. The 30-day trend's window, axes and day detail. 19. The 7-day HRV and RHR window. 20. The region panel's data. 21. The region panel's texts and numbers. 22. The ACWR ceiling lookup (derive from `rules.STAGE_CONSTRAINTS`, Key Rule 3). 23. The strain source. 24. Strain labels. 25. Day rules (no day after the caller's today). 26. The sync decision (moves with the sync). 27. Which status message wins (auth state and each sync step's last result). 28. Each score's scale (100 or 21).

**Training**
1. **The session save**: one idempotent save of a complete session with caller-minted ids (today `_save_training_exercise_record` mints a uuid per call and `save_session_notes` appends).
2. Checkpoint and restore rules, including the "already logged today" lock.
3. Prescription seeding: per exercise the resolved numbers, previous performance, delta and caption parts.
4. **The load policy**: kind, text, factor, note, reduced, failed-week hold; per exercise `next_step`, `step_blocked`, `held_because`.
5. **The warning gate's inputs** (`_warning_strains`) into `strain_regions`, returning "warning due" per exercise.
6. **The three date_overrides writes**: one service that applies a proposal and returns (phases, rejected), with reasons filtered to the allowed dates (F2), and the readiness shift working again (F1).
7. **The failed-week write and the Monday redo**: an engine job plus one read (notice, last-week line, redo offer with consequences) and a redo endpoint; the redo's re-check reads live.
8. The block changeover (to drop, D1).
9. **The guided-flow state machine** as one pure function (state + event → next state, set record, bell), so the bell and the button cannot disagree; set times from the phone (rebuild rule 3).
10. Week banner and strip. 11. Day routing. 12. The no-active-phase screen. 13. Gate 1. 14. Accessory choice inputs. 15. The flexibility retest banner. 16. The completion screen (elapsed minutes, length question, AU, heart-rate comparison). 17. The outdoor import (its note is the duplicate key). 18. The yoga save. 19. Small rules (`HOLD_TIMER_TYPES` out of the view).

**Insights and Check-in**
1. `_strength_screen_data` and the readout, axis, tonnage, unloaded and region-strip rules (A1-A6).
2. `_metabolism_screen_data` (with a store for the readings, F15), the period state, visible series, readout (`bc.window_change`), chart range, split, scan age and pills, and every derived formula (BMI, bone, BMR, water, protein, visceral, subcutaneous; F11).
3. `_flexibility_screen_data`, the capture flow (cold flag, early exit, step order, load field, setup carry-over, save rules), the leg-day check, missing-reading merges, step ticks, ladder states and the populated screen (F10, F13).
4. **Engine Data: return `today.today_directive()` and `verdict.today_verdict`** instead of rebuilding the chain (F4); metric-card rules, drift display, ACWR messages, weekly volume series.
5. The Processing Queue's parse as a job; the warnings calendar and warning-level grouping; the trend data gate; recovery labels.
6. Sleep Architecture's summary counts (F12), fused-hours map; history date filters as start/end parameters.
7. **Check-in**: the backfill window (today and the 3 days before), the field limits (the API enforces them), `meditation_done`, and "not set" sent explicitly so a field can return to its default (F3).
8. Navigation: page resolution (an unknown page → Home).

## Writes (what the API must cover)
- **Home**: the wake-time correction; the device sync chain (engine); the Oura token copy.
- **Training**: plan, accessory, yoga and outdoor saves; the local and durable checkpoints; phases (swap, carry, readiness shift, failed-week rule, redo, plan start); `plan_start_date`; gate-1 reasons; the weekly rollup and Garmin daily sync (engine).
- **Insights**: flexibility draft (local only today, F13) and assessment (Supabase config); the Processing Queue's parsed fields; the five manual sync buttons, each under `BackgroundSyncRunner.exclusive()`.
- **Check-in**: one row per date, merged field by field.
- In production every one of these goes to Supabase first and is waited for; a failure raises.

## Caches
Home holds 13 `st.cache_data` reads (30 minutes) plus `today.py`'s five; Insights holds 18 (Engine Data's eight duplicate `today.py`'s on separate clocks); Training caches logged dates (5 minutes) and regional rows (30 minutes). None is keyed by date (F9), nothing re-reads after a sync, and several clear every cache in the process. The API reads fresh per request (with the 15-minute copy freshness rule), so none of this is ported.

## Timers and sounds (Training)
Five `components.html` iframes with state in localStorage; every sound is synthesised with the Web Audio API through one compressor (no sound files). Tick: 880 Hz sine, 0.12 s. Bell: five sine partials (1, 2, 2.76, 4.07, 5.4 × the root). Endings: another rep = one D6 strike; swap sides = D6, G5; set over = C6, G5, C5; exercise over = C6, G5, E5, C5; rest "go" = rising G5, D6. The hold timer presses the done button 0.7 s after zero and the rest timer presses "→ Next Set" 0.9 s after; the activity timer rings but does not press; the stopwatch never rings. No screen-awake code exists (T88).
