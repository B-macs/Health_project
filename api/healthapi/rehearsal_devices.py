"""Made-up Oura and Garmin devices for the sync rehearsal (rebuild Phase 9).

The rehearsal (healthapi.rehearsal) runs the engine's REAL sync chain, so the
devices answer in the shapes the real sync code reads: Oura's v2 collections
(services/clients/oura.get_collection) and garminconnect's client methods
(services/clients/garmin.py calls them). Every number is invented, from a
random generator seeded by the day, so the same day always reads the same.
Nothing here is a reading of a person.

ONE MADE-UP ATHLETE, IN UTC. Every clock is UTC (+00:00), so the rehearsal
never depends on a time zone. The ring is worn on about three nights in four
and the watch on most nights; the athlete walks most mornings and trains on
the block's gym days (Scenario.trains_on), at 18:00 for 65 minutes, which is
what lets the heart-rate match find the watch's record of each session.

`until` is the last day the devices have data for: yesterday while the
history is built, today in the timed run, so the timed run brings last night
as a real morning sync would. `latency_s` is waited on every call (and
`login_latency_s` on top for a Garmin login), and `calls` counts them by name.
"""

from __future__ import annotations

import random
import threading
import time as _time
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone

UTC = timezone.utc

#: The block's gym weekdays (Monday, Tuesday, Thursday, Friday).
GYM_WEEKDAYS = (0, 1, 3, 4)
GYM_START = time(18, 0)
GYM_MINUTES = 65
WALK_START = time(8, 0)


def _rng(*parts) -> random.Random:
    return random.Random("|".join(str(p) for p in parts))


def _ms(moment: datetime) -> int:
    return int(moment.timestamp() * 1000)


def _gmt(moment: datetime) -> str:
    """Garmin's sleep segment clock: naive, denoting UTC, with a tenth."""
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.0")


def _iso(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat()


@dataclass
class Scenario:
    """The made-up history's calendar, shared by the devices and the seed."""
    today: date
    #: Nights of ring history and days of watch history.
    oura_days: int = 700
    garmin_days: int = 110
    #: Weeks of the block before today's week (its first Monday is that far back).
    block_weeks: int = 9
    phase_start: date = field(init=False)

    def __post_init__(self):
        monday = self.today - timedelta(days=self.today.weekday())
        self.phase_start = monday - timedelta(weeks=self.block_weeks)

    def trains_on(self, day: date) -> bool:
        """A gym session on the block's gym weekdays, from the block's start,
        missing about one in ten."""
        return (self.phase_start <= day and day.weekday() in GYM_WEEKDAYS
                and _rng("train", day).random() > 0.1)

    def ring_worn(self, day: date) -> bool:
        return (self.today - day).days < self.oura_days and _rng("ring", day).random() < 0.75

    def watch_worn(self, day: date) -> bool:
        return (self.today - day).days < self.garmin_days and _rng("watch", day).random() < 0.95


# ─── one night, shared by both devices ──────────────────────────────────────

def night(day: date) -> dict:
    """The night that ends on the morning of `day`: its start, its 30-second
    stages (Oura's codes: 1 deep, 2 light, 3 REM, 4 awake) and movement."""
    r = _rng("night", day)
    start = datetime.combine(day - timedelta(days=1), time(22, 30), UTC) \
        + timedelta(minutes=r.randint(0, 60))
    slots = r.randint(14 * 60, 17 * 60)            # 7 to 8.5 hours, 30-second slots
    stages: list[str] = []
    while len(stages) < slots:
        cycle = len(stages) // 180
        deep = max(8, 48 - cycle * 12)
        rem = 18 + cycle * 9
        light = 180 - deep - rem - 4
        for code, n in (("2", light // 2), ("1", deep), ("2", light - light // 2),
                        ("3", rem), ("4", 4)):
            stages.extend(code * n)
    stages = stages[:slots]
    latency = r.randint(8, 36)
    stages[:latency] = ["4"] * latency
    waking = r.randint(2, 10)
    stages[-waking:] = ["4"] * waking
    movement = []
    for code in stages:
        roll = r.random()
        if code == "4":
            movement.append(r.choice("234"))
        else:
            movement.append("1" if roll < 0.85 else "2" if roll < 0.97 else "3")
    return {"start": start, "end": start + timedelta(seconds=30 * slots),
            "stages": "".join(stages), "movement": "".join(movement), "latency": latency * 30}


class FakeOura:
    """services/clients/oura.get_collection and refresh_access_token, made up."""

    DAILY = ("daily_sleep", "daily_readiness", "daily_activity", "daily_stress",
             "daily_resilience", "daily_spo2", "daily_cardiovascular_age", "sleep_time",
             "vo2_max")

    def __init__(self, devices: "Devices"):
        self._d = devices
        self.refreshes = 0

    def _days(self, start: str, end: str) -> list[date]:
        first, last = date.fromisoformat(start), min(date.fromisoformat(end), self._d.until)
        return [first + timedelta(days=i) for i in range((last - first).days + 1)]

    def get_collection(self, token, endpoint, start_date, end_date):
        self._d.called(f"oura.{endpoint}")
        days = [d for d in self._days(start_date, end_date) if self._d.scenario.ring_worn(d)]
        if endpoint in self.DAILY:
            return [e for e in (self._daily(endpoint, d) for d in days) if e]
        if endpoint == "sleep":
            return [self._sleep(d) for d in days]
        if endpoint == "workout":
            return [w for d in days for w in self._workouts(d)]
        if endpoint == "session":
            return [self._session(d) for d in days if _rng("oura-session", d).random() < 0.02]
        return []                                   # rest_mode_period and the rest

    def refresh_access_token(self, client_id, client_secret, refresh_token):
        self._d.called("oura.refresh")
        self.refreshes += 1
        n = self.refreshes
        return {"access_token": f"made-up-access-{n}", "refresh_token": f"made-up-refresh-{n}",
                "expires_in": 30 * 86400, "token_type": "bearer", "scope": "daily heartrate"}

    def _daily(self, endpoint: str, d: date) -> dict | None:
        r = _rng("oura", endpoint, d)
        base = {"id": f"{endpoint}-{d}", "day": d.isoformat(), "timestamp": f"{d}T00:00:00+00:00"}
        score = lambda: r.randint(55, 92)  # noqa: E731
        if endpoint == "daily_sleep":
            return {**base, "score": score(), "contributors": {
                k: score() for k in ("total_sleep", "efficiency", "restfulness", "rem_sleep",
                                     "deep_sleep", "latency", "timing")}}
        if endpoint == "daily_readiness":
            return {**base, "score": score(),
                    "temperature_deviation": round(r.uniform(-0.4, 0.4), 2),
                    "temperature_trend_deviation": round(r.uniform(-0.3, 0.3), 2),
                    "contributors": {k: score() for k in (
                        "resting_heart_rate", "hrv_balance", "body_temperature", "recovery_index",
                        "sleep_balance", "activity_balance", "previous_day_activity",
                        "previous_night", "sleep_regularity")}}
        if endpoint == "daily_activity":
            return {**base, "score": score(), "steps": r.randint(5000, 13000),
                    "high_activity_time": r.randint(0, 1800),
                    "medium_activity_time": r.randint(1200, 4800),
                    "low_activity_time": r.randint(9000, 18000),
                    "sedentary_time": r.randint(25000, 40000),
                    "average_met_minutes": round(r.uniform(1.2, 1.9), 2),
                    "high_activity_met_minutes": r.randint(0, 120),
                    "medium_activity_met_minutes": r.randint(60, 300),
                    "low_activity_met_minutes": r.randint(100, 300),
                    "sedentary_met_minutes": r.randint(10, 40),
                    "non_wear_time": r.randint(0, 3600), "inactivity_alerts": r.randint(0, 3),
                    "equivalent_walking_distance": r.randint(5000, 12000),
                    "meters_to_target": r.randint(-2000, 4000), "target_meters": 8000,
                    "total_calories": r.randint(2300, 3000), "active_calories": r.randint(300, 800),
                    "target_calories": 500, "resting_time": r.randint(20000, 30000),
                    "contributors": {k: score() for k in (
                        "meet_daily_targets", "move_every_hour", "recovery_time", "stay_active",
                        "training_frequency", "training_volume")}}
        if endpoint == "daily_stress":
            return {**base, "stress_high": r.randint(0, 7200), "recovery_high": r.randint(0, 7200),
                    "day_summary": r.choice(["normal", "restored", "stressful"])}
        if endpoint == "daily_resilience":
            return {**base, "level": r.choice(["solid", "adequate", "strong"]),
                    "contributors": {"sleep_recovery": round(r.uniform(40, 90), 1),
                                     "daytime_recovery": round(r.uniform(20, 70), 1),
                                     "stress": round(r.uniform(30, 80), 1)}}
        if endpoint == "daily_spo2":
            return {**base, "spo2_percentage": {"average": round(r.uniform(95.5, 98.5), 2)},
                    "breathing_disturbance_index": r.randint(0, 12)}
        if endpoint == "daily_cardiovascular_age":
            return {**base, "vascular_age": r.randint(30, 40),
                    "pulse_wave_velocity": round(r.uniform(6.0, 8.0), 2)}
        if endpoint == "sleep_time":
            return {**base, "status": "optimal_found", "recommendation": "follow_optimal_bedtime",
                    "optimal_bedtime": None}
        return None                                 # vo2_max: often empty, as for real

    def _sleep(self, d: date) -> dict:
        n = night(d)
        r = _rng("oura-sleep", d)
        stages = n["stages"]
        count = Counter(stages)
        deep, light, rem, awake = (count[c] * 30 for c in "1234")
        in_bed = len(stages) * 30
        five = "".join(Counter(stages[i:i + 10]).most_common(1)[0][0]
                       for i in range(0, len(stages), 10))
        hr_items = [r.randint(48, 62) for _ in range(in_bed // 300)]
        hrv_items = [r.randint(28, 70) for _ in range(in_bed // 300)]
        return {
            "id": f"sleep-{d}", "day": d.isoformat(), "type": "long_sleep", "period": 0,
            "bedtime_start": _iso(n["start"]), "bedtime_end": _iso(n["end"]),
            "total_sleep_duration": deep + light + rem, "time_in_bed": in_bed,
            "awake_time": awake, "deep_sleep_duration": deep, "light_sleep_duration": light,
            "rem_sleep_duration": rem, "efficiency": round(100 * (deep + light + rem) / in_bed),
            "latency": n["latency"], "average_heart_rate": round(sum(hr_items) / len(hr_items), 2),
            "lowest_heart_rate": min(hr_items),
            "average_hrv": round(sum(hrv_items) / len(hrv_items)), "average_breath": 14.5,
            "restless_periods": r.randint(20, 70),
            "readiness": {"score": r.randint(55, 92),
                          "temperature_deviation": round(r.uniform(-0.4, 0.4), 2)},
            "sleep_score_delta": 0, "readiness_score_delta": 0,
            "sleep_algorithm_version": "v2", "sleep_analysis_reason": "foreground_sleep_analysis",
            "low_battery_alert": False,
            "sleep_phase_5_min": five, "sleep_phase_30_sec": stages,
            "movement_30_sec": n["movement"],
            "heart_rate": {"interval": 300.0, "items": hr_items, "timestamp": _iso(n["start"])},
            "hrv": {"interval": 300.0, "items": hrv_items, "timestamp": _iso(n["start"])},
        }

    def _workouts(self, d: date) -> list[dict]:
        out = []
        for walk in self._d.garmin.activities_on(d):
            start = walk["_start"]
            out.append({"id": f"workout-{walk['activityId']}", "day": d.isoformat(),
                        "activity": "walking" if walk["_kind"] == "walk" else "strength_training",
                        "intensity": "easy", "calories": int(walk["calories"]),
                        "distance": float(walk.get("distance") or 0.0),
                        "start_datetime": _iso(start),
                        "end_datetime": _iso(start + timedelta(seconds=walk["duration"])),
                        "source": "autodetected"})
        return out

    def _session(self, d: date) -> dict:
        start = datetime.combine(d, time(21, 0), UTC)
        return {"id": f"session-{d}", "day": d.isoformat(), "type": "breathing",
                "start_datetime": _iso(start), "end_datetime": _iso(start + timedelta(minutes=10)),
                "mood": "good",
                "motion_count": {"interval": 5.0, "items": [0, 1, 0, 2] * 30,
                                 "timestamp": _iso(start)}}


class FakeGarmin:
    """A garminconnect.Garmin, made up: the methods services/clients/garmin.py calls."""

    def __init__(self, devices: "Devices"):
        self._d = devices

    # ── the client ─────────────────────────────────────────────────────────
    def login(self, *args, **kwargs):
        self._d.called("garmin.login", extra_s=self._d.login_latency_s)

    def _day(self, cdate) -> date:
        return date.fromisoformat(str(cdate)[:10])

    def _has(self, d: date) -> bool:
        return d <= self._d.until and self._d.scenario.watch_worn(d)

    def get_stats(self, cdate):
        self._d.called("garmin.get_stats")
        d = self._day(cdate)
        if not self._has(d):
            return {}
        r = _rng("garmin-stats", d)
        return {"calendarDate": d.isoformat(), "totalSteps": r.randint(5000, 14000),
                "restingHeartRate": r.randint(49, 58), "averageStressLevel": r.randint(22, 40),
                "totalKilocalories": r.randint(2300, 3000), "minHeartRate": r.randint(44, 52),
                "maxHeartRate": r.randint(125, 172)}

    def get_sleep_data(self, cdate):
        self._d.called("garmin.get_sleep_data")
        d = self._day(cdate)
        if not self._has(d):
            return {}
        n = night(d)
        r = _rng("garmin-sleep", d)
        start = n["start"] + timedelta(minutes=5)
        minutes = (len(n["stages"]) * 30) // 60 - 8
        level_of = {"1": 0.0, "2": 1.0, "3": 2.0, "4": 3.0}
        per_minute = [level_of[n["stages"][min(len(n["stages"]) - 1, 10 + 2 * m)]]
                      for m in range(minutes)]
        segments, totals = [], Counter()
        i = 0
        while i < minutes:
            j = i
            while j < minutes and per_minute[j] == per_minute[i]:
                j += 1
            seg_start, seg_end = start + timedelta(minutes=i), start + timedelta(minutes=j)
            segments.append({"startGMT": _gmt(seg_start), "endGMT": _gmt(seg_end),
                             "activityLevel": per_minute[i]})
            totals[per_minute[i]] += (j - i) * 60
            i = j
        movement = [{"startGMT": _gmt(start + timedelta(minutes=m)),
                     "endGMT": _gmt(start + timedelta(minutes=m + 1)),
                     "activityLevel": round(r.uniform(0.0, 1.5) if per_minute[m] < 3.0
                                            else r.uniform(2.0, 6.0), 3)}
                    for m in range(minutes)]
        end = start + timedelta(minutes=minutes)
        return {
            "dailySleepDTO": {
                "calendarDate": d.isoformat(),
                "sleepTimeSeconds": int(totals[0.0] + totals[1.0] + totals[2.0]),
                "deepSleepSeconds": int(totals[0.0]), "lightSleepSeconds": int(totals[1.0]),
                "remSleepSeconds": int(totals[2.0]), "awakeSleepSeconds": int(totals[3.0]),
                "sleepStartTimestampGMT": _ms(start), "sleepEndTimestampGMT": _ms(end),
                "sleepStartTimestampLocal": _ms(start), "sleepEndTimestampLocal": _ms(end),
                "sleepWindowConfirmationType": "enhanced_confirmed",
            },
            "sleepLevels": segments,
            "sleepMovement": movement,
            "sleepHeartRate": [{"value": r.randint(47, 63), "startGMT": _ms(start + timedelta(minutes=m))}
                               for m in range(0, minutes, 2)],
            "sleepStress": [{"value": r.randint(5, 30), "startGMT": _ms(start + timedelta(minutes=m))}
                            for m in range(0, minutes, 3)],
            "restingHeartRate": r.randint(49, 58),
            "remSleepData": True, "skinTempDataExists": False,
        }

    def get_stress_data(self, cdate):
        self._d.called("garmin.get_stress_data")
        d = self._day(cdate)
        return {"avgStressLevel": _rng("garmin-stress", d).randint(20, 40)} if self._has(d) else {}

    def get_hrv_data(self, cdate):
        self._d.called("garmin.get_hrv_data")
        d = self._day(cdate)
        if not self._has(d):
            return {}
        return {"hrvSummary": {"lastNightAvg": _rng("garmin-hrv", d).randint(30, 60)}}

    # ── activities ─────────────────────────────────────────────────────────
    def activities_on(self, d: date) -> list[dict]:
        """The day's activities, newest first (garminconnect's shape, plus two
        private keys the fakes use: _start and _kind)."""
        if d > self._d.until or not self._d.scenario.watch_worn(d):
            return []
        r = _rng("garmin-activities", d)
        out = []
        if r.random() < 0.8:
            start = datetime.combine(d, WALK_START, UTC) + timedelta(minutes=r.randint(0, 40))
            minutes = r.randint(15, 70)
            out.append({"activityId": int(f"{d:%Y%m%d}1"), "activityName": "Morning walk",
                        "activityType": {"typeKey": "walking"},
                        "startTimeLocal": start.strftime("%Y-%m-%d %H:%M:%S"),
                        "startTimeGMT": start.strftime("%Y-%m-%d %H:%M:%S"),
                        "duration": minutes * 60.0, "distance": minutes * 80.0,
                        "averageHR": float(r.randint(92, 110)), "maxHR": float(r.randint(115, 135)),
                        "calories": float(minutes * 4), "_start": start, "_kind": "walk"})
        if self._d.scenario.trains_on(d):
            start = datetime.combine(d, GYM_START, UTC)
            out.append({"activityId": int(f"{d:%Y%m%d}2"), "activityName": "Strength",
                        "activityType": {"typeKey": "indoor_cardio"},
                        "startTimeLocal": start.strftime("%Y-%m-%d %H:%M:%S"),
                        "startTimeGMT": start.strftime("%Y-%m-%d %H:%M:%S"),
                        "duration": GYM_MINUTES * 60.0, "distance": 0.0,
                        "averageHR": float(r.randint(108, 124)), "maxHR": float(r.randint(145, 170)),
                        "calories": 420.0, "_start": start, "_kind": "gym"})
        return sorted(out, key=lambda a: a["_start"], reverse=True)

    @staticmethod
    def _public(activity: dict) -> dict:
        return {k: v for k, v in activity.items() if not k.startswith("_")}

    def get_activities(self, start, limit):
        self._d.called("garmin.get_activities")
        found: list[dict] = []
        d = self._d.until
        while len(found) < int(start) + int(limit) and (self._d.until - d).days < 120:
            found.extend(self.activities_on(d))
            d -= timedelta(days=1)
        return [self._public(a) for a in found[int(start):int(start) + int(limit)]]

    def get_activities_by_date(self, startdate, enddate=None, *args, **kwargs):
        self._d.called("garmin.get_activities_by_date")
        first = self._day(startdate)
        last = self._day(enddate or startdate)
        out = []
        d = first
        while d <= last:
            out.extend(self.activities_on(d))
            d += timedelta(days=1)
        return [self._public(a) for a in out]

    def _find(self, activity_id) -> dict | None:
        text = str(activity_id)
        try:
            d = datetime.strptime(text[:8], "%Y%m%d").date()
        except ValueError:
            return None
        return next((a for a in self.activities_on(d) if str(a["activityId"]) == text), None)

    def get_activity_details(self, activity_id, maxchart=2000, *args, **kwargs):
        self._d.called("garmin.get_activity_details")
        act = self._find(activity_id)
        if act is None:
            return {}
        r = _rng("garmin-detail", activity_id)
        start, seconds = act["_start"], int(act["duration"])
        avg = act["averageHR"]
        metrics = [{"metrics": [float(max(60, min(185, avg + r.uniform(-15, 25)))),
                                float(_ms(start + timedelta(seconds=s)))]}
                   for s in range(0, seconds, 5)]
        return {"activityId": act["activityId"],
                "metricDescriptors": [{"key": "directHeartRate", "metricsIndex": 0},
                                      {"key": "directTimestamp", "metricsIndex": 1}],
                "activityDetailMetrics": metrics,
                "summaryDTO": {"startTimeLocal": act["startTimeLocal"]}}

    def get_activity_hr_in_timezones(self, activity_id):
        self._d.called("garmin.get_activity_hr_in_timezones")
        return []


@dataclass
class Devices:
    """Both fake devices, their clock (`until`), their latency and their calls."""
    scenario: Scenario
    until: date
    latency_s: float = 0.0
    #: What a Garmin login waits on top: a real one is several requests.
    login_latency_s: float = 0.0
    calls: Counter = field(default_factory=Counter)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def __post_init__(self):
        self.oura = FakeOura(self)
        self.garmin = FakeGarmin(self)

    def called(self, name: str, extra_s: float = 0.0) -> None:
        with self._lock:
            self.calls[name] += 1
        if self.latency_s + extra_s > 0:
            _time.sleep(self.latency_s + extra_s)

    def total_calls(self) -> int:
        with self._lock:
            return sum(self.calls.values())
