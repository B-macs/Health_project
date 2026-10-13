# -*- coding: utf-8 -*-
"""Measure Restfulness: its scale, our seven Sleep Score parts against Oura's,
and whether the watch's movement could stand beside the ring's.

The measurement behind docs/restfulness_and_watch_movement_2026-10-13.md (WP-19
step 2). Read-only: it builds an OFFLINE Repository on a local copy, so every
read is served from SQLite and any write would raise. It calls no device API
and nothing on the network.

    python scripts/compare_restfulness_sources.py                  # against datastore.db
    python scripts/compare_restfulness_sources.py --db copy.db     # against a pulled copy

Three parts:

  1. THE SCALE. sleep_score._RESTLESS_BAND scores Oura's restless_periods per
     hour of sleep: 100 at 2, 0 at 12. How many real nights land inside it.
  2. OUR PARTS AGAINST OURA'S. Each of our seven sub-scores minus Oura's own
     contributor of the same name, and what the difference is worth on the
     total (weight x difference).
  3. WATCH AGAINST RING, on nights since
     sleep_movement.CALIBRATION_WATCH_FIRST_NIGHT that both devices recorded,
     recomputed through the app's own fusion code with the one-watch cut
     points. A run of movement at class 2 or above, inside sleep minutes of
     the fused hypnogram, is counted per hour of sleep on each series. On the
     ring's own series that count tracks Oura's restless_periods, which is
     what makes it a fair yardstick for the watch's series.

Measured 2026-10-13 on the 2026-10-09 backup (427 ring nights since 2023):
    restless periods per hour   median 46.7, range 3.6-120; 1 of 427 under 12
    Oura's own Restfulness      median 54, range 17-98; rank correlation with
                                the count alone -0.54 (422 nights)
    Restfulness as scored       0 on 426 of 427 nights
    ours minus Oura, 2026       total sleep +22.7, deep +17.8, efficiency +8.8,
                                rem +2.8, latency -2.2, timing -6.2,
                                restfulness -54.1; total score +3.9 (sd 6.4)
    watch vs ring, 53 nights    runs/h rho 0.35 [0.09, 0.56]; share 0.46;
                                large movements 0.29; same measure on both
                                series 0.32 [0.04, 0.55]; large movements on
                                both series -0.07; fused series 0.89
    cut points                  one watch (1.44, 2.55, 4.63) against pooled
                                (1.45, 2.52, 4.73): 0.7% of watch slots change
"""
from __future__ import annotations

import argparse
import json
import random
import sqlite3
import statistics
import sys
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from services import sleep_fusion, sleep_movement, sleep_score  # noqa: E402
from services.config import Config  # noqa: E402
from services.repository import Repository  # noqa: E402

_SLEEP_STAGES = {sleep_fusion.DEEP, sleep_fusion.LIGHT, sleep_fusion.REM}
_OURA_PARTS = {"total_sleep": "sleep_total_sleep", "efficiency": "sleep_efficiency",
               "restfulness": "sleep_restfulness", "rem": "sleep_rem_sleep",
               "deep": "sleep_deep_sleep", "latency": "sleep_latency", "timing": "sleep_timing"}


def offline_repository(db: str) -> Repository:
    """Reads from the copy, writes raise. Not load_config: that resolves to
    Supabase as the record whenever Supabase is configured, and this script
    must never reach it."""
    return Repository(Config(
        notion_api_key="offline", notion_db_readiness="offline-readiness",
        notion_db_training="offline-training", notion_db_config="offline-config",
        google_sheets_id="offline", google_service_account={},
        datastore_path=db, datastore_mode="readonly"))


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _rank(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def _pearson(x: list[float], y: list[float]) -> float:
    mx, my = statistics.fmean(x), statistics.fmean(y)
    sx = sum((a - mx) ** 2 for a in x) ** 0.5
    sy = sum((b - my) ** 2 for b in y) ** 0.5
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy) if sx and sy else float("nan")


def spearman(x: list[float], y: list[float]) -> float:
    return _pearson(_rank(x), _rank(y))


def spearman_ci(x: list[float], y: list[float], n: int = 4000, seed: int = 7) -> tuple[float, float]:
    """Percentile bootstrap over nights."""
    rnd = random.Random(seed)
    idx = list(range(len(x)))
    vals = []
    for _ in range(n):
        pick = [rnd.choice(idx) for _ in idx]
        v = spearman([x[i] for i in pick], [y[i] for i in pick])
        if v == v:
            vals.append(v)
    vals.sort()
    return round(vals[int(0.025 * len(vals))], 3), round(vals[int(0.975 * len(vals)) - 1], 3)


def runs(series: list[int], mask: list[bool], threshold: int) -> int:
    """Maximal runs at class >= threshold inside sleep slots."""
    count, inside = 0, False
    for s, ok in zip(series, mask):
        hit = ok and s in sleep_movement.CLASSES and s >= threshold
        if hit and not inside:
            count += 1
        inside = hit
    return count


def share(series: list[int], mask: list[bool], threshold: int) -> float | None:
    covered = [s for s, ok in zip(series, mask) if ok and s in sleep_movement.CLASSES]
    return sum(1 for s in covered if s >= threshold) / len(covered) if covered else None


def scale(rows: list[dict], conn: sqlite3.Connection) -> dict:
    """The input against today's band, and against Oura's own Restfulness
    contributor for the same nights — how much of Oura's reading the count
    alone carries."""
    oura = {d: _num(v) for d, v in conn.execute("select date, sleep_restfulness from oura_daily")}
    rph, pairs = [], []
    for r in rows:
        rp, tot = _num(r.get("oura_sleep_restless_periods")), _num(r.get("oura_sleep_total_seconds"))
        if rp is not None and tot:
            rph.append(rp / (tot / 3600))
            if oura.get(r["date"]) is not None:
                pairs.append((rph[-1], oura[r["date"]]))
    if not rph:
        return {"nights": 0}
    out = {
        "nights": len(rph), "median_per_hour": round(statistics.median(rph), 1),
        "range_per_hour": (round(min(rph), 1), round(max(rph), 1)),
        "nights_under_12": sum(1 for v in rph if v < 12),
        "nights_scored_above_0": sum(
            1 for v in rph if sleep_score._interp(v, sleep_score._RESTLESS_BAND) > 0),
    }
    if len(pairs) >= 3:
        theirs = [p[1] for p in pairs]
        out["oura_restfulness"] = {
            "nights": len(pairs), "median": statistics.median(theirs),
            "range": (min(theirs), max(theirs)),
            "spearman_with_count": round(spearman([p[0] for p in pairs], theirs), 3)}
    return out


def parts_against_oura(rows: list[dict], conn: sqlite3.Connection, since: str) -> dict:
    oura = {r[0]: r[1:] for r in conn.execute(
        "select date, " + ", ".join(_OURA_PARTS.values()) + ", sleep_score from oura_daily")}
    diff: dict[str, list[float]] = {k: [] for k in _OURA_PARTS}
    weighted: dict[str, list[float]] = {k: [] for k in _OURA_PARTS}
    totals = []
    for r in rows:
        d = r["date"]
        if d < since or d not in oura:
            continue
        b = sleep_score.sleep_score_breakdown(date.fromisoformat(d), rows)
        if not isinstance(b["score"], (int, float)):
            continue
        theirs_total = _num(oura[d][-1])
        if theirs_total is not None:
            totals.append(b["score"] - theirs_total)
        for i, key in enumerate(_OURA_PARTS):
            ours = next(c for c in b["contributors"] if c["key"] == key)
            theirs = _num(oura[d][i])
            if ours["score"] is None or theirs is None:
                continue
            diff[key].append(ours["score"] - theirs)
            weighted[key].append(ours["weight"] * (ours["score"] - theirs))
    out = {key: {"nights": len(v), "ours_minus_oura": round(statistics.fmean(v), 1),
                 "points_on_total": round(statistics.fmean(weighted[key]), 2)}
           for key, v in diff.items() if v}
    if totals:
        out["total_score"] = {"nights": len(totals), "ours_minus_oura": round(statistics.fmean(totals), 1),
                              "sd": round(statistics.pstdev(totals), 1)}
    out["options"] = options(rows, oura, since)
    return out


def options(rows: list[dict], oura: dict, since: str) -> dict:
    """What each way of fixing Restfulness does to the total, night by night,
    through the score's own composite. A: Oura's own Restfulness contributor.
    B: the same raw count on a band re-based on his own nights (100 at his 10th
    percentile, 0 at his 90th). C: no change. D: the part removed and its
    weight shared among the other six."""
    rph_all = sorted(
        _num(r["oura_sleep_restless_periods"]) / (_num(r["oura_sleep_total_seconds"]) / 3600)
        for r in rows
        if _num(r.get("oura_sleep_restless_periods")) is not None
        and _num(r.get("oura_sleep_total_seconds")))
    if len(rph_all) < 10:
        return {}
    band = ((round(rph_all[len(rph_all) // 10], 1), 100.0),
            (round(rph_all[(9 * len(rph_all)) // 10], 1), 0.0))
    shifts: dict[str, list[float]] = {"A": [], "B": [], "D": []}
    gaps: dict[str, list[float]] = {"A": [], "B": [], "C": [], "D": []}
    for r in rows:
        d = r["date"]
        if d < since or d not in oura:
            continue
        b = sleep_score.sleep_score_breakdown(date.fromisoformat(d), rows)
        theirs_total, theirs_rest = _num(oura[d][-1]), _num(oura[d][2])
        rest = next(c for c in b["contributors"] if c["key"] == "restfulness")
        if (not isinstance(b["score"], (int, float)) or theirs_total is None
                or theirs_rest is None or rest["raw"] is None):
            continue
        others = [(c["score"], c["weight"]) for c in b["contributors"]
                  if c["key"] != "restfulness" and c["score"] is not None]
        new = {
            "A": sleep_score._composite(others + [(theirs_rest, rest["weight"])]),
            "B": sleep_score._composite(others + [(sleep_score._interp(rest["raw"], band),
                                                   rest["weight"])]),
            "D": sleep_score._composite(others),
        }
        gaps["C"].append(b["score"] - theirs_total)
        for k, v in new.items():
            shifts[k].append(v - b["score"])
            gaps[k].append(v - theirs_total)
    if not gaps["C"]:
        return {}
    return {
        "nights": len(gaps["C"]), "band_B": band,
        **{k: {"mean_shift": round(statistics.fmean(shifts[k]), 1) if k in shifts else 0.0,
               "ours_minus_oura": round(statistics.fmean(gaps[k]), 1),
               "sd": round(statistics.pstdev(gaps[k]), 1)}
           for k in ("A", "B", "C", "D")},
    }


def watch_against_ring(repo: Repository, today: str) -> dict:
    oura_all = repo._oura_hypnograms_by_date("0000-01-01", today)
    garmin = repo.get_garmin_sleep_stages()
    cut = repo.sleep_movement_cutpoints(oura_all, garmin)
    first = sleep_movement.CALIBRATION_WATCH_FIRST_NIGHT
    try:
        sleep_movement.CALIBRATION_WATCH_FIRST_NIGHT = "0000-00-00"
        pooled = repo.sleep_movement_cutpoints(oura_all, garmin)
    finally:
        sleep_movement.CALIBRATION_WATCH_FIRST_NIGHT = first

    ring, nights = [], []
    changed = covered = 0
    for day in sorted(oura_all):
        if not (first <= day <= today):
            continue
        main = oura_all[day]
        night = repo.compute_sleep_fusion_for_date(day, oura_all, garmin, movement_cutpoints=cut)
        rp, tot = _num(main.get("restless_periods")), _num(main.get("total_sleep_duration"))
        if night is None or rp is None or not tot:
            continue
        master = sleep_fusion.decode(night.get("master_hypnogram"))
        o = sleep_fusion.decode(night.get("oura_movement"))
        g = sleep_fusion.decode(night.get("garmin_movement"))
        f = sleep_fusion.decode(night.get("master_movement"))
        mask = [i // 2 < len(master) and master[i // 2] in _SLEEP_STAGES for i in range(len(o))]
        hours = sum(mask) * sleep_movement.SLOT_SECONDS / 3600
        if not hours:
            continue
        rec = {"oura_per_hour": rp / (tot / 3600), "ring_runs": runs(o, mask, 2) / hours}
        ring.append(rec)
        watch_cover = sum(1 for s, ok in zip(g, mask) if ok and s in sleep_movement.CLASSES)
        if night["source"] != sleep_fusion.SOURCE_FUSED or watch_cover < 0.8 * sum(mask):
            continue
        rec.update({
            "watch_runs": runs(g, mask, 2) / hours, "watch_share": share(g, mask, 2),
            "watch_large": runs(g, mask, 3) / hours, "ring_large": runs(o, mask, 3) / hours,
            "fused_runs": runs(f, mask, 2) / hours,
        })
        nights.append(rec)
        ws = sleep_fusion.utc_from_iso_offset(main.get("bedtime_start"))
        slots = len(sleep_movement.oura_movement(main.get("movement_30_sec")))
        best, _overlap = repo._match_garmin_night(
            day, ws, ws + timedelta(seconds=slots * sleep_movement.SLOT_SECONDS), garmin)
        values, _diag = sleep_movement.garmin_values_on_grid(best["movement"], ws, slots)
        for v in values:
            if v is not None:
                covered += 1
                changed += sleep_movement.garmin_class(v, cut) != sleep_movement.garmin_class(v, pooled)

    out = {"cut_points_one_watch": cut, "cut_points_pooled": pooled,
           "watch_slots_changing_class_pct": round(100 * changed / covered, 1) if covered else None,
           "ring_nights": len(ring), "paired_nights": len(nights)}
    if len(ring) >= 3:
        out["yardstick_ring_runs_vs_oura"] = round(
            spearman([r["ring_runs"] for r in ring], [r["oura_per_hour"] for r in ring]), 3)
    if len(nights) >= 3:
        y = [r["oura_per_hour"] for r in nights]
        for key in ("watch_runs", "watch_share", "watch_large", "fused_runs"):
            x = [r[key] for r in nights]
            out[f"{key}_vs_oura"] = {"spearman": round(spearman(x, y), 3), "ci95": spearman_ci(x, y)}
        xo, xg = [r["ring_runs"] for r in nights], [r["watch_runs"] for r in nights]
        out["same_measure_ring_vs_watch"] = {"spearman": round(spearman(xo, xg), 3),
                                             "ci95": spearman_ci(xo, xg)}
        out["large_movements_ring_vs_watch"] = round(spearman(
            [r["ring_large"] for r in nights], [r["watch_large"] for r in nights]), 3)
        out["median_runs_per_hour"] = {k: round(statistics.median(r[k] for r in nights), 2)
                                       for k in ("ring_runs", "watch_runs", "fused_runs")}
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", default=str(_ROOT / "datastore.db"))
    ap.add_argument("--today", default=date.today().isoformat())
    ap.add_argument("--since", default="2026-01-01",
                    help="first night of the parts-against-Oura comparison")
    args = ap.parse_args()
    if not Path(args.db).exists():
        sys.exit(f"No datastore at {args.db}. Build one, or pass --db.")
    repo = offline_repository(args.db)
    rows = [asdict(r) if not isinstance(r, dict) else r
            for r in repo.get_biometric_rolling(days=1500, today=date.fromisoformat(args.today))]
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    print(json.dumps({
        "scale": scale(rows, conn),
        "parts_against_oura": parts_against_oura(rows, conn, args.since),
        "watch_against_ring": watch_against_ring(repo, args.today),
    }, indent=1, default=str))


if __name__ == "__main__":
    main()
