"""Published strength standards: what a man of a given body weight lifts on each
lift, so two lifts on two different machines can be compared (WP-44).

The athlete, 2026-11-03: "I will never use the same machine for back and chest,
that would make no sense. but if I can do 100kg row and 20kg press, it is clear
there is an imbalance". His choice the same day, "Yes A": each lift's estimated
one-rep max against a published standard for that lift at his body weight
(services/imbalance.py).

SOURCE. Strength Level, https://strengthlevel.com/strength-standards/<page>/kg,
the male "By Bodyweight" table, one-rep max in kg; read 2026-11-03. The site
builds the tables from lifts its users entered (195,513,376 lifts from
27,893,268 users, data to 11 March 2026), not from studies. It is the only
published source found that covers machines. Its limits, stated on screen:
machines differ from gym to gym, and the site does not say whether a hack
squat's sled is counted. Re-read the pages to refresh the numbers; never tune
them by hand.

Each row: body weight (kg) -> (Beginner, Novice, Intermediate, Advanced, Elite).
"""
from __future__ import annotations

SOURCE = "Strength Level (strengthlevel.com), male standards by body weight, read 2026-11-03"
SOURCE_URL = "https://strengthlevel.com/strength-standards/{page}/kg"
LEVELS = ("Beginner", "Novice", "Intermediate", "Advanced", "Elite")
#: The level a score of 100 means.
REFERENCE_LEVEL = "Intermediate"

#: Exercise name (as the plan names it) -> (the site's page, its table).
STANDARDS: dict[str, tuple[str, dict[int, tuple[int, int, int, int, int]]]] = {
    "Machine Chest Press": ("chest-press", {
        70: (33, 53, 80, 112, 147), 75: (36, 57, 85, 117, 154), 80: (39, 61, 89, 123, 160),
        85: (42, 64, 93, 128, 165), 90: (45, 68, 98, 132, 171), 95: (47, 71, 102, 137, 176),
        100: (50, 74, 105, 142, 181)}),
    # Per dumbbell, one arm: the site's own note, "Dumbbell weights are for one dumbbell".
    "Single-Arm DB Row": ("dumbbell-row", {
        70: (16, 25, 38, 53, 69), 75: (17, 27, 40, 56, 73), 80: (19, 30, 43, 59, 76),
        85: (21, 32, 46, 62, 80), 90: (23, 34, 48, 65, 83), 95: (24, 36, 51, 68, 86),
        100: (26, 38, 53, 70, 89)}),
    "Machine Shoulder Press": ("machine-shoulder-press", {
        70: (23, 42, 66, 97, 131), 75: (26, 46, 71, 103, 138), 80: (29, 50, 76, 109, 145),
        85: (32, 53, 81, 114, 152), 90: (35, 57, 86, 120, 158), 95: (38, 61, 90, 125, 164),
        100: (41, 64, 94, 130, 170)}),
    # The site's "Cable Reverse Fly", the same movement as his reverse cable crossover.
    "Reverse Cable Crossover": ("cable-reverse-fly", {
        70: (2, 8, 20, 36, 56), 75: (2, 9, 21, 37, 58), 80: (3, 10, 22, 39, 60),
        85: (3, 11, 23, 41, 62), 90: (4, 12, 25, 42, 64), 95: (4, 12, 26, 44, 66),
        100: (5, 13, 27, 45, 67)}),
    "Hack Squat": ("hack-squat", {
        70: (52, 88, 135, 193, 257), 75: (58, 95, 144, 203, 269), 80: (63, 102, 152, 213, 280),
        85: (69, 109, 161, 223, 291), 90: (74, 115, 168, 232, 302), 95: (79, 121, 176, 241, 312),
        100: (84, 127, 183, 249, 321)}),
    "Seated Leg Curl": ("seated-leg-curl", {
        70: (34, 52, 76, 103, 134), 75: (36, 55, 79, 108, 139), 80: (39, 58, 83, 112, 144),
        85: (41, 61, 86, 116, 148), 90: (44, 64, 90, 120, 152), 95: (46, 67, 93, 123, 157),
        100: (48, 69, 96, 127, 161)}),
}
