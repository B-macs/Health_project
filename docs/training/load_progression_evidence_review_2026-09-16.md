# Load progression — the evidence, and the rule the app now runs

*Written 2026-09-16. Three parallel literature reviews, each told to open and
verify every source (a fabricated paper and three miscited claims were caught
on a related topic in `rest_interval_evidence_review_2026-08-13.md` §1.9).
Grades: **A** meta-analysis or systematic review · **B** RCT · **C** other study ·
**D** mechanistic · **E** textbook, position statement or expert opinion.*

> ## What happened, and what was decided
>
> On 2026-09-15, the repeated week's squat day went up on every lift. The goblet
> squat started at **25 kg after 22.5 kg × 8, 8, 8** — the BOTTOM of its 8-12
> range — because the readiness streak was high. The athlete's back was tired
> the next afternoon. He asked that the app follow *"the best method"* from the
> best journals, and that loads not change every week.
>
> **Five rules, all live from 2026-09-16:**
>
> | # | Rule | Where | Grade of the best support |
> |---|---|---|---|
> | 1 | **Readiness never raises load.** Weight, band, reps, hold time and run minutes: a high streak changes nothing; a low one may still lower them. | `engine._READINESS_MODIFIER_TABLE`, `suggested_weight_kg`, `suggested_band_tier` | B (no trial raises load on readiness; HRV trials only held or cut) |
> | 2 | **A weight steps after two sessions in a row** at the same weight with every set at the rep target. | `engine.double_progression`, `PROGRESSION_SESSIONS` | E (ACSM 2009 body text, NSCA) — no trial compares triggers |
> | 3 | **After a step, the reps drop by what the step costs** — about 0.37 reps per 1% of load. | `engine.reps_after_load_step`, `REPS_LOST_PER_LOAD_PERCENT` | A (Nuzzo 2024 tables; the slope is derived here) |
> | 4 | **On a light weight, reps climb past the range first**, until the drop after the step still lands inside it. | `engine.progression_rep_target` | E + A (ACSM's 2-10%; the same slope read backwards) |
> | 5 | **No step when today's pain is above 5/10, or there is no check-in.** | `sessions.step_block_reason`, `STEP_PAIN_CEILING` | B, borrowed (HEAVY trial, shoulders; pain-monitoring model, Achilles) |
>
> Rules 2, 3 and 5 were the athlete's choices between options on 2026-09-16.
> The screen now says, under each lift, when its weight goes up next
> (`sessions.next_step_caption`) — it printed "3 sets × 8 reps" and never the
> range, so the trigger had been invisible.

---

## 1. When to add load, and how often

**No trial compares progression triggers** — one session against two, every
session against every week — and none tests the size of a load step. What exists
is convention:

- **ACSM 2009 position stand** (Med Sci Sports Exerc 41:687-708; PMID 19204579;
  E in substance). The body text recommends a 2-10% load increase when the
  lifter can do the current load for one to two reps over the target **on two
  consecutive sessions**. The abstract leaves out the two-session condition,
  which is why the rule is usually quoted without it. It is labelled evidence
  category B but cites one narrative review (Feigenbaum & Pollock 1999).
- **NSCA "2-for-2" rule** (Essentials of Strength Training and Conditioning; E;
  seen through secondary sources only — the textbook was not opened). Two or more
  reps over the goal on the last set, in two workouts in a row.
- **ACSM 2026 overview of reviews** (Currier et al., Med Sci Sports Exerc
  58:851-872; PMID 41843416; A). 137 reviews. Progression is not required for
  benefit in the short term; effort scales may be used to raise load as strength
  rises; there is insufficient evidence to quantify reps-in-reserve targets. It
  says nothing on triggers, frequency or step size, and it covers healthy adults.

**Why two sessions for this athlete:** it is the only published trigger; with
about one rep of session-to-session noise it is the less noisy choice; and each
lift is trained once a week, so a lift can get heavier at most every second
week — the athlete's own "don't change every week".

## 2. Adding reps works as well as adding load

- **Plotkin et al. 2022** (PeerJ 10:e14142; PMID 36199287; B). n=43 trained,
  8 weeks, sets to failure. Adding load and adding reps gave similar strength
  (squat 1RM +2.0 kg for load, 90% CI −2.4 to 7.8) and similar muscle growth.
- **Chaves et al. 2024** (Int J Sports Med 45:504-510; B). n=39 untrained, one
  leg per method, 10 weeks. No difference in strength or size.

This is what supports rule 4: when 2.5 kg is too big a jump, progressing reps
first costs nothing.

## 3. What the reps should do after a load step

**No trial tests it.** The load-reps relationship answers it:

- **Nuzzo, Pinto, Nosaka & Steele 2024** (Sports Med 54:303-321; PMID 37792272;
  A). 269 studies, 7,289 people. Reps to failure, general table: about 14.8 at
  70% 1RM, 12.4 at 75%, 9.8 at 80%, 7.2 at 85%. The reps a given step costs
  come out within about half a rep on the general, squat and bench tables;
  people differ by 2.5-3.3 reps (SD) at a given %1RM.
- **Derived here, not stated by the paper:** in the 8-15 rep zone, reps to
  failure fall about **0.37 per 1% of added load**. From 12 reps at the same
  effort:

  | Step | Example | Reps after | Old reset to 8 | Fixed −2 |
  |---|---|---|---|---|
  | +5.6% | RDL 45 → 47.5 kg | 10 | 2 reps too easy | right |
  | +6.3% | RDL 40 → 42.5 kg | 10 | 2 reps too easy | right |
  | +10% | goblet 25 → 27.5 kg | 8 | right | 2 reps too hard |
  | +11% | goblet 22.5 → 25 kg, from 13 | 9 | — | — |

- **How good is the lifter's own effort reading?** Halperin et al. 2022 (Sports
  Med 52:377; A): people under-predict reps to failure by about one rep, worse
  above 12 reps. Zourdos et al. 2021 (JSCR 35:S158; C): at a called RPE 7 in
  sets of ~16, the error was about 3.7 reps. So the calculated reps are a
  starting target, and the logged reps correct it.

**The 2026-08-10 design reset reps to the bottom of the range** and said its own
Epley-based estimate was a weak heuristic, citing this same meta-analysis. Rule 3
replaces that one decision; see §7.

## 4. Readiness must not raise load

- **HRV-guided resistance training only ever held, cut or skipped:**
  de Oliveira 2019 (Eur J Sport Sci; PMID 30702985; B, n=20) trained only when
  RMSSD was at baseline; Bittencourt 2024 (Front Physiol; PMID 39742158; B, n=21)
  skipped sessions on low RMSSD; DeBlauw 2021 (JFMK; PMID 34940511; B, n=55) cut
  volume and load by 25% on a low 7-day HRV and did half the hard days for equal
  strength. **No trial raised load because readiness was high.**
- **Morning HRV recovers before muscle does and does not predict the day's
  strength:** Flatt 2019 (Sports; C, n=10 — HRV back by 24 h, neuromuscular
  markers 48 h); Dobbs 2020 (MSSE; C, n=8 — HRV recovery not associated with
  squat velocity recovery); Thamm 2019 (IJERPH; B crossover, n=10 — no distinct
  association with maximal strength).
- **Adjusting load on the day works when it reads the lifting itself:** Hickmott
  2022 (Sports Med Open; PMID 35038063; A, 6 load studies) — autoregulated vs
  fixed loading, 1RM +2.07 kg (95% CI −0.32 to 4.46), RPE/RIR subgroup +3.15 kg
  (−0.14 to 6.45); Helms 2018 (Front Physiol; B, n=21); Graham & Cleather 2021
  (JSCR; B, n=31). These use reps in reserve, RPE or bar speed — never a morning
  score.

**Lowering on low readiness is kept.** DeBlauw supports cutting on low HRV
without loss, though that used a 7-day HRV average, not a composite score.

## 5. The pain gate

No trial compares performance-, symptom- and time-based progression for a lumbar
disc or for hypermobility. The best-matched evidence:

- **Liaghat et al. 2022, HEAVY trial** (BJSM; PMID 35649707; B). n=100,
  hypermobility with shoulder symptoms. Load rose when all sets exceeded the
  planned reps with symptoms under 5/10; function favoured heavy loading, with no
  serious adverse events.
- **Silbernagel 2007** (AJSM; PMID 17307888; B, Achilles). Loading allowed pain
  up to 5/10 if it settled by the next morning, with no harm.
- **Smith 2017** (BJSM; PMID 28596288; A). Exercise into some pain gave a small
  short-term benefit and no later difference.

The 2026-08-10 design had already chosen 5/10 on the athlete's own record.
**A missing check-in blocks a step** by his choice: an unmeasured day is not
evidence of a clean one.

## 6. Two measurements the app must not use for load

- **Heart-rate RPE per exercise is not a measure of reps in reserve.** Heart rate
  follows muscle mass and set duration: Matos-Santos 2017 (IJSM; C) — RPE did not
  correlate with any cardiovascular response; Sardeli 2017 (IJSM; C) — heart-rate
  rise did not differ between 80% and 30% 1RM to failure. The app's per-exercise
  RPE comes from %HRR; nothing in the progression reads it, and nothing should.
- **The composite readiness score** has no validation against strength
  performance. Oura's HRV input itself is accurate (Dial 2025, Physiol Rep; C).

## 7. What the 2026-08-10 design (`auto_progression_design.md`) becomes

That design was approved and never built. This review **keeps** its direction
and **changes two decisions**, both on the athlete's choice:

| 2026-08-10 design | Now | Why |
|---|---|---|
| Rep target +1 per qualifying session; step at the top (5 sessions per weight on an 8-12 range) | Two sessions in a row at the target | The only published trigger; the ladder is not tested either and at one session a week holds a weight for five weeks |
| Reps reset to the bottom of the range after a step | Reps drop by what the step costs | Nuzzo 2024 directly; the design flagged its own reset as a weak heuristic |
| Readiness nudge retired | Retired | Agrees |
| Reps first on too-coarse steps (25% cap) | Reps first whenever the drop would leave the range | Same idea, continuous |
| Pain gate 5/10, missing check-in holds | Same | Agrees |

**Not built from that design, and still open:** a rollback after a failed step,
the 21-day stale-gap reset, the 5-day step spacing (two once-weekly sessions make
it redundant for now), the RPE-ceiling gate, the decline lockout, and the stored
per-session prescription snapshot.

## 8. The one field that would improve this most

**Reps in reserve on the last set.** With it, a step would need the top of the
range AND at least the target RIR, and a set under target RIR would hold (Helms
2018; Graham & Cleather 2021). Without it, "12 reps" does not say how hard the 12
were. Not built: it is a new stored field, and the Supabase table needs its
column added by hand.

## 9. Not verified

- The NSCA textbook's exact wording and increment table (secondary sources only).
- Graham & Cleather 2021 results beyond the abstract, as read by one of the three
  reviews (another read the full text).
- Zhang 2021's effect sizes (implausible values in the abstract; not relied on).
- Mann 2010 (APRE) was not randomised — the groups trained in different years —
  so it is not relied on.
- Doherty 2025 on wearable composite scores (page blocked).

---

## 10. Addendum 2026-10-16 — his double progression

*The athlete: "now we need to look at incremental weight and range adjustments.
... research this and find out the best increase each week to be done
automatically — Lat pull down current setup is as follows - Last: 45kg × 10,
50kg × 11, 50kg × 8 (2026-10-10) · vs prescribed -3 reps ... this week it gave me
50kg x 8, to start I believe it should be a range and a weight if I go up in
weight then we try for the middle to low range until we do that weight at the
upper range for one week then we go up the next week — If the last reps of the
last set are outside the range we increase the first set of the next week
automatically."*

**What happened to the lat pulldown.** Its range is 10-12 with 2.5 kg steps.
He went 45 → 50 kg, which is +11%: at about 0.37 reps per 1% (§3) that costs
about 4 reps, so 12 becomes about 8 — under a 10-12 range. That is the −3 he
saw. The next prescription then read last time's set (50 × 8) and showed no
range at all.

**What the evidence adds, searched 2026-10-16:**

- **Still no trial compares a one-week trigger with a two-session one** (§1).
  His trigger is as well supported as the current rule, and for a lift trained
  once a week it lets the weight rise twice as often.
- **Adding reps works as well as adding load** (§2: Plotkin 2022; Chaves 2024),
  so climbing reps inside the range costs nothing.
- **The reps a step costs** (§3, Nuzzo 2024): a 2.5 kg step at 50 kg (+5%)
  costs about 2 reps, so it lands in the low-to-middle of an 8-12 range — his
  "middle to low range", by arithmetic.
- **Step size: no trial settles it.** Training guides give 2-5% for the upper
  body and small muscles and 5-10% for the lower body and large muscles; very
  small steps progressed as well as larger ones over 8 weeks (Hostler et al.
  2001, J Strength Cond Res; read through a secondary source). The usable step
  is the equipment's smallest one.
- **Adjusting the next load from the reps done** — his "last set outside the
  range" rule — is the approach that ranked first for 1RM gains among
  autoregulation methods in a 2025 network meta-analysis (APRE; *J Exerc Sci
  Fit* 2025; abstract only; the squat differences were small, so the ranking is
  tentative).
- **A wide range of loads builds muscle when sets end near failure**
  (Schoenfeld, Grgic, Van Every & Plotkin 2021, *Sports* 9:32), so a range can
  be chosen to fit the equipment's step.

**PROPOSED rule, for his approval** (it changes rules 2 and 3 of 2026-09-16):

1. Each lift has one working weight for all its working sets, a rep range, and
   today's aim — all three shown on the screen.
2. Between steps, the aim is one rep more than the last set made last time, up
   to the top of the range.
3. The weight goes up one step when the last set reached the top of the range in
   every session of that lift in the past week.
4. After a step, the aim is what the step costs from the last set's reps
   (0.37 per 1%), kept inside the range.
5. A range is at least one step wide: its width is at least the reps one step
   costs, plus one. Defaults: 8-12 for compounds, 10-15 for isolation. When a
   step is too coarse even so, the reps climb past the top first (rule 4 of
   2026-09-16, kept).
6. The last set under the bottom of the range in two sessions in a row, at one
   weight: back one step (the rollback this review listed as missing in §7).
7. Kept: readiness never raises load; pain above 5/10 or no check-in blocks a
   step; a failed week holds the load.

**His lat pulldown under it:** range 8-12, 50 kg. The last set made 8, inside
the range, so next time is 50 kg with an aim of 9; when the last set makes 12,
the next session is 52.5 kg with an aim of 10.

**Sources (2026-10-16):** [Hostler et al. 2001, via PEDro](https://search.pedro.org.au/search-results/record-detail/10350) ·
[Autoregulated training network meta-analysis, 2025](https://lida.sport-iat.de/ta/Record/4094556) ·
[Schoenfeld et al. 2021](https://doaj.org/article/6d51b905504d46f0873bb43d5d84bf21) ·
[increment guidance, a study guide (not a primary source)](https://open-exam-prep.com/study-guides/cscs/program-design/resistance-training-program-design).
