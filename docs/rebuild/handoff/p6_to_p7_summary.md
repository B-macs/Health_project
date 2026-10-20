# Phase 6 → Phase 7 handoff (2026-10-20)

**Done: the training session on the phone, from Start to Save, with timer alerts.** Every p6 counter is 0 except the owner's real-session checklist (10 items: one gym session in the new app). Signed off under the owner's standing instruction; his session stays open in his batch.

**Address:** https://health.lauscher-worker.workers.dev (Worker deed0fd2; engine revision health-engine-00010-hpf, commit 7a751f5).

## What exists
- **The session store and its states.** Start downloads the whole session (GET /api/training/session: every exercise as dosed today, its seeded numbers and captions, the flow walked in advance with the bells and the timer-start marks) and mints the session id and the exercise ids once. The state lives in the database's `session` row from Start to Save: the overview (no row), the flow (`step` < steps), the save screen (`saving`), saved (`savedId`, then the heart-rate answer in `hr`). It survives a reload, an app kill and an app update; an update waits while it exists. `lib/training.ts` (the state and its taps), `loadState` (a row from an earlier version takes the new fields at their start).
- **The flow.** One exercise at a time: the day line, today's progress and the list (done, now, next), the set chips, the steppers (reps, weight by the engine's increment, band over the engine's tiers; the second side follows the first until edited), the timer, Next/Then, the previous session and where today's numbers came from, how to do it, a note, Back (30 taps) and Skip (asks first). A walk or run with Garmin takes its minutes from the watch (8 s, else the save asks again when online). A warning shows only when the engine sent one.
- **Timers and sounds.** Timers run on timestamps (`lib/timers.ts`): no drift after a background; a timer that ended while hidden says when it ended and moves on only on a tap. A rest starts on any arrival; a hold starts by itself only when a timer that ran out brought the flow to it — the engine's mark (`guided_flow.timer_starts`, moved out of the Streamlit page, which now asks the same function). Bells on Web Audio (`lib/sounds.ts`): 1 strike next rep, 2 falling swap sides, 3 set over, 4 exercise over (the walk's ending); a rising pair at the rest's end; 880 Hz ticks at 3-2-1. The audio type is "playback": the bells play with the silent switch on and over other audio (the owner's choice).
- **The save.** The review (the watch's time or the engine's estimate, the dosed sets, the weight), the watch check before the save, the rating, the length question past the engine's threshold, the engine's load, notes; one save through the outbox with the ids minted at Start (stored once however often sent); "Saved on the phone", then "Saved"; then the heart-rate match (measured against the rating, the day's activities to choose from, or why there is none).
- **Timer alerts (T87).** Settings > Timer alerts. As the app goes to the background with a countdown running, the phone asks the Worker for an alert at its end; coming back cancels it. A Durable Object on the Worker keeps the subscription and one alert and sends it on the second (Web Push, aes128gcm and VAPID, a declarative message iOS shows by itself).
- **Engine additions:** `guided_flow.hold_starts_next` and the walk's `timer_starts`; `plan_days` on the session plan; the heart-rate match takes the session the phone saved (`training_session.sets_by_name`).
- **The field check:** `scripts/session_field_check.py --date <day>` compares the owner's real session with the last Streamlit session of the same kind, names and counts only.

## What iOS allows and refuses (from the docs; his session confirms)
- **Screen stays on:** the Wake Lock API works in Home Screen apps from iOS 18.4 (WebKit bug 254545); asked again each time the app comes back.
- **Bells with the silent switch on:** `navigator.audioSession.type = 'playback'` (Safari 17+); it stops other audio.
- **Audio after the lock screen:** Lauscher found it can fail; to be checked in his session.
- **Background:** a page runs no code while the phone is locked, so a timer cannot ring then; the Web Push alert covers it. Web Push needs the Home Screen app and a tap for permission (iOS 16.4+).

## Phase 7 may rely on
`TrainingTab` (the tab's three states and `noSessionReason`), `SessionFlow` with an accessory plan (the same flow; `plan.kind` 'accessory', `ask_length_above_minutes` null), `useApp().alerts`, the outbox pattern for a save with its own confirmation, `dev/session_fixture.json` from the engine's walk, the mock's `/api/dev/received` and `/api/dev/sessions`, and the browser-test helpers (`startTraining`, `leaveSession`, the muted `test`).

## Open
- The owner's real session (owner_checks.json p6, 10 items, the alerts included) and `scripts/session_field_check.py` after it.
- His answers to 4a (the length at Save: stop the clock at the last tap — recommended — ask "When did you finish?", or keep as now) and 4b (no card photos — recommended yes).
- Carried: the Phase 4 iPhone checklist, the Phase 5 two mornings, the hosted-app check, the Strength reference, the voice app's address, the voice secrets.
- The image store: 599 MB on 2026-10-20 before revision 10, over the 0.5 GB free amount until the daily clean-up removes the 2026-10-19 images; billed on the month's average.
