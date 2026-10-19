# Phase 1 → Phase 2 handoff (2026-10-19)

**Done: Voice Training is its own app.** It runs on Streamlit Community Cloud from `B-macs/health-voice-training` with one secrets section, `[voxplot_supabase]` (`url`, `secret_key`), and its own Supabase project. The owner checked it on his phone: it opens from its Home Screen icon and records. Its address is still to be added here.

## What changed in the health app
- Three tabs (Home, Training, Insights); the Voice Training tab, its route and `views/sync.py` are gone, and an unknown page lands on Home.
- The `voice_training/voxplot` submodule and the four voice-only libraries are gone.
- No test was moved or retired; two parametrised cases ended with `views/sync.py`, the file they checked. Floor 4963 → 4970.
- The engine image never held Voice Training and was not rebuilt.

## Decisions to keep
- **Push automatically** after each finished step, only when the full gate passes, and say so each time (rebuild rule 11, changed 2026-10-19). Git uses the B-macs account through a repo setting; the PC also holds bmac-work.
- From Phase 0: one sync a day at the first morning open with the retry rule; transform the whole app first; no fixes to the live Streamlit app.

## Open
- The voice app's address.
- The Notion Phase 2 and Phase 9 pages still describe Notion as the store; update them before Phase 2.
- The voice project pauses after 7 days without use (it did before 2026-10-19).
- Check the image store on 2026-10-20 (about 190 MB expected after the clean-up).

## Phase 2 may rely on
Three health pages plus Check-in, no voice code; the engine and the Worker as Phase 0 left them; only the Streamlit app syncs until Phase 9.
