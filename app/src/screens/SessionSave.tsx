// The save screen (rebuild Phase 6; inventory T89-T102). What was done, how hard the
// session was (the owner's own rating: it feeds the session load), the length to save, the
// session notes, and one Save. The save goes through the outbox with the ids minted at
// Start, so it works offline and the engine stores it once however often it is sent
// (rebuild rule 4); the screen says "saved on the phone", then "saved" when the engine
// confirms it.
//
// The length: the clock counts from the first completion tap, with the plan's floor; past
// the threshold the engine sent with the plan (T93), the owner picks the plan's length or
// the clock's. The load shown is the engine's (POST /api/training/completion), when it
// answers; offline it is worked out when the save is sent.
import { useLiveQuery } from 'dexie-react-hooks'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { components } from '../generated/api'
import { api } from '../lib/api'
import { useApp } from '../lib/appState'
import { enqueue } from '../lib/outbox'
import { asksLength, clockMinutes, saveBody, type TrainingState } from '../lib/training'
import { S } from '../strings'

type Completion = components['schemas']['CompletionOut']

/** Each exercise as it was done: its sets, or skipped. */
function Review({ s }: { s: TrainingState }) {
  return (
    <section className="card group" aria-label={S.session.review}>
      <h2 className="eyebrow">{S.session.review}</h2>
      <ul className="list">
        {s.plan.exercises.map((ex) => {
          const sets = s.sets[ex.index] ?? []
          const last = sets[sets.length - 1]
          const weight = last?.right?.weight_kg
          return (
            <li key={ex.index} className="kv">
              <span>{ex.name}</span>
              <span className="caption">
                {sets.length ? `${S.session.setsDone(sets.length)}${weight ? ` · ${weight}` : ''}` : S.session.skipped}
              </span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

export function SessionSave({ s, update, onDone }: {
  s: TrainingState
  update: (f: (s: TrainingState) => TrainingState) => void
  onDone: () => void
}) {
  const { store, ctx } = useApp()
  const end = useMemo(() => Date.now(), [])
  const clock = clockMinutes(s, end)
  const ask = asksLength(s, clock)
  const [rpe, setRpe] = useState(5)
  const [choice, setChoice] = useState<'plan' | 'clock'>(ask ? 'plan' : 'clock')
  const [notes, setNotes] = useState('')
  const [completion, setCompletion] = useState<Completion | null>(null)
  const minutes = choice === 'plan' ? s.plan.model_minutes : clock
  const saved = useLiveQuery(async () => {
    if (!s.savedId) return 'unsaved' as const
    const row = await store.outbox.where('id').equals(s.savedId).first()
    return row ? (row.state === 'failed' ? ('refused' as const) : ('waiting' as const)) : ('confirmed' as const)
  }, [store, s.savedId])

  // The load at each rating for each length, from the engine (no rule here).
  useEffect(() => {
    if (s.savedId || !s.firstSetAt) return
    void api<Completion>('/api/training/completion', {
      method: 'POST', key: ctx.key, engineDown: ctx.engineDown,
      body: { model_minutes: s.plan.model_minutes, start_ts: s.firstSetAt / 1000, end_ts: end / 1000, rpe, kind: s.plan.kind },
    }).then(setCompletion, () => setCompletion(null))
    // once, at the screen's start; the answer carries every rating's load
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  const au = completion?.choices.find((c) => c.minutes === minutes)?.au_by_rpe[rpe - 1]

  // A second tap before the first is stored would queue the save twice (the engine would
  // still keep one, by its ids): the button waits for the first.
  const sending = useRef(false)
  const [busy, setBusy] = useState(false)
  const save = async () => {
    if (sending.current) return
    sending.current = true
    setBusy(true)
    const id = await enqueue(store, { kind: 'session', method: 'POST', path: '/api/training/sessions', body: saveBody(s, minutes, rpe, notes) })
    update((x) => ({ ...x, savedId: id }))
  }

  if (s.savedId) {
    return (
      <div className="screen train">
        <div className="sky" aria-hidden="true" />
        <header className="head">
          <h1 className="head__title">{S.session.title}</h1>
        </header>
        <section className="card group" role="status" data-testid="save-state" data-state={saved}>
          <p>{saved === 'confirmed' ? S.session.saved : saved === 'refused' ? S.session.refused : S.session.savedPhone}</p>
          {s.plan.next_day && <p className="caption">{S.session.tomorrow(s.plan.next_day.day_num, s.plan.next_day.objective)}</p>}
        </section>
        <button className="btn btn--primary btn--wide" onClick={onDone}>{S.session.done}</button>
      </div>
    )
  }

  return (
    <div className="screen train">
      <div className="sky" aria-hidden="true" />
      <header className="head">
        <h1 className="head__title">{S.session.complete(s.plan.day_num)}</h1>
      </header>
      <Review s={s} />
      <section className="card group">
        <label className="group">
          <span className="kv"><span>{S.session.effort}</span><span className="num">{S.session.effortValue(rpe)}</span></span>
          <input type="range" className="slider" min={1} max={10} step={1} value={rpe} aria-label={S.session.effort}
            onChange={(e) => setRpe(Number(e.target.value))} />
        </label>
      </section>
      {ask && (
        <section className="card group">
          <p>{S.session.lengthAsk(clock, s.plan.model_minutes)}</p>
          <div className="segmented segmented--wrap" role="radiogroup" aria-label={S.session.lengthAsk(clock, s.plan.model_minutes)}>
            {(['plan', 'clock'] as const).map((c) => (
              <button key={c} role="radio" aria-checked={choice === c}
                className={`segmented__item${choice === c ? ' segmented__item--on' : ''}`} onClick={() => setChoice(c)}>
                {c === 'plan' ? S.session.lengthPlan(s.plan.model_minutes) : S.session.lengthClock(clock)}
              </button>
            ))}
          </div>
        </section>
      )}
      <p className="caption">{S.session.duration(minutes)}</p>
      <p className="caption">{au != null ? S.session.load(au) : S.session.loadLater}</p>
      <label className="group">
        <span className="caption">{S.session.sessionNotes}</span>
        <textarea className="field field--area" value={notes} onChange={(e) => setNotes(e.target.value)} />
      </label>
      <button className="btn btn--primary btn--wide" disabled={busy} onClick={() => void save()}>{S.session.save}</button>
    </div>
  )
}
