# The switch-over plan (rebuild Phase 9) — DRAFT

**Status: a draft. It waits for (1) the checks before the switch to pass and (2) the owner's OK.** Nothing below is done yet. After his OK the switch is done with him, step by step, and stops after the first sync. Then he uses only the new app for 7 days.

**What the switch does:** the engine becomes the only process that writes in the background (the device syncs and the automatic writes). It is one planned step, and each part can be undone.

## The checks before the switch (2026-10-20)
Run `python scripts/switch_check.py` (read-only). All must pass.

| Check | Result on 2026-10-20 |
|---|---|
| Every kept inventory row built, each with a test | ✓ 282 rows |
| Parity, last 28 days (Today and Insights, under the engine's Python) | ✓ 0 differences each |
| A daily backup on each of the last 7 days | ✗ none on 2026-10-17. The old app makes the backup in its sync chain, and runs the chain only when its Home page loads to its end (found 2026-10-19). |
| The Oura login against a mocked Oura | ✓ (the engine's API tests) |
| The sync rehearsal on Cloud Run, devices mocked, inside the time limit | ✗ not built yet |
| His phone: no save waiting, none refused in 7 days | his check |

## Still to build before the switch
1. **The Oura login on the phone**: a Settings > Oura card (start the login), and the page Oura sends him back to (`/oura/callback` on the new address), which hands the code to the engine. Step 4 needs it.
2. **The sync buttons in Settings > Data turned on when the engine is the writer** (they are drawn off now). Step 6 needs them.
3. **The old app's retired banner and its write refusal, keyed on the setting**: when `background_writer` is "engine", every page of the Streamlit app shows "This app is retired. Use the Health app on your Home Screen." and refuses writes with the same words. Keyed on the setting, step 8 happens with step 3 and is undone with it, and no push is needed during the switch.
4. **"Off" for the cache-freshness pull** (`HEALTH_CACHE_MAX_AGE_MINUTES=off`). Step 7 needs it.
5. **The sync rehearsal**: a separate Cloud Run service (never the real engine, never the real store) with made-up data and every device and store call mocked, timed through one request. Its time decides whether the 280 s the Worker now allows is enough.
6. **`scripts/set_background_writer.py`** (dry run first): the one write of step 3, and its undo.

## Known risk: a sync cut off mid-way
The sync runs inside the phone's request. If the app goes to the background during a sync (about 1-2 minutes with real devices), the request can end before the chain does. Each step's writes stand on their own, and the run is recorded only at the end, so the next open asks again. The one fragile moment is Oura's token refresh: Oura spends the old refresh token when it gives a new one, and the engine saves the new one at once. The rehearsal measures the chain; the screen says "Syncing…" until it ends.

## The steps (each with its check and its undo)
Do the switch right after a Streamlit sync has finished, at a time when no training session is in progress.

1. **He adds the new Oura redirect address** (`https://health.lauscher-worker.workers.dev/oura/callback`) to his Oura developer app, beside the old one. Check: both are listed. Undo: remove the new one.
2. **The last Streamlit sync finished without an error.** Check: the old app's Home shows no sync error. Undo: none needed.
3. **Set `background_writer` to "engine"** (one write to Supabase's config table: `scripts/set_background_writer.py --to engine`). From then on the Streamlit app runs no sync and no automatic write, and shows the retired banner (item 3 above). Check: open the Streamlit app; no sync starts and the banner shows. Undo: `--to streamlit`.
4. **He logs in to Oura from the new app** (Settings > Oura). The engine stores the new token where the Repository keeps it. Check: Settings' sync card shows the Oura login as valid with its expiry, never its value. Undo: log in again through the Streamlit app's address.
5. **Turn on the sync paths at the Worker** (`SYNC_ENABLED` true) and deploy the Worker. Undo: false, deploy. *His decision (2026-10-19): the sync runs at the first open of the morning, and again at a later open (at most hourly) while last night is missing. So no sync cron is added. The existing daily data check (a Worker cron) already reads Supabase every day; whether that read counts as activity against the Free plan's 7-day pause is still to confirm (Supabase's page on it was not found on 2026-10-20). If it does not, one daily keep-alive cron goes in here.*
6. **Run the first sync by hand** from Settings > Data and check each step: Oura, Garmin, the blend, session heart rate, metrics history, sleep fusion, the backup and the store send. Check: Settings' sync card lists each step as done. Undo: none needed (each step only adds what is new).
7. **Turn off both cache-freshness pulls** (`HEALTH_CACHE_MAX_AGE_MINUTES=off` on the engine and in the Streamlit app's secrets): the engine is now the only writer. Undo: remove the setting.
8. **The Streamlit app's banner and refusal** (automatic with step 3). Check: a save in the old app is refused with the banner's words. Undo: with step 3's undo.

## ROLLBACK the switch-over (ready to paste)
```
ROLLBACK THE SWITCH-OVER (rebuild Phase 9). Do these in this order, and check each:
5. Set SYNC_ENABLED to false in worker/wrangler.jsonc and deploy the Worker. Check: POST /api/sync answers 409 sync_disabled.
3. python scripts/set_background_writer.py --to streamlit. Check: GET /api/status names "streamlit" and no sync is due.
4. Log in to Oura again through the Streamlit app (its Insights > Sync > Oura). Check: the Streamlit app's Oura sync runs.
8. Nothing to do: the banner and the refusal follow step 3. Check: the Streamlit app saves again.
7. Remove HEALTH_CACHE_MAX_AGE_MINUTES=off from the engine and from the Streamlit app's secrets. Check: each copy is pulled again after 15 minutes.
1. (Optional) Remove the new redirect address from the Oura developer app.
Then record the rollback in docs/rebuild/week_log.md and stop.
```

## The week after the switch
He uses only the new app for 7 days. Each day Settings shows the syncs that ran and their times, the Oura and Garmin status, the store check, the outbox count, and the failed-week rule's step. `docs/rebuild/week_log.md` records the events, with no personal values. If a step fails: propose a fix or the rollback; never decide alone.
