"""The tier decider's ratings: five numbers per exercise, from its mechanics.

services/tier_decider.py turns them into a score and a tier. RECORDED rates
every row of the five source lists in docs/training/tier_lists/ — keyed by the
file and the row number, with the row's own name, which a test compares to the
markdown — so the decider can be calibrated and checked against the sources.
DECIDED rates the candidates of the areas no source has ranked yet (back and
chest, 2026-10-16); their tiers are the decider's, written into back.md and
chest.md, until a video for that area arrives.

THE RULE FOR EACH VALUE (0, 1 or 2). Rate the exercise, not the source's tier:

stretch  2  the hardest point, or high tension, is where the target muscle is
            longest, over a full range
         1  some tension at long length, or a partial range
         0  little or no tension at long length (the hardest point is the short
            end, or the range never reaches the long end)
target   2  the target muscle is what ends the set
         1  it shares the work, so another muscle or the trunk often ends it
         0  something else ends it (balance, grip, the hip flexors, breathing,
            the other half of a combination)
stable   2  a machine, cable or bench, with the body supported or braced
         1  a free weight or standing, with some balance
         0  an unstable surface, a swing, a ballistic move, or a high balance
            demand
load     2  small steps over a wide range (stack, plates, dumbbells, cable)
         1  load added awkwardly or capped (one dumbbell held, ankle weights,
            body-weight progressions, assistance)
         0  no practical way to add load (bands, body weight only, light tools)
comfort  2  a smooth resistance curve, joint-friendly, a quick set-up
         1  one known problem (a pinch, an awkward bar, a long set-up, a joint
            that complains for some)
         0  commonly uncomfortable or risky
not_growth  a combination move, a jump or swing, an unstable-surface drill, or
            cardio: mainly something other than muscle-building work

The target muscle is the area the row belongs to: the abs in abs.md, the quads
in quads.md, the named head in shoulders.md; in hamstrings.md, the hamstrings
and glutes together, or the lower back for row 5. For back, the lats and the
upper back; for chest, the pecs.

These ratings were written on 2026-10-16 by someone who had read the five
lists, so the decider's agreement with them is in-sample. See the decider's
docstring for what that does and does not show.
"""
from services.tier_decider import Features as F

RECORDED: dict[str, dict[int, F]] = {
    "abs.md": {
        1: F("Sit-up", 0, 0, 2, 1, 1, why="the floor stops the stretch; the hip flexors finish the rep"),
        2: F("Crunch on the floor", 0, 2, 2, 1, 2, why="abs do the work; the floor stops the stretch"),
        3: F("Crunch on an ab mat or a rolled towel", 2, 2, 2, 1, 2, why="the mat lets the abs lengthen"),
        4: F("Lat-pulldown crunch, unassisted (knees under the pad)", 2, 2, 2, 1, 1,
             why="deep stretch, very stable; body weight only, very hard"),
        5: F("Lat-pulldown crunch, cable-assisted", 2, 2, 2, 2, 2,
             why="the stack sets the assistance in small steps"),
        6: F("Lying leg raise", 0, 0, 2, 1, 1, why="the hip flexors lift the legs"),
        7: F("Hanging knee raise", 0, 0, 1, 1, 1, why="hip flexors; hanging swing; grip"),
        8: F("Hanging straight-leg raise (L-shape)", 0, 0, 1, 1, 1, why="a longer lever on the hip flexors"),
        9: F("Hanging leg raise with a pelvic curl (C-shape)", 1, 1, 0, 1, 1, why="the abs help; the swing"),
        10: F("Hanging leg raise, back braced against a bar", 1, 1, 2, 1, 1,
              why="braced; ankle weights; hip flexors still high"),
        11: F("Captain's chair leg raise, with a pelvic curl", 1, 1, 2, 1, 2, why="pads instead of a grip"),
        12: F("Plank", 0, 1, 2, 0, 2, why="no range, no stretch, no load"),
        13: F("RKC plank", 0, 2, 2, 0, 1, why="the abs work hard; no range, no load"),
        14: F("Dragon flag", 0, 2, 1, 1, 0, why="high activity; no stretch; hard on the neck and shoulders"),
        15: F("Front lever raise", 0, 2, 1, 1, 0, why="as the dragon flag, hanging"),
        16: F("Garhammer hold", 2, 1, 1, 1, 1, why="held where the abs are long; progress hard to track"),
        17: F("Garhammer raise", 2, 2, 1, 1, 1, why="the abs curl the pelvis from a long position"),
        18: F("Reverse crunch on a bench, knees at 90°", 0, 2, 2, 1, 2, why="the bench stops the stretch"),
        19: F("Reverse crunch with an ab mat or towel under the lower back", 2, 2, 2, 1, 2,
              why="the mat restores the stretch"),
        20: F("Ab wheel rollout", 2, 1, 1, 0, 1, why="long at full reach; the shoulders share; hard to load"),
        21: F("Bicycle crunch", 0, 1, 2, 0, 2, why="no stretch, no load"),
        22: F("V-up", 0, 0, 1, 1, 1, why="hip flexors"),
        23: F("Butterfly (flutter) kicks", 0, 0, 2, 0, 1, why="almost all hip flexor"),
        24: F("Mountain climbers", 0, 0, 1, 0, 2, not_growth=True, why="cardio"),
        25: F("Dead bug", 0, 1, 2, 0, 2, why="a bracing drill"),
        26: F("Cable crunch, kneeling, facing the machine", 1, 1, 1, 2, 2,
              why="little tension at the stretch; the hips can swing"),
        27: F("Cable crunch, kneeling, facing away", 2, 2, 2, 2, 2, why="the hips rest on the pole"),
        28: F("Cable crunch, standing, facing away", 2, 2, 2, 2, 2, why="as kneeling, steadier"),
        29: F("Lat-pulldown cable crunch, facing the machine", 1, 2, 2, 2, 2, why="stable; not a full stretch"),
        30: F("Lat-pulldown cable crunch, facing away (seat pad as low-back support)", 2, 2, 2, 2, 2,
              why="full stretch, hips held by two pads"),
    },
    "quads.md": {
        1: F("Squat or lunge combined with an upper-body move (e.g. squat + press, lunge + curl)",
             1, 0, 1, 1, 1, not_growth=True, why="the upper body ends the set"),
        2: F("Bosu-ball squat", 1, 0, 0, 0, 1, not_growth=True, why="unstable surface"),
        3: F("Barbell back squat, high bar", 2, 1, 1, 2, 1, why="deep knee bend; the glutes and back share"),
        4: F("Barbell front squat", 2, 2, 1, 2, 0, why="more quad; an awkward bar position"),
        5: F("Barbell back squat, low bar", 1, 1, 1, 2, 1, why="less knee bend"),
        6: F("Hack squat", 2, 2, 2, 2, 2, why="deep, supported, easy to load"),
        7: F("Pendulum squat", 2, 2, 2, 2, 2, why="deep, supported, a natural arc"),
        8: F("Smith machine squat", 2, 1, 2, 2, 2, why="deep and stable; foot position shares it"),
        9: F("45° leg press", 1, 2, 2, 2, 2, why="often less depth"),
        10: F("Horizontal leg press", 0, 2, 2, 1, 2, why="short range; the stack runs out"),
        11: F("Lunge, as a quad exercise", 2, 1, 1, 1, 1, why="the glutes share; dumbbells held"),
        12: F("Leg extension, seat set back", 1, 2, 2, 2, 1, why="hardest at the short end; knee load for some"),
        13: F("Reverse Nordic", 2, 2, 1, 0, 1, why="deep quad stretch; hard to load"),
        14: F("Goblet squat", 2, 1, 1, 1, 2, why="capped by what can be held"),
        15: F("Jump squat", 0, 1, 1, 0, 1, not_growth=True, why="a jump"),
        16: F("Bulgarian split squat", 2, 1, 1, 1, 1, why="big stretch; dumbbells held; very tiring"),
        17: F("Deadlift", 0, 0, 1, 2, 1, why="a quarter squat for the quads"),
        18: F("Step-up", 1, 1, 0, 1, 2, why="balance; little quad stretch"),
        19: F("Pistol squat", 2, 1, 0, 0, 1, why="balance; body weight"),
        20: F("Sissy squat", 2, 2, 1, 0, 1, why="huge stretch; hard to load"),
    },
    "glutes.md": {
        1: F("Barbell hip thrust", 0, 2, 1, 2, 0, why="little stretch; the bar pinches; slow set-up"),
        2: F("Machine hip thrust (belt type)", 0, 2, 2, 2, 2, why="little stretch; comfortable, stable"),
        3: F("Single-leg dumbbell hip thrust", 0, 2, 1, 1, 2, why="little stretch; one side at a time"),
        4: F("Glute bridge", 0, 1, 2, 2, 1, why="a hip thrust with less range"),
        5: F("Frog pumps", 0, 1, 2, 0, 2, why="hard to load, little stretch"),
        6: F("Barbell squat", 2, 1, 1, 2, 1, why="big glute stretch; the quads share"),
        7: F("Smith machine squat, feet forward", 2, 1, 2, 2, 2, why="feet forward for the glutes; stable"),
        8: F("Bulgarian split squat, front foot forward, leaning forward", 2, 1, 1, 1, 1,
             why="deep stretch; dumbbells held; very tiring"),
        9: F("Donkey kick", 0, 1, 2, 0, 2, why="little tension in the stretch; hard to load"),
        10: F("Fire hydrant", 0, 1, 2, 0, 2, why="little tension; hard to load"),
        11: F("Kickback, cable or machine, braced", 1, 2, 2, 2, 2, why="a small stretch; stable, smooth"),
        12: F("Step-up, box at or above knee height", 2, 1, 1, 1, 1, why="deep stretch from a high box; balance"),
        13: F("Machine hip abduction, leaning forward about 30°", 1, 2, 2, 2, 2,
              why="the lean adds stretch; direct, easy to load"),
        14: F("Cable hip abduction", 1, 2, 1, 1, 1, why="harder to load and set up"),
        15: F("Lateral band walk", 0, 1, 1, 0, 2, why="a band: no tension in the stretch"),
        16: F("Walking lunge, long strides, slight forward lean", 2, 1, 1, 1, 1,
              why="deep stretch; dumbbells held; balance"),
        17: F("Smith machine lunge", 2, 1, 2, 2, 2, why="the lunge's stretch, on a stable bar"),
        18: F("Smith machine lunge, front foot on a small box", 2, 1, 2, 2, 2, why="more range at the bottom"),
        19: F("Curtsy lunge", 2, 1, 0, 1, 1, why="balance; harder to load"),
        20: F("Conventional deadlift", 2, 0, 1, 2, 0, why="big stretch, but the whole body tires first"),
        21: F("Sumo deadlift", 2, 0, 1, 2, 0, why="as the conventional deadlift"),
        22: F("Romanian deadlift", 2, 1, 1, 2, 1, why="loaded at the stretch; the hamstrings share"),
        23: F("45° back extension, upper back rounded", 2, 1, 2, 1, 2,
              why="the glutes work long and short; plates held"),
        24: F("Cable pull-through", 2, 1, 1, 1, 1, why="awkward once heavy"),
        25: F("Kettlebell swing", 0, 0, 1, 1, 1, not_growth=True, why="a swing"),
    },
    "hamstrings.md": {
        1: F("Romanian deadlift", 2, 1, 1, 2, 1, why="loaded at the stretch"),
        2: F("Stiff-leg deadlift", 2, 1, 1, 2, 1, why="as the Romanian deadlift"),
        3: F("Single-leg Romanian deadlift", 2, 1, 0, 1, 1, why="balance"),
        4: F("Low-bar squat", 0, 0, 1, 2, 1, why="the hamstrings barely lengthen in a squat"),
        5: F("Hyperextension and reverse hyperextension (ranked together)", 2, 1, 2, 1, 1,
             why="the lower back works from long to straight"),
        6: F("Nordic hamstring curl", 2, 2, 1, 0, 0, why="lengthening under load; hard to load; risky"),
        7: F("Seated leg curl", 2, 2, 2, 2, 2, why="the hips bent keep the hamstrings long"),
        8: F("Lying leg curl", 1, 2, 2, 2, 2, why="the hips straight: a shorter hamstring"),
        9: F("Good morning", 2, 1, 1, 1, 0, why="a bar on the back; injury risk"),
        10: F("Butt blaster (machine)", 1, 2, 2, 2, 2, why="a machine kickback"),
        11: F("Cable glute kickback", 1, 2, 1, 2, 2, why="a small stretch; standing"),
        12: F("Donkey kick", 0, 1, 2, 0, 2, why="no resistance"),
        13: F("Hip thrust (the version is not named)", 0, 2, 1, 2, 1, why="little stretch"),
        14: F("Single-leg hip thrust", 0, 2, 1, 1, 2, why="little stretch; lighter"),
        15: F("Reverse lunge", 2, 1, 1, 1, 2, why="the step back loads the glutes long"),
        16: F("Step-up", 1, 1, 0, 1, 2, why="balance; a normal box"),
    },
    "shoulders.md": {
        1: F("Standing dumbbell lateral raise", 0, 2, 1, 2, 2, why="no tension at the bottom"),
        2: F("Lean-in dumbbell lateral raise (leaning against a bench or rack)", 1, 2, 1, 2, 2,
             why="the lean moves tension toward the stretch"),
        3: F("Lean-away dumbbell lateral raise", 0, 2, 1, 2, 2, why="still little tension at the stretch"),
        4: F("Super-range lateral raise", 0, 2, 1, 2, 1, why="the dumbbell curve"),
        5: F("Barbell overhead press, standing", 2, 1, 0, 2, 1, why="the triceps share; balance"),
        6: F("Barbell overhead press, seated", 2, 1, 1, 2, 1, why="the triceps share"),
        7: F("Dumbbell shoulder press", 2, 1, 1, 2, 2, why="deep; the triceps share"),
        8: F("Machine shoulder press", 2, 1, 2, 2, 2, why="deep and stable"),
        9: F("Arnold-style side-lying dumbbell raise", 2, 2, 2, 1, 1, why="tension at the stretch; one light dumbbell"),
        10: F("Front raise — dumbbell, cable or machine", 0, 2, 1, 2, 2, why="hardest at the top"),
        11: F("Standing machine lateral raise", 1, 2, 2, 2, 2, why="a smaller stretch than cables"),
        12: F("Seated machine lateral raise", 1, 2, 2, 2, 0, why="the pad sits badly"),
        13: F("Cable lateral raise, cable at hand height", 2, 2, 2, 2, 2, why="tension at the stretch; braced"),
        14: F("Cable Y raise", 2, 2, 2, 2, 1, why="more range; harder to learn"),
        15: F("Behind-the-back cuffed cable lateral raise", 2, 2, 1, 2, 2, why="both arms at once, standing"),
        16: F("Banded lateral raise", 0, 2, 1, 0, 2, why="a band: no tension at the stretch"),
        17: F("Upright row, cable with a rope", 0, 0, 1, 2, 1, why="the upper traps take over"),
        18: F("Reverse pec deck", 1, 2, 2, 2, 2, why="even tension; a modest stretch"),
        19: F("Rope face pull", 2, 1, 1, 2, 2, why="a big stretch; the middle traps share"),
        20: F("Bent-over reverse dumbbell fly", 0, 2, 0, 2, 1, why="no tension at the stretch; bent over"),
        21: F("Reverse cable crossover", 2, 2, 1, 2, 2, why="huge range, even tension; standing"),
    },
}

DECIDED: dict[str, list[F]] = {
    "back": [
        F("Pull-up, overhand grip", 2, 1, 1, 1, 1, why="a full hang; grip and body weight"),
        F("Chin-up, underhand grip", 2, 1, 1, 1, 1, why="the biceps share more"),
        F("Neutral-grip pull-up", 2, 1, 1, 1, 2, why="the friendliest grip"),
        F("Assisted pull-up machine (kneeling pad)", 2, 2, 2, 2, 2, why="the stack sets the help"),
        F("Lat pulldown, wide overhand grip", 1, 2, 2, 2, 2, why="a shorter range than a close grip"),
        F("Lat pulldown, close neutral grip", 2, 2, 2, 2, 2, why="full stretch at the top, thighs held"),
        F("Single-arm cable pulldown, half-kneeling", 2, 2, 1, 2, 2, why="more stretch; less braced"),
        F("Behind-the-neck lat pulldown", 1, 2, 2, 2, 0, why="a strained shoulder position"),
        F("Straight-arm cable pulldown", 2, 2, 1, 2, 2, why="the lats alone, from long"),
        F("Cable pullover, lying or kneeling", 2, 2, 2, 2, 2, why="the lats alone, from long, supported"),
        F("Dumbbell pullover across a bench", 2, 1, 2, 1, 1, why="the chest shares; one dumbbell"),
        F("Machine pullover", 2, 2, 2, 2, 2, why="the lats alone, supported"),
        F("Barbell bent-over row", 1, 1, 1, 2, 1, why="the lower back holds the position"),
        F("Pendlay row (from the floor each rep)", 2, 1, 1, 2, 0, why="explosive; the lower back"),
        F("Yates row (underhand, more upright)", 1, 1, 1, 2, 1, why="a shorter range"),
        F("Chest-supported T-bar row", 2, 2, 2, 2, 2, why="the chest held; full range"),
        F("Seal row (lying on a high bench)", 2, 2, 2, 2, 1, why="a bench to set up"),
        F("Chest-supported dumbbell row (incline bench)", 2, 2, 2, 2, 2, why="the chest held; dumbbells"),
        F("Machine row, chest-supported", 2, 2, 2, 2, 2, why="the chest held; the stack"),
        F("Seated cable row, close grip", 2, 1, 1, 2, 2, why="the torso can swing"),
        F("Single-arm dumbbell row (hand and knee on a bench)", 2, 2, 2, 2, 2, why="braced; one side at a time"),
        F("Kroc row (heavy, with some body swing)", 2, 1, 1, 2, 1, why="the swing and the grip"),
        F("Meadows row (landmine, one arm)", 2, 2, 1, 2, 1, why="a landmine to set up"),
        F("Single-arm seated cable row", 2, 2, 1, 2, 2, why="long reach; less braced"),
        F("Inverted row", 1, 1, 1, 0, 2, why="body weight; only the angle changes"),
        F("Conventional deadlift (as a back exercise)", 0, 0, 1, 2, 0, why="the lats only hold the bar in"),
        F("Rack pull", 0, 0, 1, 2, 1, why="the upper back holds, it does not move"),
        F("High row machine (pulling down and back)", 2, 2, 2, 2, 2, why="supported, full range"),
        F("Band pull-apart", 0, 1, 1, 0, 2, why="a band: no tension at the stretch"),
        F("Renegade row", 1, 0, 0, 1, 1, not_growth=True, why="a plank and a row together"),
    ],
    "chest": [
        F("Barbell bench press, flat", 2, 1, 1, 2, 1, why="the triceps share; the bar stops at the chest"),
        F("Incline barbell bench press", 2, 1, 1, 2, 1, why="as the flat bench, upper chest"),
        F("Decline barbell bench press", 1, 1, 1, 2, 1, why="a shorter range"),
        F("Close-grip bench press", 1, 0, 1, 2, 1, why="the triceps end the set"),
        F("Barbell floor press", 0, 1, 2, 2, 2, why="the floor stops the range"),
        F("Dumbbell bench press, flat", 2, 1, 1, 2, 2, why="deeper than a barbell"),
        F("Incline dumbbell press", 2, 1, 1, 2, 2, why="deeper than a barbell"),
        F("Smith machine bench press", 2, 1, 2, 2, 2, why="deep and stable"),
        F("Smith machine incline press", 2, 1, 2, 2, 2, why="deep and stable, upper chest"),
        F("Machine chest press, seated", 2, 1, 2, 2, 2, why="stable; the depth depends on the machine"),
        F("Machine incline press", 2, 1, 2, 2, 2, why="stable, upper chest"),
        F("Dip, leaning forward", 2, 1, 1, 1, 0, why="deep; hard on the shoulder for many"),
        F("Push-up", 1, 1, 2, 0, 2, why="the floor limits the depth; body weight"),
        F("Deficit push-up (hands on handles or plates)", 2, 1, 2, 0, 2, why="full depth; body weight"),
        F("Weighted push-up (plate or vest)", 1, 1, 2, 1, 2, why="load added awkwardly"),
        F("Dumbbell fly, flat", 2, 2, 1, 1, 1, why="hardest at the stretch; light dumbbells"),
        F("Incline dumbbell fly", 2, 2, 1, 1, 1, why="as the flat fly, upper chest"),
        F("Standing cable fly, cables at chest height", 2, 2, 1, 2, 2, why="tension at the stretch; standing"),
        F("Low-to-high cable fly", 1, 2, 1, 2, 2, why="less stretch"),
        F("High-to-low cable fly", 2, 2, 1, 2, 2, why="tension at the stretch; standing"),
        F("Seated cable fly (bench between the cables)", 2, 2, 2, 2, 2, why="tension at the stretch, supported"),
        F("Pec deck (machine fly)", 2, 2, 2, 2, 2, why="tension at the stretch, supported"),
        F("Svend press", 0, 1, 1, 0, 2, why="light plates; little stretch"),
        F("Single-arm landmine press", 1, 0, 1, 2, 2, why="the front delt and triceps lead"),
        F("Guillotine press (bar to the neck)", 2, 1, 1, 2, 0, why="a risky shoulder position"),
        F("Band chest press", 0, 1, 2, 0, 2, why="a band: no tension at the stretch"),
        F("Clap push-up", 0, 1, 1, 0, 1, not_growth=True, why="a jump"),
    ],
    # ── Step 8's better-exercise checks, 2026-10-16 (CLAUDE.md Key Rule 25) ──
    # The athlete: "even then it can be overwritten with a better exercise to get
    # the same goal quicker". Five areas of the 12-week block have no ranked list;
    # each pick is checked against the decider's list for its area. The target
    # muscle is named in each file's title.
    "abs_sides": [
        F("Cable side bend, standing (low pulley)", 2, 2, 1, 2, 1,
          why="the cable loads the long side; bending sideways under load"),
        F("Side bend on the 45° back-extension bench", 2, 2, 2, 1, 1,
          why="braced on the bench; a plate held; bending sideways"),
        F("Dumbbell side bend", 2, 2, 1, 1, 1, why="one dumbbell held; bending sideways under load"),
        F("Kneeling cable crunch with a twist", 2, 1, 2, 2, 0,
          why="bending and twisting under load together"),
        F("High-to-low cable woodchop", 1, 1, 1, 2, 2, why="the hips and arms share the turn"),
        F("Low-to-high cable woodchop", 1, 1, 1, 2, 2, why="as the high-to-low, turning upward"),
        F("Landmine rotation", 1, 1, 1, 2, 1, why="a landmine to set up; the hips share"),
        F("Side plank with hip raises", 1, 1, 1, 1, 2,
          why="a short range; the support shoulder shares; body weight"),
        F("Pallof press", 0, 1, 1, 2, 2, why="no movement, so no stretch"),
        F("Suitcase carry", 0, 1, 1, 2, 2, why="the sides hold; they do not move"),
        F("Side-lying crunch on the floor", 0, 2, 2, 0, 2, why="the floor blocks the stretch; body weight"),
        F("Hanging oblique knee raise", 1, 0, 0, 1, 1, why="the hip flexors lift the knees; a swing"),
        F("Side plank, held", 0, 1, 1, 0, 2, why="no range; only time is added"),
        F("Russian twist with a plate", 0, 1, 1, 1, 0, why="bending and twisting; little stretch"),
    ],
    "hip_rotators": [
        F("Prone cable hip rotation (face down, knee bent, cable at the ankle)", 2, 2, 2, 2, 1,
          why="the hips stay straight; a long set-up"),
        F("Seated cable hip rotation (knee bent, cable at the ankle)", 2, 2, 2, 2, 1,
          why="the hip bent to 90 degrees; a long set-up"),
        F("90/90 hip rotation with lift-offs", 2, 1, 2, 0, 2, why="turns to the end of the range; body weight only"),
        F("Hip airplane (hand on a wall)", 1, 1, 1, 1, 2,
          why="turns the pelvis on a standing leg; balance shares the work"),
        F("Prone hip internal rotation with ankle weights", 0, 2, 2, 1, 2,
          why="hardest at the short end; ankle weights"),
        F("Side-lying clamshell with a band", 0, 2, 2, 0, 2, why="a band: no tension at the stretch"),
        F("Seated band hip rotation", 0, 2, 2, 0, 2, why="a band: no tension at the stretch"),
        F("Fire hydrant", 0, 1, 2, 0, 2, why="little range; body weight"),
        F("Standing band hip rotation", 0, 1, 1, 0, 2, why="a band; balance"),
        F("Lateral band walk", 0, 0, 1, 0, 2, why="the hip abductors more than the rotators"),
    ],
    "shoulder_blades": [
        F("Chest-supported dumbbell row, elbows wide (incline bench)", 2, 1, 2, 2, 2,
          why="the middle traps with the rear delts; the chest held"),
        F("Scapular pulldown (straight arms, only the shoulder blades move)", 2, 1, 2, 2, 2,
          why="the lower traps pull the shoulder blades down; the lats and pec minor share"),
        F("Single-arm scapular pulldown", 2, 1, 2, 2, 2, why="as the scapular pulldown, one side at a time"),
        F("Face pull, rope", 2, 1, 1, 2, 2, why="a big stretch; the rear delts share"),
        F("Single-arm cable Y raise (low pulley, arm up and out)", 2, 1, 1, 2, 2,
          why="tension with the arm across the body; the delts share"),
        F("Scapular pull-up (hanging)", 2, 2, 1, 1, 1, why="a hang; body weight"),
        F("Wall slide with a band", 1, 1, 2, 0, 2, why="a light band; little load"),
        F("Prone T raise (dumbbells)", 0, 2, 2, 1, 2,
          why="the middle traps; hardest at the top, where they are shortest"),
        F("Prone Y raise (dumbbells)", 0, 1, 2, 1, 2,
          why="hardest at the top, where the lower traps are shortest; light dumbbells"),
        F("Band pull-apart", 0, 1, 1, 0, 2, why="a band: no tension at the stretch"),
    ],
    "hip_flexors": [
        F("Bench-edge hip flexion (lying, the thigh lifted from below the bench)", 2, 2, 2, 1, 2,
          why="the thigh starts below the bench line; ankle weights"),
        F("Cable hip flexion from behind the body (standing, cable at the ankle)", 2, 2, 1, 2, 2,
          why="starts with the hip behind the body, under load; one leg"),
        F("Half-kneeling knee-hover isometric", 2, 2, 1, 1, 2,
          why="the back hip held straight, the knee hovering; body weight"),
        F("Reverse Nordic curl", 2, 1, 2, 1, 1, why="the front of the thigh at length; the quads share most"),
        F("Standing psoas march", 1, 2, 1, 0, 2, why="active range; body weight only"),
        F("End-range psoas isometric (seated, knee above hip height)", 0, 2, 2, 1, 2,
          why="the psoas at its shortest"),
        F("Seated knee raise with ankle weights", 0, 2, 2, 1, 2, why="hardest at the short end"),
        F("Banded standing hip flexion", 0, 2, 1, 0, 2, why="a band: no tension at the stretch"),
        F("Hanging knee raise", 0, 2, 0, 1, 1, why="a swing; hardest at the short end"),
    ],
    "adductors": [
        F("Adductor machine, seated, from a wide start", 2, 2, 2, 2, 2,
          why="knees bent, starts wide under load; supported"),
        F("Cable hip adduction, standing (ankle cuff)", 2, 2, 1, 2, 1,
          why="the knee straight, not bent; one leg; an ankle cuff"),
        F("Frog lift-offs (lying, knees bent and open)", 2, 2, 2, 0, 2,
          why="the tested position; body weight only"),
        F("Cossack squat (one dumbbell held)", 2, 1, 1, 1, 1, why="a deep side lunge; the quads and glutes share"),
        F("Copenhagen adduction, long lever (moving)", 1, 2, 1, 1, 1, why="body weight; a long lever"),
        F("Sumo squat with a dumbbell (wide stance)", 1, 1, 1, 1, 2, why="the quads and glutes share; one dumbbell"),
        F("Side-lying adductor lift (bottom leg, ankle weight)", 0, 2, 2, 1, 2,
          why="the adductors at their shortest when it is hardest"),
        F("Adductor ball squeeze (knees bent)", 0, 2, 2, 0, 2, why="no movement; body weight"),
        F("Copenhagen plank, short lever (held)", 0, 2, 1, 1, 1, why="held near mid-length; the knee on the bench"),
        F("Banded standing hip adduction", 0, 2, 1, 0, 2, why="a band: no tension at the stretch"),
    ],
}
