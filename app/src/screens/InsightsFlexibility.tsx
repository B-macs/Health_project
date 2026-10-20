// Insights › Flexibility (rebuild Phase 8, inventory I26-I31, I41-I51): the battery's answer.
// Three states, each its own screen as in the old app: unreadable (the record could not be
// read, never shown as empty), empty (nothing measured yet: one button), and populated (the
// pattern and the one thing to train, or why there is no pattern and the one or two readings
// that would give one). An assessment in progress shows on top with a way back into it.
//
// The battery is the engine's (services/flexibility.py and the cluster modules): the
// pattern, the ladder, the stack, the slots run, the readings it waits on and the retest are
// its answers. The screen lays them out and never decides any of them.
import { useState } from 'react'
import type { components } from '../generated/api'
import { ApiError, api } from '../lib/api'
import { useApp } from '../lib/appState'
import { keepAnswer, useCached, type View } from '../lib/cache'
import { shortDate, yearDate } from '../lib/dates'
import { S } from '../strings'
import { Freshness } from '../ui/Freshness'
import { InsightsHead } from '../ui/InsightsHead'
import { Marked, plain } from '../ui/Marked'
import { Contributor } from '../ui/parts'
import {
  CAPTURE_PAGE, FLEXIBILITY, failure, freshCapture, numberOf, type FlexibilityAnswer, type Guide,
} from './FlexibilityShared'

type Schemas = components['schemas']
type Report = Schemas['FlexReport']

type Rung = {
  key: string; label: string; muscle: string; state: string; unit: string
  measured: number | null; target: number | null; fraction: number | null
  detail: string; pattern: string | null; provisional: boolean
}
type Slot = { slot: number; label: string; question: string; passed: boolean; indeterminate: boolean; basis: string; reason: string }
type Missing = { test_key: string; side: string; setup: boolean; label: string; hint: string }
type Detail = Record<'spectrum' | 'position' | 'movement' | 'feel' | 'stop' | 'progress' | 'note' | 'adapted_from' | 'reverts_when' | 'deferred_until', string>
type Stack = {
  pattern: string; limiter: string; outro: string
  items: { exercise: string; dose: string; note: string; detail: Detail | null }[]
  held_back: { exercise: string; detail: Detail | null }[]
}

/** The empty state (I28-I31): the standing goal, Start, what an assessment produces, the
 *  slots and why they run in order, and the tests held back for now. */
function Empty({ guide, onStart }: { guide: Guide; onStart: () => void }) {
  return (
    <>
      <section className="card group" data-testid="flex-empty">
        <span className="eyebrow">{S.flex.standingGoal}</span>
        <span className="answer">{S.flex.notMeasured}</span>
        <p className="caption"><Marked text={S.flex.emptyAbout(guide.cluster_label, guide.test_count)} /></p>
        <p className="caption">{S.flex.emptyOften}</p>
      </section>
      <button className="btn btn--primary" onClick={onStart}>{S.flex.start}</button>
      <section className="card group">
        <span className="eyebrow">{S.flex.producesTitle}</span>
        <p className="caption"><Marked text={S.flex.produces} /></p>
      </section>
      <details className="card guide">
        <summary className="tapline">{S.flex.slotsTitle}</summary>
        {guide.slots.map((s) => (
          <div key={s.slot} className="group">
            <p><Marked text={S.flex.slotLine(s.slot, s.label, s.question)} /></p>
            <p className="caption">{S.flex.decides(s.decides)}</p>
          </div>
        ))}
        <p className="caption">{S.flex.stopFirst}</p>
      </details>
      {guide.held_back.length > 0 && (
        <details className="card guide">
          <summary className="tapline">{S.flex.heldTitle(guide.held_back.length)}</summary>
          <p className="caption">{S.flex.heldWhy}</p>
          {guide.held_back.map((h) => (
            <div key={h.key} className="group">
              <p><Marked text={S.flex.heldLine(h.label, h.until)} /></p>
              {h.safety && <p className="caption"><Marked text={h.safety} /></p>}
            </div>
          ))}
        </details>
      )}
    </>
  )
}

/** One rung's reading against its target, as the engine measured it. */
function rungValue(r: Rung): string {
  if (r.fraction != null && r.measured != null && r.target != null) {
    return S.flex.rungValue(plain(r.measured), plain(r.target), r.unit, r.fraction)
  }
  return r.measured != null ? `${plain(r.measured)}${r.unit}` : S.ins.none
}

/** How full a rung's bar is drawn: a climbed rung with no target reads full, an unmeasured
 *  or botched one has no bar (unknown, never zero). */
function rungFill(r: Rung): number | null {
  if (r.state === 'passed') return r.fraction ?? 1
  if (r.state === 'limiting' || r.state === 'context') return r.fraction ?? 0
  return null
}

function rungTag(r: Rung): string {
  const tag = r.state === 'limiting' ? S.flex.rung.limiting(r.pattern)
    : (S.flex.rung as Record<string, unknown>)[r.state]
  const words = typeof tag === 'string' ? tag : S.flex.rung.unmeasured
  return r.provisional && r.fraction != null ? `${words} · ${S.flex.provisional}` : words
}

/** The ladder (I45): the battery's decision path, top rung first, tightest at the bottom. */
function Ladder({ rungs, reduced }: { rungs: Rung[]; reduced: boolean }) {
  if (rungs.length === 0) return null
  return (
    <section className="card group" aria-label={S.flex.ladderTitle} data-testid="ladder">
      <h2 className="eyebrow">{S.flex.ladderTitle}</h2>
      {rungs.map((r) => (
        <div key={r.key} className="rung" data-state={r.state}>
          <Contributor name={`${r.label} · ${r.muscle}`} value={rungValue(r)} fraction={rungFill(r)}
            note={rungTag(r)} reduced={reduced} />
          {r.detail && <p className="caption">{r.detail}</p>}
        </div>
      ))}
      <p className="caption">{S.flex.ladderNote}</p>
    </section>
  )
}

/** The one or two readings the battery waits on (I42), taken here: the battery runs again
 *  over them by the path a live reading takes. */
function MissingForm({ missing, onAnswer }: { missing: Missing[]; onAnswer: (a: FlexibilityAnswer) => void }) {
  const { ctx } = useApp()
  const [values, setValues] = useState<Record<string, string>>({})
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const id = (m: Missing) => `${m.test_key}|${m.side}|${m.setup ? 1 : 0}`
  async function send() {
    setBusy(true)
    setError(null)
    const entries = missing.map((m) => ({ test_key: m.test_key, side: m.side, setup: m.setup, value: numberOf(values[id(m)]) }))
    try {
      onAnswer(await api<FlexibilityAnswer>(`${FLEXIBILITY}/missing`, {
        method: 'POST', key: ctx.key, engineDown: ctx.engineDown, fetchImpl: ctx.fetchImpl, body: { entries },
      }))
    } catch (err) {
      setError(err instanceof ApiError && err.code === 'nothing_entered' ? S.flex.nothingEntered : failure(err))
    } finally {
      setBusy(false)
    }
  }
  if (missing.length === 0) return null
  return (
    <section className="card group" data-testid="flex-missing">
      <span className="eyebrow">{S.flex.missingTitle}</span>
      <p className="caption">{S.flex.missingWhy(missing.length)}</p>
      {missing.map((m) => (
        <label key={id(m)} className="group">
          <span><b>{m.label}</b>: {m.hint}</span>
          <input className="field" inputMode="decimal" value={values[id(m)] ?? ''} aria-label={m.label}
            onChange={(e) => setValues({ ...values, [id(m)]: e.target.value })} />
        </label>
      ))}
      {error && <p className="alert" role="alert">{error}</p>}
      <button className="btn btn--primary" disabled={busy} onClick={() => void send()}>{S.flex.addRerun}</button>
    </section>
  )
}

/** One exercise of the stack (I46): how before why, as the old app showed it. */
function StackItem({ n, item }: { n: number; item: Stack['items'][number] }) {
  const d = item.detail
  return (
    <details className="card guide" data-testid="stack-item">
      <summary className="tapline">{S.flex.stackItem(n, item.exercise, item.dose)}</summary>
      {d && (
        <div className="group">
          <span className="caption spectrum" data-spectrum={d.spectrum}>{d.spectrum}</span>
          {d.position && (Object.keys(S.flex.how) as (keyof typeof S.flex.how)[]).map((k) => (
            <p key={k}><b>{S.flex.how[k]}</b>: {d[k]}</p>
          ))}
          {d.note && <p><Marked text={S.flex.why(d.note)} /></p>}
          {d.adapted_from && <p className="caption"><i>{S.flex.adapted(d.adapted_from, d.reverts_when)}</i></p>}
        </div>
      )}
      {item.note && <p><Marked text={item.note} /></p>}
    </details>
  )
}

/** The pattern, the ladder, the stack, the trail, the readings and the retest (I43-I51). */
function Populated({ r, reduced, onAnswer, onReassess }: {
  r: Report; reduced: boolean; onAnswer: (a: FlexibilityAnswer) => void; onReassess: () => void
}) {
  const ladder = r.ladder as Rung[]
  const slots = r.slots as Slot[]
  const stack = r.stack as Stack | null
  const assessed = r.assessed_on ? yearDate(r.assessed_on) : ''
  if (!r.pattern) {
    return (
      <>
        <section className="card group" data-testid="flex-no-pattern">
          <span className="eyebrow">{S.flex.assessedOn(assessed)}</span>
          <span className="answer">{S.flex.noPattern}</span>
          {r.reason && <p className="caption">{r.reason}</p>}
        </section>
        <p className="notice">{S.flex.notAPass}</p>
        <MissingForm missing={r.missing as Missing[]} onAnswer={onAnswer} />
        <Ladder rungs={ladder} reduced={reduced} />
      </>
    )
  }
  const retest = r.retest as { status: string; reason: string } | null
  return (
    <>
      <section className="card group" data-testid="flex-pattern">
        <span className="eyebrow">
          {S.flex.clusterAssessed(r.cluster_label ?? '', assessed)}
          {!r.cold && <> · <b>{S.flex.warm}</b></>}
        </span>
        <span className="eyebrow">{S.flex.stopping}</span>
        <span className="answer" data-testid="pattern-label">{r.pattern_label}</span>
        <div className="kv">
          <span>{S.flex.patternIs(r.pattern)}</span>
          <span>{S.flex.stoppedAt(r.stopped_at ?? '')}</span>
          <span>{S.flex.slotsRun(slots.length, r.slots_total)}</span>
        </div>
      </section>
      {r.reason && <p className="caption">{r.reason}</p>}
      {!r.trusted && <p className="alert" data-testid="flex-hypothesis"><Marked text={S.flex.hypothesis(r.baseline_required, r.baseline_sessions)} /></p>}
      <Ladder rungs={ladder} reduced={reduced} />
      {r.stack_refused && <p className="alert" role="alert">{r.stack_refused}</p>}
      {stack && (
        <section className="group" data-testid="flex-stack">
          <h2 className="eyebrow">{S.flex.stackTitle(stack.pattern, stack.limiter)}</h2>
          {stack.items.map((item, i) => <StackItem key={item.exercise} n={i + 1} item={item} />)}
          {stack.held_back.length > 0 && (
            <details className="card guide">
              <summary className="tapline">{S.flex.heldTitle(stack.held_back.length)}</summary>
              {stack.held_back.map((h) => (
                <div key={h.exercise} className="group">
                  <p><b>{h.exercise}</b></p>
                  {h.detail?.deferred_until && <p className="caption">{S.flex.heldUntil(h.detail.deferred_until, h.detail.reverts_when)}</p>}
                </div>
              ))}
            </details>
          )}
          {stack.outro && <p><Marked text={stack.outro} /></p>}
        </section>
      )}
      <details className="card guide" data-testid="flex-trail">
        <summary className="tapline">{S.flex.trailTitle(slots.length)}</summary>
        {slots.map((s) => (
          <div key={s.slot} className="group">
            <p>
              <Marked text={S.flex.trailLine(s.passed ? S.flex.mark.pass : s.indeterminate ? S.flex.mark.undecided : S.flex.mark.fail,
                s.slot, s.label, s.question)} />
              {' · '}<i>{S.flex.basis[s.basis] ?? s.basis}</i>
            </p>
            <p className="caption">{s.reason}</p>
          </div>
        ))}
        {r.slots_not_run > 0 && <p className="caption">{S.flex.notRun(r.slots_not_run)}</p>}
      </details>
      <details className="card guide" data-testid="flex-readings">
        <summary className="tapline">{S.flex.readingsTitle}</summary>
        {r.readings.map((x, i) => (
          <p key={i}>
            <b>{x.label || x.test_key}</b>{x.side && <> <i>{x.side}</i></>}{': '}
            {plain(x.value)}{x.unit}{x.load_kg ? S.flex.readingLoad(plain(x.load_kg)) : ''}
            {x.setup_value != null ? S.flex.readingSetup(plain(x.setup_value)) : ''}
          </p>
        ))}
      </details>
      {retest && (
        retest.status === 'not_due' ? <p className="caption" data-testid="flex-retest">{`${retest.reason.charAt(0).toUpperCase()}${retest.reason.slice(1)}.`}</p>
          : retest.status === 'blocked' ? <p className="alert" data-testid="flex-retest">{S.flex.retestDue(retest.reason)}</p>
            : <p className="notice" data-testid="flex-retest">{S.flex.retestReady(retest.reason)}</p>
      )}
      <button className="btn btn--glass" onClick={onReassess}>{S.flex.reassess}</button>
      <p className="caption"><Marked text={r.retest_text} /></p>
    </>
  )
}

/** The screen drawn from one read: the tests draw it in each state. */
export function FlexibilityBody({ view, reduced, onAnswer, onResume, onAssess }: {
  view: View<FlexibilityAnswer>; reduced: boolean; onAnswer: (a: FlexibilityAnswer) => void
  onResume: () => void; onAssess: () => void
}) {
  const d = view.data
  const capture = d?.capture
  return (
    <div className="screen insights" data-testid="flexibility">
      <div className="sky sky--quiet" aria-hidden="true" />
      <InsightsHead title={S.ins.flexibility} />
      <Freshness view={view} />
      {d?.state === 'unreadable' && <p className="alert" role="alert" data-testid="flex-unreadable">{S.flex.unreadable(d.load_error ?? '')}</p>}
      {capture && (
        <section className="card group" data-testid="flex-resume">
          <p className="caption">{S.flex.inProgress(capture.progress.done ?? 0, capture.progress.total ?? 0, shortDate(capture.taken_on))}</p>
          <button className="btn btn--primary" onClick={onResume}>{S.flex.resume}</button>
        </section>
      )}
      {d?.state === 'empty' && <Empty guide={d.guide as unknown as Guide} onStart={onAssess} />}
      {d?.state === 'populated' && d.report && (
        <Populated r={d.report} reduced={reduced} onAnswer={onAnswer} onReassess={onAssess} />
      )}
    </div>
  )
}

export function FlexibilityScreen() {
  const { store, ctx, go, reduced } = useApp()
  const view = useCached<FlexibilityAnswer>(store, FLEXIBILITY, null, ctx)
  async function answered(a: FlexibilityAnswer) {
    await keepAnswer(store, FLEXIBILITY, null, a)
    view.again()
  }
  return (
    <FlexibilityBody view={view} reduced={reduced} onAnswer={(a) => void answered(a)}
      onResume={() => go(CAPTURE_PAGE)}
      onAssess={() => {
        // Start and Re-assess open a new assessment on its first test; Resume keeps the place.
        freshCapture()
        go(CAPTURE_PAGE)
      }} />
  )
}
