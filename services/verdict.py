"""services/verdict.py — TODAY'S ONE VERDICT, the object BOTH screens render.

⚠ WHY THIS EXISTS. On 2026-08-23 the athlete opened Home, saw a readiness of
66, went to Training, and was told to reduce load: "I saw 66 but then saw
reduce load in training ... I dont want to be suprised when I see the deload
statement in training."

Neither screen was wrong. THEY SHARED NO NUMBER AT ALL. Home's card shows
readiness.compute_readiness_trend (an EMA over ~14 days, services/dashboard.py's
compute_daily_metrics_snapshot); the training decision buckets the RAW
compute_readiness for the same day, which on that date read 56.2 against the
trend's 66; and views/training.py never displays a readiness figure of any kind.
So the fix is not reconciling two numbers — it is putting the DECISION on Home.

WHAT THIS MODULE IS, AND IS NOT. It is a widening for display. It calls
services.sessions.load_policy — which stays exactly where it is, unchanged, as
the input clamp_to_ceiling reads — and hangs the numbers Home already shows off
the result. ONE load_policy call per render, made in here, so the two screens
cannot be reading different policies.

⚠ THE DECISION FIELDS ARE A PURE FUNCTION OF (directive, readiness_modifier) —
the same two arguments load_policy itself takes. readiness_display,
readiness_raw, readiness_band and hrv_note are CARRIED AND PRINTED, never read
by any branch in this file. That is what makes the 4-night HRV run warn-only:
not a comment and not an import fence, but a property proved by a test that
hands this function absurd values for all four and asserts every decision field
is identical.

hrv_note arrives as an OPAQUE STRING. This module never imports hrv_trend, has
no name through which it could reach it, and is on that module's own
forbidden-consumer list. The string is composed in today.py — outside services/
— from the RING alone, which is the same source engine.traffic_light already
scores HRV against (biometrics.HRV_GARMIN_HOLD keeps hrv_ms Oura's or nothing),
so key rule 2b gains no new exposure. The 60/40 combined figure never leaves
services/hrv_trend.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from services import sessions

#: banner_kind -> the muted Home tone. These are the EXACT hex strings
#: dashboard.readiness_meta already emits, so the card and the line beneath it
#: cannot drift apart. Deliberately NOT engine.SIGNAL_COLORS: #FF4B4B on a 460px
#: hero card reads as an alarm, and the requirement is "not surprised", not
#: "alarmed".
HOME_TONES = {
    "":        "#6BAF8B",
    "info":    "#BFA06A",
    "warning": "#BFA06A",
    "error":   "#C47878",
}

#: banner_kind -> the pill under the readiness figure. Derived from banner_kind
#: ALONE, so a kind that renders on Training but not on Home cannot be
#: constructed — which is the reported bug in its most general form.
BADGE_WORDS = {
    "":        "",
    "info":    "VOLUME HELD",
    "warning": "REDUCED LOAD",
    "error":   "REST ADVISED",
}


@dataclass(frozen=True)
class Verdict:
    """What both screens print. See the module docstring for the two halves."""

    # ── THE DECISION. A pure function of (directive, readiness_modifier). ────
    reduced:       bool
    banner_kind:   str            # "" | "info" | "warning" | "error"
    banner_text:   str            # load_policy's own string, never re-authored
    driver:        str | None
    standing_cap:  bool
    volume_factor: float
    reasons:       tuple[str, ...]
    #: load_policy's dict, untouched, for the clamp path. resolve_prescription
    #: and clamp_to_ceiling keep receiving exactly what they receive today.
    policy:        dict = field(default_factory=dict)

    # ── PRESENTATION, derived from banner_kind alone. ───────────────────────
    badge: str = ""
    tone:  str = HOME_TONES[""]

    # ── CARRIED, NEVER CONSULTED. Nothing here may move anything above. ─────
    readiness_display: float | None = None   # the trend — Home's big number
    readiness_raw:     float | None = None   # what the engine actually bucketed
    readiness_band:    str = ""              # readiness_meta's word
    hrv_note:          str = ""              # opaque; composed in today.py

    @property
    def has_something_to_say(self) -> bool:
        """Whether Home renders the line at all. A clear day adds nothing —
        matching Training, which shows no banner on green or grey, and matching
        hrv_trend's own rule that a quiet day says nothing rather than
        reassuring."""
        return bool(self.reduced or self.hrv_note)


def today_verdict(directive: dict | None,
                  readiness_modifier: dict | None,
                  readiness_display: float | None = None,
                  readiness_raw: float | None = None,
                  readiness_band: str = "",
                  hrv_note: str = "") -> Verdict:
    """Compose today's one verdict.

    The first two arguments are load_policy's own, and they alone decide
    everything in the decision half. The rest are printed.
    """
    policy = sessions.load_policy(directive, readiness_modifier)
    kind = policy["banner_kind"]
    return Verdict(
        reduced=policy["reduced"],
        banner_kind=kind,
        # ⚠ THE SAME STRING OBJECT load_policy produced, not a copy and not a
        # re-authoring. One sentence exists in the process; a test asserts
        # identity rather than equality, and a source scan keeps the banner
        # literals out of app.py and views/training.py entirely.
        banner_text=policy["banner_text"],
        driver=policy.get("driver"),
        standing_cap=bool(policy.get("standing_cap")),
        volume_factor=policy["volume_factor"],
        reasons=tuple(policy.get("reasons") or ()),
        policy=policy,
        badge=BADGE_WORDS.get(kind, ""),
        tone=HOME_TONES.get(kind, HOME_TONES[""]),
        readiness_display=readiness_display,
        readiness_raw=readiness_raw,
        readiness_band=readiness_band,
        hrv_note=hrv_note or "",
    )


def readiness_scale_caption(readiness_display: float | None,
                            readiness_raw: float | None) -> str:
    """Why the number on the card and the number under it differ.

    The readiness drill-down shows the trend in its masthead and the raw score
    in the contributors panel a few centimetres below, with nothing explaining
    the gap — the same silent divergence that produced the 66-then-reduce-load
    report. _sleep_contributors_block already solved this shape with a one-line
    caption; this is its readiness twin.

    Returns "" when there is nothing to explain, rather than a sentence that
    says the two agree.
    """
    if readiness_display is None or readiness_raw is None:
        return ""
    if round(readiness_display) == round(readiness_raw):
        return ""
    return ("The score above carries the last two weeks forward; the "
            "contributors below are last night alone "
            f"({readiness_raw:.0f} today).")
