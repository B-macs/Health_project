# Chest — the decider's tier list

**No source has ranked chest exercises yet.** This list is the tier decider's
(`services/tier_decider.py`; the ratings and their rules are in
`exercise_features.py`), made 2026-10-16 at the athlete's request: *"use the
same script to create a tier list for back and chest, I can copy in later
videos to see if you're correct but go for that for now."*

- **How close it gets:** on the five lists already recorded, scored on a list it
  had not been calibrated on, it gives the source's exact tier 46 times in 111
  (41%) and comes within one tier 107 times (96%). Guessing "A" for everything
  gives 32% and 74%. Expect about four exact tiers in ten, and most of the rest
  one tier off.
- **Used like a source list until a video arrives** (athlete: *"go for that for
  now"*): step 5 picks from its S and A tiers. When a video for this area is
  pasted, its list replaces this one, and
  `python scripts/tier_decider.py compare <file>` records how close the decider
  was.
- **Known weak spot:** the decider sees risk only through "comfort", so a
  position most lists mark down for joint risk scores higher than a video
  would likely put it (here, the guillotine press and the dip). The athlete's own rules remove those anyway.
- **The method:** score = 3 × stretch + target + stable + load + comfort,
  minus 4 for a combination move, jump, swing or cardio (−4 to 14). D from 3,
  C from 4, B from 6, A from 8, S from 13 — cut points calibrated on the five
  recorded lists.

## The full list — the decider's, best first

| # | Exercise | Tier | Score | Why |
|---|---|---|---|---|
| 1 | Pec deck (machine fly) | **S** | 14 | tension at the stretch, supported |
| 2 | Seated cable fly (bench between the cables) | **S** | 14 | tension at the stretch, supported |
| 3 | High-to-low cable fly | **S** | 13 | tension at the stretch; standing |
| 4 | Machine chest press, seated | **S** | 13 | stable; the depth depends on the machine |
| 5 | Machine incline press | **S** | 13 | stable, upper chest |
| 6 | Smith machine bench press | **S** | 13 | deep and stable |
| 7 | Smith machine incline press | **S** | 13 | deep and stable, upper chest |
| 8 | Standing cable fly, cables at chest height | **S** | 13 | tension at the stretch; standing |
| 9 | Dumbbell bench press, flat | A | 12 | deeper than a barbell |
| 10 | Incline dumbbell press | A | 12 | deeper than a barbell |
| 11 | Barbell bench press, flat | A | 11 | the triceps share; the bar stops at the chest |
| 12 | Deficit push-up (hands on handles or plates) | A | 11 | full depth; body weight |
| 13 | Dumbbell fly, flat | A | 11 | hardest at the stretch; light dumbbells |
| 14 | Incline barbell bench press | A | 11 | as the flat bench, upper chest |
| 15 | Incline dumbbell fly | A | 11 | as the flat fly, upper chest |
| 16 | Guillotine press (bar to the neck) | A | 10 | a risky shoulder position |
| 17 | Low-to-high cable fly | A | 10 | less stretch |
| 18 | Dip, leaning forward | A | 9 | deep; hard on the shoulder for many |
| 19 | Weighted push-up (plate or vest) | A | 9 | load added awkwardly |
| 20 | Decline barbell bench press | A | 8 | a shorter range |
| 21 | Push-up | A | 8 | the floor limits the depth; body weight |
| 22 | Single-arm landmine press | A | 8 | the front delt and triceps lead |
| 23 | Barbell floor press | B | 7 | the floor stops the range |
| 24 | Close-grip bench press | B | 7 | the triceps end the set |
| 25 | Band chest press | C | 5 | a band: no tension at the stretch |
| 26 | Svend press | C | 4 | light plates; little stretch |
| 27 | Clap push-up | F | -1 | a jump |

## By tier

- **S (8):** #1, #2, #3, #4, #5, #6, #7, #8
- **A (14):** #9, #10, #11, #12, #13, #14, #15, #16, #17, #18, #19, #20, #21, #22
- **B (2):** #23, #24
- **C (2):** #25, #26
- **F (1):** #27

## Against the athlete's rules (checked 2026-10-16)

- **Barbells are out:** the barbell bench press (flat, incline and decline),
  the close-grip bench press, the barbell floor press and the guillotine press.
- **Out by his own precaution** (2026-10-16): dips and the deep wide-grip bench.
- **The measured right-arm limit:** a fly or a deep press takes the arm behind
  the line of the body; on the right it goes only as deep as it goes easily,
  never forced deep (a face-down arm raise, 20 cm right against 40 cm left,
  2026-08-13).
- **The right-shoulder release** comes straight before any chest press (his
  rule, 2026-10-16: *"It's to release the area before working on it"*).
- **Gym:** the machine chest press, the cable stack, dumbbells and benches are
  confirmed; the Smith machine is taken as present. Not confirmed: the pec deck
  and the incline machine.
- **Safety rules:** every chest exercise here reads "unknown"; the pick gets a
  rule before it is used.

**Pick (step 5, 2026-10-16, for his approval):** the **machine chest press** (S).
The chest is one of goal A's main lifts, whose working weight gate 1 measures,
so its pick is a press, not a fly; among the S presses it is the one confirmed
in his gym, on a fixed path with the back supported. One chest exercise of 3
sets in two sessions a week gives the area its 6 hard sets.

## Unranked source advice

None yet — no video about chest exercises has been pasted.
