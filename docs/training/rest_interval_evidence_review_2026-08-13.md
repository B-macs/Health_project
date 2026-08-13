# Rest intervals — the evidence, and what it means for the next block

> ## ⛔ REQUIRED READING BEFORE THE NEXT BLOCK IS AUTHORED
>
> **Gated on the EVENT, not on a date** — the `HRV_GARMIN_HOLD` idiom, and the
> same gate as `docs/training/warmup_evidence_review_2026-08-10.md`. Read this
> before authoring a day of the next block. Checkable the same way: state how it
> influenced the plan, or say plainly that it did not and why.
>
> **⚠ THE QUESTION THAT PRODUCED THIS DOCUMENT RESTED ON A FALSE PREMISE, AND
> THE PREMISE IS THE MOST IMPORTANT FINDING.** The athlete asked whether rest
> should go to 3–5 minutes, and whether the right and left sides of a unilateral
> exercise need a 1-minute pause between them, *"because my current plan only
> has 45 s to 1 min after doing both sides."* The clock reading is right. The
> **per-muscle** reading is not — and per-muscle rest is the quantity every
> study in §1 measures. `views/training.py:3527` has no rest timer on the
> right→left transition, so **the other side's working time IS the first side's
> rest**. Actual per-side rest in Stage 2A is **75–105 s**, not 45–60 (§0.1).
>
> **The three answers, all priced in §3:**
>
> ```
> Split right/left with 1 min?   NO   — pooled effect SMD −0.02 [−0.14, 0.09]
>                                       cost +9/+9/+11 min per session
> Go to 3–5 min between sets?    NO   — ACSM 2026 issues NO rest prescription
>                                       cost +23.5 min per session
> Change anything at all?        ONE  — 90 s → 120–180 s on the top 1–2 heavy
>                                       compounds, STAGE 2B ONLY, cost 1–3 min
> ```
>
> **The prerequisite that makes the "one" conditional (§3.3):** rest duration is
> **not logged anywhere in this repo**. At a fixed rep target, shortening rest
> does not reduce work — it inflates RPE (Farah 2012, §1.4) — and `session_au`
> is computed from RPE. **A rest change therefore moves Strain and ACWR with no
> change in the work performed, and nothing in the data can tell the two apart.**
> That is key rule 2b's failure by another door. It sits beside the per-set
> warm-up flag as a blocking prerequisite, not a follow-up.
>
> **Four things that will bite if skipped:** §0.2 (the duration estimator
> silently omits every unilateral exercise's second side — **5.5–6.9 min per gym
> session**, so every time-budget conversation to date has run on numbers that
> understate the session) · §1.4 (**the whole "longer rest preserves reps"
> literature uses sets to failure**, and at RPE 5–6 with a prescribed rep count
> there is no rep to lose) · §1.6 (going heavier does **not** cleanly require
> longer rest — one study found the *lighter* load needed *more*) · §1.9 (**one
> fabricated paper and two miscited claims** are in circulation on exactly this
> topic, and one of them is the only study that would answer the question).
>
> **⚠ Read §2.4 before dosing the Stage 2B isometric holds.** It is out of the
> scope of the athlete's question and is the most consequential thing here.

*Written 2026-08-13, three days before the Day 28 reassessment (2026-08-16).
This is a REVIEW, not a protocol and not code. Nothing here is implemented.
Nothing in `training_plan.py`, `services/` or `views/` is touched. It exists so
that on the day, the rest-interval question is a lookup rather than an argument,
in the same idiom as `docs/training/warmup_evidence_review_2026-08-10.md` and
`docs/training/flexibility_integration_2026-08-16.md`.*

**Method.** Six parallel evidence sweeps, each independently fact-checked by an
adversarial verifier instructed to refute rather than confirm. Citations that
could not be confirmed against a primary source are marked as such rather than
dropped silently — §1.9 records what that caught. Every repository claim in §0
and §3 was verified directly against the working tree on 2026-08-13.

**Evidence grades**, same scale as the warm-up review: **A** = meta-analysis or
systematic review · **B** = controlled trial in trained humans · **C** = single
small trial or special population · **D** = mechanistic reasoning · **E** =
expert framework, no direct trial support.

---

## 0 · Three findings that came before the literature

Facts about the current system, checkable in the tree today. All three reframe
the question.

### 0.1 The plan does not have 45–60 s of rest — it has 75–105 s per muscle

`views/training.py:3527` states it in a comment: *"Right→left side transition
has no rest timer."* `tp_phase` only enters `"resting"` once **both** sides are
done (`:3512`, `:3548`, `:3592`). The sequence is:

```
right side → left side → coded rest → next set
```

So the right side's actual rest between its own sets is **the left side's
working time plus the coded interval**:

| Exercise | Coded rest | Other side's work | **Actual per-side rest** |
|---|---|---|---|
| Full Side Bridge (3 × 45 s/side) | 45 s | 45 s | **~90 s** |
| Pallof Press, cable (3 × 10/side) | 60 s | ~20–30 s | **~80–90 s** |
| Single-Arm DB Row (3 × 10/arm) | 60 s | ~20–30 s | **~80–90 s** |
| Single-Leg Glute Bridge (3 × 8 × 3 s) | 60 s | ~24 s | **~84 s** |
| Bulgarian Split Squat (3 × 8/leg) | 75 s | ~20–30 s | **~95–105 s** |
| Pallof Press Hold (3 × 30 s/side) | 45 s | 30 s | **~75 s** |

**Every unilateral exercise in Stage 2A already delivers 75–105 seconds of
per-muscle rest.** That is inside the zone where Singer 2024 found the return
flattens (§1.3) and well above the <60 s threshold below which Grgic 2018 still
reports robust strength gains.

The bilateral exercises are the ones actually at the coded number, and they are
the ones §3.1 is about.

### 0.2 The duration estimator omits every unilateral exercise's second side

`services/sessions.py:879-891` (`exercise_duration_seconds`) computes a `hold`
as `sets × hold_seconds` and a `reps` set as `sets × 20`. **It never reads
`laterality`.** `estimate_duration` (`:893-895`) just sums that plus 30 s per
exercise and a 120 s base.

So a Full Side Bridge coded 3 × 45 s **each side** is estimated at 135 s of work
when the real work is 270 s. Measured across every Stage 2A gym day:

| Session | Estimate shown | Uncounted 2nd-side work | True working estimate | Coded rest |
|---|---|---|---|---|
| Squat + Press + Core (d1/8/15/22) | 40 min | **+6.2–6.9 min** | ~46–47 min | 16.5 min |
| Hinge + Pull + Core (d3/10/17/24) | 39 min | **+5.5 min** | ~44.5 min | 16.5 min |
| Unilateral/Glute (d5/12/19/26) | 35 min | **+6.1–6.5 min** | ~41–41.5 min | 13.0 min |

Two things follow. First, **every time-budget conversation in this repo to date
has run on numbers that understate the session by 5.5–6.9 minutes** — including
the warm-up review's "~30 min working portion" against which the 10–15 minute
preparation ceiling was set. That ceiling is the athlete's and is not reopened
here; the *ratio* it was justified by is worse than stated, which strengthens it
rather than weakening it.

Second, **rest is already 13.0–16.5 minutes per session** — 37–42% of the
displayed estimate, 32–36% of the corrected one. Rest is charged
`(sets − 1) × rest_seconds` (`services/sessions.py:885-889`), so it is the
second-largest line item in a gym day before a single second is added.

*This is a reporting defect, not a training defect — the work is prescribed
correctly and performed correctly, only the estimate is short. It is recorded
here because §3 prices two proposals in minutes, and the denominator matters. It
is not fixed by this document.*

### 0.3 90 seconds is the ceiling in the entire repository

Across all 117 coded `rest_seconds` values in `training_plan.py`, the distinct
values are **0, 30, 45, 60, 75, 90**. Only **four exercises** reach 90 s: Wall
Sit (Isometric Quad) and Wall Sit (Extended Duration) in Stage 1, and **Goblet
Squat** and **Romanian Deadlift** in Stage 2A.

Those last two are the right two. But the current 90 s is delivered on a 12.5 kg
dumbbell at RPE 6–7 — and §1.3's one guideline-level claim for a trained lifter
is *">2 min to maximise 1RM"*, which starts to bind only when the load does.

---

## 1 · What the literature actually says

### 1.1 The guideline everyone quotes has been withdrawn

**ACSM's 2026 position stand** (Currier et al., *MSSE* 58(4):851-872) is an
umbrella review of **137 systematic reviews, >30,000 participants**. It
classifies inter-set rest duration as:

- **"does not impact" voluntary strength** — 2 reviews, n=982, quality of
  evidence 63%
- **"cannot determine" for hypertrophy** — 4 reviews, n=265, QoE 44%

and **issues no rest-duration prescription anywhere in the document** (grade
**A**).

That reverses ACSM's own **2009** stand (Ratamess et al., *MSSE*
41(3):687-708), which is the source of nearly every rest number in circulation.
Its grades are worth stating, because they are almost never quoted with them:

| 2009 recommendation | Evidence category |
|---|---|
| ≥2–3 min, core exercises, strength | **B** |
| 1–2 min, assistance exercises | **C** (non-randomised/observational) |
| 1–2 min, hypertrophy, novice/intermediate | **C** |
| 2–3 min, power | **D** (panel consensus) |
| **"3–5 min" for 1–6RM work** (Summary section only) | **none — no grade at all** |

**No rest-specific recommendation in the 2009 document ever reached category A**,
and the 3–5 minute figure — the one the athlete's question was pitched against —
carries no grade and contradicts the body of its own document.

**NSCA 2019** (Fragala et al., *JSCR* 33(8):2019-2052, adults ≥50 y) has **no
rest row in its recommendations table at all**. Rest appears only narratively:
*"1.5 to 3.0 minutes … based on toleration of the protocol with a need for
symptom-free progression."* No grade attached. **That framing — tolerance, not
a physiological target — is the only guideline language that fits a rehab
context, and it is unsupported by any grade of evidence** (§2.2).

### 1.2 Where longer rest helps, the mechanism is volume load — not rest

**Longo et al. 2022** (*JSCR* 36(6):1554-9) is the causal test, and the only
study that crosses the two variables (grade **B**). Four unilateral
knee-extension arms, 10 weeks, volume load deliberately equated across rest
conditions:

| Arm | Rest | Volume | Quad CSA |
|---|---|---|---|
| LI | 3 min | native | **13.1%** |
| VLI-SI | 1 min | **+ extra sets** | **12.9%** |
| SI | 1 min | native | 6.8% |
| VSI-LI | 3 min | **cut to match short-rest** | 6.6% |

**Volume load sorted the groups; rest did not.** All four arms gained
26.5–31.2% on 1RM with no between-arm difference.

This is corroborated in the direction that matters: **de Souza 2010** found a
9.4–13.9% volume deficit from decreasing rest produced *no* difference in CSA,
1RM or isokinetic torque; **Fink 2017** found outcomes independent of rest
(30 s vs 150 s) at 40% 1RM taken to failure; **Attarieh 2026** found 20 s and
2 min identical when volume was equated by repetitions (untrained, single-joint
— grade **C**).

The hormonal rationale that once justified short rest is dead and should never
be repeated: **West et al. 2010** (*J Appl Physiol* 108(1):60-7) produced large
acute GH/IGF-1/testosterone elevation and measured **zero** extra hypertrophy
(p=0.25) or strength (p=0.43). This matters because it is the stated
justification for de Salles 2009's widely-quoted **"30–60 s for hypertrophy"**.

### 1.3 Where longer rest does pay, and how much

Two findings, both pointing at **2 minutes**, neither at 3–5.

**Grgic et al. 2018** (*Sports Med* 48(1):137-151; 23 studies, 491 participants,
413 M / 78 F; systematic review, **no pooling** — grade **A** with a caveat):

> "Robust gains in muscular strength can be achieved even with short RIs
> (<60 s)"; **">2 min appears necessary to maximize strength gains in
> resistance-trained individuals"**; 60–120 s sufficient in untrained.

⚠ **Those thresholds are synthesis judgement, not effect-size-derived.** The
review pools nothing. It is nonetheless the strongest statement available in
this direction, and it is the sole basis for §3.0's one supported change.

**Schoenfeld et al. 2016** (*JSCR* 30(7):1805-12; RCT, 8 wk, n=21 **trained**
men; grade **B**): 3 min beat 1 min for squat 1RM, bench 1RM and anterior-thigh
thickness. ⚠ Triceps was a **trend only (p=0.06)**, elbow flexors NS, endurance
NS, and the abstract reports no percentages, effect sizes or CIs.

**Where it flattens.** Singer et al. 2024 (*Front Sports Act Living*
6:1429789; Bayesian meta-analysis, 9 RCTs, 188 participants — grade **A**, but
only 2–3 studies used trained participants):

| Site | SMD, longer − shorter | Credible interval |
|---|---|---|
| Arm | 0.13 | [−0.27, 0.51] |
| Thigh | 0.17 | [−0.13, 0.43] |
| Whole body | −0.08 | [−0.45, 0.29] |

All three cross zero. The authors' own words: a small benefit above 60 s
*"perhaps mediated by reductions in volume load"*, but they **"did not detect
appreciable differences in hypertrophy when resting >90 s"** — and NSCA's
30–90 s hypertrophy guidance *"warrants reconsideration."*

**And the ceiling.** **Ahtiainen et al. 2005** (*JSCR* 19(3):572-82; crossover,
**6 months**, n=13 trained men, volume-matched) found **2 min and 5 min
produced similar gains in muscle mass and strength** (⚠ confound: intensity was
deliberately not held constant). **Scudese et al. 2015** (*JSCR* 29(11):3079-83),
testing near-maximal **3RM** bench, concludes practitioners may use
**"a time-efficient minimum of 2 minutes"** without impairing repetition
performance.

### 1.4 Why that mechanism cannot operate at RPE 5–6 — the decisive point

The entire "longer rest preserves reps" literature — Willardson & Burkett 2005
and 2006, Miranda 2009, Senna 2011, Scudese 2015 — uses **sets taken to failure
at RM loads**, where residual fatigue immediately costs a repetition because
there is no buffer.

**At 4–5 reps in reserve against a fixed rep target, there is no rep to lose.**

The one study that tested a fixed submaximal rep scheme found the cost surfaced
somewhere else. **Farah et al. 2012** (*Percept Mot Skills* 115(1):273-282;
n=19, five exercises at 50% 1RM, fixed reps, 30 s vs 90 s; grade **C**): with
30 s rest, RPE rose between sets in **all five** exercises; with 90 s, in
**three of five**. ⚠ The study reports **no repetition-completion data**, so it
cannot show reps were preserved — only that RPE rose. That is enough for the
conclusion drawn here, and not enough for a stronger one.

**Mechanistic support** (grade **D**). Refalo et al. 2023 (*Sports Med Open*
9:10, n=24 trained) quantified the effort gradient: velocity loss across six
sets was **−8.1% (M) / −1.1% (F)** at 3-RIR versus **−28.8% / −19.6%** to
failure; at 4 min post-exercise the decrement was **−0.05 vs −0.15 m/s** (ES
1.87 [1.26, 2.47]), with 3-RIR fully recovered at 24 h. Phosphocreatine
resynthesis is **biphasic** — fast component t½ 21–22 s, slow component
**t½ >170 s** (Harris 1976) — and it is the slow, pH-sensitive tail that a short
rest truncates. A set of 10–12 at RPE 5–6 does not generate the acidosis that
makes that tail long.

> ⚠ **Say plainly that this is reasoning, not measurement.** **No study has ever
> manipulated rest interval while holding effort at RIR 4–5.** No study has
> measured PCr or force recovery after a submaximal non-failure set — every time
> course available (Harris 1976, Bogdanis 1995) used all-out efforts or
> contractions to fatigue, and Bogdanis explicitly notes its own recovery is
> *slower* than after longer dynamic exercise, i.e. it is the worst case.
>
> **And the only direct test disagrees.** Singer 2024's subgroup analysis found
> training to failure vs stopping short **did not meaningfully influence** the
> rest × hypertrophy interaction (thigh: 0.31 [−0.03, 0.61] vs 0.27 [−0.02,
> 0.51]). That rests on three studies per arm with intervals crossing zero, and
> its "non-failure" studies stop at ~1–3 RIR, not 4–5 — so it is **weak evidence
> of no effect rather than evidence of no effect**. It does not settle the
> question. It is recorded because it is the only direct evidence and it points
> the other way.

### 1.5 The right/left question

**Answer: the contralateral side counts as rest, and a deliberate 1-minute pause
between sides is not supported. But this is inference from an adjacent
literature, not a direct finding.**

**It has essentially never been studied directly.** Exactly one study manipulated
the rest interval between the two sides of the same exercise: **Lacerda et al.
2024** (*J Bodyw Mov Ther* 37:360-5) separated the two limbs by either **20
minutes or 24 hours** and found no difference in the second limb's force or
quadriceps activation. That is n=10, untrained men, one isolation exercise, and
its **shortest** interval is longer than any real side transition (grade **C**).
**Nobody has measured reps, load or bar velocity on the second side as a
function of how long you waited.**

**The pooled non-local muscle fatigue estimate** — **Behm et al. 2021**
(*Sports Med* 51(9):1893-1907; multilevel meta-analysis, **52 studies, 278
effect sizes, 303 participants**, median n≈6 per group; grade **A**):

| Outcome | SMD | 95% CI |
|---|---|---|
| **All outcomes** | **−0.02** | **[−0.14, 0.09]** |
| Strength | **+0.11** | [0.01, 0.21] — nominally in the *better* direction |
| Power | −0.01 | [−0.24, 0.22] |
| Endurance | −0.54 | [−0.95, −0.14] — the only impaired subgroup, imprecise |

Trivial **and precisely estimated** — not an underpowered shrug. Heterogeneity
was substantial (I²=67.4%) and **none** of the tested moderators explained it:
not design, homologous vs heterologous muscle, upper vs lower body, training
status, sex, age, timing, or fatigue-protocol severity.

> ⚠ **One superseded finding to drop.** Halperin, Chapman & Behm 2015 (*EJAP*
> 115(10):2031-48) is widely cited for a lower-limb/upper-body split — non-local
> fatigue in 76% of lower-limb vs 32% of upper-body outcome measures. That is
> **vote-counting**, the method that manufactures subgroup structure out of
> differential statistical power, and the later pooled analysis **by the same
> senior author** found upper-vs-lower was not a moderator. Superseded, not a
> companion finding.

**Where an effect is found, it is a few percent, and the variance swamps it:**
Davies 2023 (preprint, n=10 trained, 10×10 @ 50% 1RM — the only realistic
training stimulus in the set) **−8% [−13, −3]**; Gioda 2024 **−8.5% ± 16.2%**
(⚠ SD nearly twice the mean, so much of that sample showed no change or an
increase); Halperin 2014 found 2–8% in rested knee extensors and **nothing at
all** in rested elbow flexors (p≥0.33).

**Well-conducted nulls sit beside these, sometimes from the same lab:** Benitez
2023 (n=20, p=0.962, mean difference −1.34 kgf [−8.72, +6.04] — read as "no
detectable effect at n=20", the interval is wide); Arora 2015 (n=16, **Behm's
own lab**, nothing across force, activation, onset timing or postural stability
despite −44.8% in the fatigued limb); **Power 2021** (n=32 incl. varsity
athletes — **the largest and most sex-balanced primary sample** — no non-local
fatigue *and* no non-local potentiation).

**The dose threshold is what settles it.** Crossover fatigue is **cumulative**,
not present after one effort. **Doix 2013** needed **two** 100-second maximal
bouts before the resting limb dropped at all (after one: −4.9%, non-significant).
**Doix 2018** found nothing after a single 30-second maximal effort. **Power
2021** found nothing after 4 × 5 s MVICs. **A single set per side is very
unlikely to matter.**

**Time course**, for completeness — **Zahiri 2024** (n=17): contralateral MVIC
−15.8% at 1 min (d=0.72), −8.5% at 3 min (d=0.30), **+8.9% at 5 min (d=0.15,
ns)**. ⚠ The fatigue protocol was **two 100-second continuous maximal isometric
contractions**, nothing like a working set; and a +8.9% mean at d=0.15 implies
enormous between-subject variance, so the correct statement is *"no longer
detectable at 5 min"*, not *"recovered by 5 min"*.

**Two adjacent worries that do not hold up.** de Oliveira 2023 (n=22) found
unilateral exercise produced **smaller** heart-rate and rate-pressure-product
rises than bilateral, even to concentric failure. And **bilateral deficit is
irrelevant here** — it is a maximal-force phenomenon of *simultaneous* bilateral
contraction, inconsistent in existence and magnitude, and says nothing about
sequential unilateral work. Do not cite it as a mechanism.

**Where the uncertainty is real:** **rate of force development** and
**endurance/time-to-failure**. Kawamoto 2014 (n=12) found contralateral RFD down
**23.7%** and **34.6%** while MVC fell only 4.4–7.1% (⚠ that paper's abstract
and results section disagree with each other on significance — p=0.002 vs "only
a trend", p=0.09). **If single-leg jumps are ever programmed, the case for real
inter-side rest is much stronger.** It does not describe a split squat at RPE 6.

### 1.6 The requirement does not scale cleanly with load — and may run backwards

This is counter-intuitive and matters directly for Stage 2B.

**Willardson & Burkett 2006** (*JSCR* 20(2):396-9, n=16 trained) tested **80%
and 50% 1RM** at 1/2/3 min: 3 min was superior at **both** loads, and *"the
sustainability of repetitions was **not** significantly different between
loads"* (p=0.849).

**Senna et al. 2017** (*J Hum Kinet* 58:197-206, n=16 trained) found the
opposite of intuition: at **80% 1RM, 3 min was statistically identical to 5 min**
(p>0.900), while at **50% 1RM, 5 min still beat 3 min** (p=0.005) — because more
total repetitions means more accumulated metabolic disturbance per set.

Both are sets to failure, and they disagree with each other on whether load
interacts at all. **Do not assume that going heavier in Stage 2B automatically
requires longer rest; the acute literature does not support a clean load
gradient.** What it does support is Grgic 2018's **training-status** threshold,
which is the basis for §3.0.

### 1.7 Buying time back — structures, not shorter rest

**The core insight: a superset does not shorten the rest a given muscle receives
— it fills that rest with work for a different muscle.** That is why supersets do
not contradict §1.3. Burke 2025 (n=43 trained, 8 wk) still rested **2 minutes
after each pair**; the 36% saving came from deleting the dead clock between
exercise A and exercise B.

| Structure | Best evidence | Time saved | Cost |
|---|---|---|---|
| **Agonist-antagonist pairing** | Zhang et al. 2025, *Sports Med* 55(4):953-975 — 19 studies, 313 participants, mostly trained (**A**) | **~37%**, efficiency SMD 1.74 [0.46, 3.01], p=0.01 | No detected difference in reps, volume load, 1RM or hypertrophy — ⚠ **non-significant with wide intervals, not demonstrated equivalence**. Real costs: lactate 0.94–1.13, energy cost 1.93, RPE 0.77. **Configuration is the whole intervention:** antagonist pairing yields *more* reps (+0.68 [0.20, 1.17]); **same-muscle pairing significantly loses volume load (−1.08 [−1.72, −0.44])**. |
| Upper/lower alternating | García-Orea 2022, *Sports* 10(7):110 (**C**, n=9 vs 10) | 45% (42.2 → 23.3 min) | Identical bar velocity, but **total squat reps fell 19%** (p<0.05) while bench was unaffected. Squat was **first** in the pair — so this is not "the second exercise suffers", it is that the more demanding lift paid for having its rest occupied. |
| **Cluster sets / rest redistribution** | Latella 2019 (25 studies); Jukic 2020 (32); Jukic 2021 (17) (**A**) | **None.** Rest redistribution is time-neutral *by construction*; cluster sets *add* intra-set rest. | Chronic payoff ≈ zero: strength SMD −0.06, hypertrophy −0.03, endurance −0.38 **favouring traditional**. The benefit is within-session fatigue attenuation, never saved time. **Wrong tool for this problem.** |
| Drop sets | Sødal 2023, *Sports Med Open* 9:66 (**A**) | ½ to ⅓ the time | Hypertrophy SMD 0.155 [−0.199, 0.509], p=0.392 — ⚠ **only 2 of 6 studies reported any timing**, authors attribute the null to low power. Iversen warns against them on heavy compounds for safety. |
| Rest-pause | Prestes 2019, *JSCR* 33(S1):S113-21 (**C**, n=18) | −38% (57 → 35 min) | Equal 1RM, greater thigh thickness (11±14% vs 1±7%) — ⚠ **SD exceeds the mean**. Takes a set to failure and repeats it: poor fit where a joint is symptomatic. |

> ⚠ **One dissenting data point on recovery cost.** Against Zhang 2025's pooled
> null, **Weakley 2017** (*EJAP* 117(9):1877-89, n=14 rugby players,
> volume-equated, magnitude-based inference) cut session time 42.3 → 24.0 → 17.7
> min across traditional → superset → tri-set but measured **CK at 24 h of
> +8.2% / +42.7% / +24.4%**. Note the pattern is **not monotonic** — the most
> compressed condition had a *smaller* 24-h CK rise than the less compressed one
> — so "more compression, more cost" is **not** in the data. Note also the
> inversion: immediately post-session the **traditional** condition had the
> largest CMJ drop (−6.2%) and recovered by 24 h. **How a session feels at the
> end predicts the opposite of the 24-hour state.**

**And the anchor time-efficiency review's own advice is not "cut rest."**
Iversen, Norum, Schoenfeld & Fimland 2021 (*Sports Med* 51(10):2079-95 — note
the fourth author is **Fimland**, not Fisher; the warm-up review cites the same
paper) recommends **1–2 min untrained, ≥2 min trained**, and buys time by
restructuring the session, cutting exercise count, and cutting general warm-up
and stretching — *not* by shortening per-muscle rest. It states its own scope:
written for people who name time as a barrier, explicitly **not** for those
optimising adaptation.

### 1.8 Rest for isometric and tendon-directed work

The inter-set rest literature does not cover this modality at all. **Bohm et al.
2015** (*Sports Med Open* 1:7; meta-analysis, 27 studies, 264 participants)
states explicitly that **no rest-interval guidance exists anywhere in the
review**. The 2-minute figure appearing in tendon protocols is a convention
carried between labs, never a tested optimum.

What the tendon literature *does* establish, and it cuts against long holds:

- **Bohm et al. 2014** (*J Exp Biol* 217(22):4010-7; n=39, 14 wk, **matched
  total loading time**; grade **B**): four **3-second** contractions with 3 s
  rests produced **stiffness +57%, modulus +51%**; one **12-second** hold
  produced **+25% and +17%** (p=0.025, p=0.021). **Same time under load. Longer
  holds were worse.**
- **Kubo et al. 2001** (*J Physiol* 536:649-55, n=8, volume-matched): 20 s holds
  increased tendon stiffness; **1 s contractions did not**, despite equal
  strength (+31.8% vs +33.9%) and hypertrophy gains. Sets a **floor** on
  contraction duration.
- **Tsai et al. 2024** (*Sci Rep* 14:6875; n=52, 16 wk, five protocols; grade
  **B** — the largest): 90% MVC, **4 × 3 s per set, 2 min between sets**, total
  loading **180–300 s per WEEK**. *"Against our hypothesis, the temporal
  coordination of loading and recovery did not notably affect the intervention
  outcomes"*; no volume effect; **low volume beat high volume for stiffness**
  (p=0.04).
- Intensity is the variable that matters: Bohm 2015 found **>70% MVC gives
  stiffness SMD 0.90 [0.71, 1.08], I²=0%**, while **≤70% gives 0.04 [−0.46,
  0.53]** (difference p<0.00001).

> ⚠ **The 45-second hold does not have the pedigree it is given.** It originates
> in **Rio et al. 2015** (*BJSM* 49:1277-83), which is **n=6**, is about
> **analgesia not adaptation**, and has **failed to replicate three times**:
> Holden 2020 (n=21, not sustained at 45 min), **van der Vlist 2020 (n=91,
> outright null**, essentially the same dose), and Clifford 2020 (meta-analysis,
> 10 RCTs, n=294, level-3 evidence, p=0.19 — *"the response to isometric
> exercise is variable both within and across tendinopathy populations"*). The
> **30-second** hold traces to Baar 2019, an **n=1 case study**, justified by
> stress relaxation from *ex vivo* tissue sections.
>
> ⚠ **The "10 min loading / 6 h refractory" rule is cell work.** Paxton et al.
> 2012 is an **in vitro engineered ligament**. It is the sole origin of the
> rule. Robling 2001 is **rat bone**. Neither is human tendon in vivo, and the
> Baar annex's own §6 gates already say so.
>
> ⚠ **HSR set/rep/rest structure could not be verified.** Kongsgaard 2009 and
> Beyer 2015 establish that heavy slow resistance works and is durable
> (VISA-A 74 at 12 wk → 87 at 52 wk; compliance 92% vs 78% eccentric), but the
> **"3 sets, 6RM, 2–3 min rest"** structure commonly attributed to them could
> not be confirmed from primary sources. **Do not encode it as fact.**

### 1.9 Evidence integrity — three things not to cite

The adversarial fact-check caught three claims in circulation on this exact
topic. Each one, taken at face value, would change the recommendation. Recorded
here so the next search does not re-import them.

**1. A paper that does not exist.** Two web searches returned a confident
description of a three-arm trial: *"36 natural amateur bodybuilders, 10 weeks,
60 s vs 90 s vs 180 s, vastus lateralis +3.9% / +8.0% / +8.8%."* **No such paper
exists** — a Europe PMC title/abstract sweep of the 2023–2026 rest-interval
literature does not contain it. It is a search-summariser confabulation, and it
is **the only trial that would directly answer the 60-vs-90-vs-180 question**,
which is presumably why one was invented. **Do not use those numbers.**

**2. A claim not present in the source.** A widely-circulated claim holds that
the AHA's 2024 resistance-training statement (Paluch et al., *Circulation*
149(3):e217-e231) says one minute is insufficient for HR/BP recovery in cardiac
rehab. **That sentence is not in the statement.** What it says, verbatim, is
that after six months individuals free from contraindications may use heavier
loads (>80% 1RM) *"with longer rest intervals between sets."* No number.

**3. Three routinely miscited primaries.**

- **Fink 2018** is quoted for 9.93% vs 4.73% arm growth at 30 s vs 3 min. Those
  are **within-group** changes; the paper reports **no significant between-group
  difference** — and it varied rest *and* load together (30 s + 20RM vs 3 min +
  8RM), so it isolates neither. Its one usable finding is that acute GH
  elevation did not correlate with CSA change.
- **Senna 2011** is quoted for multi-joint lifts needing more rest than
  isolation lifts. The paper's own conclusion is the opposite: multi- and
  single-joint exercises *"exhibited similar repetition performance patterns and
  RPE, independent of the rest interval length."* The real split in that data is
  **free-weight vs machine**.
- **Jukic 2020** is quoted for "5.09% squat / 5.68% bench" from cluster sets.
  Those figures are **not from that meta-analysis** — they are from a single
  primary study (Cuevas-Aburto 2022). Never present them as pooled estimates.

⚠ Also excluded from every conclusion above: **Davidson & Barillas 2025**
(medRxiv preprint) — its own abstract **uses the SMD sign incoherently**
(−0.74 said to favour longer rest, −0.66 to favour shorter, −0.64 to favour
longer). The direction cannot be recovered. **Do not rely on it.**

---

## 2 · Four things about this athlete that break the generic answer

### 2.1 The cost of short rest lands on RPE — and RPE is a load input here

This is the finding with software consequences, and it is why §3.3 is a
prerequisite rather than a suggestion.

At a fixed rep target, shortening rest does not reduce work — it **inflates
RPE** (§1.4, Farah 2012). `session_au` is computed from a self-reported RPE.
Therefore **a rest change moves Strain and ACWR without any change in the work
performed**.

**Rest duration is not logged anywhere in this repo.** `rest_seconds` is a
*plan* value consumed by the timer (`views/training.py:3475`, `:3518`, `:3555`)
and the duration estimate (`services/sessions.py`); nothing persists what was
actually taken. So an AU rise following a rest change is **indistinguishable in
the data** from one caused by harder training.

That is precisely key rule 2b's hazard — *"swings on button behaviour rather
than physiology"* — arriving by a different door, and it is the same class as
the per-set warm-up flag (Known Open Issues). **Both are prerequisites to the
same block.**

### 2.2 There is no rest-interval evidence in any relevant population

Stated plainly because the temptation is to reason past it:

1. **Trained-participant data barely exists for hypertrophy.** Of Singer 2024's
   9 studies, only **2–3** used trained participants, and the authors state
   outright that limited trained data prevented a robust subanalysis. The
   "trained lifters need longer rest" claim rests on Schoenfeld 2016 (n=21) plus
   narrative synthesis — **not pooled evidence**.
2. **Nothing on rehabilitation or clinical populations.** Every study cited here
   is healthy young adults, overwhelmingly male (Grgic 2018: 413 M / 78 F).
   There is **no** rest-interval evidence in anyone with lumbar disc pathology,
   hypermobility, or a live positional symptom.
3. **Nothing on trunk or core musculature** — stated explicitly as a limitation
   by Singer 2024. Everything is arm, thigh, or a whole-body proxy. **All three
   Stage 2A sessions sequence core last by design**, which is the condition
   least like anything measured.
4. **Nothing on hypermobility.** Any argument either way is invention. The one
   adjacent finding worth carrying: **Senna 2022** found that *at equated
   volume*, 1-min rest still produced **~37% higher CK exposure** (4572±1170 vs
   3330±716 u/L·h, p<0.01) and elevated IL-1β and TNF-α than 3-min rest. That is
   the one cost of short rest that survives volume-equating, and it is a
   **recovery-budget** cost rather than a performance one — relevant to a fixed
   weekly allowance and a live symptom. ⚠ n=10, and it is CK, not tissue damage
   anyone has shown to matter clinically.

**The only guideline framing that fits** is NSCA 2019's *"symptom-free
progression"* (§1.1) — a tolerance rule, with no evidence grade. That is the
honest position: **rest here is set by tolerance and by the time budget, and the
literature constrains it only loosely at both ends.**

### 2.3 The measured RPE hold interacts with this

`docs/focus.md`'s measured-RPE-vs-self-reported hold is due for review
2026-08-16, and its exit criterion is a per-athlete conversion regressed from
sessions carrying **both** signals. **Changing rest intervals during that
comparison window contaminates it**: §2.1 says a rest change moves self-reported
RPE, while HR-derived RPE (%HRR, active-time-weighted) responds to a different
thing entirely — shorter rest raises average HR mechanically.

**So a rest change would move the two signals in uncoordinated directions
inside the exact window the regression is being built from.** With one paired
point on record (2026-08-06: measured 5.2 vs reported 5.0), that is cheap to
avoid and expensive to undo.

**This is an argument for sequencing, not for refusing the change** — but it is
a reason the §3.0 change should land with rest logging (§3.3) already in place.

### 2.4 ⚠ The Stage 2B isometric holds — read before dosing

**Out of scope of the athlete's question, and the most consequential item here.**

`patient_profile.py`'s Stage 2B direction is that *isometric hold durations
follow the scientific literature for tendon adaptation, dosed across a
~10-minute period*, and this is recorded as physio-confirmed and closed. §1.8
says the tendon literature does not support what that is usually taken to mean:

- The best-evidenced human protocol is **4 × 3 s contractions per set at 90%
  MVC**, 2 min between sets, **180–300 s of total loading per week** (Tsai 2024,
  n=52).
- At **matched loading time**, four 3-second efforts **more than doubled** the
  stiffness gain of one 12-second hold (Bohm 2014). **Long holds were worse.**
- **Intensity, not duration, is the variable** — >70% MVC gives SMD 0.90; ≤70%
  gives 0.04.
- The 45 s hold is **n=6**, about analgesia, and has failed to replicate three
  times. The 30 s hold is **n=1**.

**And the target tissue is not a tendon.** The interscapular symptom was solved
to **left trapezius, position-loaded, perfusion-limited** (`symptom_log`
2026-08-13) — where **sustained low-level contraction is the provocative
mechanism**, and a shrug held 20–30 s in the provocative position is worse
*after* release.

> **Dosing scapular holds "to the tendon literature" imports a rationale from a
> different tissue, a different mechanism and a different body region — and the
> tendon literature itself argues for short repeated efforts over long sustained
> ones.**

**This does not overturn the physio's decision and nothing here changes
`training_plan.py`.** It is a question to put at the Day 28 sitting, in the same
form as the warm-up review's §4 questions: *are the scapular holds intended as
tendon-adaptation work, and if so does the 4 × 3 s structure fit the perfusion
finding better than a sustained hold?* See §4.

---

## 3 · What this implies for the block build

### 3.0 The ONE supported change

> **Raise 90 s → 120–180 s on the top one or two heavy compounds — Goblet Squat
> and RDL — and ONLY in Stage 2B, when the loads are near-maximal.**

Basis: Grgic 2018's *">2 min to maximise strength gains in resistance-trained
individuals"* (§1.3) plus Schoenfeld 2016. It is the only guideline-level claim
that will bind, and it binds on **training status and load proximity**, not on
the exercise being a compound per se.

**It does not apply at 12.5 kg and RPE 6.** §0.3 notes the current 90 s is
already delivered at that load; the change is conditional on Stage 2B actually
moving the load, not on the calendar.

**Cost:** at most four intervals per session (2 exercises × 2 inter-set gaps at
3 sets) → **+1 to +3 minutes**. Everything else stays.

Assistance work needs nothing: Incline DB Press (75 s), Hip Thrust (75 s), Lat
Pulldown (60 s) and Face Pull (60 s) already sit inside even ACSM 2009's
category-C 1–2 min.

### 3.1 Do NOT split right/left — priced

**Evidence:** pooled non-local fatigue **SMD −0.02 [−0.14, 0.09]**, strength
**+0.11**; crossover fatigue is cumulative and needs a stimulus far harsher than
a working set to appear at all; per-muscle rest is **already 75–105 s** (§0.1).

**Cost.** A side transition occurs once per set of every genuinely two-sided
unilateral exercise. Counted from `PLAN_STAGE2` (excluding the **right-only**
items — Right Posterior Hip Capsule Stretch and Right Hip Tendon Path Drill —
which are coded `laterality="unilateral"` but have no second side):

| Session | Two-sided unilateral exercises | Transitions | **Cost at 60 s** |
|---|---|---|---|
| A — Squat + Press + Core | PNF, Pallof Press, Full Side Bridge | 9 | **+9 min** |
| B — Hinge + Pull + Core | PNF, Single-Arm DB Row, Pallof Hold | 9 | **+9 min** |
| C — Unilateral/Glute | PNF, Bulgarian Split Squat, SL Glute Bridge, Side Bridge w/ Hip Dip | 11 | **+11 min** |

Against a corrected working portion of ~41–47 min (§0.2), that is a **~20–25%
increase in session length** to push per-muscle rest from 75–105 s to
135–165 s, buying an effect estimated at SMD −0.02. **It is the same trade
already rejected on the preparation phase.**

⚠ **The one exception to keep in view:** if single-leg **jumps** or other
explosive unilateral work are ever programmed, §1.5's RFD finding (contralateral
RFD −23.7% and −34.6% where MVC fell 4.4–7.1%) makes the case materially
stronger. Nothing in Stage 2A or the current Stage 2B direction is explosive.

### 3.2 Do NOT go to 3–5 minutes — priced

**Evidence:** ACSM 2026 issues **no rest prescription** and grades it "does not
impact" strength; the 3–5 min figure in ACSM 2009 appears only in the Summary
and **carries no evidence grade**; Ahtiainen found 2 min and 5 min identical
over **six months** in trained men; Scudese recommends 2 min even at 3RM;
Singer found no detectable benefit past ~90 s for hypertrophy.

**Cost.** Session A already charges **990 s = 16.5 min of coded rest** (§0.2).
Taking the six working exercises to 180 s per interval → 12 intervals × 180 s =
**2160 s**, against the current **750 s** in that block: **+23.5 minutes**, on
top of a session already understated by ~6 min.

### 3.3 ⛔ PREREQUISITE — log the rest actually taken, before any rest change ships

Per §2.1: rest is not logged, the cost of short rest surfaces as RPE, and
`session_au` is computed from RPE. **Ship a rest change without this and the
Strain/ACWR series carries an uninterpretable step** — indistinguishable from
harder training, exactly the failure key rule 2b names.

This is the **same class and the same block** as the per-set warm-up flag, which
Known Open Issues already lists as blocking. Both are per-set booleans/integers
on the same write path. **Doing them together is one change; doing them
separately is two migrations of the same rows.**

Minimum shape: seconds actually elapsed on the rest timer, per set. The timer
already runs (`views/training.py:3475`, `:3518`, `:3555`) — the value exists at
the moment the "Next Set" button is pressed and is currently discarded.

### 3.4 Buy time back with pairing, not with shorter rest

If the time budget needs to give, §1.7 says the lever is **agonist-antagonist
pairing** (~37% shorter sessions, SMD 1.74; antagonist configurations produce
*more* reps, +0.68), **never** shorter per-muscle rest and **never** cluster
sets / rest redistribution (time-neutral by construction, chronic payoff ≈ zero).

Two constraints on doing it here:
- **The pairing must be genuinely non-competing.** Same-muscle pairing
  significantly **loses** volume load (SMD −1.08).
- **Order matters and is unresolved** (§4). García-Orea 2022's squat — placed
  *first* — lost 19% of its reps while the bench it was paired with lost none.
  The more demanding lift paid for having its rest occupied.

⚠ Face Pull is already *deliberately* paired with pressing per finding #6 in
`patient_profile.py`. That is a clinical pairing, not a time-efficiency one, and
it is antagonist by construction — worth noting that the structure §1.7
recommends is already partly present for a different reason.

### 3.5 Interaction with the warm-up review's locked time budget

`warmup_evidence_review_2026-08-10.md` §3.0-b locks **total preparation at 10–15
minutes**, justified against a *"~30 min working portion."* §0.2 shows the
working portion is really **~41–47 min** once the second side is counted.

**That strengthens the lock rather than weakening it** — preparation at 10–15
min against a 41–47 min working portion is 18–27% of the session, better than
the 25–33% the lock was argued for. **No change to the budget is proposed here,
and the ceiling is the athlete's.** It is recorded so that the next person to do
this arithmetic does not "discover" a discrepancy and re-open a settled
decision.

**One genuine conflict to be aware of:** §3.0 adds 1–3 min and §3.4's pairing
removes ~37%; the warm-up review's phase 2 adds 5–10 min. These land in the same
block and compete for the same clock. **Sequence: phase 2 is locked and goes
first (warm-up review §3.0), then §3.0's rest change, then pairing if the total
still does not fit.**

---

## 4 · Questions that need answering before authoring

1. **Do the Stage 2B isometric holds intend tendon adaptation?** (§2.4) If yes,
   the evidence favours **4 × 3 s at high intensity** over a sustained hold, and
   the target tissue — perfusion-limited left trapezius — makes sustained
   low-level contraction the *provocative* mechanism. **Physiotherapist's call
   at Day 28.** Note the release-block dose question is CLOSED and this is not a
   re-opening of it; it is a different question about a different item.
2. **Does the per-set rest field land with the warm-up flag?** (§3.3) One
   migration or two. **Athlete's/engineering call**, but the answer decides
   whether §3.0 can ship in Stage 2B at all.
3. **If pairing is used, which lift goes first?** (§3.4) Unresolved in the
   literature; García-Orea's result hints the more demanding lift should not be
   the one whose rest is occupied. **No evidence to settle it — decide by
   observation and log it.**
4. **Should the 45 s on core/scapular/release work change?** Honest answer:
   there is **no evidence at all** bearing on it (§2.2, point 3 — no study has
   measured rest-interval effects on trunk musculature; nothing exists on
   unloaded holds, activation drills or mobility work). **Leaving them at 45 s
   is not evidence-based, but neither would changing them be.** Recommend
   leaving them and spending the decision budget elsewhere.

---

## 5 · Evidence summary

| Claim | Grade | Note |
|---|---|---|
| ACSM 2026: inter-set rest "does not impact" strength, no prescription issued | **A** | 137 systematic reviews. The strongest single item here. |
| ACSM 2009's "3–5 min" for 1–6RM | **none** | Summary section only, **no evidence grade**, contradicts its own graded body. |
| Longer rest helps **via volume load**, not physiologically | **B** | Longo 2022 — the only study that crosses the two variables. |
| >2 min to **maximise** 1RM in resistance-trained lifters | **A** with caveat | Grgic 2018 — synthesis judgement, review pools nothing. Basis for §3.0. |
| No detectable hypertrophy benefit past ~90 s | **A** | Singer 2024 — but only 2–3 trained studies of 9. |
| 2 min ≈ 5 min over six months in trained men | **B** | Ahtiainen 2005 — ⚠ intensity not held constant. |
| The rep-loss mechanism requires **sets to failure** | **A/D** | Every study in that literature. **The decisive point for RPE 5–6.** |
| At fixed reps, short rest raises **RPE**, not work | **C** | Farah 2012 — ⚠ reports no repetition data. |
| Rest requirement at RIR 4–5 | **none — never studied** | §1.4. Everything said about it is extrapolation. |
| Non-local muscle fatigue, pooled | **A** | SMD −0.02 [−0.14, 0.09]; strength **+0.11**. 52 studies. |
| Crossover fatigue is **cumulative** — absent after one bout | **B/C** | Doix 2013/2018, Power 2021. **Settles §3.1.** |
| Rest **between the two sides** of one exercise | **C, essentially unstudied** | One study, n=10, shortest interval 20 min. |
| Halperin 2015's upper/lower NLMF split | **superseded** | Vote-counting; same senior author's later pooled analysis found no moderator. |
| Bilateral deficit as a mechanism for inter-side rest | **invalid** | Different phenomenon. Do not cite. |
| Heavier load ⇒ longer rest | **not supported** | Willardson 2006 (no interaction); Senna 2017 (**lighter** load needed *more*). |
| Agonist-antagonist pairing: ~37% time saved | **A** | ⚠ Outcome "equivalence" is non-significance with wide CIs. |
| Same-muscle pairing loses volume load | **A** | SMD −1.08 [−1.72, −0.44]. The configuration is the intervention. |
| Cluster sets / rest redistribution save time | **refuted** | Time-neutral by construction; chronic SMDs −0.06 / −0.03 / −0.38. |
| Rest **between exercises** (vs between sets) | **none — never isolated** | Every study varies both together and says so. §6. |
| 60 vs 90 vs 180 s as three arms | **does not exist** | And a fabricated paper claiming to be it is in circulation (§1.9). |
| Tendon: >70% MVC required for stiffness | **A** | SMD 0.90 vs 0.04. **Intensity, not duration.** |
| Tendon: 4 × 3 s beats one 12 s hold at matched time | **B** | +57% vs +25%. **Long holds are worse.** |
| The 45 s isometric hold | **C, failed replication ×3** | n=6, analgesia not adaptation. The 30 s hold is **n=1**. |
| "10 min loading / 6 h refractory" | **D — cell culture** | Paxton 2012, engineered ligament in vitro. |
| Rest-interval evidence in rehab / hypermobile / core | **none** | §2.2. Say so rather than reasoning past it. |

---

## 6 · What this document deliberately does not do

- **No code.** Nothing in `services/`, `training_plan.py` or `views/` is
  touched. §0.2's estimator defect and §3.3's missing rest field are **recorded,
  not fixed**.
- **No protocol.** No exercise's `rest_seconds` is changed. §3.0 is a
  constraint for the block build, not an edit.
- **No re-opening of the release-block dose.** Physio-confirmed 2026-08-12 and
  closed. §2.4 raises a *different* question about a *different* item.
- **No re-opening of the 10–15 minute preparation ceiling.** §3.5 corrects the
  denominator it was argued against and finds the lock **better** supported, not
  worse. The ceiling is the athlete's.
- **No claim that rest length matters much at RPE 5–6.** §1.4 and §2.2 say the
  evidence for that is absent in both directions, and this repo's habit is to
  say so rather than pick the flattering side.
- **No unified rest recommendation across modalities.** Loaded compounds,
  assistance work, core holds, isometrics and mobility items are governed by
  different evidence — three of those five by none at all.

---

### Sources

**Guidelines** · Currier et al. 2026, *MSSE* 58(4):851-872 (ACSM umbrella review) ·
Ratamess et al. 2009, *MSSE* 41(3):687-708 — [PubMed 19204579](https://pubmed.ncbi.nlm.nih.gov/19204579/) ·
Fragala et al. 2019, *JSCR* 33(8):2019-2052 (NSCA, ≥50 y) ·
Paluch et al. 2024, *Circulation* 149(3):e217-e231 (AHA) ·
Patterson et al. 2019, *Front Physiol* 10:533 (BFR consensus)

**Chronic trials** · Longo et al. 2022, *JSCR* 36(6):1554-9 ·
Schoenfeld et al. 2016, *JSCR* 30(7):1805-12 — [PubMed 26605807](https://pubmed.ncbi.nlm.nih.gov/26605807/) ·
Ahtiainen et al. 2005, *JSCR* 19(3):572-82 ·
Villanueva et al. 2015, *EJAP* 115(2):295-308 ·
Buresh et al. 2009, *JSCR* 23(1):62-71 ·
Attarieh et al. 2026, *Sport Sci Health* 22(1):32 ·
Fink et al. 2017, *Int J Sports Med* 38(2):118-24 ·
Fink et al. 2018, *Clin Physiol Funct Imaging* 38(2):261-8 ⚠ ·
de Souza et al. 2010, *JSCR* 24(7):1843-50 ·
Simão et al. 2022, *JSCR* 36(2):540-4 ·
Mao et al. 2023, *Front Physiol* 14:1301535

**Meta-analyses** · Grgic et al. 2018, *Sports Med* 48(1):137-151 — [PubMed 28933024](https://pubmed.ncbi.nlm.nih.gov/28933024/) ·
Grgic et al. 2017, *Eur J Sport Sci* 17(8):983-93 ·
Singer et al. 2024, *Front Sports Act Living* 6:1429789 ·
Zhang et al. 2023, *Int J Sports Med* 44(12):857-64 ·
de Salles et al. 2009, *Sports Med* 39(9):765-77 ·
Henselmans & Schoenfeld 2014, *Sports Med* 44(12):1635-43

**Acute** · Willardson & Burkett 2006, *JSCR* 20(2):396-9 ·
Senna et al. 2017, *J Hum Kinet* 58:197-206 ·
Senna et al. 2011, *JSCR* 25(11):3157-62 ⚠ ·
Senna et al. 2022, *Front Physiol* 13:827847 ·
Scudese et al. 2015, *JSCR* 29(11):3079-83 ·
Farah et al. 2012, *Percept Mot Skills* 115(1):273-282 ·
Miranda et al. 2009, *J Sports Sci Med* 8(3):388-92 ·
de Freitas Maia et al. 2015, *J Exerc Sci Fit* 13(2):104-10 ·
Behenck et al. 2022, *JSCR* 36(3):781-6 ·
Gaspar et al. 2026, *J Sports Med Phys Fitness* 66(5):624-30

**Non-local fatigue** · Behm et al. 2021, *Sports Med* 51(9):1893-1907 ·
Halperin, Chapman & Behm 2015, *EJAP* 115(10):2031-48 (superseded) ·
Halperin, Copithorne & Behm 2014, *APNM* 39(12):1338-44 ·
Arora et al. 2015, *EJAP* 115(10):2177-87 ·
Benitez et al. 2023, *JFMK* 8(2):85 ·
Power et al. 2021, *JSSM* 20(2):339-48 ·
Kawamoto et al. 2014, *JSSM* 13(4):836-45 ⚠ ·
Doix et al. 2013, *PLoS ONE* 8(5):e64910 ·
Doix et al. 2018, *Biol Sex Differ* 9:29 ·
Zahiri et al. 2024, *JSSM* 23(2):425-35 ·
Gioda et al. 2024, *PLoS ONE* 19(2):e0293417 ·
Lacerda et al. 2024, *J Bodyw Mov Ther* 37:360-5 ·
de Oliveira et al. 2023, *Int J Exerc Sci* 16(2):1154-64 ·
Škarabot et al. 2016, *EJAP* 116(11-12):2057-84 (bilateral deficit — not applicable)

**Recovery physiology** · Harris et al. 1976, *Pflügers Arch* 367(2):137-42 ·
Bogdanis et al. 1995, *J Physiol* 482(2):467-80 ·
Carroll, Taylor & Gandevia 2017, *J Appl Physiol* 122(5):1068-76 ·
Refalo et al. 2023, *Sports Med Open* 9:10 ·
West et al. 2010, *J Appl Physiol* 108(1):60-7 ·
McKendry et al. 2016, *Exp Physiol* 101(7):866-82

**Time-efficient structures** · Zhang et al. 2025, *Sports Med* 55(4):953-975 ·
Iversen, Norum, Schoenfeld & Fimland 2021, *Sports Med* 51(10):2079-95 ·
Weakley et al. 2017, *EJAP* 117(9):1877-89 ·
García-Orea et al. 2022, *Sports* 10(7):110 ·
Latella et al. 2019, *Sports Med* 49(12):1861-77 ·
Jukic et al. 2020, *Sports Med* 50(12):2209-36 ·
Jukic et al. 2021, *Sports Med* 51(5):1061-86 ·
Sødal et al. 2023, *Sports Med Open* 9:66 ·
Prestes et al. 2019, *JSCR* 33(S1):S113-21 ·
Burke et al. 2025, *Science & Sports* 41(1):77-90

**Tendon / isometric** · Bohm et al. 2015, *Sports Med Open* 1:7 ·
Bohm et al. 2014, *J Exp Biol* 217(22):4010-7 ·
Kubo et al. 2001, *J Physiol* 536:649-55 — [PubMed 11600697](https://pubmed.ncbi.nlm.nih.gov/11600697/) ·
Tsai et al. 2024, *Sci Rep* 14:6875 ·
Rio et al. 2015, *BJSM* 49:1277-83 ⚠ ·
Holden et al. 2020, *J Sci Med Sport* 23(3):208-14 — [PubMed 31735531](https://pubmed.ncbi.nlm.nih.gov/31735531/) ·
van der Vlist et al. 2020, *Scand J Med Sci Sports* 30(9):1712-21 ·
Clifford et al. 2020, *BMJ Open Sport Exerc Med* 6:e000760 ·
Paxton et al. 2012, *Tissue Eng Part A* 18(3-4):277-84 ·
Baar 2017, *Sports Med* 47(S1):5-11 · Baar 2019, *IJSNEM* 29(4):453-7 ⚠ n=1 ·
Kongsgaard et al. 2009, *Scand J Med Sci Sports* 19(6):790-802 ⚠ ·
Beyer et al. 2015, *AJSM* 43(7):1704-11 ⚠

⚠ = miscited in circulation, failed replication, or structure unverifiable — see §1.9 and §1.8.

**Excluded, do not cite:** the "36 amateur bodybuilders, 60/90/180 s" trial
(**does not exist**, §1.9) · Davidson & Barillas 2025 medRxiv (SMD signs
incoherent) · the AHA "1 minute is insufficient" claim (**not in the source**).
