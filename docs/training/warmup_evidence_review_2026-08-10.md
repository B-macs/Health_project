# Warm-up — the evidence, and what it means for the next block

> ## ⛔ REQUIRED READING BEFORE THE NEXT BLOCK IS AUTHORED
>
> **Gated on the EVENT, not on a date** — the `HRV_GARMIN_HOLD` idiom. Read
> this file in full before authoring a single day of the next training block,
> whenever that happens. It sits alongside CLAUDE.md Key Rule 11's
> clinical-document gate and is checkable in the same way: state how it
> influenced the plan, or say plainly that it did not and why.
>
> **⚠ Corrected 2026-08-10, athlete's direction: the training plan is NOT
> being rebuilt on 2026-08-16.** An earlier draft of this banner gated on that
> date. The Day 28 reassessment still happens then and still gates the three
> deferred decisions, but a new block is not authored on the day — so this
> document waits for the block build rather than expiring with the
> reassessment. **If Stage 2A is extended rather than replaced, the budget in
> §3.0-b and the shape in §3.3 can land in the extension** — they are guidance
> until implemented, and nothing here depends on a block boundary. That is a
> decision for the athlete, not an assumption this document makes.
>
> The next block is the first to run loads close to maximum. **This system
> currently contains no warm-up at all** (§0.1) and the block that looks like
> one costs 16–22 minutes and is documented as 5 (§0.2). Authoring heavier
> sessions on top of that structure without reading §0 and §3 is the specific
> mistake this document exists to prevent.
>
> **The five things that will bite if skipped:** §1.4 (warm-up value is not a
> constant — it scales with load proximity) · §2.1 (his own 2025 log names
> "glutes not warmed up before squats" as a cause of the squat breakdown) ·
> §2.2 (the literature's best general warm-up is the one his log blames for
> glute inhibition) · §3.5 (**ramp sets corrupt tonnage, Strain and e1RM
> unless a per-set flag lands first** — a prerequisite, not a follow-up) ·
> §3.8 (it collides with the one-new-stressor-per-week rule).
>
> **Two corrections already applied — do not re-derive the originals:** the
> force-deficit exposure is one exercise, not the block (§1.5 dose table), and
> the orthostatic transition is **rare** and is not a design driver (§2.4,
> athlete's correction 2026-08-10).
>
> ### The shape the protocol must be authored in
>
> ```
> TODAY:    [ quiet things down ] → [ load ]
>
> REQUIRED: [ quiet things down ] → [ wake things back up ] → [ load ]
> ```
>
> Phase 1 exists and costs 16–22 minutes. **Phase 2 does not exist at all** —
> it is the entire deliverable, and its job is to undo phase 1's acute cost
> while keeping phase 1's clinical benefit. Phase 1 does not need anything
> deleted for that to work. Full definition and the per-phase table in §3.3;
> the reasoning in §2.3. **Use these three names in patient-facing text.**
>
> **🔒 LOCKED, athlete's direction 2026-08-10 (§3.0): phase 2 is MANDATORY and
> is the fixed point of the block build.** It is specified first, from the
> evidence, and everything else — including the release block's duration —
> adjusts around it. Read §3.0 before §3's other items; it supersedes the
> earlier framing that treated phase 2 as fitting into leftover time.
>
> **The trap §3.0 exists to prevent:** phase 2 has two jobs. **Job A
> (restore)** is what the lock requires, the evidence is about its *presence*
> and specifies **no duration**. **Job B (maximise)** is the 15-min raise, pays
> only near 1RM, and is optional. Pricing Job A at Job B's 15 minutes would
> spend the whole time budget on something Job A does not need.
>
> **🔒 LOCKED, athlete's direction 2026-08-10 (§3.0-b): TOTAL preparation time
> is 10–15 minutes**, phases 1 and 2 together, from first movement to first
> working rep. 15 is a ceiling, not a target. At today's ~30 min against a
> ~30 min working portion, preparation is **half the session**. Indicative
> split: **phase 1 ≈ 5 min** — which is `patient_profile.py:439`'s own figure,
> so this **restores the prescription rather than cutting it** — and **phase 2
> ≈ 5–10 min**. The squeeze falls entirely on phase 1, and phase 1 is the part
> that drifted.

*Written 2026-08-10, six days before the block is authored (2026-08-16). This is
a REVIEW AND A DESIGN BRIEF, not a protocol and not code. Nothing here is
implemented. It exists so that on the day, the warm-up question is a lookup
rather than an argument, in the same idiom as
`docs/training/flexibility_integration_2026-08-16.md`.*

**The prompt that produced it:** the next block moves to higher reps and heavier
load, closer to max than this transition phase. That is the first block in which
warm-up stops being optional. Two failure modes were named up front and both are
real:

1. Warming up every muscle, then training only the biceps.
2. Spending 15+ minutes when 5 minutes — or one set at ~60% load for ~60% of the
   reps — would have done the same job.

---

## 0 · Two findings that came before the literature

These are facts about the current system, checkable in the tree today, and they
reframe both failure modes.

### 0.1 There is no warm-up anywhere in this system

`grep -i` for warm-up/ramp/potentiate across the repo returns **zero hits in the
training layer**. Every match is either the flexibility battery's *"measure
COLD, no warm-up"* gate — the opposite concern — or the substring `ramp` inside
the word `cramp`.

A Stage 2A gym day is, in order (`training_plan.py:1900-1985`):

```
UPPER_GLUTE_RELEASE → PIRIFORMIS_PNF → RIGHT_HIP_CAPSULE_REVISED →
COXA_SALTANS_DRILL → Goblet Squat, set 1, working weight
```

There is no raise, no ramp set, and no transition of any kind between the last
release hold and the first loaded rep. At 10 kg this was survivable. It is the
thing that has to change before load goes up.

### 0.2 The block that looks like a warm-up costs ~20 minutes and is not one

`patient_profile.py:439` describes a **"5-minute release block."** The coded
doses (`training_plan.py:101-198`) sum to considerably more:

| Item | Coded dose | Clock |
|---|---|---|
| Upper Glute / TFL Self-Release | 2 × 90 s, rest 30 (prose says *each side*; `laterality` says bilateral) | 3.5–7.5 min |
| Piriformis Contract-Relax (PNF) | 3 sets × 5 cycles **each side**, rest 60 | ~8–10 min |
| Right Posterior Hip Capsule (Revised) | 2 × 60 s, rest 45, right only | ~2.7 min |
| Coxa Saltans Drill | 2 × 10, rest 45, right only | ~1.8 min |
| **Total** | | **≈ 16–22 min** |

Two things follow. First, the time budget is not empty — it is already
overspent, on something that isn't a warm-up. Second, there is a live
discrepancy worth resolving on its own: `UPPER_GLUTE_RELEASE` is coded
`laterality="bilateral"` while both its `mechanics` text and the profile say
each side. That is a 2× difference in the largest single item.

---

## 1 · What the literature actually says

Evidence grades used below: **A** = meta-analysis or systematic review · **B** =
controlled crossover trial in trained humans · **C** = single small trial or
special population · **D** = mechanistic/physiological reasoning · **E** =
expert framework, no direct trial support.

### 1.1 Mechanisms, and their measured size

Warm-up effects split into temperature-dependent and temperature-independent.
Muscle temperature rises ~**0.1 °C per minute** during a 20-minute warm-up and
falls at roughly the same **0.1 °C per minute** once you stop, with the
performance benefit largely gone by **~15 minutes** of inactivity
([Racinais/McGowan lineage; Res Q Exerc Sport 2023 review](https://www.tandfonline.com/doi/full/10.1080/02701367.2021.2007212), grade **A/D**).
Force development improves roughly **5% per 1 °C** of temperature rise
(grade **D** — a physiological constant, not a training outcome).

The practical corollary is the one people skip: **the clock starts when you stop
warming up.** A perfect warm-up followed by 15 minutes of plate-loading and
phone-checking has decayed to baseline.

### 1.2 The general ("raise") portion — the dose-response is measured, and counter-intuitive

This is the single most useful study for the "5 minutes vs 15 minutes" question,
because it tested exactly that grid.

**Barroso et al. 2013, J Strength Cond Res 27(4):1009-1013** — 16 strength-trained
men, leg press 1RM, five conditions (grade **B**):

| Condition | Protocol | 1RM (kg) | vs control |
|---|---|---|---|
| **LDLI** | **15 min @ 40% VO₂max** | **367.8 ± 70.1** | **+~3% (p = 0.01)** |
| SDMI | 5 min @ 70% VO₂max | 359.4 ± 69.2 | no difference (p = 0.99) |
| SDLI | 5 min @ 40% VO₂max | 359.1 ± 69.3 | no difference (p = 0.99) |
| CTRL | none | 359.4 ± 70.4 | — |
| LDMI | 15 min @ 70% VO₂max | 345.6 ± 70.5 | **−~4% (p = 0.01)** |

**Read the middle rows carefully. Five minutes was indistinguishable from doing
nothing at all** — at either intensity. And going harder rather than longer was
the only condition that made things actively worse.

This agrees with **Abad et al. 2011, JSCR 25(8):2242-2245** (13 trained
participants, crossover, grade **B**): general warm-up (20 min cycling @ 60%
HRmax) **plus** specific warm-up beat specific warm-up alone by **8.4%
(p = 0.002)** on leg-press 1RM.

The synthesis across both: **duration buys temperature; intensity buys fatigue.**
Long and genuinely easy wins. Short is worthless. Long and moderate is negative.

**The caveat that matters here, and it is large.** In both studies the general
warm-up was a *cycle ergometer* and the test was a *leg press*. The "general"
warm-up was working the same muscles as the test. These studies do not show that
15 minutes of cycling prepares a bench press — see §1.7.

### 1.3 The specific portion (ramp sets)

**Ribeiro et al. 2020, IJERPH 17:6882** — 40 resistance-trained men (14 squat,
26 bench), three warm-up conditions before 3 × 6 at 80% 1RM (grade **B**):

- **WU** (progressive): 6 reps @ 40% of training load, then 6 @ 80% of training load
- **WU80**: 6 reps @ 80% of training load only
- **WU40**: 6 reps @ 40% of training load only

Results: squat mean propulsive velocity was higher after **WU80** than WU40 in
set 2 (0.71 vs 0.67, p = 0.02, **ES 0.80**) and set 3 (p = 0.05, ES 0.51). Bench
press favoured the **progressive WU** on time-to-peak-velocity (p < 0.01, ES 0.69)
and total work (4749.9 vs 4631.8 J, p = 0.01, ES 0.54). The authors' conclusion:
*warming up with minimal load and volume is insufficient.*

**Note what the winning squat dose converts to.** "80% of training load" where
training load is 80% 1RM = **6 reps at ~64% of 1RM**, against a 6-rep working
set. That is almost exactly the instinct in the original brief — *one set at
~60% weight* — and the literature backs it. The one correction: the reps were
**matched to the working set, not reduced to 60%**. Load came down; volume did
not.

### 1.4 Where the specific warm-up stops being worth anything

This is the counterweight, and it is the finding that answers failure mode 2.

**Warming up to improved performance? (SportRxiv preprint 559 / J Sci Sport Exerc
2025)** — 29 trained individuals (4.5 ± 3.9 y experience), crossover, Smith bench
press and 45° leg press (grade **B**):

- **1SET**: 3-4 reps @ 75% of 10RM
- **2SET**: 3-4 @ 55% 10RM, then 3-4 @ 75% 10RM
- **CON**: no warm-up

Result: *negligible to small* differences, with evidence ratios giving **strong
evidence against** any superiority of the structured warm-ups. The authors'
recommendation is blunt — *it is possible to achieve greater time efficiency in
RT sessions by forgoing a specific warm-up when training at ~10RM loads.*

And the specific warm-up can cost you. **Nunes et al. 2024, 57 resistance-trained
older women** (grade **C** — special population, but directly on point): a
45-second specific warm-up set **reduced** reps on the small upper-limb
exercises — triceps pushdown 28.0 vs 31.0 control (**ES −0.5**), preacher curl
25.6 vs 28.1 (**ES −0.4**) — while the lower-limb exercises benefited from
preparation. Their conclusion: preparation should be **limb-specific**.

**The synthesis — this is the design rule.** Warm-up value is not a constant. It
scales with two things:

| | Warm-up value |
|---|---|
| Load near 1RM, large multi-joint pattern, high joint stakes | **Real and measured** (+3–8%) |
| Load around 10RM, familiar pattern | **≈ zero for performance** |
| Small single-joint muscle, isolation work | **Can be negative** — it is just fatigue |

The next block moves *toward* the top row. That is precisely why the question is
being asked now and was not worth asking at 10 kg.

### 1.5 Stretching before lifting

**Behm et al. / Blazevich et al. 2018**, and the current best synthesis,
**Warneke et al. 2024, J Sport Health Sci — systematic review with multilevel
meta-analysis, 83 studies, 400+ effect sizes, 2,012 participants** (grade **A**):

| Dose | Effect on maximal strength |
|---|---|
| Static stretch **≥60 s per bout** | **ES −0.84** (p = 0.004) — large |
| Static stretch **<60 s per bout** | ES −0.18 (p = 0.03) — trivial |
| Total volume >480 s | ES −0.46 (p = 0.03) |
| Total volume ≤480 s | ES −0.14 (p = 0.24) — not significant |

Crucially: *"active warm-up routines can counteract the stretch-induced force
deficit when they are performed subsequently."* The authors explicitly reject a
blanket ban — *"a rigorous prohibition of including stretching to (dynamic)
warm-up routines seems without evidence"* — while advising against extensive
stretching immediately before maximal strength efforts.

Two adjacent findings, both needed below:

- **Self-myofascial release / sustained pressure does NOT carry this cost.**
  Multiple reviews find foam rolling and SMR increase ROM *without* subsequent
  loss of force or activation (grade **A**). Pressure ≠ stretch.
- **PNF contract-relax reduces muscle-tendon stiffness like static stretching
  does** — a direct comparison of static, ballistic and PNF found *no clinically
  relevant difference* between them on MTU stiffness (grade **B**). On *force*
  the PNF-specific evidence is weaker than usually implied: the direct CMJ
  comparison often cited (−8.7% CR-PNF vs −8.2% static) reported those drops as
  **not statistically significant**, in a small sample (grade **C**). Treat
  "PNF reduces stiffness" as reasonably supported and "PNF costs you X% of your
  strength" as not established.

**Applying the dose thresholds to the block that actually exists** (§0.2) —
this matters, because the answer is not the intuitive one:

| Item | Stretch bout length | Verdict against the moderators |
|---|---|---|
| Upper Glute / TFL Self-Release (2 × 90 s) | n/a — sustained **pressure** | No force cost (SMR literature) |
| Ischial Tuberosity Release (2 × 90 s) | n/a — sustained **pressure** | No force cost |
| Piriformis PNF (3 × 5 cycles/side) | **~3 s** per end-range hold, ~45 s total per side | Falls in the **<60 s trivial** bucket (ES −0.18) |
| **Right Posterior Hip Capsule (2 × 60 s)** | **60 s** per bout | **The only item at the ≥60 s threshold** (ES −0.84 bucket) |

Total stretching volume across the block is ~200 s — comfortably inside the
≤480 s band where the total-volume moderator is **not significant**. So the
force-deficit exposure here is **narrow and specific**: one item, right side
only, not the block as a whole.

### 1.6 PAPE (heavy prep single before working sets) — no

Pooled effect **ES ≈ 0.13–0.14** with wide requirements: optimal rest **4–7
minutes**, submaximal 70–80% 1RM loads, and rest intervals of 0–1 min actively
*harmful* (d = −0.33) (grade **A**, jump/power outcomes). Amateur and elite
effect sizes were statistically indistinguishable (0.14 vs 0.13).

A ~0.13 effect that costs 4–7 minutes of standing still, per exercise, is not a
good trade for anyone who isn't peaking for a competition. **Recommend
excluding.** This is a clean "no" and it saves the time budget.

### 1.7 Specificity and transfer — failure mode 1, answered

Direct evidence on cross-body transfer is thin, but it points one way: local
muscle temperature governs peripheral contractile properties, while *core*
temperature has a separate and partly opposing profile (raised core temperature
impairs voluntary activation even as it improves evoked twitch properties)
(grade **D**). Lower-body pre-loading has repeatedly failed to enhance upper-body
performance in the trials that tested it (grade **C**).

Combine that with §1.2's confound — every strong "general warm-up works" result
used a general warm-up that happened to work the tested muscles — and the honest
conclusion is:

> **Warming up tissue you are not about to load has no demonstrated performance
> benefit. The raise portion should bias toward the pattern being trained.**

Which is exactly the concern in the original brief, and it is correct.

### 1.8 Injury prevention — the honest gap, and it is a chasm

This is where the review has to be blunt, because it is the reason most people
warm up and the evidence does not support it in this setting.

The strong injury-prevention evidence is **neuromuscular warm-up programmes in
team sports** — FIFA 11+, Nordic hamstring protocols — with meaningful reductions
in lower-extremity injury (grade **A**, *in that population*). Those programmes
are 15–20 minutes, run before *sprinting, cutting and jumping*, and their active
ingredient is widely argued to be the strength/neuromuscular training dose
accumulated over a season rather than the acute pre-session effect.

**There is no comparable body of evidence that warming up before resistance
training reduces resistance-training injuries.** The 2025 systematic review that
covers both explicitly limits itself on "heterogeneity in study designs, outcome
measures, and populations." Nobody has run the trial.

**So: the injury-prevention rationale for a lifting warm-up is grade D —
mechanistic reasoning, not evidence.** It may well be right. It is not
demonstrated. Any protocol built here should say so rather than borrow the
authority of the FIFA 11+ literature, which does not transfer.

### 1.9 RAMP — a framework, not an evidence base

**Raise · Activate · Mobilise · Potentiate** (Jeffreys 2007) was published in
*Professional Strength and Conditioning* — a coaching magazine, not a
peer-reviewed journal. It is a genuinely useful organising structure and it is
what most coaches teach. It has **no direct trial support as a protocol**
(grade **E**). Its components have varying independent support: Raise **B**,
Mobilise **A** (for the dose limits, §1.5), Potentiate **A but tiny** (§1.6),
Activate **D**.

Worth using as a checklist. Not worth citing as evidence. Claims found in the
wild that RAMP "reduces injury risk by up to 50%" trace back to the team-sport
literature in §1.8 and do not survive the transfer.

---

## 2 · Four things about this athlete that break the generic answer

The generic answer would be "15 min easy cardio, some dynamic work, ramp your
first exercise." Every clause of that is wrong here, for a different reason.

### 2.1 His own 2025 log already names the mechanism — and it is activation, not temperature

`Input_files/2025-training-year.md` reaches this conclusion independently,
before any of the above was read:

- *"Very dependent on warm-up to fire properly"* — glutes (line 265)
- *"**glutes not warmed up before squats**"* — listed as one of four named causes
  of the squat breakdown pattern (line 332)
- *"When tired **or cold**, the back is first to complain"* — hinge (line 315)
- *"Back injuries came from the hole of the squat each time"* (line 330)
- Root cause: *"Glute max fires during isolated work, but when things get heavy
  and tired the lumbar takes over"* (line 276)

This is the highest-weight evidence in the whole document, because it is grade
**C** in the literature sense but **n-of-1 on the actual athlete**, and it names
the exact injury mechanism the entire rehab programme exists to prevent.

It also reclassifies the problem. The warm-up's job here is **not** the 3–8%
performance gain in §1.2. It is **getting glute max to take its share of the
squat and the hinge before the erectors are asked to.** Those need different
content, and the second one has much weaker literature behind it.

### 2.2 The literature's best general warm-up is the thing his log blames for glute inhibition

Barroso's winning condition was **15 minutes of low-intensity cycling**. The 2025
log says, twice:

- *"Often fatigued from cycling, which makes the hinge unstable"* (line 266)
- *"cycling tightens hip flexors and inhibits glutes"* (line 317)

And `patient_profile.py`'s whole compensation model is *hip flexors and upper
glutes over-gripping while glute max under-fires.* **The single best-evidenced
general warm-up in the literature is contraindicated-by-mechanism for this
athlete on exactly the days it would matter most.** Rowing, incline walking, or a
sled/carry are the obvious substitutions, but this needs deciding, not assuming.

### 2.3 Hypermobility inverts the mobility half of the warm-up

Beighton **6/9**, three shoulder dislocations, two shoulder surgeries, a shallow
glenoid, and a documented pattern of *"muscles doing stabilising work that lax
ligaments under-support"* (`Input_files/hypermobility-profile.md`,
`injury_profile.md`).

For this body the goal of preparation is **stiffness and control, not range**.
The general hypermobility guidance (grade **D/E** — the EDS Society is explicit
that no official exercise guidelines exist) is proprioception and low-load
control work, progressing static → dynamic → resisted, and to be wary of
stretching as a default.

This puts the existing pre-session block in tension with itself — though
**narrowly, and not where you would guess.** Per §1.5's dose table, the PNF is
the largest item by *time* (~8–10 min) but its stretch bouts are ~3 s, which is
the trivial bucket. The item carrying the real force-deficit dose is the **Right
Posterior Hip Capsule Stretch at 2 × 60 s** — one exercise, right side only.

The *stiffness* concern is broader than the force concern and applies to both:
PNF and static stretch both reduce muscle-tendon stiffness acutely, and this is
a body whose whole problem is that its passive restraints don't hold. That is
grade **D** reasoning — nobody has tested stretch-induced stiffness loss as an
injury mechanism in hypermobile lifters — but it is the direction the mechanism
points.

To be fair to it — and this matters — the PNF and the capsule stretch are there
for a **clinical** reason (inhibit the overactive structures so glute max can
fire), prescribed on assessment, not for performance. The answer is therefore
**not** "delete them." §1.5 supplies the actual resolution: *an active warm-up
performed subsequently counteracts the stretch-induced deficit.* Which is
precisely what is missing.

> **The clearest single design conclusion in this document:** the current
> session runs stiffness-reducing work and then immediately loads the joint. The
> fix is not to remove the release block but to **insert a middle phase between
> it and the first working set** — the warm-up's job here is to buy back the
> release block's acute cost while keeping its clinical benefit.
>
> ```
> TODAY:    [ quiet things down ] → [ load ]
> REQUIRED: [ quiet things down ] → [ wake things back up ] → [ load ]
> ```
>
> **This is the canonical shape. See §3.3 — the protocol must be authored in
> it.**

### 2.4 The spine, and the clock on the wall

L5/S1 moderate active osteochondrosis with right foraminal stenosis; L3/4 and
L4/5 broad-based protrusions **each with a covered annular tear**.

**Adams & Hutton** and the diurnal-variation literature (grade **A/D**): discs
are maximally hydrated on rising, and **bending stresses on the lumbar discs are
~300% higher in the early morning**, with discs and ligaments at greatest risk of
injury then. Discs become stiffer in compression and more flexible in bending
as water content falls across the day.

So for this athlete, **time of day changes what the warm-up must do**, and it is
not a temperature question. A morning session needs unloaded time upright before
anything asks the lumbar spine to bend under load; an evening session does not
carry the same exposure. This interacts with the flexibility battery's cold
morning measurement and with `flexibility_window()`, which already reasons about
session placement.

**Two smaller modifiers worth carrying:**

- **Autonomic — and read the correction before using this.** Cold extremities,
  poor temperature regulation and suspected low blood volume are ongoing
  features (`hypermobility-profile.md`). The useful consequence is temperature:
  his baseline peripheral temperature is likely lower than the studies'
  participants, so the argument for a genuine raise is *stronger* for him than
  average (grade **D**).

  > **⚠ ATHLETE CORRECTION, 2026-08-10.** An earlier draft of this document
  > treated the supine→standing transition out of the floor-based release block
  > as a live per-session hazard, on the strength of the profile's "head rushes
  > on standing up". **He corrected it: this is EXTREMELY RARE and is to be
  > understood as rare.** The profile's own wording is *intermittent*, and
  > intermittent was read as frequent.
  >
  > **Consequence for the block build: the orthostatic transition is NOT a
  > design driver and must not be used to justify a single minute of warm-up.**
  > It stays on record because it is a real self-observed feature, at the
  > frequency he states — rare — and nothing more. If a graded upright raise
  > ends up in the protocol it will be there for temperature and glute
  > activation, which are the reasons that survive.
  >
  > The POTS/Levine recumbent-first literature does **not** apply and should not
  > be cited here: standing still for 10 minutes is explicitly not a problem for
  > him, which is the opposite of that picture.
- **Tendon (Baar).** Tenocytes take ~**10 minutes** of loading to receive their
  maximal anabolic signal and are refractory after that; further loading adds
  wear without signal (grade **B/D**, largely engineered-tissue and small human
  work). This is an argument about *tendon adaptation dosing*, not about warming
  up, and it belongs to `Input_files/baar_tendon_annex.md` — but it means a
  10-minute preparation block is not neutral tissue-wise, and it should not be
  authored in ignorance of the annex.

---

## 3 · What this implies for the block build (implications, not a design)

Stated as constraints the eventual protocol has to satisfy. **No design is
proposed here** — that is the 08-16 conversation.

### 3.0-b · LOCKED — the TOTAL time budget is 10–15 minutes

> **ATHLETE'S DIRECTION, 2026-08-10:** *"30 mins before the working set is too
> much, can we put in a recommendation of 10–15 mins before the working set;
> otherwise the entire time is just warming up."*
>
> **Total time from the start of preparation to the first working rep: 10–15
> minutes. Treat 15 as a ceiling, not a target.** This covers phase 1 AND
> phase 2 together, not phase 2 alone.

**The ratio argument, made concrete.** A Stage 2A Session A working portion is
**≈30 min** — derived by summing the coded tempos, rep counts and
`rest_seconds` across its six exercises, excluding setup and transitions. So:

| Preparation | Share of total session |
|---|---|
| 30 min (phase 1 today + a Job-B-sized phase 2) | **~50%** — half the session is preparation |
| **10–15 min (this budget)** | **~25–33%** |

At 50% the description *"the entire time is just warming up"* is literally
accurate. This is the constraint that makes the budget a real number rather
than a preference.

#### ⚠ The budget is NOT a cut to the prescription — it RESTORES it

This is the most important sentence in the section, and it changes who has to
approve what.

> **`patient_profile.py:439` — "5-minute release block before every session."**

**The clinical intent was always 5 minutes.** The coded doses (§0.2) drifted to
16–22 min. So compressing phase 1 back toward ~5 min is **returning to the
documented prescription**, not overriding it. Nobody is being asked to accept
less than what was prescribed; they are being asked which items carry the
clinical effect *at the dose the profile itself states*.

**Indicative allocation inside the budget** — the split is the
physiotherapist's to confirm, the ceiling is not:

| | Budget | Basis |
|---|---|---|
| **Phase 1 — quiet things down** | **~5 min** | `patient_profile.py:439`'s own figure |
| **Phase 2 — wake things back up** | **~5–10 min** | Job A always; Job B scales in on the heaviest days only |
| **Total** | **10–15 min** | This lock |

Phase 2 fits comfortably: a per-exercise ramp is ~1 set of ~6 reps at ~60–65%
of working load (§1.3) on the heavy compounds **only** — seconds of work plus
one rest — and Job A specifies no duration at all (§3.0). The squeeze is
entirely on phase 1, and phase 1 is the part that drifted.

**What this does NOT authorise:** this repo still does not cut a single item
from the release block. §4.2 is the conversation, and it is now a much easier
one — *"your own note says 5 minutes; the code says 20; which items carry the
effect at 5?"* rather than *"may we reduce your prescription?"*

---

### 3.0 · LOCKED DECISION — phase 2 is the anchor, not the leftover

> **ATHLETE'S DIRECTION, 2026-08-10:** *"If the science papers say it must be
> woken back up then we need to make sure that is added back in, everything
> works around that after."*
>
> **Phase 2 is mandatory and it is the FIXED POINT of the block build.** It is
> specified first, from the evidence, and the rest of the session — including
> the duration of the release block — adjusts around it. This inverts the
> earlier framing in this document, which treated the release block as fixed
> and left phase 2 to fit in whatever time remained. That framing is
> superseded; where the two disagree, this section wins.

**Why the "must" holds here specifically.** It is not a universal law, and it
should not be quoted as one in a future block. It holds because two conditions
are both true for this athlete in this block, and it weakens if either stops
being true:

1. Stretching work runs **immediately before load** with nothing between
   (§0.1) — this is what creates the deficit that needs counteracting.
2. The block runs **loads close to maximum** (§1.4) — the regime where warm-up
   effects are measurable rather than absent.

**⚠ Phase 2 has TWO jobs with very different price tags. Do not conflate them —
conflating them is what would blow the time budget for no benefit.**

| | **Job A — restore** | **Job B — maximise** |
|---|---|---|
| What it does | Undoes phase 1's slack; gets glute max contracting before the bar asks | Squeezes out peak force via muscle temperature |
| Evidence | Warneke 2024, 83 studies: *"active warm-up routines can counteract the stretch-induced force deficit when performed subsequently"* (grade **A**) | Barroso 2013, Abad 2011: +3–8% on 1RM (grade **B**) |
| What it costs | **Active work. No duration is specified by the evidence** — the finding is about *presence*, not minutes | **Expensive.** 15 min low-intensity; 5 min measured worthless |
| When it pays | **Always, here** — condition 1 above | Only near 1RM. At ~10RM it is worth ≈nothing |
| Status | **MANDATORY** — this is what the locked decision requires | **Optional, scales in as loads climb** |

The 15-minute figure answers Job B, which is a *different question* (maximising
1RM from a cold start). Importing it as the price of Job A would cost ~15
minutes to buy something Job A does not need. **Job A is the thing that must be
added back in, and there is no evidence it is expensive.**

**The consequence, stated plainly.** ~16–22 min of phase 1 plus a phase 2 sized
by Job B would put 30+ minutes in front of the first working set, which is
rejected on its face. So this decision **forces** the release-block dose
question that §4.2 previously listed as merely open. It is now unavoidable, and
it is a physiotherapist question — see §4.2, which is upgraded from "worth
asking" to "must be answered on the day."

**What is NOT changed by this decision:** phase 2 is still scaled **per
exercise**, not per session (item 1 below). "Mandatory" means the phase exists
in every session, not that every exercise gets a ramp — ramping the face pull
would be pure fatigue (§1.4), and that is failure mode 1, which this decision
does not license.

---

1. **The warm-up must be scaled per exercise, not per session.** §1.4 is the
   whole game: ramp the squat and the hinge, do not ramp the face pull. A single
   session-level warm-up block is the wrong shape and would reproduce failure
   mode 1 by construction.
2. **The raise should bias toward the pattern being trained** (§1.7), and the
   default modality question is open because cycling is ruled out on his own
   evidence (§2.2).
3. **The order has to change even if nothing is added — this is THE SHAPE, and
   the protocol authored on 08-16 must be set up in it.** The session today is
   two phases. It has to be three:

   ```
   TODAY:    [ quiet things down ] → [ load ]

   REQUIRED: [ quiet things down ] → [ wake things back up ] → [ load ]
   ```

   | Phase | What it is | Cost / benefit | Exists today? |
   |---|---|---|---|
   | **1 · Quiet things down** | Pressure releases, PNF, capsule stretch — inhibit the over-active structures so glute max can fire | Clinical benefit, paid for in slack (§1.5, §2.3) | **Yes** — all 16–22 min of it |
   | **2 · Wake things back up** | Raise, then per-exercise ramp | Buys the slack back, and gets glute max contracting before the bar does | **No. Nothing.** |
   | **3 · Load** | The working sets | — | Yes |

   Phase 2 is the entire deliverable. Its job is **not** the 3–8% performance
   bump in §1.2 — it is to undo phase 1's acute cost while keeping phase 1's
   clinical benefit, which is what the meta-analysis says a subsequent active
   warm-up does (§1.5). Nothing in phase 1 needs deleting for this to work.

   In the technical vocabulary, phase 1 is `pressure → stiffness-reducing work`
   and phase 2 is `raise → ramp`. **Use the three-phase names in anything
   patient-facing** — per `feedback_patient_facing_text`, how before why.

   One free improvement inside phase 1, at zero cost to anything: the Right
   Posterior Hip Capsule Stretch (2 × 60 s) is the **only** item at the harmful
   stretch dose and currently runs third of four. The pressure releases carry
   no force cost, so moving them after it puts more distance between the one
   ≥60 s stretch and the first loaded rep.
4. **Total time is a fixed budget that is already overspent.** ~16–22 min of
   pre-session work exists now. Anything added should come substantially out of
   that, and §0.2's laterality ambiguity should be resolved first — it may be
   worth 4 minutes on its own.
5. **⚠ The accounting hazard is real and is already a known open issue.** The
   moment ramp sets exist, they get logged with **reps and a real external
   load** — which is exactly `services/tonnage.py`'s eligibility predicate
   (`if reps and weight`, line 155). Warm-up sets would silently inflate weekly
   tonnage, feed `EXERCISE_MOVEMENT_WEIGHT` into Strain/AU, and pollute
   `services/strength.estimated_1rm`. CLAUDE.md's *"No per-set warm-up flag"*
   row stops being cosmetic the day this ships. **A per-set boolean is a
   prerequisite, not a follow-up.**
6. **Every new movement name needs its map entries** —
   `EXERCISE_MOVEMENT_WEIGHT`, `EXERCISE_BODY_REGION`,
   `sessions.movement_category` — or Strain lies at the 1.0 default. This is
   step 4 of `flexibility_integration_2026-08-16.md`, and it is the Stage 1 bug
   by another door (34 of 63 names).
7. **Every new movement name must clear `services/rules.py`.** Warm-up
   vocabulary is exactly the kind that collides — "good morning", "hip circles",
   "toe touch", "hands walking forward" — and `rules.py` has already been bitten
   by a hyphen and by a false CLEARED match on a heading token.
8. **⚠ It collides with the one-new-stressor-per-week rule.** Week 1 of the new
   block already has candidates: new loads, running, scapular endurance holds,
   isometric micro-doses, and the flexibility cluster session
   (`flexibility_integration_2026-08-16.md` §3). A warm-up change touches *every
   session*, which makes it either the least attributable change or, better, the
   one that goes in **first and alone** because it is the enabling change for
   the load increase rather than an added stressor. Worth deciding deliberately.
9. **If it is worth doing, it is worth pre-registering.** The house idiom exists
   (`release_protocols_2026-08-10.md`, `HRV_GARMIN_HOLD`): name the instrument
   and the verdict date before starting. The obvious instrument is already being
   collected — bracing failure rep number and right-hip drift are logged
   per-exercise as progression/regression criteria, and the 2025 log gives the
   baseline (*"brace collapses on rep 6+"*). A warm-up that works should move
   that number.

---

## 4 · The three questions that need answering before authoring

Genuinely open — they change the design, and they are not mine to settle.

1. **Modality for the raise**, given cycling is out on his own evidence (§2.2).
   Rowing, incline treadmill walk, and loaded carries all have different
   spine/hip-flexor profiles.
2. **⛔ Time budget — SETTLED AS A CEILING (§3.0-b), still open as an
   ALLOCATION.** Phase 2 is mandatory (§3.0) and the total is capped at 10–15
   min (§3.0-b), so the release block's dose is the variable that has to move.
   **The ceiling is the athlete's and is not in question. The split inside it
   is the physiotherapist's, and nothing in the release block gets cut by this
   repo.**

   **Open with the drift, not with a request.** `patient_profile.py:439` says
   *"5-minute release block before every session"* and the coded doses run
   16–22 min — so the question is *"which items carry the clinical effect at
   the 5 minutes your own note specifies?"*, not *"may we reduce this?"*. Take
   three specific items, in this order:

   - **The PNF dose.** 3 sets × 5 cycles *each side* is ~8–10 min, the largest
     single item by time. Its stretch bouts are only ~3 s, so it is **not** the
     force-deficit problem (§1.5) — the question is purely whether the
     inhibition it buys needs 30 cycles or fewer.
   - **The `laterality` discrepancy** (§0.2). `UPPER_GLUTE_RELEASE` is coded
     bilateral, its own text and the profile say *each side*. Resolving this
     may free ~4 min on its own, and it is a transcription question before it
     is a clinical one.
   - **The Right Posterior Hip Capsule Stretch at 2 × 60 s.** The only item at
     the ≥60 s dose where the force deficit turns large. Ask whether the
     clinical effect survives 2 × 45 s, and whether it can be moved earlier in
     phase 1 so the pressure work (no force cost) sits between it and load.
3. **Morning or evening sessions in the new block** (§2.4) — this changes the
   spinal exposure more than anything the warm-up itself contains.

---

## 5 · Evidence summary

| Claim | Grade | Practical implication |
|---|---|---|
| Muscle temp rises/falls ~0.1 °C/min; benefit gone ~15 min after stopping | A/D | The clock starts when you stop. Don't warm up then chat. |
| 5 min general warm-up = no better than nothing (1RM) | B | "5 minutes is enough" is measurably false *for near-max work*. |
| 15 min *low* intensity = +3%; 15 min *moderate* = −4% | B | Duration buys temperature; intensity buys fatigue. |
| General + specific beats specific alone by 8.4% (leg press 1RM) | B | Both components earn their place — near max. |
| Best squat ramp = 6 reps @ ~64% 1RM, reps matched to working set | B | The ~60%-load instinct is right; don't cut the reps. |
| At ~10RM loads, specific warm-up ≈ worthless | B | Don't ramp what you're not loading heavily. |
| Specific warm-up *reduced* reps on small upper-limb isolation | C | Over-preparing a small muscle is pure fatigue. |
| Static stretch ≥60 s/bout: ES −0.84; <60 s: ES −0.18 | A | Dose, not presence, is the variable. |
| A subsequent active warm-up counteracts the stretch deficit | A | **The fix for the current session order.** |
| Foam rolling / sustained pressure: no force cost | A | The two self-release items are fine where they are. |
| PNF/static/ballistic all reduce MTU stiffness comparably | B | Bad interaction with laxity — but a stiffness argument, not a force one. |
| PNF-specific *force* deficit (the −8.7% CMJ figure) | C | Reported as **non-significant**. Don't lean on it. |
| Applying dose thresholds: only the 2 × 60 s capsule stretch hits ≥60 s | A applied | Exposure is one exercise, right side only — not the block. |
| PAPE: ES ≈ 0.13, needs 4–7 min rest | A | Exclude. Bad time trade. |
| Cross-body warm-up transfer: limited/absent | C/D | Warming up untrained tissue buys nothing. |
| Warm-up reduces injury in **team sport** | A | Does **not** transfer to resistance training. |
| Warm-up reduces injury in **resistance training** | **none** | Say "mechanistic reasoning," never cite FIFA 11+. |
| RAMP as a protocol | E | Checklist, not evidence. |
| Early-morning lumbar bending stress ~300% higher | A/D | Time of day changes the requirement, not just the content. |
| Hypermobility: prepare for stiffness, not range | D/E | No official guidelines exist. Say so. |
| **His own log: glutes don't fire without warm-up; squat failures trace to it** | **n-of-1** | **The actual reason to build this.** |

---

## 6 · What this document deliberately does not do

- **No code.** Nothing in `services/`, `training_plan.py` or `views/` is touched.
- **No protocol.** No exercises named, no sets, no doses. §3 is constraints only.
- **No change to the release block.** §2.3 raises a real tension between a
  clinical prescription and a measured stiffness cost; resolving it is a
  physiotherapist decision and belongs on the 2026-08-16 list, not in a design
  doc.
- **No claim that warming up prevents injury.** §1.8 — the evidence isn't there,
  and this repo's habit is to say so rather than borrow authority from an
  adjacent literature.

---

### Sources

Barroso et al. 2013, *JSCR* 27(4):1009-1013 — [PubMed 22692116](https://pubmed.ncbi.nlm.nih.gov/22692116/) ·
Abad et al. 2011, *JSCR* 25(8):2242-2245 — [PubMed 21544000](https://pubmed.ncbi.nlm.nih.gov/21544000/) ·
Ribeiro et al. 2020, *IJERPH* 17:6882 — [PMC7558980](https://pmc.ncbi.nlm.nih.gov/articles/PMC7558980/) ·
Warneke et al. 2024, *J Sport Health Sci* — [PMC11336295](https://pmc.ncbi.nlm.nih.gov/articles/PMC11336295/) ·
"Warming up to improved performance?" 2025 — [SportRxiv 559](https://sportrxiv.org/index.php/server/preprint/view/559) ·
Nunes et al. 2024, older women upper/lower limb — [PMC11671542](https://pmc.ncbi.nlm.nih.gov/articles/PMC11671542/) ·
PAPE rest-interval meta-analysis — [PMC12852009](https://pmc.ncbi.nlm.nih.gov/articles/PMC12852009/) ·
Muscle temperature and performance review — [Tandfonline / RQES 2023](https://www.tandfonline.com/doi/full/10.1080/02701367.2021.2007212) ·
Adams & Hutton, diurnal spinal stresses — [PubMed 3589804](https://pubmed.ncbi.nlm.nih.gov/3589804/) ·
Jeffreys 2007, RAMP — [ResearchGate](https://www.researchgate.net/publication/280945961_Jeffreys_I_2007_Warm-up_revisited_The_ramp_method_of_optimizing_warm-ups_Professional_Strength_and_Conditioning_6_12-18) ·
EDS Society exercise guidance — [ehlers-danlos.org](https://www.ehlers-danlos.org/information/exercise-and-movement-for-adults-with-hypermobile-ehlers-danlos-syndrome-and-hypermobility-spectrum-disorders/) ·
Foam rolling vs stretching meta-analysis — [Frontiers Physiol 2021](https://www.frontiersin.org/journals/physiology/articles/10.3389/fphys.2021.720531/full)
