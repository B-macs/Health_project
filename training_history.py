"""
TRAINING HISTORY — what was prescribed and what was required, kept for the
record.

Moved out of patient_profile.py on 2026-09-18, verbatim. The athlete's
instruction, when asked whether the pre-session release protocol and the
retired stage exit criteria belonged in his clinical profile: "Both come out
they're not my profile. Move it to somewhere more relevant like previous
training history."

The split this file exists to hold:

  * patient_profile.py is his POSITION — the imaging, the findings, the
    imbalances, the symptom log, the transitions that happened.
  * training_plan.py is what a session RUNS today. Every block authors its own
    release block there, which is why the copy below was a second statement of
    a live thing and could drift from it.
  * this file is the RECORD — what was prescribed, and what a stage change was
    once required to show.

NOTHING READS IT. It is history, and a rule that still binds belongs in
services/rules.py or in the block that runs it, not here. The stage criteria
carry their own "HISTORICAL" notes: physiotherapist sign-off was retired as a
gate on 2026-08-17, and the Stage 2B criteria were scored in
docs/hypothesis.md rather than used as a gate.
"""
from __future__ import annotations

HISTORY: dict = {
    # ─────────────────────────────────────────────────────────────────────────
    #  Pre-Session Release Protocol (runs at the START of every session)
    # ─────────────────────────────────────────────────────────────────────────

    "pre_session_release": {
        "rationale": (
            "Overactive glute medius/piriformis will compete with and inhibit "
            "glute max during activation work unless released first. "
            "5-minute release block before every session."
        ),
        "always_include": [
            "Upper Glute / TFL Self-Release (wall or fist) — 2 × 90s each side",
            "Piriformis Contract-Relax PNF — 3 × 5 cycles each side",
        ],
        "add_when_hip_focused": [
            "Right Posterior Hip Capsule Cross-Body Stretch — 3 × 60s right only",
            "Ischial Tuberosity Hamstring Release — 2 × 90s each side",
        ],
        # ── AS BUILT IN STAGE 2B (rewritten 2026-08-24) ──────────────────────
    # The 2026-08-14 version of this note is gone rather than amended: it was
    # wrong in three ways at once and each one would have misled somebody
    # reading it to find out what the block does. It said the anterior release
    # starts in week 3 (it starts day 1, ungated 2026-08-17); it said the
    # capsule stretch and the Coxa Saltans drill lead on hip-loaded days (both
    # retired 2026-08-17, each on a measurement); and it said the daily
    # front-of-hip protocol "continues alongside and is the larger dose", which
    # was never true — see the last paragraph.
    #
    # WHAT RUNS, in order.
    #   Hip-loaded days (2, 4, 5, 8, 9, 11, 13, 15, 16, 18, 20, 22, 23, 25):
    #     Ischial Tuberosity Hamstring Release 2 x 90 s + 1 x 45 s bilateral ->
    #     Upper Glute / TFL Self-Release 1 x 90 s EACH SIDE ->
    #     Piriformis PNF 1 x 5 cycles each side ->
    #     Anterior Hip Pressure Release 1 x 60 s each side, no pause between.
    #   Upper-body days (6, 12, 19, 26): the last three, no ischial release.
    #   Rest, travel and mobility days (3, 7, 10, 14, 17, 21, 24, 27): the
    #     anterior release ONLY — two minutes. See _s2b_release's own note for
    #     why that does not hole the withdrawal trial running on those days.
    #   Day 1: as a hip-loaded day. Day 28: no anterior release, because that
    #     screen's value is comparability with its Stage 1 and 2A selves.
    #
    # Preparation, first movement to first working rep, measured with both
    # sides counted: 13.28 min on hip-loaded days, 12.95 on runs, 12.42 on
    # flexibility days, 10.55 on upper days, 2.00 on the rest days. Inside the
    # athlete's 10-15 min band everywhere it applies.
    #
    # ── 2026-08-24: THE FRONT OF THE HIP IS NOW TRAINED, NOT ONLY RELEASED ───
    # The athlete's correction, and it reframes this whole section: "release is
    # only going to help the next 2-3 hours of training, without isometric
    # holds or strengthing the muscle will just return to its original
    # position. We need to only a few minutes of release to allow for
    # successful training but more time on holds and strengthing to get the
    # real benefits."
    #
    # He is right and this file already said so — imbalances' own caveat is
    # that overactive_tight is a list of muscles with high resting TONE, not
    # short muscles, and hypermobility.training_implications prescribes
    # controlled-range strength and stability work over passive end-range
    # stretching. Nothing had joined those two lines up. So the block gained
    # three items OUTSIDE this release block, appended to the session where no
    # preparation ceiling applies:
    #
    #   Half-Kneeling Knee-Hover Isometric  — hip-flexor strength at LENGTH.
    #     Days 2, 4, 6, 8, 11, 12, 15, 18, 19, 22, 25, 26. Dose steps by week:
    #     2 x 10 s -> 3 x 15 s -> 3 x 20 s per side.
    #   End-Range Psoas Isometric — the psoas is the only hip flexor still
    #     working above 90 degrees of flexion. Same days, 3 x (4 x 5 s) a side.
    #   Straddle lift-offs from a flat back — 3 x 8, flexibility days only
    #     (11, 18, 25), at the END of the session per the battery's pattern G.
    #
    # Front-of-hip minutes per week: release 13.5, holds and strength 19 in
    # week 1 rising to 30 in week 4. Before this change: release 7.5, strength
    # ZERO — Stage 1's Standing Hip Flexor Release and 90/90 Hip Flexor Hold
    # vanished at the Stage 2A transition with no recorded reason and nothing
    # ever replaced them.
    #
    # ⚠ ONE REMOVAL STILL STANDS, and it is a trade rather than a correction:
    #
    #   Right Posterior Hip Capsule Stretch and the Coxa Saltans path drill,
    #   out 2026-08-17. Each on its own measurement, not on the budget — prone
    #   internal rotation came back past 45 degrees BOTH sides with no
    #   asymmetry, so there is no capsular restriction to treat; and the click
    #   is gone in neutral rotation, which is what the drill existed to
    #   retrain. REVERT: a measured right-left internal-rotation gap beyond
    #   ~10 degrees, or the click reappearing in neutral.
    #
    # ── ⚠ "THE SECOND ZONE" ALWAYS MEANS ZONE 2. Settled by the athlete
    #    2026-08-24 after three wrong write-ups in one day: "update it to mean
    #    zone 2 each time." ─────────────────────────────────────────────────
    #
    # ZONE 2 IS THE SPOT AND THERE IS NOTHING ELSE TO IT.
    # docs/training/release_protocols_2026-08-10.md numbers two ball targets
    # for Anterior Hip Pressure Release. Zone 1 is the meaty pocket-corner just
    # below and OUTSIDE the point of the hip bone. Zone 2 is slightly INWARD
    # and higher, just inside it. His words: "the second zone is where I get
    # the pressure release during anterior hip flexor release, there is no
    # release in the outside point of the hip bone that I do for that
    # exercise."
    #
    #   • Zone 2 is what the block presses, and ONE SPOT PER SIDE IS THE DOSE.
    #   • Zone 1 does nothing for him. It is not a warm-up to it, not a first
    #     half of it, and not something owed at a later block.
    #   • Nothing here is half of anything, and no further spot is scheduled.
    #
    # HOW IT WENT WRONG, because the shape of the error is the useful part.
    # The block named ZONE 1 from day 1 and ran that way for a week. He was
    # ignoring the instruction and pressing zone 2 — which his very first
    # session note recorded on 2026-08-18 ("inside of my right") and which was
    # filed HERE as a protocol deviation instead of read as the finding. Then a
    # correction of his was written into training_plan.py, this file and
    # CLAUDE.md twice in opposite directions: first as "the block halved its
    # own dose", then as "zone 2 is an optional extra for a double-training
    # day". Both confident, both detailed, both wrong.
    #
    # ⚠ DO NOT CONFUSE THIS WITH THE ACCESSORY SESSION. Separate thing, and it
    # is what the phrase got mixed up with: the "+" button on the training
    # page, services/accessory.py, a whole 10-20 min mini-session rather than a
    # ball position. Opt-in, never once run, and its tier logic already shrinks
    # it to release-only whenever the main session is heavy (RPE >= 6), the day
    # is rest or assessment, or the engine has cut volume. When either is meant
    # in future, NAME IT: "zone 2" for the ball, "the accessory session" for
    # the button. Never "the second one".
    #
    # THE TWO REUSABLE RULES:
    #   1. A source document's dose is not a standard the block owes. Where the
    #      block and the document differ, that is a DECISION to record, not a
    #      deficit to close. Reading it as a deficit produced the original
    #      "halved its own dose" story.
    #   2. PIN THE REFERENT BEFORE WRITING A CORRECTION DOWN. Asking cost one
    #      sentence; guessing cost three files and two commits. Ordinals are
    #      the trap — "the second zone", "the other block" — especially when
    #      the word was introduced by whoever is doing the writing.
    #
    # WHAT WAS ACTUALLY WRONG WITH THE BLOCK, and it stands: twelve of its days
    # carried NO front-of-hip work at all — the eight rest, travel and mobility
    # days, and the four upper-body days — while the desk day is the exposure
    # the protocol treats. That is the gap the 2026-08-24 change closed, at one
    # spot per side, which is the dose.
    #
    # The 2026-08-14 note's line that the daily protocol "continues alongside
    # and is the larger dose" is REMOVED, not amended: it described something
    # that was not running, and it made the in-block dose read as a fraction of
    # a whole when it is the whole.



    # ── 2026-09-11: AS BUILT IN BLOCK B ──────────────────────────────────
    # The release block is unchanged in CONTENT and re-coded in SHAPE:
    #   Hip-loaded days (squat days, run days, cluster days, race day):
    #     Ischial Tuberosity Hamstring Release 90 s RIGHT then 90 s LEFT, no
    #     pause (it was two bilateral sets with 45 s between; his 2026-09-10
    #     note: "Why is there a pause between a stretch?") ->
    #     Upper Glute / TFL 90 s each side -> Piriformis PNF 5 cycles each
    #     side -> Anterior Hip Pressure Release 60 s each side.
    #   Press days: the last three.
    #   Mobility and rest days: the anterior release only (withdrawal trial).
    # Phase 2 is the raise and ONE activation item: Single-Leg Glute Bridge on
    # lower days, Scapular Wall Slide on upper days. DEAD BUG IS OUT — one set
    # of six is potentiation, he said so twice, and nothing in the record
    # names deep core as failing to fire before a squat. REVERT: the brace
    # failing before rep 8 on the squat with the glute bridge alone in
    # preparation. PRONE Y-RAISE IS OUT of the press day's preparation (two
    # sets of strength work in a one-activation-item slot; face pull and the
    # retraction isometric cover the tissue; the timed single-arm hold is
    # finding #6's instrument). REVERT: a right-left Y-hold gap over 15% or
    # instability under the press.
    #
    # Preparation costs ~21 min on a squat day and ~17 on a press day ONCE
    # THE CHANGEOVERS ARE PRICED AT THEIR MEASURED COST (74 s per floor item);
    # the 10-15 min figure above was computed at 30 s a change. The items are
    # the same; the clock was wrong. Not re-opened, recorded.

    "add_when_right_hip_loaded": [
            "Right Hip Tendon Path Drill (Coxa Saltans) — 2 × 10 reps right only",
        ],
    },

    # ─────────────────────────────────────────────────────────────────────────
    #  Stage Advancement Criteria
    #  stage_1_exit_criteria: evaluated at Day 21 (2026-07-19) — MET. Physio
    #  signed off on external load; see stage_transitions below for the record.
    #  stage_2_exit_criteria: to be evaluated at Day 28 (2026-08-16).
    # ─────────────────────────────────────────────────────────────────────────

    "stage_1_exit_criteria": {
        "pain": "All 5 functional positions ≤ 2/10 consistently",
        "tightness": "Average tightness score ≤ 3/10 over last 7 days",
        "pain_free_days": "≥ 14 consecutive pain-free training days",
        "hip_click": "Coxa Saltans snap controllable with neutral rotation cue",
        "upper_glute": "Measurable reduction in resting grip/tightness of upper glute",
        "hinge": "Pain-free hip hinge to full range (arms past knees)",
        "physio_sign_off": "HISTORICAL — this is what actually gated the Stage 1 → 2 "
                            "transition on 2026-07-19. Retired as a gate 2026-08-17; not a "
                            "forward requirement. See stage_transitions.",
    },

    # Evaluated at the Stage 2A Day 28 reassessment. Physiotherapist sign-off
    # for Stage 2B was obtained 2026-08-12 — see stage_transitions below.
    "stage_2_exit_criteria": {
        "pain": "≤ 2/10 across all working lifts, no worsening trend through the block",
        "hip_click": "No increase in Coxa Saltans frequency under loaded squat/split-squat work",
        "shoulder": "No instability sensation or left-tilt compensation under the incline-press loading introduced this block",
        "working_loads": "Final working loads logged on all six primary lifts (Goblet Squat, Incline DB Press, RDL, Hip Thrust, Lat Pulldown, Single-Arm DB Row) as the new baseline",
        "functional_screen": "McGill Big 3, Single-Leg Balance, Hip Hinge Full Range, Walk+Stair — matching or beating the Day 21 Stage 1 screen",
        "physio_sign_off": "HISTORICAL — retired as a gate 2026-08-17, before this was "
                            "evaluated. Both decisions were made against the recorded "
                            "measurements. Not a forward requirement.",
    },

    # Draft — evaluated at the Stage 2B Day 28 reassessment (2026-09-13), which
    # is also where Block B is authored. Mirrors stage_2_exit_criteria's shape.
    # Not yet evaluated.
    #
    # Note what is NOT here: a distance target. Block A is not trying to reach
    # 10 km, and judging it against the race would be judging the wrong block.
    "stage_2b_exit_criteria": {
        "pain": "≤ 2/10 across all working lifts and all runs, no worsening trend through the block",
        "running_tolerance": "NO left anterior hip / Sartorius signal at any point in the six-run "
                             "progression. This is the criterion the whole running introduction is "
                             "conditional on — it has strained twice before, both times from "
                             "running volume, and a signal here stops the build rather than slowing it",
        "hip_click": "No increase in Coxa Saltans frequency under loaded squat work OR under "
                     "running. A clean verdict releases the horse-stance and Cossack deferrals in "
                     "cluster_a_mechanics; record the outcome either way, since the hold is judged "
                     "on its condition and never expires by date",
        "shoulder": "No instability sensation or left-tilt compensation under incline press",
        "interscapular": "Tightness ≤ 3/10 and pain 0/10, with the desk raised — the 2026-08-12 "
                         "reading of pain 1/10 is the number to beat, and the intervention being "
                         "tested is the desk height, not the training",
        "load_recovery": "Working loads back at or above their pre-travel values by the end of "
                         "week 4, having stepped down one increment on re-entry",
        "flexibility_baseline": "Battery run cold on three separate mornings, a pattern label "
                                "recorded, and at least two cluster sessions completed",
        "sign_off": "THE ATHLETE'S OWN, against the recorded measurements. No "
                    "physiotherapist confirmation is required now or in the future — his "
                    "standing decision, 2026-08-17, superseding the physio_sign_off line "
                    "that used to sit here. The reasoning channel it replaces it with is "
                    "docs/hypothesis.md: pre-registered predictions scored at every block "
                    "boundary, so decisions rest on what was measured rather than on an "
                    "appointment that does not exist.",
    },

}
