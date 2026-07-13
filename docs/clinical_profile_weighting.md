# Clinical Profile Weighting

How the local, gitignored clinical profile documents in `Input_files/` (beyond `MRI_Lower_back.pdf`, which `patient_profile.py` is already built from) modulate training design. This is methodology only — no medical specifics live in this file, so it's safe to commit; the actual documents stay local per `.gitignore`.

Read this alongside `patient_profile.py` and whatever `Input_files/*.md` documents are present, per Key Rule 11 in `CLAUDE.md`, before authoring any new training block.

---

## 1. Injury history — 2-tier, not age-based

Weight is decided by **current relevance, not how long ago it happened**:

- **Symptomatic or recurring** (still causing issues, or with a known pattern of flaring under certain loads/positions) → **full weight**. Treated exactly like the current L5/S1 findings in `patient_profile.py` — shapes contraindications directly, feeds `services/rules.py`-style movement caution the same way.
- **Fully resolved** (no current effect, regardless of whether it was 6 months or 6 years ago) → **low weight**. Noted for context only. Does not shape exercise selection unless a specific movement pattern in the *new* program would directly re-stress that old structure (e.g. a resolved shoulder injury is still worth a beat of caution before prescribing heavy overhead pressing, even though it doesn't broadly constrain the plan).

Deliberately not a 3-tier age-based model — a resolved injury from last year gets the same low weight as one from a decade ago; an actively-recurring pattern gets full weight regardless of when it first appeared.

## 2. Hypermobility profile — persistent, not time-decayed

Hypermobility is structural, not something that resolves — the recency logic in §1 does not apply here at all. Default treatment until the actual document says otherwise:

- **Always weighted heavily**, every block, not decayed or reassessed the way injury relevance is.
- Shifts emphasis toward **controlled-range stability/strength work** and away from passive end-range stretching or ballistic/uncontrolled movement into end range.
- Shapes rep tempo and control cues broadly across the program, not just in specific exercises.
- Once the actual document is read, refine this default — it may flag specific joints needing more (or less) caution than a blanket rule, the same way `patient_profile.py`'s biomechanical findings are joint-specific rather than generic.

## 3. Strength training analysis — deloaded baseline, not a hard number

Currently: `Input_files/2025-training-year.md` (full-year strength log + movement-pattern analysis).

- Documented working weights/volumes are a **ceiling, not a starting point**. Stage 2 (or any block introducing/reintroducing external load) starts at a conservative percentage of those numbers — accounting for time away, reduced/rehab-focused training since, and the current injury — then the existing `+2.5 kg/session` progressive-overload rule (`docs/resume.md`, Stage 2 section) takes over from there.
- Equally important as the numbers: the **movement-pattern analysis** (what patterns were staples, what consistently broke down under fatigue, which structures under-fired during compound lifts vs. isolation work). This informs exercise *selection* and *sequencing* independent of load — e.g. a pattern that reliably lost bracing/control at moderate load in the past is a candidate for more conservative progression or an assistance-exercise emphasis, regardless of what absolute weight it reaches.
- Where the strength analysis's own injury notes overlap with the injury history document (§1) or `patient_profile.py`, treat them as the same finding, not double-counted — cross-reference rather than layering separate cautions for what's really one issue.
