// Insights › Flexibility › the assessment (rebuild Phase 8, inventory I32-I40): the battery
// taken one test at a time. First the cold gate (cold or warm, yesterday's leg day, the
// protocol), then each test in the engine's order: its LOCK first and loudest, the setup, how
// to read it, and the form. After every step the engine answers the order again and whether
// the battery has its answer: a pattern means stop here, because a reading taken below a
// failing slot cannot be interpreted.
//
// The phone never chooses a test: it shows the engine's order at the position the owner
// moves (Save & next and Skip forward, Back back), as the old app did, and the early answer
// is the engine's. The assessment is kept in the store after every step, so Pause (or a
// closed app) loses nothing; it needs the engine, which decides the next test each time.
import { useEffect, useRef, useState } from 'react'
import type { components } from '../generated/api'
import { api } from '../lib/api'
import { useApp } from '../lib/appState'
import { cacheKey, keepAnswer, useCached } from '../lib/cache'
import { S } from '../strings'
import { Freshness } from '../ui/Freshness'
import { InsightsHead } from '../ui/InsightsHead'
import { Marked, plain } from '../ui/Marked'
import {
  FLEXIBILITY, failure, freshCapture, numberOf, position, type FlexibilityAnswer, type Guide,
} from './FlexibilityShared'

type Schemas = components['schemas']
type Capture = Schemas['FlexCapture']
type Test = Schemas['FlexTest']
type Reading = Schemas['FlexReading']

const CAPTURE = `${FLEXIBILITY}/capture`
const BACK = '/insights/flexibility'

/** Before the first test (I32-I35): cold or warm, the leg-day warning, the protocol. */
export function ColdGate({ guide, legs, busy, onBegin }: {
  guide: Guide; legs: boolean; busy: boolean; onBegin: (cold: boolean) => void
}) {
  const { go } = useApp()
  const [cold, setCold] = useState(true)
  return (
    <>
      <section className="card group" data-testid="cold-gate">
        <span className="eyebrow">{S.flex.beforeStart}</span>
        <span className="answer">{S.flex.measureCold}</span>
        <p className="caption">{S.flex.coldWhy}</p>
      </section>
      <div className="segmented" role="radiogroup" aria-label={S.flex.coldQuestion}>
        {([[true, S.flex.coldChoice], [false, S.flex.warmChoice]] as const).map(([value, label]) => (
          <button key={label} role="radio" aria-checked={cold === value}
            className={`segmented__item${cold === value ? ' segmented__item--on' : ''}`}
            onClick={() => setCold(value)}>{label}</button>
        ))}
      </div>
      {legs && <p className="alert" role="alert" data-testid="leg-day">{S.flex.legDay}</p>}
      <details className="card guide" open>
        <summary className="tapline">{S.flex.threeNumbers}</summary>
        {guide.measures.map((m) => (
          <div key={m.measure} className="group">
            <p><Marked text={S.flex.measureLine(m.measure.charAt(0).toUpperCase() + m.measure.slice(1), m.short)} /></p>
            <p className="caption">{m.long}</p>
          </div>
        ))}
        <p><Marked text={guide.gap} /></p>
        <p className="caption"><Marked text={S.flex.order} /></p>
      </details>
      <details className="card guide">
        <summary className="tapline">{S.flex.lockTitle}</summary>
        <p><Marked text={guide.lock} /></p>
      </details>
      <details className="card guide">
        <summary className="tapline">{S.flex.onceTitle}</summary>
        <p className="caption">{S.flex.onceWhy}</p>
        {guide.frozen.map((f) => <p key={f.name}><Marked text={S.flex.constantLine(f.name.replaceAll('_', ' '), f.why)} /></p>)}
        <p><Marked text={S.flex.movingLine(guide.progression_variable.name.replaceAll('_', ' '), guide.progression_variable.why)} /></p>
      </details>
      <details className="card guide">
        <summary className="tapline">{S.flex.neverChase}</summary>
        <p><b>{S.flex.nerveCheck}</b></p>
        <p><Marked text={guide.nerve_check} /></p>
        <p><b>{S.flex.innerKnee}</b></p>
        <p><Marked text={guide.medial_knee_note} /></p>
      </details>
      <div className="pair">
        <button className="btn btn--primary" disabled={busy} onClick={() => onBegin(cold)}>{S.flex.begin}</button>
        <button className="btn btn--glass" onClick={() => go(BACK)}>{S.flex.cancel}</button>
      </div>
    </>
  )
}

/** The battery answered early (I36): stop here and save, or keep going anyway. */
export function EarlyAnswer({ c, busy, onSave, onKeepGoing }: {
  c: Capture; busy: boolean; onSave: () => void; onKeepGoing: () => void
}) {
  return (
    <section className="card group card--hi" data-testid="early-answer">
      <span className="eyebrow">{S.flex.yourAnswer}</span>
      <span className="answer">{S.flex.patternLine(c.early_pattern ?? '', c.early_pattern_label)}</span>
      {c.early_reason && <p className="caption">{c.early_reason}</p>}
      <p className="caption">{S.flex.nothingMore}</p>
      <div className="pair">
        <button className="btn btn--primary" disabled={busy} onClick={onSave}>{S.flex.saveAssessment}</button>
        <button className="btn btn--glass" onClick={onKeepGoing}>{S.flex.keepGoing}</button>
      </div>
    </section>
  )
}

export interface StepEntry {
  entered: Record<string, number | null>
  load: number | null
  setup_value: number | null
  void: boolean
}

/** One test's form (I39): a value per side (the reading already in is offered back), the
 *  added load on an isometric spectrum test, the setup number (the last one offered back:
 *  it is meant to be the same every time), and the void tick for a lost lock. */
export function StepForm({ test, readings, last, busy, onSave }: {
  test: Test; readings: readonly Reading[]; last: boolean; busy: boolean; onSave: (e: StepEntry) => void
}) {
  const sides = test.bilateral ? ['left', 'right'] : ['']
  const prior = (side: string) => readings.find((r) => r.test_key === test.key && r.side === side)
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(sides.map((side) => {
      const r = prior(side)
      return [side, r ? plain(r.value) : '']
    })))
  const [load, setLoad] = useState('')
  const [setup, setSetup] = useState(test.prior_setup != null ? plain(test.prior_setup) : '')
  const [voided, setVoided] = useState(false)
  return (
    <form className="card group" data-testid="step-form" onSubmit={(e) => {
      e.preventDefault()
      onSave({
        entered: Object.fromEntries(sides.map((side) => [side, numberOf(values[side])])),
        load: test.takes_load ? numberOf(load) : null,
        setup_value: test.setup_input ? numberOf(setup) : null,
        void: voided,
      })
    }}>
      {test.input_hint && <p><Marked text={S.flex.whatToType(test.input_hint)} /></p>}
      <div className="figures">
        {sides.map((side) => (
          <label key={side} className="group">
            <span className="eyebrow">{S.flex.side[side]}</span>
            <input className="field" inputMode="decimal" aria-label={`${test.label} ${S.flex.side[side]} (${test.unit})`}
              value={values[side] ?? ''} onChange={(e) => setValues({ ...values, [side]: e.target.value })} />
          </label>
        ))}
      </div>
      {test.takes_load && (
        <label className="group">
          <span className="caption">{S.flex.load}</span>
          <input className="field" inputMode="decimal" aria-label={S.flex.load} value={load} onChange={(e) => setLoad(e.target.value)} />
        </label>
      )}
      {test.setup_input && (
        <label className="group">
          {test.prior_setup_from_earlier && test.prior_setup != null && (
            <span className="caption"><Marked text={S.flex.lastTime(plain(test.prior_setup))} /></span>
          )}
          <span className="caption">{S.flex.setupField(test.setup_input)}</span>
          <input className="field" inputMode="decimal" aria-label={test.setup_input} value={setup} onChange={(e) => setSetup(e.target.value)} />
        </label>
      )}
      <label className="field-row">
        <span>{S.flex.void}</span>
        <input type="checkbox" role="switch" className="switch" checked={voided} onChange={(e) => setVoided(e.target.checked)} />
      </label>
      <button type="submit" className="btn btn--primary" disabled={busy}>{last ? S.flex.saveFinish : S.flex.saveNext}</button>
    </form>
  )
}

/** The test at the owner's position (I37-I40): the ticks, the header, the LOCK, the setup,
 *  how to read it, the form, and Skip / Back / Pause. */
export function Step({ c, at, busy, onSave, onMove }: {
  c: Capture; at: number; busy: boolean; onSave: (test: Test, last: boolean, e: StepEntry) => void; onMove: (to: number) => void
}) {
  const { go } = useApp()
  const order = c.order
  const test = order[at]
  if (!test) return null
  const last = at === order.length - 1
  return (
    <>
      <div className="ticks" aria-hidden="true">
        {order.map((t, i) => (
          <i key={t.key} className={`tick${i === at ? ' tick--now' : c.done.includes(t.key) ? ' tick--done' : ''}`} />
        ))}
      </div>
      {c.skip_notes.map((note) => <p key={note} className="caption">{note}</p>)}
      <div className="kv" data-testid="step-head">
        <span className="steptitle">{test.label}</span>
        <span className="caption">{S.flex.stepOf(at + 1, order.length, test.slot, test.slot_label)}</span>
      </div>
      <p className="lockbox" data-testid="lock"><b>{S.flex.lock}</b>: <Marked text={test.lock} /></p>
      <section className="card"><p><Marked text={test.setup} /></p></section>
      <details className="card guide">
        <summary className="tapline">{S.flex.howToRead}</summary>
        <p className="caption"><Marked text={test.measurement} /></p>
        <p><b>{S.flex.testing}</b></p>
        <p className="caption">{test.what_youre_testing}</p>
        {test.adapted_from && <p className="caption"><i>{S.flex.adaptedFor(test.adapted_from)}</i></p>}
        {test.safety && <p className="alert"><Marked text={test.safety} /></p>}
      </details>
      <StepForm key={test.key} test={test} readings={c.readings} last={last} busy={busy}
        onSave={(e) => onSave(test, last, e)} />
      <div className="trio">
        <button className="btn btn--glass" onClick={() => onMove(Math.min(at + 1, order.length - 1))}>{S.flex.skip}</button>
        <button className="btn btn--glass" disabled={at === 0} onClick={() => onMove(Math.max(0, at - 1))}>{S.flex.back}</button>
        <button className="btn btn--glass" onClick={() => go(BACK)}>{S.flex.pause}</button>
      </div>
    </>
  )
}

export function FlexibilityCapture() {
  const { store, ctx, go } = useApp()
  const view = useCached<FlexibilityAnswer>(store, FLEXIBILITY, null, ctx)
  const [live, setLive] = useState<Capture | null>(null)
  const [step, setStepState] = useState(position.step)
  const [keepGoing, setKeepGoingState] = useState(position.keepGoing)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const setStep = (n: number) => {
    position.step = n
    setStepState(n)
  }
  const goOn = () => {
    position.keepGoing = true
    setKeepGoingState(true)
  }
  // The engine's own answer, never a saved one: the order and the early answer are decided
  // after every step, so the capture runs only while the engine answers.
  const d = view.state === 'fresh' ? view.data : undefined
  const capture = live ?? d?.capture ?? null
  const send = <T,>(path: string, method: 'POST' | 'PUT', body?: unknown) =>
    api<T>(path, { method, key: ctx.key, engineDown: ctx.engineDown, fetchImpl: ctx.fetchImpl, body })

  async function act(action: () => Promise<void>) {
    setBusy(true)
    setError(null)
    try {
      await action()
    } catch (err) {
      setError(S.flex.failed(failure(err)))
    } finally {
      setBusy(false)
    }
  }

  /** The assessment as the engine now holds it; the Flexibility page's saved answer shows it
   *  too (its "in progress" line), so going back never shows it missing. */
  async function hold(c: Capture) {
    setLive(c)
    const saved = await store.cache.get(cacheKey(FLEXIBILITY, null))
    if (saved) await store.cache.put({ ...saved, body: { ...(saved.body as FlexibilityAnswer), capture: c } })
  }

  async function finish() {
    await keepAnswer(store, FLEXIBILITY, null, await send<FlexibilityAnswer>(`${CAPTURE}/finish`, 'POST'))
    freshCapture()
    go(BACK)
  }

  const begin = (cold: boolean) => act(async () => {
    await hold(await send<Capture>(CAPTURE, 'POST', { cold }))
    setStep(0)
  })

  const save = (test: Test, last: boolean, e: StepEntry) => act(async () => {
    await hold(await send<Capture>(CAPTURE, 'PUT', { test_key: test.key, ...e }))
    if (last) await finish()
    else setStep(step + 1)
  })

  // A new step, the early answer or the cold gate opens at the top: the LOCK is read first.
  const root = useRef<HTMLDivElement>(null)
  const shown = !capture ? 'gate' : capture.early_pattern && !keepGoing ? 'early' : `step ${step}`
  useEffect(() => {
    root.current?.closest('.scroller')?.scrollTo?.(0, 0)
  }, [shown])

  let body
  if (!d && !live) {
    body = view.state === 'loading' ? null : <p className="notice" data-testid="needs-engine">{S.flex.needsEngine}</p>
  } else if (!capture) {
    body = <ColdGate guide={d?.guide as unknown as Guide} legs={d?.legs_loaded_yesterday ?? false} busy={busy} onBegin={(cold) => void begin(cold)} />
  } else if (capture.early_pattern && !keepGoing) {
    body = <EarlyAnswer c={capture} busy={busy} onSave={() => void act(finish)} onKeepGoing={goOn} />
  } else {
    const at = Math.max(0, Math.min(step, capture.order.length - 1))
    body = <Step c={capture} at={at} busy={busy} onSave={(t, last, e) => void save(t, last, e)} onMove={setStep} />
  }
  return (
    <div className="screen insights" data-testid="flex-capture" ref={root}>
      <div className="sky sky--quiet" aria-hidden="true" />
      <InsightsHead title={S.ins.flexibility} back={BACK} backLabel={S.ins.flexibility} />
      {!live && <Freshness view={view} />}
      {error && <p className="alert" role="alert" data-testid="capture-error">{error}</p>}
      {body}
    </div>
  )
}
