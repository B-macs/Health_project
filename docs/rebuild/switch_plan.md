# The switch-over plan (rebuild Phase 9) — DRAFT

**Status: his answers of 2026-10-20 ("a yes b yes c yes d yes"): (a) the backup gap of 2026-10-17 is accepted as the old app's known fault; (b) his phone checks of Phases 4-8 come first, then the switch; (c) the six items below are built first; (d) the switch is done with him, step by step.** Nothing below is switched yet. After his OK the switch is done with him, step by step, and stops after the first sync. Then he uses only the new app for 7 days.

**What the switch does:** the engine becomes the only process that writes in the background (the device syncs and the automatic writes). It is one planned step, and each part can be undone.

## The checks before the switch (2026-10-20)
Run `python scripts/switch_check.py` (read-only). All must pass.

| Check | Result on 2026-10-20 |
|---|---|
| Every kept inventory row built, each with a test | ✓ 282 rows |
| Parity, last 28 days (Today and Insights, under the engine's Python) | ✓ 0 differences each |
| A daily backup on each of the last 7 days | ✓ with the gap he accepted: none on 2026-10-17 — **accepted by the owner (a)**, and recorded in `scripts/switch_check.py` (`ACCEPTED_BACKUP_GAPS`), which still names it; any other day without a copy fails: the old app makes the backup in its sync chain, and runs the chain only when its Home page loads to its end (found 2026-10-19). After the switch the engine's sync makes it at the first open of any screen. |
| The Oura login against a mocked Oura | ✓ (the engine's API tests) |
| The sync rehearsal on Cloud Run, devices mocked, inside the time limit | ✓ **88.75 s against 280 s** (2026-10-20, engine revision 20): all 11 steps done, one Oura refresh, no outgoing connection tried; the service deleted after the run |
| His phone: no save waiting, none refused in 7 days | his check |

## Still to build before the switch (built 2026-10-20 unless marked)
1. **The Oura login on the phone** ✓: Settings > Oura login (on only while the engine is the writer) and the Worker's `/oura/callback`, which hands the code to the engine itself (the login finishes even when iOS opens the return page in Safari, which does not hold the key) and opens the app's result page. The phone's date travels with the login's state (rule 3). Found by its browser test: the service worker answered `/oura/` page loads from its saved copy; `/oura/` now goes to the network.
2. **The sync buttons in Settings > Data turned on when the engine is the writer** ✓: one button per sync the engine names (Settings' `manual_syncs`); the phone's own list had two names the engine did not know.
3. ✓ **The old app's retired banner and its write refusal, keyed on the setting** (`Repository._refuse_if_retired`, read live at most once a minute): when `background_writer` is "engine", every page of the Streamlit app shows "This app is retired. Use the Health app on your Home Screen." and refuses writes with the same words. Keyed on the setting, step 8 happens with step 3 and is undone with it, and no push is needed during the switch.
4. ✓ **"Off" for the cache-freshness pull** (`HEALTH_CACHE_MAX_AGE_MINUTES=off`). Step 7 needs it.
5. ✓ **The sync rehearsal** (`scripts/sync_rehearsal.py --cloud`): a separate Cloud Run service, `health-rehearsal`, deployed from the image the engine runs (no build), with the engine's CPU, memory and timeout and nothing else (no secret, no public access, one instance), deleted after the run. It runs the engine's own app and its REAL sync chain (`POST /api/sync` with force) over a made-up history built through the real sync and save code (`api/healthapi/rehearsal.py`: two years of ring nights, four months of watch days, the block's sessions, check-ins, heart-rate matches), with every device and store call faked (`api/healthapi/rehearsal_devices.py`, `services/memory_store.py`) and every outgoing connection refused. The waits are assumptions and the record says so: 2.0 s a device call and 10 s more for a Garmin login (neither device may be called from this PC), 0.15 s a store call (measured 2026-08-11). Its time decides whether the 280 s the Worker now allows is enough; `scripts/switch_check.py` passes it only for a Cloud Run run with every step done. On this PC: 81 s.
6. ✓ **`scripts/set_background_writer.py`** (dry run first): the one write of step 3, and its undo.

## Known risk: a sync cut off mid-way
The sync runs inside the phone's request. If the app goes to the background during a sync (about 1-2 minutes with real devices), the request can end before the chain does. Each step's writes stand on their own, and the run is recorded only at the end, so the next open asks again. The one fragile moment is Oura's token refresh: Oura spends the old refresh token when it gives a new one, and the engine saves the new one at once. The rehearsal measures the chain; the screen says "Syncing…" until it ends.

## The steps (each with its check and its undo)
Do the switch right after a Streamlit sync has finished, at a time when no training session is in progress.

1. **He adds the new Oura redirect address** (`https://health.lauscher-worker.workers.dev/oura/callback`) to his Oura developer app, beside the old one. Check: both are listed. Undo: remove the new one.
2. **The last Streamlit sync finished without an error.** Check: the old app's Home shows no sync error. Undo: none needed.
3. **Set `background_writer` to "engine"** (one write to Supabase's config table: `scripts/set_background_writer.py --to engine`). From then on the Streamlit app runs no sync and no automatic write, and shows the retired banner (item 3 above). Check: open the Streamlit app; no sync starts and the banner shows. Undo: `--to streamlit`.
4. **Turn on the sync paths at the Worker** (`SYNC_ENABLED` true) and deploy the Worker. Undo: false, deploy. *Moved before the Oura login on 2026-10-20: the Worker refuses `/api/oura/` and `/oura/callback` until this is on.*
5. **He logs in to Oura from the new app** (Settings > Oura login). The engine stores the new token where the Repository keeps it. Check: Settings' sync card shows the Oura login as valid with its expiry, never its value. Undo: log in again through the Streamlit app's address. *His decision (2026-10-19): the sync runs at the first open of the morning, and again at a later open (at most hourly) while last night is missing. So no sync cron is added. The existing daily data check (a Worker cron) already reads Supabase every day; whether that read counts as activity against the Free plan's 7-day pause is still to confirm (Supabase's page on it was not found on 2026-10-20). If it does not, one daily keep-alive cron goes in here.*
6. **Run the first sync by hand** from Settings > Data and check each step: Oura, Garmin, the blend, session heart rate, metrics history, sleep fusion, the backup and the store send. Check: Settings' sync card lists each step as done. Undo: none needed (each step only adds what is new).
7. **Turn off both cache-freshness pulls** (`HEALTH_CACHE_MAX_AGE_MINUTES=off` on the engine and in the Streamlit app's secrets): the engine is now the only writer. Undo: remove the setting.
8. **The Streamlit app's banner and refusal** (automatic with step 3). Check: a save in the old app is refused with the banner's words. Undo: with step 3's undo.

## ROLLBACK the switch-over (ready to paste)
```
ROLLBACK THE SWITCH-OVER (rebuild Phase 9). Do these in this order, and check each:
4. Set SYNC_ENABLED to false in worker/wrangler.jsonc and deploy the Worker. Check: POST /api/sync answers 409 sync_disabled. Set `SWITCHED_OVER = None` in scripts/rebuild_gate.py with it.
3. python scripts/set_background_writer.py --to streamlit. Check: GET /api/status names "streamlit" and no sync is due.
5. Log in to Oura again through the Streamlit app (its Insights > Sync > Oura). Check: the Streamlit app's Oura sync runs.
8. Nothing to do: the banner and the refusal follow step 3. Check: the Streamlit app saves again.
7. Remove HEALTH_CACHE_MAX_AGE_MINUTES=off from the engine and from the Streamlit app's secrets. Check: each copy is pulled again after 15 minutes.
1. (Optional) Remove the new redirect address from the Oura developer app.
Then record the rollback in docs/rebuild/week_log.md and stop.
```

## The week after the switch
He uses only the new app for 7 days. Each day Settings shows the syncs that ran and their times, the Oura and Garmin status, the store check, the outbox count, and the failed-week rule's step. `docs/rebuild/week_log.md` records the events, with no personal values. If a step fails: propose a fix or the rollback; never decide alone.
