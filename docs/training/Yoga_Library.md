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

## 16-Minute Shoulder, Scapula & Neck Flow

Video: *(not yet sourced — the pose list is authored, the video is not)*
Estimated RPE: 3/10 (restorative/mobility pace — same Foster-AU pipeline).
Suitable for: rest day, active rest day.
Primary focus: shoulder flexion · thoracic extension · scapular control ·
cervical · relaxation.

Added 2026-08-05. The hip/spine flow above touches the upper body almost
nowhere, and the two live upper-body questions in the record — the interscapular
endurance gap (`symptom_log` 2026-08-03) and the overhead restriction — had no
unloaded session addressing them at all.

**The dosing constraint that shaped this flow.** Down Dog produces interscapular
burn at a measured **50–60 s**. Every scapular hold here is **25 s, deliberately
below that threshold**. These are *positioning* drills, not the endurance
prescription — long isometric holds are a prescription change and belong to the
physiotherapist on 2026-08-16 (`docs/training/physio_brief_2026-08-16.md` §1).
An earlier draft of this flow built 55 s holds *around* the measured onset; that
was caught in review as pre-empting a decision that is not this codebase's to
make. **Do not lengthen these holds without the physio's sign-off.**

| # | Pose | Start | Hold | Tag | Why |
|---|---|---|---|---|---|
| 1 | Supported Diaphragmatic Breathing (Supine, Knees Bent) | 00:20 | 60s | cleared | Sets the rib position the rest of the session works from. Loads neither shoulder nor neck. |
| 2 | Supine Arms-Overhead Reach (Elbows Toward the Floor) | 01:30 | 45s | caution | **The athlete's own failed test** — he cannot rest both elbows on the floor overhead. Unloaded and self-limited: never a partner pressing the elbows down, which puts passive end-range pressure into a post-Latarjet shoulder whose stability is muscular, not ligamentous (finding #6). Keep the low back flat — **arching is how the lumbar spine buys fake overhead range**. A folded towel under the low back tells you the moment you arch. |
| 3 | Cat-Cow (Mid-Range, Thoracic-Biased) | 02:25 | 45s | cleared | **Mid-range only**, thoracic-biased. The extension half stops well short of end range — L5/S1 retrolisthesis plus activated osteochondrosis means end-range lumbar extension is contraindicated. |
| 4 | Thoracic Extension over a Rolled Towel | 03:20 | 60s | caution | Towel at **mid-thoracic (T6–T10)**, the region finding #3 identifies as sitting-stiffened, and **not** at the lumbar spine. Placement is the entire safety margin: too low and this becomes the contraindicated end-range lumbar extension. |
| 5 | Thread the Needle (Right Arm Under) | 04:30 | 45s | cleared | Unloaded thoracic rotation — the family already used in the pre-session release protocol. |
| 6 | Thread the Needle (Left Arm Under) | 05:25 | 45s | cleared | As above, other side. |
| 7 | Extended Puppy Pose | 06:20 | 45s | caution | Passive shoulder flexion with the **lats on stretch** — the one pose here that reaches the lat, otherwise the gap in this athlete's overhead ladder. Let the chest sink rather than pushing into it. |
| 8 | Prone Scapular Retraction Hold (Arms Low, Palms Down) | 07:15 | **25s** | caution | **Arms low, not a prone T** — 90° of abduction moves a post-Latarjet shoulder toward apprehension. 25 s is deliberately below the measured 50–60 s onset. |
| 9 | Wall Forearm Press Hold (Elbows Below Shoulder Height) | 08:00 | **25s** | caution | **Elbows stay below shoulder height** — above it the drill drifts toward abduction + external rotation. Serratus-biased. Below threshold, same reason. |
| 10 | Supported Chest Opening over a Rolled Towel (Arms at 45°) | 08:45 | 60s | caution | **Arms at 45°, not a supine 90/90 T** — 90° abduction with external rotation is the apprehension position for anterior instability. The towel runs *along* the spine, so the load is gravity on an open chest rather than an external frame levering the joint. |
| 11 | Seated Neck Tilt — Right Ear to Right Shoulder | 09:55 | 40s | caution | **Self-generated only, no hand overpressure** — at Beighton 6/9 the cervical spine is the last place to hang on ligament, and `symptom_log` 2026-07-31 records asymmetric flexion tightness with mechanical crepitus. |
| 12 | Seated Neck Tilt — Left Ear to Left Shoulder | 10:45 | 40s | caution | As above. **Left is the documented dominant side** of the interscapular/cervical pattern, so expect asymmetry and do not chase it into end range. |
| 13 | Levator Scapulae Stretch (Left) | 11:35 | 40s | caution | Levator scapulae is the anatomical bridge between the cervical spine and the superior medial scapular angle — **the corridor the ache migrates along** in `symptom_log` 2026-08-03. Releasing it *before* the scapular work would be ideal; here it follows, because the holds above are positioning rather than loading. |
| 14 | Levator Scapulae Stretch (Right) | 12:25 | 40s | caution | **Not merely "the other side."** `symptom_log` 2026-08-03's CORRECTION 2 records the pattern as **bilateral with left dominance** — right on 07-16 and 07-23, left from 07-21 — and it was the left-lateralised framing that obscured a postural-endurance driver. Treating the right as an afterthought reintroduces exactly that error. |
| 15 | Supine Rest with Arms Overhead on a Cushion | 13:15 | 60s | cleared | Supported overhead position with no reach demand — the shoulder **rests at range** rather than working to get there. |
| 16 | Deep Relaxation (Savasana) | 14:25 | 60s | cleared | Passive rest. |

**Net:** 6 cleared, 10 caution, **0 contraindicated**. Three distinct mechanisms
drive every caution: the post-Latarjet apprehension position (poses 2, 8, 9, 10),
end-range lumbar extension (3, 4), and cervical overpressure at Beighton 6/9
(11–14). None of them is expressible as a generic `rules.py` keyword without
losing the position detail that makes each one safe, so all are authored on the
pose.

---

## Retests — questions carried back to the pose that can answer them

`YogaPose.retest` holds an open clinical question on the pose best placed to
close it. Three are set, all on the hip/spine flow, all from the 2026-08-05
baseline:

| Pose | Question | Baseline |
|---|---|---|
| Seated Cross-Legged Side Bend | Is the restriction still in the **hips** rather than the spine, and does the arm still refuse to straighten? Also confirm the movement is still as described — **the whole re-tag depends on it.** | 40/100, *"only can go about 60-70 percent down, restriction in hips"*, arm would not straighten at all. This is the pose that first showed the seated posterior-tilt pattern, so it is the cheapest place to see that pattern move. |
| Down Dog | **Time the burn.** Note whether onset moves and whether the rightward twist persists. | Onset **50–60 s**, right shoulder reaching back, small whole-body twist right. The **only** quantified endurance figure for the interscapular gap, and physio brief §11 asks for the hold prescription to be set against it — so a second reading is worth more here than anywhere else in the flow. |
| Deep Lunge Hip Opener (Left) | Does the right shoulder still reach the back foot with ease, and does the front of the joint feel stable there? | Reaches easily, no instability, quad is the limiter at 46/100. Finding #6 says right-shoulder stability is **maintenance-dependent and regresses when training lapses** — so this is a cheap unloaded check on whether that has started, and a change here shows well before a loaded one does. |

---

## Measured ROM baseline — 2026-08-05

Safety tags say nothing about how far into a pose this athlete can actually get.
That was measured separately and lives here rather than in `services/yoga.py`,
because it is observational data about one person, not a rule.

> **⚠ These 22 ratings do NOT feed the Flexibility sector, and must not be made
> to.** `services/flexibility.py` scores rungs from **passive / isometric /
> active** readings taken in a **locked** position, measured cold. A 1–100
> self-rating of a yoga pose answers none of those three questions, and no pose
> here isolates a locked joint. **Nothing in the flexibility model inherits a
> value from this table**, `flexibility_baselines.LEGACY_POSE_DEPTH_RATINGS_2026_08_05`
> keeps it as provenance only, and a test pins that nothing computes from it.
>
> Its value is clinical and historical, and it is considerable: **the straddle
> row is what identified the seated pelvic-tilt deficit that the whole of
> Cluster A is now built around.** 25/100, his worst of the 22, with the note
> that his back fully rounds — which is the compensation, not the restriction.

**Scale:** 1 = can barely enter the position · 100 = at the physical limit, no
stretch sensation left. **High is not good, clinically** — per
`patient_profile.PROFILE["hypermobility"]["training_implication"]`, a pose scoring
85 is one reached with no muscular stop, which is the load case this profile is
told to avoid. Note this is a *clinical* reading of the rating, not a scoring
rule: an early version of the Flexibility sector encoded it as a two-sided band
that penalised high values, and **that model was refuted and deleted** — a
rating measures how far he got, not whether he controlled it, and inferring one
from the other was the error. See `docs/resume.md` § FLEXIBILITY. `Pred` is a
prediction made from the clinical documents *before* the athlete rated anything;
it is kept so the profile's forecasting accuracy stays auditable.

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
   independently in four seated positions here.

   **Restated against the Jan-2025 gym goniometry**, which reads hamstrings
   89°/86° and calls them *Normal*: this is not short hamstrings, it is **normal
   hamstring length with no reserve**. Long-sitting upright is already ~90° of hip
   flexion with the knee straight, so at 86–89° he is at the limit just sitting up
   with his legs out, and every further degree has to come from the spine. An
   ordinary hamstring under an exceptional lumbar spine is what produces a 25.
   Holds only if that reading is a straight-leg raise — the protocol is
   unrecorded, so confirm it at the next scan.
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

`services.yoga.suggest_for_day(day_kind, *, focus_hint=..., recent_slugs=...)`.
**Rebuilt 2026-08-05 from a first-match filter into a real ranking**, which is
what the previous docstring promised once a second session existed.

Deterministic lexicographic sort over a key tuple where **every element is
smaller-is-better**, slug last so the result never depends on `YOGA_LIBRARY`'s
list order:

1. **`focus_hint` miss count** — a caller asking for shoulder work gets the
   shoulder session. This is the whole reason a second session exists.
2. **Repeat penalty** — a slug in `recent_slugs` sorts later, so **alternating is
   the default** rather than always returning the first match.
3. **Intensity, direction depending on the day** — an *active* rest day prefers
   the higher-intensity option, a plain rest day the lower one.
4. **Slug**, for a strict total order.

No argument is required, so existing single-argument call sites keep working.

> **⚠ Unresolved: the app offers yoga on rest days, which the flexibility model
> calls the *worst* window for adaptation.** A restorative flow there is fine; an
> adaptation-seeking session is not, and **nothing in the code distinguishes
> them** — which is why `services.flexibility.flexibility_window()` accepts
> `is_rest_day` and deliberately does *not* downgrade on it (downgrading would
> penalise the harmless case). Agreed fix, 2026-08-06: an **`intent` field
> (`restorative` | `training`) on `YogaSession`**, with rest days restricted to
> restorative. **Deferred to the training-schedule overhaul** by athlete
> **RESOLVED 2026-08-06.** The Cluster A prescription's dosage section settles
> it: a flexibility *cluster session* is adaptation-seeking by definition and is
> never a rest-day activity, so `services.flexibility.flexibility_window` now
> returns `poor` for a rest day. **A restorative yoga flow on a rest day is
> still fine** — that is this library's business and it is a different thing.
> The `intent` field is therefore no longer needed to answer the scheduling
> question, though it would still be useful for surfacing the right flow.

## Adding a new yoga

1. Add a `YogaSession` entry to `YOGA_LIBRARY` in `services/yoga.py` with its
   full pose list (`YogaPose` per pose: name, start/hold seconds, safety tag,
   `safety_note`, optional `option_note` and `retest`). Set `primary_focus` and
   `intensity` deliberately — `suggest_for_day` ranks on both, so a session with
   a vague `primary_focus` will never be the one a focused caller gets.
2. Review every pose against `patient_profile.py`'s biomechanical findings and
   `services/rules.py`'s `MOVEMENT_RULES`, the same way as above — add a row
   to a new table in this file.
3. If a pose matches a *generic* pattern not yet in `services/rules.py`
   (e.g. another "forward fold" variant), rely on the existing keyword rather
   than re-authoring a one-off tag. If it's genuinely novel, add the keyword
   to `MOVEMENT_RULES` so future poses/exercises benefit too.
4. Add a test to `tests/test_yoga.py` for anything the suggestion logic now
   needs to distinguish between entries.
5. If a pose can answer an open clinical question, put that question in its
   `retest` field with the **baseline value written into the question** — a
   retest that does not carry what it is being compared against is a note, not
   a measurement.
6. **Do not author a hold longer than the measured interscapular onset (50–60 s)
   under shoulder-girdle load** without physiotherapist sign-off. That duration
   is a prescription, and prescriptions are not this codebase's to write.
