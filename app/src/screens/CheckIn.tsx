// The morning check-in (slate), as a sheet over Today (rebuild Phase 5; inventory I94-I114).
//
// The form is drawn from the engine's answer (GET /api/checkin?date=): the days a check-in
// can be saved for, the day's stored entry or the defaults, and every control's range and
// options. The phone holds no range of its own. A save goes through the outbox (PUT
// /api/checkin, one row per date: the engine merges or replaces), so it works offline and
// is sent when the engine can take it; the form's saved answer is updated at once, so the
// sheet opens with what was saved even before it is sent.
//
// The owner, 2026-10-21: "When I press check In it should have completing tag and then
// completed viewable to the user at the bottom when I pressed it. Then check in should be
// done, I can press another button to do another check in for the same day otherwise check
// in should be marked as complete." So Save turns into "Saving…" with a turning ring where
// it was pressed, then "Check-in complete" there, then the sheet shows the day as done (what
// was saved, Done, and a button for another check-in, which replaces this one: the store
// keeps one check-in a day). A day the store already holds opens as done.
import { useLiveQuery } from 'dexie-react-hooks'
import { useEffect, useRef, useState } from 'react'
import { PAGE_FAMILY } from '../design/tokens'
import type { components } from '../generated/api'
import { localDay } from '../lib/api'
import { useApp } from '../lib/appState'
import { cacheKey, useCached } from '../lib/cache'
import { enqueue } from '../lib/outbox'
import { S } from '../strings'
import { Freshness } from '../ui/Freshness'
import { IconCheck } from '../ui/icons'
import { Spinner, longDate } from '../ui/parts'
import { Sheet } from '../ui/Sheet'

type Form = components['schemas']['CheckInFormOut']
type Values = components['schemas']['CheckInValues']
type Field = keyof Values

/** Where a check-in saved on this phone stands (its outbox item): being sent (the first
 *  try), waiting (not sent yet: no connection, or the engine down), refused (with the
 *  engine's reason) or done (the engine has it). */
export type Sending = { state: 'sending' } | { state: 'waiting' } | { state: 'refused'; code: string } | { state: 'done' }

/** What the sheet shows: the form; the form with "Saving…" where Save was; the form with
 *  "Check-in complete" there; or the day done. */
export type Stage = 'form' | 'saving' | 'complete' | 'done'

/** How long "Check-in complete" stays where Save was pressed before the day shows as done. */
export const COMPLETE_SHOWN_MS = 1_500

/** The sheet's stage. `pressing`: Save was pressed and the save is being put on the phone
 *  (its id not known yet); `sentId`: this sheet's own save (its outbox id), null before one;
 *  `sending`: that save's state, or with no save of its own, the day's check-in still on
 *  the phone; `existing`: the store holds the day; `editing`: "Do another check-in" was
 *  pressed; `shownComplete`: "Check-in complete" was shown (or skipped, after a wait). */
export function checkinStage(p: {
  pressing?: boolean; sentId: string | null; sending: Sending | null; existing: boolean; editing: boolean
  shownComplete: boolean
}): Stage {
  // First: between queuing the save and knowing its id, the new item is the day's check-in
  // still on the phone, which alone reads as the day done (found by the browser test: the
  // form went and came back, and the sheet jumped to its top).
  if (p.pressing) return 'saving'
  if (p.sentId === null) {
    if (p.editing || p.sending?.state === 'refused') return 'form'
    return p.existing || p.sending !== null ? 'done' : 'form'
  }
  if (p.sending === null || p.sending.state === 'sending') return 'saving'
  if (p.sending.state === 'refused') return 'form'
  if (p.sending.state === 'done' && !p.shownComplete) return 'complete'
  return 'done'
}

/** The check-in save of `sentId`, or with none, the day's newest check-in still on the
 *  phone (a save from an earlier visit not sent yet). */
function useSending(day: string, sentId: string | null): Sending | null {
  const { store } = useApp()
  return useLiveQuery(async (): Promise<Sending | null> => {
    const rows = await store.outbox.toArray()
    const row = sentId
      ? rows.find((r) => r.id === sentId)
      : rows.filter((r) => r.kind === 'checkin' && (r.body as { date?: string } | null)?.date === day).at(-1)
    if (!row) return sentId ? { state: 'done' } : null
    if (row.state === 'failed') return { state: 'refused', code: row.last_error ?? '' }
    return { state: row.attempts > 0 ? 'waiting' : 'sending' }
  }, [store, day, sentId], null)
}

export const formPath = (day: string) => `/api/checkin?date=${day}`

function dayLabel(day: string, today: string, yesterday: string): string {
  if (day === today) return S.checkin.today
  if (day === yesterday) return S.checkin.yesterday
  return longDate(day)
}

function Steps({ field, min, max, step = 1, value, onChange, format }: {
  field: Field
  min: number
  max: number
  step?: number
  value: number
  onChange: (v: number) => void
  format?: (v: number) => string
}) {
  const label = S.checkin.fields[field].label
  return (
    <div className="field-row">
      <span>{label}</span>
      <div className="stepper">
        <button type="button" className="iconbtn" aria-label={S.checkin.less(label)} disabled={value <= min}
          onClick={() => onChange(Math.max(min, Math.round((value - step) * 100) / 100))}>{S.detail.minus}</button>
        <output className="num stepper__value" aria-live="polite">{format ? format(value) : value}</output>
        <button type="button" className="iconbtn" aria-label={S.checkin.more(label)} disabled={value >= max}
          onClick={() => onChange(Math.min(max, Math.round((value + step) * 100) / 100))}>{S.detail.plus}</button>
      </div>
    </div>
  )
}

function Scale({ field, min, max, value, onChange }: { field: Field; min: number; max: number; value: number; onChange: (v: number) => void }) {
  const label = S.checkin.fields[field].label
  return (
    <div className="group">
      <div className="kv"><span>{label}</span><span className="num">{value}</span></div>
      <input type="range" className="slider" min={min} max={max} step={1} value={value} aria-label={label}
        onChange={(e) => onChange(Number(e.target.value))} />
    </div>
  )
}

function Choice({ field, options, value, onChange }: { field: Field; options: readonly (number | string)[]; value: number | string; onChange: (v: never) => void }) {
  const label = S.checkin.fields[field].label
  return (
    <div className="group">
      <span>{label}</span>
      <div className="segmented segmented--wrap" role="radiogroup" aria-label={label}>
        {options.map((option) => (
          <button type="button" key={option} role="radio" aria-checked={option === value}
            className={`segmented__item${option === value ? ' segmented__item--on' : ''}`}
            onClick={() => onChange(option as never)}>
            {typeof option === 'number' && option > 0 && field === 'hunger_deviation' ? `+${option}` : String(option)}
          </button>
        ))}
      </div>
    </div>
  )
}

function Chips({ field, options, value, onChange }: { field: Field; options: readonly string[]; value: readonly string[]; onChange: (v: string[]) => void }) {
  const label = S.checkin.fields[field].label
  return (
    <div className="group">
      <span>{label}</span>
      <div className="chips" role="group" aria-label={label}>
        {options.map((option) => {
          const on = value.includes(option)
          return (
            <button type="button" key={option} aria-pressed={on} className={`chip${on ? ' chip--on' : ''}`}
              onClick={() => onChange(on ? value.filter((v) => v !== option) : [...value, option])}>
              {option}
            </button>
          )
        })}
      </div>
    </div>
  )
}

function Switch({ field, value, onChange }: { field: Field; value: boolean; onChange: (v: boolean) => void }) {
  const label = S.checkin.fields[field].label
  return (
    <label className="field-row">
      <span>{label}</span>
      <input type="checkbox" role="switch" className="switch" checked={value} onChange={(e) => onChange(e.target.checked)} />
    </label>
  )
}

function Guide({ title, intro, rows }: { title: string; intro: string; rows: readonly (readonly [string, string, string])[] }) {
  return (
    <details className="guide">
      <summary className="tapline">{title}</summary>
      <p className="caption">{intro}</p>
      {rows.map(([range, name, text]) => (
        <p key={range} className="caption"><strong>{`${range} · ${name}`}</strong>{` ${text}`}</p>
      ))}
    </details>
  )
}

export function CheckInForm({ form, stage = 'form', refused = null, onSaving, onSaved }: {
  form: Form
  stage?: Stage
  refused?: string | null
  onSaving?: () => void
  onSaved: (id: string, values: Values) => void
}) {
  const { store } = useApp()
  const [values, setValues] = useState<Values>(form.values)
  const [touched, setTouched] = useState(false)
  const [pressed, setPressed] = useState(false)
  // A newer answer refills the form, unless the owner has already changed something.
  useEffect(() => {
    if (!touched) setValues(form.values)
  }, [form, touched])
  const set = <K extends Field>(field: K) => (value: Values[K]) => {
    setTouched(true)
    setValues((v) => ({ ...v, [field]: value }))
  }
  const whole = Object.fromEntries(form.whole.map((r) => [r.field, r]))
  const decimal = Object.fromEntries(form.decimal.map((r) => [r.field, r]))
  const range = (field: Field) => {
    const r = whole[field]
    return Array.from({ length: r.max - r.min + 1 }, (_, i) => r.min + i)
  }
  const busy = pressed || stage === 'saving' || stage === 'complete'
  const save = async () => {
    if (busy) return
    setPressed(true)
    onSaving?.()
    const day = String(form.date)
    const id = await enqueue(store, { kind: 'checkin', method: 'PUT', path: '/api/checkin', body: { date: day, opened_entry: form.existing, values }, day: localDay() })
    // The sheet opens with what was saved, even before the engine has it.
    const path = formPath(day)
    await store.cache.put({ key: cacheKey(path, null), path, day: null, body: { ...form, values, existing: true }, fetched_at: new Date().toISOString() })
    onSaved(id, values)
    setPressed(false)
  }
  const d = decimal
  return (
    <form className="checkin" onSubmit={(e) => { e.preventDefault(); void save() }}>
      {form.existing && <p className="caption" role="note">{S.checkin.existing}</p>}
      {form.read_failed && <p className="caption" role="note">{S.checkin.readFailed}</p>}

      <fieldset className="checkin__fields" disabled={busy}>
        <h3 className="eyebrow">{S.checkin.tissue}</h3>
        <Scale field="tightness_score" min={whole.tightness_score.min} max={whole.tightness_score.max} value={values.tightness_score} onChange={set('tightness_score')} />
        <Scale field="pain_score" min={whole.pain_score.min} max={whole.pain_score.max} value={values.pain_score} onChange={set('pain_score')} />
        <Choice field="current_condition" options={form.conditions} value={values.current_condition} onChange={set('current_condition') as (v: never) => void} />
        <Guide title={S.checkin.tightnessGuide.title} intro={S.checkin.tightnessGuide.intro} rows={S.checkin.tightnessGuide.rows} />
        <Guide title={S.checkin.painGuide.title} intro={S.checkin.painGuide.intro} rows={S.checkin.painGuide.rows} />

        <h3 className="eyebrow">{S.checkin.where}</h3>
        <Chips field="anatomical_locations" options={form.locations} value={values.anatomical_locations} onChange={set('anatomical_locations')} />
        <Chips field="sensation_tags" options={form.tags} value={values.sensation_tags} onChange={set('sensation_tags')} />
        <label className="group">
          <span>{S.checkin.fields.subjective_tightness.label}</span>
          <input className="field" type="text" value={values.subjective_tightness} placeholder={S.checkin.notePlaceholder}
            onChange={(e) => set('subjective_tightness')(e.target.value)} />
        </label>

        <h3 className="eyebrow">{S.checkin.lifestyle}</h3>
        <Choice field="psych_stress_score" options={range('psych_stress_score')} value={values.psych_stress_score} onChange={set('psych_stress_score') as (v: never) => void} />
        <Steps field="alcohol_units" min={d.alcohol_units.min} max={d.alcohol_units.max} step={d.alcohol_units.step} value={values.alcohol_units} onChange={set('alcohol_units')} />
        <Switch field="travel_flag" value={values.travel_flag} onChange={set('travel_flag')} />

        <h3 className="eyebrow">{S.checkin.jointGut}</h3>
        <Steps field="instability_events" min={whole.instability_events.min} max={whole.instability_events.max} value={values.instability_events} onChange={set('instability_events')} />
        <Choice field="bristol_type" options={range('bristol_type')} value={values.bristol_type} onChange={set('bristol_type') as (v: never) => void} />
        <Switch field="unusual_stool_colour" value={values.unusual_stool_colour} onChange={set('unusual_stool_colour')} />

        <h3 className="eyebrow">{S.checkin.body}</h3>
        <Choice field="hunger_deviation" options={range('hunger_deviation')} value={values.hunger_deviation} onChange={set('hunger_deviation') as (v: never) => void} />
        <Choice field="thirst_intensity" options={range('thirst_intensity')} value={values.thirst_intensity} onChange={set('thirst_intensity') as (v: never) => void} />
        <Switch field="electrolytes_taken" value={values.electrolytes_taken} onChange={set('electrolytes_taken')} />

        <h3 className="eyebrow">{S.checkin.meditation}</h3>
        <Steps field="meditation_minutes" min={d.meditation_minutes.min} max={d.meditation_minutes.max} step={d.meditation_minutes.step} value={values.meditation_minutes} onChange={set('meditation_minutes')} />
        <Choice field="relaxation_depth" options={range('relaxation_depth')} value={values.relaxation_depth} onChange={set('relaxation_depth') as (v: never) => void} />
      </fieldset>

      {refused !== null && <p className="alert" role="alert" data-testid="checkin-refused">{S.checkin.refused(refused)}</p>}
      {stage === 'complete' ? (
        <p className="donemark" role="status" data-testid="checkin-complete"><IconCheck />{S.checkin.complete}</p>
      ) : (
        <button type="submit" className="btn btn--primary btn--wide" disabled={busy} aria-busy={busy} data-testid="checkin-save">
          {busy ? <><Spinner />{S.checkin.saving}</> : S.checkin.save}
        </button>
      )}
    </form>
  )
}

/** The day done: what was saved, Done, and a button for another check-in (which replaces
 *  this one). `waiting`: saved on this phone and not sent yet. */
function CheckInDone({ values, waiting, onAgain, onFinish }: {
  values: Values; waiting: boolean; onAgain: () => void; onFinish: () => void
}) {
  const top = useRef<HTMLElement>(null)
  // The long form was here a moment ago: the done card is brought into view.
  useEffect(() => {
    top.current?.scrollIntoView?.({ block: 'nearest' })
  }, [])
  return (
    <section ref={top} className="card group" data-testid="checkin-done">
      {waiting
        ? <p className="note" role="status">{S.checkin.saved}</p>
        : <p className="donemark" role="status"><IconCheck />{S.checkin.complete}</p>}
      <div className="kv"><span>{S.checkin.fields.tightness_score.label}</span><span className="num">{values.tightness_score}</span></div>
      <div className="kv"><span>{S.checkin.fields.pain_score.label}</span><span className="num">{values.pain_score}</span></div>
      <div className="kv"><span>{S.checkin.fields.current_condition.label}</span><span>{values.current_condition}</span></div>
      <button type="button" className="btn btn--primary btn--wide" onClick={onFinish}>{S.checkin.finish}</button>
      <button type="button" className="btn btn--glass btn--wide" data-testid="checkin-again" onClick={onAgain}>{S.checkin.again}</button>
      <p className="caption">{S.checkin.againNote}</p>
    </section>
  )
}

export function CheckIn({ onClose }: { onClose: () => void }) {
  const { store, ctx } = useApp()
  const today = localDay()
  const [day, setDay] = useState(today)
  const [editing, setEditing] = useState(false)
  const [sentId, setSentId] = useState<string | null>(null)
  const [savedValues, setSavedValues] = useState<Values | null>(null)
  const [shownComplete, setShownComplete] = useState(false)
  const [pressing, setPressing] = useState(false)
  const view = useCached<Form>(store, formPath(day), null, ctx)
  const sending = useSending(day, sentId)
  const form = view.data
  const stage = checkinStage({ pressing, sentId, sending, existing: !!form?.existing, editing, shownComplete })
  const again = view.again
  // A save that had to wait for the connection skips "Check-in complete" at the bottom: the
  // sheet already shows the day as done, and it says "complete" when the engine has it.
  const waited = sentId !== null && sending?.state === 'waiting'
  useEffect(() => {
    if (waited) setShownComplete(true)
  }, [waited])
  // The engine has it: "Check-in complete" stays where Save was for a moment, then the day
  // shows as done, and the form is read again (what the store now holds).
  const confirmed = sentId !== null && sending?.state === 'done'
  useEffect(() => {
    if (!confirmed) return
    if (shownComplete) {
      again()
      return
    }
    const timer = setTimeout(() => {
      setShownComplete(true)
      again()
    }, COMPLETE_SHOWN_MS)
    return () => clearTimeout(timer)
    // only when the engine's yes arrives
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [confirmed])
  const pick = (iso: string) => {
    setDay(iso)
    setPressing(false)
    setEditing(false)
    setSentId(null)
    setSavedValues(null)
    setShownComplete(false)
  }
  const yesterday = form?.options[1] ? String(form.options[1]) : ''
  const values = savedValues ?? form?.values
  const waiting = sending !== null && (sending.state === 'waiting' || (sentId === null && sending.state === 'sending'))
  return (
    <div className={`fam-${PAGE_FAMILY.checkin}`}>
      <Sheet title={S.checkin.title} closeLabel={S.checkin.close} onClose={onClose} contained>
        {form && (
          <div className="segmented segmented--wrap" role="radiogroup" aria-label={S.checkin.date}>
            {form.options.map((option) => {
              const iso = String(option)
              return (
                <button type="button" key={iso} role="radio" aria-checked={iso === day}
                  className={`segmented__item${iso === day ? ' segmented__item--on' : ''}`}
                  onClick={() => pick(iso)}>
                  {dayLabel(iso, today, yesterday)}
                </button>
              )
            })}
          </div>
        )}
        <Freshness view={view} />
        {form && values && stage === 'done' && (
          <CheckInDone values={values} waiting={waiting} onFinish={onClose}
            onAgain={() => {
              setEditing(true)
              setSentId(null)
              setShownComplete(false)
            }} />
        )}
        {form && stage !== 'done' && (
          // The form is left as it is while it saves: a note added at its top would push
          // "Check-in complete" out of view (found by the browser test). Another check-in
          // opens with what was saved.
          <CheckInForm key={`${day}-${editing}`} form={editing && savedValues ? { ...form, values: savedValues, existing: true } : form}
            stage={stage} refused={sending?.state === 'refused' ? sending.code : null}
            onSaving={() => setPressing(true)}
            onSaved={(id, saved) => {
              setSavedValues(saved)
              setShownComplete(false)
              setSentId(id)
              setPressing(false)
            }} />
        )}
      </Sheet>
    </div>
  )
}
