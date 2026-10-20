# Phase 5 → Phase 6 handoff (2026-10-20)

**Done: Today, the detail screens and the check-in, on the engine's numbers.** Every p5 counter is 0 except the owner's two mornings (6). Python 5556, Vitest 142, Playwright 47, parity 0 differences. Signed off under the owner's standing instruction; his two mornings stay open in his batch.

**Address:** https://health.lauscher-worker.workers.dev (Worker f249a9d9; engine revision 9, commit 5c00178).

## What exists
- **Today**: the week strip (one readiness ring per day, the same figure each day's card shows), the readiness card with the engine's verdict, badge and sync notices, sleep and strain tiles, the day's session. Arrows, the strip and a swipe change the day; the day lasts the visit and the engine decides the day to open on.
- **The detail screens**: readiness, sleep (the night strip, movement, debt, naps, vitals, the wake-time correction through the outbox) and strain (the split by body area, the source, the 7-day and 30-day charts). A night with no score shows only the reason line.
- **The check-in**: every field from the engine's ranges, today and the three days before; saved through the outbox, so it works offline.
- **Parity**: `scripts/rebuild_parity.py` over the 14 days to 2026-10-20 found 0 differences between the live engine and services/, and 0 sleep-rule violations.
- **Charts**: hand-drawn SVG from the engine's axes and tap bands; no library.

## Phase 6 may rely on
`ui/detail.tsx` and `ui/charts.tsx` (the frame, sections, contributor rows, line charts, strips, the reading panel), `ui/Sheet.tsx`, `useApp()` for the store, the request context and the day, the Screen/Body split for state tests, the outbox pattern with its own confirmation (the wake-time stepper), and `dev/fixtures.ts` typed against the contract.

## Open
- The owner's two mornings (p5) and the Phase 4 iPhone checklist (p4).
- H19 card photos: the chosen design has none — to confirm with him.
- The check-in form opens offline only after the app has read it once that day.
- The Oura re-authorise path on the phone comes later; the notice says "on the PC".
- The image store after two deploys today; check before the next engine deploy.
- Carried: the hosted-app check, the Strength reference, the voice app's address, the voice secrets.
