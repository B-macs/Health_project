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

| Pose | Start | Hold | Tag | Why |
|---|---|---|---|---|
| Spine Mobilisation | 00:20 | 30s | cleared | Gentle controlled spinal mobility — same family as `cat-cow` (already cleared in `services/rules.py`). |
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

**Net:** 12 poses cleared, 8 caution, 2 contraindicated (both forward folds).
Nothing here is unique to this routine — the forward-fold contraindication and
the lateral-flexion cautions reuse the exact keywords already in
`services/rules.py`'s `MOVEMENT_RULES` (`effective_safety()` cross-checks both
the pose's authored tag and a live `rules.check_movement()` call, so a future
`rules.py` addition is picked up automatically without re-authoring this file).
The two Coxa-Saltans cautions (90/90, Half Pigeon Right) are laterality-specific
to finding #4 and aren't expressible as a generic `rules.py` keyword, so they're
authored directly on the pose.

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
