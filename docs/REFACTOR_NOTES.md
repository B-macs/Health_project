# REFACTOR_NOTES.md — services/ extraction

*Written 2026-07-07 at the end of the "extract a framework-agnostic services/
layer" refactor. This was a refactor-only pass — no new features, no UI
changes, no schema changes, no changes to what's read from or written to
Sheets/Notion. Anything below that reads like a bug/smell was found during
migration; most were left as-is per that rule. A few were fixed because the
fix was inherent to the extraction itself (called out explicitly below) —
everything else is untouched and just relocated.

---

## Fixed because the extraction required it

**`sleep_hours` / `sleep_duration_hours` field-name drift.** `views/sync.py`
had its own independent column-mapping loop for the "Engine View" table,
separate from `sync_sheets.get_biometric_rolling()`'s mapping — and the two
had drifted: the page's own loop used `sleep_hours`, the canonical mapping
used `sleep_duration_hours`. Consolidating "column names live only in
`repository.py`" (a hard rule of the extraction) meant picking one; the
canonical name won. The one visible effect: that debug table's column header
changed from `sleep_hours` to `sleep_duration_hours`.

**`engine.py`'s buried `date.today()` calls.** `readiness_training_modifier`
and `acwr` both called `date.today()` internally instead of accepting it as a
parameter — the one required logic change per the refactor's explicit rules
("no hidden clock reads; pass `today: date` as a parameter"). Both now take
an optional `today: date | None = None`, defaulting to real "today" when
omitted so callers who don't care are unaffected.

**`views/sync.py`'s duplicate mapping logic.** The page had two tables: a
raw passthrough and an "Engine View" that was doing its own 28-day window +
column mapping — functionally identical to `get_biometric_rolling(28)`
except for the field-name drift above. It now reuses
`repo.get_repository().get_biometric_rolling(days=28)` directly instead of
re-implementing the mapping.

---

## Found, not fixed (pre-existing, noted for future cleanup)

**`app.py` had an undocumented dashboard-math cluster.** 7-day windowing,
rolling prior-strain calculation, step-count strain modifier + clamping, and
sleep baseline/percentage math all lived inline in `app.py` with no tests
and no clear ownership. This is now relocated verbatim (with `today`
parameterized) into `services/dashboard.py`, but the underlying formulas
were not reviewed or changed for correctness — only extracted and given
test coverage for the first time.

**`GOOGLE_SHEETS_TAB` secret is configured but never read anywhere in the
code.** `sync_sheets.py` (now `services/clients/sheets.py`) hardcoded
`WORKSHEET = "Sheet1"` instead. The secret still exists in
`.streamlit/secrets.toml` as dead configuration. Not touched — fixing it
would be a behavior change (which sheet tab gets read), out of scope for a
refactor-only pass.

**`views/insights.py` had several ad-hoc reimplementations of logic that
already existed elsewhere:** chart date-window construction duplicated
`engine.acwr`'s acute/chronic split concept instead of reusing it, and
slope→direction classification duplicated `stats.trend_slope`'s intent
instead of calling it. Both are now consolidated in `services/insights.py`
(`acwr_chart_data`, `slope_direction_rows`) to call the real
`engine.acwr` / `stats.trend_slope` functions rather than re-deriving the
same math a second time — this was necessary to satisfy "no duplicated
column/mapping logic" for the extraction, not a behavior change (same
output, one code path instead of two).

**`get_recent_sessions()`'s return shape changed internally.** The old
`db.py` version returned one flat dict per logged exercise row. The new
`Repository.get_recent_sessions()` groups those into one `SessionRecord`
per session date, with a nested `list[ExerciseEntry]`. This is *not* a
change to what's read from or written to Notion — same underlying rows,
same fields — just a more useful in-memory shape now that it's a typed
return value. Every call site (`views/training.py`'s past-completed-day
rendering) was updated accordingly and re-verified with `AppTest`.

**`db.py`'s old `_secret()` helper did env-var-first, `st.secrets`-fallback
lookup with an inline `import streamlit` inside the fallback branch.** This
exact pattern is what `services/config.py`'s `load_config()` formalizes
(env vars first, then an injected `overrides` dict) — but the old function
itself is deleted along with the rest of `db.py`, so there's nothing left
to migrate here; noted only because it was the seed of the `Config` design.

---

## Structural notes (not bugs, just worth knowing)

- `services/plan.py`'s `DayCell.session_ref` deliberately stayed a loose
  `dict | None` rather than a full `SessionRecord` — the day-strip's
  existence check never needs more than that, and forcing a full typed
  record there would mean constructing one solely for a lookup.
- The 6 "core" models (`Phase`, `SessionRecord`, `ExerciseEntry`, `DayCell`,
  `CheckInRecord`, `BiometricRecord`) are full dataclasses; the remaining
  ~34 repository methods (trends, correlations, movement risk, flagged
  entries) still return plain dicts. This was an explicit scope decision,
  not an oversight — full typing everywhere was judged not worth the extra
  surface area for data that's only ever displayed, never branched on.
