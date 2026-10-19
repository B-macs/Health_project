# Rebuild state (rolling)

*The phone-app rebuild: see the "Phone app rebuild (from 2026-10-07)" section of CLAUDE.md. Update this file during every rebuild session.*


## Now
**Phase 3 — Design bake-off: the owner's design is on the preview address, 2026-10-19 evening.** He asked for the designs that evening (*"While we are here provide the UI Designs and ill decide one of them"*). Three directions were built on seeded mock data and shown (A Calm: the Oura look; B Board: the Whoop board; C Logbook: the research's warm-paper page, `docs/rebuild/design_research.md`). He chose none: *"None of those, make it more slick like oura style"*. One Oura-style design replaced them (never committed; this file and the report record them): a night sky whose glow takes today's readiness colour, glass cards, thin light numbers, three glowing score rings in a row, contributor bars, a white pill button; light mode the same in the morning. It runs as a Worker VERSION under the preview alias `design` (`wrangler versions upload --preview-alias design`); the production version is untouched. **Waiting for his yes or his changes**, then PROMPT 2 (design.md, the p3 counters, the report) and Phase 4.

**Phase 2 — signed off 2026-10-19 under the owner's standing instruction** (*"I said auto sign off of phase 2 and onwards, untill all the steps are completed not just step 2"*): every later gate is signed off the same way and he reviews them in one batch (CLAUDE.md, gate protocol step 5). The gate read 🟠: every counter 0 but `streamlit_app_broken`, his own check of the hosted app, which stays open in his batch (P2-11 stays false). History: archive.md; handoff: `handoff/p2_to_p3_summary.md`.

## Waiting on the owner (his batch)
1. **The hosted Streamlit app after the night's pushes** (Home, Training, Insights, Check-in; a day that already has a check-in opens filled in, and pain can go back to 0): owner_checks.json p2 `streamlit_app_opens`.
2. **The Strength reference for the engine**: the store's config row `strength_reference` (recommended) or a secret; on a yes, `python scripts/upload_strength_reference.py --apply`. Until then the engine's Strength screen answers 409 strength_reference_missing; the Streamlit app is unaffected.
3. **The Phase 3 design**: yes to the Oura-style preview, or what to change (open it from the Home Screen on the iPhone).
4. Carried: the voice app's address (for `p1_to_p2`); removing `[voxplot_supabase]` from the health app's secrets; the image store on 2026-10-20 (455.5 MB of the 0.5 GiB free tonight; about 190 MB once the clean-up has run).

## Next
- Phase 3 PROMPT 1: research, three directions (tokens + Today, the training screen mid-set, the Strength card, the tab bar) on seeded mock data, a preview address, the bake-off report. Then his pick, PROMPT 2 (gate), and Phase 4.

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
