// The morning check-in (slate), as a sheet over Today (rebuild Phase 5; inventory I94-I114).
//
// The form is drawn from the engine's answer (GET /api/checkin?date=): the days a check-in
// can be saved for, the day's stored entry or the defaults, and every control's range and
// options. The phone holds no range of its own. A save goes through the outbox (PUT
// /api/checkin, one row per date: the engine merges or replaces), so it works offline and
// is sent when the engine can take it; the form's saved answer is updated at once, so the
// sheet opens with what was saved even before it is sent.
import { useEffect, useState } from 'react'
import { PAGE_FAMILY } from '../design/tokens'
import type { components } from '../generated/api'
import { localDay } from '../lib/api'
import { useApp } from '../lib/appState'
import { cacheKey, useCached } from '../lib/cache'
import { enqueue } from '../lib/outbox'
import { S } from '../strings'
import { Freshness } from '../ui/Freshness'
import { longDate } from '../ui/parts'
import { Sheet } from '../ui/Sheet'

type Form = components['schemas']['CheckInFormOut']
type Values = components['schemas']['CheckInValues']
type Field = keyof Values

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

export function CheckInForm({ form, onSaved }: { form: Form; onSaved: () => void }) {
  const { store } = useApp()
  const [values, setValues] = useState<Values>(form.values)
  const [touched, setTouched] = useState(false)
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
  const save = async () => {
    const day = String(form.date)
    await enqueue(store, { kind: 'checkin', method: 'PUT', path: '/api/checkin', body: { date: day, opened_entry: form.existing, values }, day: localDay() })
    // The sheet opens with what was saved, even before the engine has it.
    const path = formPath(day)
    await store.cache.put({ key: cacheKey(path, null), path, day: null, body: { ...form, values, existing: true }, fetched_at: new Date().toISOString() })
    onSaved()
  }
  const d = decimal
  return (
    <form className="checkin" onSubmit={(e) => { e.preventDefault(); void save() }}>
      {form.existing && <p className="caption" role="note">{S.checkin.existing}</p>}
      {form.read_failed && <p className="caption" role="note">{S.checkin.readFailed}</p>}

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

      <button type="submit" className="btn btn--primary btn--wide">{S.checkin.save}</button>
    </form>
  )
}

export function CheckIn({ onClose }: { onClose: () => void }) {
  const { store, ctx } = useApp()
  const today = localDay()
  const [day, setDay] = useState(today)
  const [saved, setSaved] = useState(false)
  const view = useCached<Form>(store, formPath(day), null, ctx)
  const form = view.data
  const yesterday = form?.options[1] ? String(form.options[1]) : ''
  return (
    <div className={`fam-${PAGE_FAMILY.checkin}`}>
      <Sheet title={S.checkin.title} closeLabel={S.checkin.close} onClose={onClose}>
        {form && (
          <div className="segmented segmented--wrap" role="radiogroup" aria-label={S.checkin.date}>
            {form.options.map((option) => {
              const iso = String(option)
              return (
                <button type="button" key={iso} role="radio" aria-checked={iso === day}
                  className={`segmented__item${iso === day ? ' segmented__item--on' : ''}`}
                  onClick={() => { setDay(iso); setSaved(false) }}>
                  {dayLabel(iso, today, yesterday)}
                </button>
              )
            })}
          </div>
        )}
        {saved && <p className="caption" role="status">{S.checkin.saved}</p>}
        <Freshness view={view} />
        {form && <CheckInForm key={day} form={form} onSaved={() => setSaved(true)} />}
      </Sheet>
    </div>
  )
}
