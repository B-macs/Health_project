# Phase 8 → Phase 9 handoff (2026-10-20)

**Done: Insights.** Every p8 counter is 0 except the owner's comparison checklist (9 items: each Insights screen against the Streamlit app, and one assessment when one is due). Signed off under the owner's standing instruction; his comparison stays open in his batch.

**Address:** https://health.lauscher-worker.workers.dev (Worker 00b0373a; engine revision health-engine-00012-qq2, commit 6fb84c9).

## The screens
- **Insights** (`/insights`): the four cards (Strength, Flexibility, Metabolism, Cardio coming soon), then Engine data, Warnings, Trends and Sleep architecture.
- **Strength:** the headline and calibration, the five series with this week against last, the chart on the engine's axis, the work without load, the body parts with core's hold time, the imbalances. Until the 2025 reference is stored, the engine refuses and the screen says why.
- **Metabolism:** kg fat and fat-free with the date, the split, six measures over Week/Month/Year/All with the engine's steps, the chart on the engine's scale, the gym scan's two readings with their age, every other figure marked measured, worked out or not measured.
- **Flexibility and its capture:** unreadable, empty, in progress, the report or no pattern with the readings it waits on. The capture: the cold gate, each step the engine's order at the owner's place (LOCK first), the engine's early answer, Pause and Resume.
- **Engine data, Warnings, Trends, Sleep architecture:** as the Streamlit tabs, every number and chart top from the engine.
- **Settings > Data:** the parse queue, the session checks, the three tables (two with a date range), the sleep-fusion shadow report, the syncs (off: "Syncs run in the old app until the switch-over").

## The rules as built
- **No rule and no scale in the phone.** The engine sends every figure, word, scale and chart top.
- **No figure fused or added** (scale with scan, strength with tonnage): checked in the code and by the engine's own tests.
- **The capture never chooses a test.** It shows the engine's order at the place the owner moves to; the early answer is the engine's. It writes straight to the engine (not through the outbox), because the engine decides each next test; the draft is stored after every step.

## Engine changes (each with its tests)
The metabolism chart's scale (`metabolism_screen.chart_axis`, used by the Streamlit view too); the flexibility answer's cluster name, stop slot, early reason and reading names; the AU and volume charts' tops; each region's share; the trend timeline oldest first with its 0-10 scale (`insights.score_timeline_axis`); a night's strips in the Sleep screen's shape.

## Parity
28 days to 2026-10-20: **0 differences**; Strength refused alike. A first run showed 3 differences in the fused sleep debt. **Cause: the Python version.** The gate computed the services' side under Python 3.11 (`venv/`); the engine runs 3.12, whose `sum()` adds floats more exactly, so a 28-night average crossed a 2-decimal rounding step. The parity run now uses `.venv-engine` (3.12).

## What waits for Phase 9
- The five manual syncs (drawn off; the engine refuses them until `background_writer` is "engine").
- The Oura login (needs the redirect URI, the owner's step), the scheduled syncs, the automatic writes.

## Open
- The owner's Insights comparison (9 items).
- The Strength reference upload.
- **Python 3.11 against 3.12**: a rounded figure can differ by one step between the two. For the Phase 9 side by side: compare under 3.12, or let the services add with `math.fsum` (the owner decides).
- Carried: the Phase 7 week, the Phase 6 session, the Phase 5 mornings, the Phase 4 checklist, the hosted-app check, answers 4a and 4b, the voice app items.
