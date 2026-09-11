# -*- coding: utf-8 -*-
"""Measure what an exercise change actually costs, from the set timestamps.

This is the measurement behind services.sessions.CHANGEOVER_SECONDS. Run it
before changing those constants: they are medians of the athlete's own
changeovers, and the right way to move them is to re-measure.

For every logged session with per-set timestamps, and every consecutive pair
of exercises in it (ordered by first set), the changeover is

    (first set of the next exercise) - (last set of this one) - (that set's work)

where a set's work is estimated from the exercise's own later sets
(timestamp gap minus the rest actually taken) or, for a single set, from its
tut / reps. Pairs logged in a burst (< 20 s apart — the athlete logged several
sets at once) are excluded on both sides; so are gaps over 15 minutes, which
are interruptions, not changeovers.

    python scripts/measure_changeovers.py                  # against datastore.db
    python scripts/measure_changeovers.py --db copy.db     # against a pulled copy

Measured 2026-09-11 over 13 sessions / 109 changes:
    floor  median  74 s   (p25 52,  p75 114)
    gym    median 117 s   (p25 60,  p75 161)
    band   median 158 s   (p25 96,  p75 212)
"""
from __future__ import annotations

import argparse
import sqlite3
import statistics as st
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from services import sessions as sess  # noqa: E402

BURST_SECONDS = 20
INTERRUPTION_SECONDS = 900


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def measure(conn: sqlite3.Connection) -> list[dict]:
    conn.row_factory = sqlite3.Row
    out: list[dict] = []
    for s in conn.execute("select session_id, session_date from training_sessions order by session_date"):
        rows = []
        for e in conn.execute("select exercise_id, movement_name from training_exercises where session_id=?",
                              (s["session_id"],)):
            sets = [dict(x) for x in conn.execute(
                "select reps, tut, ts, rest_taken_seconds from training_sets "
                "where exercise_id=? and ts is not null order by ts", (e["exercise_id"],))]
            if not sets:
                continue
            ts = [_parse(x["ts"]) for x in sets]
            works = [(ts[k] - ts[k - 1]).total_seconds() - sets[k - 1]["rest_taken_seconds"]
                     for k in range(1, len(sets))
                     if sets[k - 1]["rest_taken_seconds"] is not None
                     and (ts[k] - ts[k - 1]).total_seconds() > 15]
            if works:
                w1 = st.median(works)
            elif sets[0]["tut"] and sets[0]["tut"] > 5:
                w1 = sets[0]["tut"]
            else:
                w1 = (sets[0]["reps"] or 8) * sess.REPS_SECONDS_DEFAULT
            rows.append({"name": e["movement_name"], "first": ts[0], "last": ts[-1], "w1": w1})
        if len(rows) < 3:
            continue
        rows.sort(key=lambda r: r["first"])
        burst = [False] + [(rows[i]["first"] - rows[i - 1]["last"]).total_seconds() < BURST_SECONDS
                           for i in range(1, len(rows))]
        for i in range(1, len(rows)):
            if burst[i] or burst[i - 1]:
                continue
            gap = (rows[i]["first"] - rows[i - 1]["last"]).total_seconds()
            t = gap - rows[i]["w1"]
            if 0 < t < INTERRUPTION_SECONDS:
                out.append({"date": s["session_date"], "from": rows[i - 1]["name"],
                            "to": rows[i]["name"], "seconds": t,
                            "kind": sess.station_kind({"name": rows[i]["name"],
                                                       "equipment_type": _equipment(rows[i]["name"])})})
    return out


def _equipment(name: str) -> str | None:
    """The logged row carries no equipment; read it off the authored plans."""
    import training_plan as tp
    for plan in (tp.PLAN, tp.PLAN_STAGE2, tp.PLAN_STAGE2B, tp.PLAN_BLOCK_B):
        for day in plan.values():
            for ex in day["exercises"]:
                if ex["name"] == name:
                    return ex.get("equipment_type")
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(_ROOT / "datastore.db"))
    args = ap.parse_args()
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    changes = measure(conn)
    print(f"{len(changes)} changeovers measured")
    for kind in ("floor", "gym", "band"):
        v = sorted(c["seconds"] for c in changes if c["kind"] == kind)
        if not v:
            print(f"{kind:6s} n=0")
            continue
        print(f"{kind:6s} n={len(v):3d} median={st.median(v):4.0f}s  "
              f"p25={v[len(v) // 4]:4.0f}  p75={v[3 * len(v) // 4]:4.0f}  "
              f"(constant in code: {sess.CHANGEOVER_SECONDS[kind]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
