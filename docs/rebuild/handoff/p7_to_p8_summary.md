# Phase 7 → Phase 8 handoff (2026-10-20)

**Done: the training week and the extra sessions.** Every p7 counter is 0 except the owner's training-week checklist (7 items: one week in the new app). Signed off under the owner's standing instruction; his week stays open in his batch.

**Address:** https://health.lauscher-worker.workers.dev (Worker 40674e06; engine revision health-engine-00011-sbc, commit 0caa08d).

## The week screen's states
- **The week:** the rollup banner (streak, this week against the plan with the next line, tallies); last week's line while the engine sends it; the Monday repeat notice; the Monday redo (two presses, then the engine's list of what moves); the carry (plain or in order) and the readiness shift; gate 1 (the one-tap reason, the card with the count and the four lifts, the flare-up asked twice); the retest notice; the strip with the engine's markers and its arrows clamped to the block; "Today"; another week's stored verdict.
- **The days:** today is the Phase 6 overview with the day's schedule note (or the rest view, or the gap). Another day: logged, missed (with the swap), future (with "Do this session today" and the engine's warnings), rest (its yoga flow; on today, how to train anyway), no block (the next block and the stranded days), damaged phases (said; nothing written; yoga still opens).
- **The "+" menu**, on the week page only (fault F18): yoga, an outdoor activity from Garmin, and the accessory session in the same guided flow, saved as its own kind with its note. Each screen has its own address under `/training/`.

## The move rules as built
- **Nothing moves until the owner answers.** The engine's week and day reads write nothing.
- **Each answer goes through the outbox.** A swap, a carry, a shift and a redo carry an id the phone mints; the engine applies an id once, so an answer sent again after a lost reply moves nothing twice. Gate 1's answers need none.
- **Every move goes through `scheduling.apply_schedule_change`** (Key Rule 18b: refused whole, never clamped). A refusal comes back with the rule's own words; the page says why, and OK clears it. Only a schedule answer can be cleared that way.
- **A question answered stays closed** until a read newer than the answer; Start waits until today's session is read again after a move. A "no" is remembered by the engine.
- **The same yoga or outdoor save sent again answers as it did** the first time; another save of it is told it is already logged.

## Engine changes (each with its tests)
`sessions.join_notes` (the accessory note before the typed notes; the Streamlit save uses it too); each yoga pose's hold; `gate1.how_text` (both apps); the yoga and outdoor savers' answer to the same save sent again. New: `scripts/week_saves_check.py` (the owner's week: each save stored once; the week's schedule notes by date; counts and dates only).

## What waits for Phase 9
- **The automatic writes** (the failed-week rule, the stored no-movement records) run only in the app `background_writer` names, still "streamlit". The new app shows the stored schedule and never judges a week itself.
- The Garmin daily sync and the weekly rollup sync on open move to the engine's scheduled sync (T5, T6).

## The owner's week
Not done yet: owner_checks.json p7. Swap one day; decline one proposed move; log one short extra session, one yoga flow and one outdoor activity; open a past day and a future day. Then `python scripts/week_saves_check.py --from <first day> --to <last day>` shows every save stored once.

## Phase 8 may rely on
The outbox's kept answers (`answerOf`), `lib/schedule.ts` for answers that must apply once, `lib/dates.ts`, `ui/timeline.tsx`, the mock's `e2e_run` and `e2e_week` cookies, the browser-test helper `tapToSave`, and the routes under `/training/` as the pattern for screens with their own address. Phase 8 moves the data tables and the manual sync buttons to Settings > Data.

## Open
- The owner's training week (7 items), then the week check.
- His answers to 4a (the length at Save) and 4b (no card photos).
- Carried: the Phase 6 real session (10 items), the Phase 4 iPhone checklist, the Phase 5 two mornings, the hosted-app check, the Strength reference, the voice app's address, the voice secrets.
- Artifact Registry: 704 MB before revision 11; the clean-up rule is set and had not run yet.
