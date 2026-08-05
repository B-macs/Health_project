# Yoga Library — Clinical Review

Source of truth for the *data* is `services/yoga.py` (`YOGA_LIBRARY`). This
document is the human-readable rationale behind each pose's safety tag, so a
future yoga can be added/reviewed the same way. See `patient_profile.py` for
the numbered findings referenced below, and `services/rules.py` for the
deterministic `MOVEMENT_RULES` this catalogue cross-checks against
(`services.yoga.effective_safety()`).

Tags are **advisory, not enforced** — unlike `services/rules.py`, nothing here
blocks the "Complete" button. These are externally-sourced videos the patient
chooses to follow, not exercises this app prescribes; the tags exist so the
UI can surface an informed caution before/while following along.

**Severity legend:** `cleared` — no mechanism of concern · `caution` — do it,
but with the noted form cue · `contraindicated` — matches a hard MRI/rules.py
constraint; substitute or skip.

---

## 15-Minute Hip & Spine Mobility Flow

Video: https://www.youtube.com/watch?v=HzXkMnvqojE
Estimated RPE: 3/10 (restorative/mobility pace — feeds `session_au = rpe × duration_minutes`, same Foster-AU pipeline as the rehab plan, so it contributes to Strain/ACWR like any other logged session).
Suitable for: rest day, active rest day.

**Laterality convention:** a `(Right)`/`(Left)` suffix names the **front / worked
leg**, never the side receiving the stretch. For a pigeon those are the same leg;
for a **lunge they are opposite legs** — `Deep Lunge (Right)` is right-foot-forward
and stretches the *left* hip flexor. Resolved 2026-08-05; the `option_note` fields
are the internal evidence ("grab your left foot" sits on the *Right* hip opener).
Getting this backwards silently moves every laterality-specific caution onto the
wrong side, and both of the right-only mechanisms here (Coxa Saltans, post-Latarjet
shoulder) are the kind that matters.

| Pose | Start | Hold | Tag | Why |
|---|---|---|---|---|
| Seated Cross-Legged Side Bend (Shoulder Drop) | 00:20 | 30s | caution | **Re-identified 2026-08-05.** Authored as "Spine Mobilisation" and cleared as cat-cow-family spinal mobility — it is not that movement. Per the athlete: cross-legged, hand on the knee, drawing the shoulder down toward it, repeated both sides. That is lateral flexion with rotation, i.e. the *same* mechanism as the two Seated Side Stretches below, so it takes the same caution. Now also caught by the new `side bend` keyword in `services/rules.py`. |
| Seated Side Stretch (Right) | 01:00 | 30s | caution | Lateral flexion — right foraminal stenosis at L5/S1 (`rules.py`: "right lateral"). Keep it light, self-supported. |
| Seated Side Stretch (Left) | 01:40 | 30s | caution | Lateral flexion — left dorsolateral protrusions at L3/4, L4/5 (`rules.py`: "left lateral"). Keep it light. |
| 90/90 Hip Rotation | 02:20 | 30s | caution | Passes the right hip through flexion + external rotation — the exact position that triggers the documented right-hip snap (finding #4, Coxa Saltans). Cue neutral/internal rotation on the right. |
| Butterfly Forward Fold | 03:00 | 30s | **contraindicated** | Seated forward fold — end-range lumbar flexion loads the covered annulus tears at L3/4, L4/5 (`rules.py`: "forward fold"). Sit tall instead, or hinge from the hips with a flat back. |
| Walk the Dog (Down Dog pedaling) | 03:40 | 30s | caution | Mild spinal flexion under bodyweight load. Keep knees soft, back flat — don't force a hamstring-driven round. |
| Deep Lunge (Right) | 04:20 | 30s | cleared | Hip flexor/psoas stretch — directly addresses the psoas hypertonicity called out in the MRI downstream findings. Keep the pelvis neutral. |
| Deep Lunge Hip Opener (Right) | 05:00 | 30s | caution | Reach/backbend combination risks end-range lumbar extension + rotation. Keep the reach modest. |
| Half Pigeon Pose (Right) | 05:40 | 30s | caution | Front-leg hip flexion + external rotation on the right — the Coxa Saltans mechanism (finding #4). Neutral/slight-internal-rotation bias; ease out if it snaps. |
| Seated Twist (Left) | 06:20 | 30s | cleared | Gentle unloaded rotation — same family as thread-the-needle (already used in the release protocol, finding #5). |
| Down Dog | 07:00 | 30s | caution | Same reasoning as Walk the Dog. |
| Deep Lunge (Left) | 07:40 | 30s | cleared | Hip flexor/psoas stretch, no right-side-specific concern on this leg. |
| Deep Lunge Hip Opener (Left) | 08:20 | 30s | caution | Same reach/backbend reasoning as the right side — general extension/rotation caution, not Coxa-Saltans-specific (that finding is right-only). |
| Half Pigeon Pose (Left) | 09:00 | 30s | cleared | No right-hip mechanism on this side. Still avoid forcing external rotation to end range. |
| Seated Twist (Right) | 09:40 | 30s | cleared | Gentle unloaded rotation. |
| Straddle Forward Fold | 10:20 | 30s | **contraindicated** | Seated wide-leg forward fold — same mechanism as Butterfly Forward Fold. |
| Knee to Chest (Right) | 11:00 | 30s | cleared | Supine, unloaded flexion — decompressive for the L5/S1 facet base (finding #3). |
| Lying Twist (Right) | 11:40 | 30s | cleared | Supine, unloaded rotation — decompressive, same family as thread-the-needle. |
| Knee to Chest (Left) | 12:20 | 30s | cleared | Supine, unloaded flexion — decompressive. |
| Lying Twist (Left) | 13:00 | 30s | cleared | Supine, unloaded rotation — decompressive. |
| Happy Baby | 13:40 | 30s | cleared | Supine hip flexion, fully supported — decompressive for the low back. |
| Deep Relaxation (Savasana) | 14:20 | 30s+ | cleared | Passive rest. No mechanism of concern. |

**Net:** 11 poses cleared, 9 caution, 2 contraindicated (both forward folds).
Nothing here is unique to this routine — the forward-fold contraindication and
the lateral-flexion cautions reuse the exact keywords already in
`services/rules.py`'s `MOVEMENT_RULES` (`effective_safety()` cross-checks both
the pose's authored tag and a live `rules.check_movement()` call, so a future
`rules.py` addition is picked up automatically without re-authoring this file).
The two Coxa-Saltans cautions (90/90, Half Pigeon Right) are laterality-specific
to finding #4 and aren't expressible as a generic `rules.py` keyword, so they're
authored directly on the pose.

## Measured ROM baseline — 2026-08-05

Safety tags say nothing about how far into a pose this athlete can actually get.
That was measured separately and lives here rather than in `services/yoga.py`,
because it is observational data about one person, not a rule.

**Scale:** 1 = can barely enter the position · 100 = at the physical limit, no
stretch sensation left. **High is not good** — per
`patient_profile.PROFILE["hypermobility"]["training_implication"]`, a pose scoring
85 is one reached with no muscular stop, which is the load case this profile is
told to avoid. `Pred` is a prediction made from the clinical documents *before*
the athlete rated anything; it is kept so the profile's forecasting accuracy stays
auditable.

| Pose | Pred | **Measured** | Δ | Athlete's note (verbatim, condensed) |
|---|---|---|---|---|
| Seated Cross-Legged Side Bend | — | **40** | n/a | "unable to straighten arm at all when bending down, only can go about 60-70 percent down, restriction in hips" — prediction invalid, wrong pose assumed |
| Seated Side Stretch (R) | 62 | **60** | +2 | "bottom hand can get the forearm down but not elbow, but the hips are in flexion with tail bone under me" |
| Seated Side Stretch (L) | 68 | **65** | +3 | as above |
| 90/90 Hip Rotation | 33 | **85** | **−52** | "able to bring both knees to the ground with ease, also the difficulty of this is not that difficult" |
| Butterfly Forward Fold | 82 | **82** | 0 | "slight tightness in my hip flexors but nearly at the end of the stretch" |
| Walk the Dog | 76 | **76** | 0 | correct |
| Deep Lunge (R) | 57 | **57** | 0 | "I hold the position upright with the hips flexed… strongest stretch of the entire exercise along with half pigeon" |
| Deep Lunge Hip Opener (R) | 46 | **46** | 0 | "deep stretch in the quad… feels as if it's not even in flexion where it is past 180° but still in 170°" |
| Half Pigeon (R) | 30 | **40** | −10 | "can fix parallel but right buttock a fist off the floor, can forward fold over the shins and get a deep stretch in the glutes. **No pinch or click** at the front of the right hip" |
| Seated Twist (L) | 66 | **66** | 0 | "no lumbar pops normally… most of the twist comes from the upper body" |
| Down Dog | 64 | **64** | 0 | "right shoulder reaches back, whole body does small twist to the right. **Shoulder doesn't burn in 20-30 but more like 50-60s**" |
| Deep Lunge (L) | 50 | **57** | −7 | "right and left are the same — no blocking sensation on right side" |
| Deep Lunge Hip Opener (L) | 38 | **46** | −8 | "right arm can reach the back leg with ease, the quad generates a huge stretch" |
| Half Pigeon (L) | 48 | **40** | +8 | "it is the same as the right side so giving it the same score" |
| Seated Twist (R) | 68 | **68** | 0 | correct |
| Straddle Forward Fold | 80 | **25** | **+55** | "hips stuck in flexion with tail bone down, back fully rounds, unable to get shoulders over the hips unless greatly bending the knees. **One of the worst stretches in this list**" |
| Knee to Chest (R) | 85 | **85** | 0 | correct |
| Lying Twist (R) | 86 | **85** | +1 | correct |
| Knee to Chest (L) | 88 | **88** | 0 | correct |
| Lying Twist (L) | 88 | **88** | 0 | correct |
| Happy Baby | 80 | **80** | 0 | correct |
| Savasana | 100 | **100** | 0 | not a stretch |

**Accuracy:** 12 of 21 comparable poses predicted exactly, 19 of 21 within 10
points, MAE **2.05** excluding the two structural misses, signed bias −0.58.

**The two misses are the finding, and both are instrument errors:**

1. **Straddle, +55.** The prediction used the Beighton *palms-flat-to-floor*
   positive as evidence of hamstring length. A Beighton score is a **laxity
   screen**, not a ROM measurement — palms-to-floor scores the whole flexion
   chain (hips + lumbar flexion + gravity + locked knees). The real restriction
   is an inability to reach **anterior pelvic tilt in sitting**, reported
   independently in four seated positions here, and it is the proximal hamstring
   already listed in `imbalances.overactive_tight`.
2. **90/90, −52.** The prediction read `overactive_tight` as "short". It is
   **resting tone**, not length. Tone predicts behaviour under active control and
   load; it does not predict passive range.

**The prior that reproduces all 21 rows** — useful when rating a *new* yoga
before the athlete has tried it:

| Pose class | Expect |
|---|---|
| Passive, floor-supported, hamstrings slack | **80–88** |
| Requires anterior pelvic tilt against hamstring length | **25–65** — the one true restriction |
| Requires hip-flexor / rectus femoris length in extension | **40–57** — where tone findings legitimately apply |
| Loaded through the shoulder girdle | **~64**, endurance-limited at ~50–60s, not range-limited |

Synthesis and clinical implications: `patient_profile.py` `symptom_log`
2026-08-05. Dosing consequences for the scapular ask:
`docs/training/physio_brief_2026-08-16.md` §11.

## Suggestion rule

`services.yoga.suggest_for_day(day_kind)` returns the first catalogue entry
whose `suitable_for` list contains `day_kind` (`"rest_day"` or
`"active_rest_day"`). It's a plain filter, not a ranking — with one entry in
the library there's nothing to rank yet. When a second yoga is added, extend
this into an actual ranking (e.g. prefer higher `intensity` on an active rest
day vs. a fully passive rest day) rather than leaving it a first-match filter.

## Adding a new yoga

1. Add a `YogaSession` entry to `YOGA_LIBRARY` in `services/yoga.py` with its
   full pose list (`YogaPose` per pose: name, start/hold seconds, safety tag).
2. Review every pose against `patient_profile.py`'s biomechanical findings and
   `services/rules.py`'s `MOVEMENT_RULES`, the same way as above — add a row
   to a new table in this file.
3. If a pose matches a *generic* pattern not yet in `services/rules.py`
   (e.g. another "forward fold" variant), rely on the existing keyword rather
   than re-authoring a one-off tag. If it's genuinely novel, add the keyword
   to `MOVEMENT_RULES` so future poses/exercises benefit too.
4. Add a test to `tests/test_yoga.py` for anything the suggestion logic now
   needs to distinguish between the two entries.
