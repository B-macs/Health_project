# Rebuild state (rolling)

*The phone-app rebuild: see the "Phone app rebuild (from 2026-10-07)" section of CLAUDE.md. Update this file during every rebuild session.*


## Now
**Phase 5 — Today, the detail screens and the check-in: signed off 2026-10-20 under the owner's standing instruction.** Today, readiness, sleep and strain and the check-in run on the engine's numbers at https://health.lauscher-worker.workers.dev (Worker f249a9d9, engine revision 9 from 5c00178). Parity over the 14 days to 2026-10-20: 0 differences. Gate: every p5 counter 0 except the owner's two mornings (6). Python 5556, Vitest 142, Playwright 47. Handoff: `handoff/p5_to_p6_summary.md`.

**Phase 4 — signed off 2026-10-20** (its iPhone checklist open in his batch); **Phase 3 — signed off 2026-10-20**; **Phase 2 — signed off 2026-10-19** (P2-11 open).

**Pushes held on 2026-10-20 from 08:22:** the owner trains on the Streamlit app, and a push redeploys it. The commits wait locally; push when he says he has finished.

## Waiting on the owner (his batch)
0. **The Phase 4 iPhone checklist** (owner_checks.json p4): install from Safari, paste the key, open each tab, airplane mode and reopen, the "act as if the engine is down" switch.
00. **The Phase 5 two mornings** (owner_checks.json p5): open the Streamlit app first, then the new app; compare the three scores and the sleep night; on the second morning do the check-in in the new app and check that the Streamlit app shows it within about 15 minutes. Also: confirm that the chosen design replaces the card photos (H19).
000. **Phase 6 decision**: the "When did you finish?" question before saving a session whose last set was over 20 minutes before Save (the prompt asks for his OK before it is built).
1. **The hosted Streamlit app** (owner_checks.json p2 `streamlit_app_opens`): Home, Training, Insights, Check-in still work after the pushes; a day that already has a check-in opens filled in, and pain can go back to 0.
2. **The Strength reference for the engine**: the store's config row `strength_reference` (recommended) or a secret; on a yes, `python scripts/upload_strength_reference.py --apply`. Until then the engine's Strength screen answers 409 strength_reference_missing.
3. Carried: the voice app's address (for `p1_to_p2`); removing `[voxplot_supabase]` from the health app's secrets; the image store (455.5 MB of the 0.5 GiB free on 2026-10-19, about 190 MB once the clean-up has run — check before the next engine deploy).

## Next
- Phase 6 — the training session (the guided flow on the phone, timers and sounds, the idempotent save through the outbox), from the Notion prompt set.

## The owner's decisions, 2026-10-19 (after the cost estimate)
- **The new app syncs ONCE A DAY, at the first app open in the morning** — not every 2 hours (*"that is enough"*). This sets the engine's sync design for Phase 2 and Phase 9; the Streamlit app keeps its own 2-hourly-on-open cadence until the switch-over (recommended, and he asked for no change there). **When last night's data is still missing after that first sync, a later open syncs again, at most once an hour, until last night is in** (*"Retry the sync"*, 2026-10-19) — otherwise a morning opened before the ring has reached Oura stays empty until the next day.
- **Supabase answers are compressed** (*"Yes compress"*): `services/supabase_store.py` asks for gzip on every Data API request. A full copy of every table, measured against the real project: 9.24 MB → 1.36 MB. The engine copies it at every cold start, and the Free plan includes 5 GB of egress a month.
- **Transform the whole app first** (*"lets continue for now to transform the entire app"*); he will remove the parts he does not use once the new app runs. The Phase 2 screen inventory still lists every feature.
- **No fix to the live Streamlit app's sync** (*"We're switching anyway so it doesn't matter"*). Found the same day: the live app syncs only when the Home page loads to its end (the other pages `st.stop()` before `_run_startup_sync`), a sync that finds nothing waits 2 hours, and Home keeps its reads for 30 minutes and does not re-read after a sync — so a morning that goes straight to Training syncs nothing. The new app must not repeat any of the three (Phase 2/5: sync at the first open whatever the screen, update the screen when the sync ends, the retry rule above).
- **The cost does not decide the switch** (*"if it's not free it's not going to change the outcome of switching, ignore and continue"*). The free-tier and cold-start targets are still measured and reported, as facts for the design, not as a reason to stop.

## Open items
- `services/clients/local_cache.py` writes `.sync_state.json` next to the repo root with no setting to move it; the container makes /app writable for its user. Phase 2 did not need one (the engine runs no sync until Phase 9); Phase 9 can add a setting if the container needs one.
- Starlette 1.7 warns that its TestClient on httpx is deprecated (httpx2). Still one warning in Phase 2's 171 engine tests; move to httpx2 when Starlette drops the old client.
- **Import time on Cloud Run** was 2.3–5.5 s against 1.3 s on the PC. The precompiled image (2ff03cf) is not timed. If starts feel slow in Phase 5+, the next step is lazy imports of what Supabase mode never uses at start: gspread (0.19 s on the PC), notion_client (0.11 s), garminconnect (0.24 s).
- **Artifact Registry held 455.5 MB on 2026-10-19 after revision 7** (six images of 115-120 MB from the day's deploys, sharing layers; the free amount is 0.5 GiB-month). The clean-up deletes all but the two newest once they are a day old: check it on 2026-10-20, it should be about 190 MB. Check the size before the next deploy, because each image adds new layers until the clean-up has run.
- **The voice app's own Supabase project pauses too** after 7 days without use (it did before 2026-10-19). Not the health app's concern any more, but the owner should know it is why the voice app can stop reaching its database.
- **Supabase's Free plan pauses after 7 days without activity.** The new app syncs only when it is opened, so a week away still pauses it. Phase 9: a small daily keep-alive from the Worker's cron, or accept it.
- **The engine's starts grew to about 9 s** on revision 7 (imports 5.6 s against 2.5 s on revision 6: Phase 2 added the screen services). The lazy-import step above is the lever if a cold open feels slow on the phone.
- **The parse runs on save** (I63): the check-in and session saves run the keyword parse after the store answers. A parse failure leaves the item on the queue and never fails the save.
