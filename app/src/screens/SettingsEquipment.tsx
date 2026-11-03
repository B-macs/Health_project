// Settings › Weight steps (WP-46, the owner, 2026-11-03: "I should have settings to change
// the weight increments"; his answer "A": a list of equipment, each with its step, and each
// lift linked to one item). The phone edits the list and sends it whole; the engine checks
// it, stores it and uses it for every step (services/equipment.py). The phone holds no rule.
import { useEffect, useState } from 'react'
import type { components } from '../generated/api'
import { useApp } from '../lib/appState'
import { ApiError, api } from '../lib/api'
import { useCached } from '../lib/cache'
import { S } from '../strings'

type Schemas = components['schemas']
export type EquipmentAnswer = Schemas['EquipmentOut']
type Item = Schemas['EquipmentItem']

export const EQUIPMENT = '/api/settings/equipment'

/** The list as it is being edited: each step as typed, and the links that differ from the
 *  lift's default item. */
export type Draft = { items: (Omit<Item, 'step'> & { step: string })[]; links: Record<string, string> }

export function draftOf(a: EquipmentAnswer): Draft {
  return {
    items: a.items.map((i) => ({ ...i, step: String(i.step) })),
    links: Object.fromEntries(a.exercises
      .filter((e) => e.item_id !== e.default_item_id).map((e) => [e.name, e.item_id])),
  }
}

/** The body the engine takes: every item with its step as a number, and the links. */
export function bodyOf(d: Draft): { items: Omit<Item, 'default'>[]; links: Record<string, string> } {
  return {
    items: d.items.map(({ id, name, step, unit, kind }) => ({ id, name, step: Number(step), unit, kind })),
    links: d.links,
  }
}

function newId(): string {
  const c = globalThis.crypto as Crypto | undefined
  return `custom-${c?.randomUUID ? c.randomUUID() : String(Date.now())}`
}

/** Why a refusal came back, in the engine's own words when it gave them. */
export function refusalWords(err: unknown): string {
  if (!(err instanceof ApiError) || err.kind !== 'rejected') return S.settings.equipmentOffline
  const [, ...why] = err.code.split(': ')
  return S.settings.equipmentRefused(why.join(': ') || err.code)
}

export function EquipmentCard({ answer, busy, error, saved, onSave }: {
  answer: EquipmentAnswer | undefined; busy: boolean; error: string | null; saved: boolean
  onSave: (d: Draft) => void
}) {
  const [draft, setDraft] = useState<Draft | null>(answer ? draftOf(answer) : null)
  useEffect(() => { if (answer) setDraft(draftOf(answer)) }, [answer])
  if (!answer || !draft) return null
  const setItem = (id: string, patch: Partial<Draft['items'][number]>) =>
    setDraft({ ...draft, items: draft.items.map((i) => (i.id === id ? { ...i, ...patch } : i)) })
  const remove = (id: string) => setDraft({
    items: draft.items.filter((i) => i.id !== id),
    links: Object.fromEntries(Object.entries(draft.links).filter(([, v]) => v !== id)),
  })
  const add = () => setDraft({
    ...draft,
    items: [...draft.items, { id: newId(), name: S.settings.equipmentNew, step: '2.5', unit: 'kg', kind: 'machine', default: false }],
  })
  const linkOf = (e: Schemas['EquipmentLift']) => draft.links[e.name] ?? e.default_item_id ?? e.item_id
  const setLink = (e: Schemas['EquipmentLift'], id: string) => {
    const links = { ...draft.links }
    if (id === e.default_item_id) delete links[e.name]
    else links[e.name] = id
    setDraft({ ...draft, links })
  }
  return (
    <section className="card group" aria-labelledby="equipment-title" data-testid="equipment">
      <h2 id="equipment-title" className="eyebrow">{S.settings.equipment}</h2>
      <p className="caption">{S.settings.equipmentWhat}</p>
      {draft.items.map((item) => (
        <div key={item.id} className="group" data-item={item.id}>
          <input className="field" type="text" aria-label={S.settings.equipmentName} value={item.name}
            onChange={(e) => setItem(item.id, { name: e.target.value })} />
          <div className="kv">
            <span className="caption">{S.settings.equipmentStep}</span>
            <input className="field" type="text" inputMode="decimal" aria-label={`${item.name} ${S.settings.equipmentStep}`}
              value={item.step} onChange={(e) => setItem(item.id, { step: e.target.value.replace(',', '.') })} />
            <span className="caption">{S.settings.equipmentUnits[item.unit] ?? item.unit}</span>
          </div>
          {!item.default && (
            <div className="kv">
              <select className="field" aria-label={`${item.name} ${S.settings.equipmentKind}`} value={item.kind}
                onChange={(e) => setItem(item.id, { kind: e.target.value })}>
                {Object.entries(S.settings.equipmentKinds).map(([k, label]) => <option key={k} value={k}>{label}</option>)}
              </select>
              <select className="field" aria-label={`${item.name} ${S.settings.equipmentUnit}`} value={item.unit}
                onChange={(e) => setItem(item.id, { unit: e.target.value })}>
                {Object.entries(S.settings.equipmentUnits).map(([u, label]) => <option key={u} value={u}>{label}</option>)}
              </select>
              <button className="btn btn--glass" onClick={() => remove(item.id)}>{S.settings.equipmentRemove}</button>
            </div>
          )}
        </div>
      ))}
      <button className="btn btn--glass" onClick={add}>{S.settings.equipmentAdd}</button>
      <h3 className="eyebrow">{S.settings.equipmentLifts}</h3>
      {answer.exercises.map((e) => (
        <label key={e.name} className="group" data-lift={e.name}>
          <span className="caption">{e.pair ? `${e.name} (${S.settings.equipmentPair})` : e.name}</span>
          <select className="field" value={linkOf(e)} onChange={(ev) => setLink(e, ev.target.value)}>
            {draft.items.map((i) => <option key={i.id} value={i.id}>{i.name}</option>)}
          </select>
        </label>
      ))}
      {error && <p className="alert" role="alert">{error}</p>}
      {saved && !error && <p className="notice" role="status">{S.settings.equipmentSaved}</p>}
      <button className="btn btn--primary" disabled={busy} onClick={() => onSave(draft)}>{S.settings.equipmentSave}</button>
    </section>
  )
}

export function Equipment() {
  const { store, ctx } = useApp()
  const view = useCached<EquipmentAnswer>(store, EQUIPMENT, null, ctx)
  const [answer, setAnswer] = useState<EquipmentAnswer | undefined>(undefined)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  async function save(d: Draft) {
    setBusy(true)
    setError(null)
    setSaved(false)
    try {
      setAnswer(await api<EquipmentAnswer>(EQUIPMENT, {
        method: 'PUT', key: ctx.key, engineDown: ctx.engineDown, fetchImpl: ctx.fetchImpl, body: bodyOf(d),
      }))
      setSaved(true)
    } catch (err) {
      setError(refusalWords(err))
    } finally {
      setBusy(false)
    }
  }
  return <EquipmentCard answer={answer ?? view.data} busy={busy} error={error} saved={saved} onSave={(d) => void save(d)} />
}
