# Phase 2 → Phase 3 handoff (2026-10-19)

**Done: the engine API.** 50 endpoint operations over services/ answer every screen of the app, each answer the services' own, with the caller's day from X-Local-Date. All 282 KEEP or MOVE rows of the screen inventory map to an endpoint with a test, or to the phone with a reason. Every p2 counter is 0 except the owner's own check of the hosted Streamlit app; self-rated 🟠.

## What changed
- 55 view rules moved into services/ with their tests; 27 faults fixed (F27 found while building the strain endpoint: the drill-down's stage start was read from the server's today).
- The `background_writer` setting gates every background write in both processes; the engine's sync, its manual syncs and the Oura login refuse until Phase 9.
- Each process's local copy of Supabase is pulled again after 15 minutes; a row written during a pull is kept.
- The keyword parse runs on save (I63).
- The engine runs as `health-engine-00007-fs7` (commit 5c05933); it starts in about 9 s.
- Main gate 4970 → 5501.

## For the owner
- Check the hosted app after the night's pushes (Home, Training, Insights, Check-in; a saved check-in opens filled in and pain can go back to 0).
- The Strength reference: a config row (recommended; `python scripts/upload_strength_reference.py --apply`) or a secret.
- Sign off the gate. Phase 3 is the design bake-off and needs his choices.

## Phase 3 may rely on
Typed answers for every screen (`shared/openapi.json`, `app/src/generated/api.ts`); charts with their axes and tap details; the guided flow walked in advance, so a session runs offline; idempotent saves on ids the phone mints; fixed text in the phone's strings file; the Streamlit app as the background writer until Phase 9.
