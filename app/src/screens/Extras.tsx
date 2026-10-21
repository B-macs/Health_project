// The "+" menu on the Training tab (rebuild Phase 7, inventory T103-T112): yoga, an outdoor
// activity from Garmin, and the accessory session. The menu is drawn only on the week page,
// never while a session runs (inventory fault F18: the old page let yoga and the outdoor
// import open mid-session).
//
// - Yoga (T109, T110): the flows with their form notes at the stored stage (advisory:
//   nothing here blocks a flow); Complete sends one save with the ids minted once, and the
//   engine writes a flow once a day however often it is sent.
// - Outdoor (T111, T112): a day's Garmin activities, the hike, walk and trail-run family
//   first (the engine's order); the owner's rating sets the load (the engine's figure for
//   each rating); the activity id is the duplicate key, so it is logged once.
// - Accessory (T104-T108): the short second session the engine chooses from the strain by
//   body area. It runs in the same guided flow as the plan session and saves as its own
//   kind, so it never marks a plan day as done.
import { useLiveQuery } from 'dexie-react-hooks'
import { useRef, useState } from 'react'
import type { components } from '../generated/api'
import { ApiError, api, localDay } from '../lib/api'
import { useApp } from '../lib/appState'
import { useCached } from '../lib/cache'
import { answerOf, enqueue } from '../lib/outbox'
import { startSession } from '../lib/session'
import { newExerciseIds, newSessionId, startSessionState, type Plan } from '../lib/training'
import { S } from '../strings'
import { Freshness } from '../ui/Freshness'
import { IconBack, IconForward } from '../ui/icons'
import { longDate } from '../ui/parts'
import { Sheet } from '../ui/Sheet'
import { Timeline } from '../ui/timeline'

type Schemas = components['schemas']
type Catalogue = Schemas['YogaCatalogueOut']
type Flow = Schemas['YogaFlow']
type Activity = Schemas['OutdoorActivity']

/** The menu (T103). */
export function ExtrasMenu({ onClose }: { onClose: () => void }) {
  const { go } = useApp()
  return (
    <Sheet title={S.extras.title} closeLabel={S.extras.close} onClose={onClose}>
      <div className="group" data-testid="extras-menu">
        <button className="btn btn--glass btn--wide" onClick={() => go('/training/yoga')}>{S.extras.yoga}</button>
        <button className="btn btn--glass btn--wide" onClick={() => go('/training/outdoor')}>{S.extras.outdoor}</button>
        <button className="btn btn--glass btn--wide" onClick={() => go('/training/accessory')}>{S.extras.accessory}</button>
      </div>
    </Sheet>
  )
}

/** The back link (to the page the screen opened from) and the title. */
function Head({ title, back, onBack, caption }: { title: string; back: string; onBack: () => void; caption?: string }) {
  return (
    <>
      <header className="topbar">
        <button className="backlink" aria-label={S.extras.back} onClick={onBack}>
          <IconBack />
          <span>{back}</span>
        </button>
        <span />
        <span />
      </header>
      <header className="head">
        <h1 className="head__title">{title}</h1>
        {caption && <div className="caption">{caption}</div>}
      </header>
    </>
  )
}

/** What a save sent through the outbox has come to: waiting, refused, or the engine's
 *  answer (kept by the outbox for the screen, lib/outbox.ts answerOf). */
type Sent = { state: 'waiting' | 'refused' } | { state: 'answered'; answer: unknown }

function useSent(id: string | null): Sent | null {
  const { store } = useApp()
  return useLiveQuery(async () => {
    if (!id) return null
    const row = await store.outbox.where('id').equals(id).first()
    if (row) return { state: row.state === 'failed' ? 'refused' : 'waiting' } as Sent
    return { state: 'answered', answer: answerOf(id) } as Sent
  }, [store, id], null)
}

// ── Yoga ─────────────────────────────────────────────────────────────────────

const YOGA = '/api/training/yoga'

/** One flow to pick, as a row: its whole name (wrapped, never cut at the screen's edge;
 *  the owner, 2026-10-21: "all the text should be on the page") and its minutes. */
export function FlowChoice({ name, minutes, onPick }: { name: string; minutes: number; onPick: () => void }) {
  return (
    <button type="button" className="choice" onClick={onPick}>
      <span className="choice__text">
        <span className="choice__title">{name}</span>
        <span className="caption">{S.extras.minutes(minutes)}</span>
      </span>
      <IconForward />
    </button>
  )
}

/** The flows (T109). */
export function YogaList() {
  const { store, ctx, go } = useApp()
  const view = useCached<Catalogue>(store, YOGA, null, ctx)
  const flows = view.data?.flows ?? []
  return (
    <div className="screen train" data-testid="yoga-list">
      <div className="sky" aria-hidden="true" />
      <Head title={S.extras.yogaTitle} back={S.nav.training} onBack={() => go('/training')} />
      <Freshness view={view} />
      {view.data && flows.length === 0 && <p className="caption">{S.extras.yogaNone}</p>}
      {!view.data && view.state !== 'loading' && <p className="caption">{S.extras.yogaNeedsEngine}</p>}
      <div className="group">
        {flows.map((f) => (
          <FlowChoice key={f.slug} name={f.name} minutes={f.minutes} onPick={() => go(`/training/yoga/${f.slug}`)} />
        ))}
      </div>
    </div>
  )
}

/** One flow (T110): the video, the form notes, the routine, a note and Complete. */
export function YogaDetail({ slug }: { slug: string }) {
  const { store, ctx, go } = useApp()
  const view = useCached<Catalogue>(store, YOGA, null, ctx)
  const flow: Flow | undefined = view.data?.flows.find((f) => f.slug === slug)
  const [note, setNote] = useState('')
  const [sentId, setSentId] = useState<string | null>(null)
  const sending = useRef(false)
  const sent = useSent(sentId)
  if (!flow) {
    return (
      <div className="screen train">
        <div className="sky" aria-hidden="true" />
        <Head title={S.extras.yogaTitle} back={S.extras.yoga} onBack={() => go('/training/yoga')} />
        <Freshness view={view} />
        {view.state !== 'loading' && <p className="caption">{S.extras.yogaNeedsEngine}</p>}
      </div>
    )
  }
  const complete = async () => {
    if (sending.current) return
    sending.current = true
    const day = localDay()
    const id = await enqueue(store, { kind: 'yoga', method: 'POST', path: YOGA, day, body: {
      slug: flow.slug, session_id: newSessionId(day), pose_ids: newExerciseIds(flow.poses.length), note,
    } })
    setSentId(id)
  }
  const logged = sent?.state === 'answered' ? (sent.answer as { logged?: boolean } | undefined)?.logged : undefined
  return (
    <div className="screen train" data-testid="yoga-detail">
      <div className="sky" aria-hidden="true" />
      <Head title={flow.name} back={S.extras.yoga} onBack={() => go('/training/yoga')} caption={S.extras.yogaMeta(flow.minutes, flow.rpe)} />
      {/* An external video, opened in its own app: not a move inside this app (Key Rule 17). */}
      <a className="btn btn--glass btn--wide" href={flow.video_url} target="_blank" rel="noopener noreferrer">{S.extras.watch}</a>
      {flow.cautions.length > 0 && (
        <section className="card group" data-testid="yoga-cautions">
          <h3 className="eyebrow">{S.extras.formNotes}</h3>
          {!view.data?.stage_read && <p className="caption">{S.extras.stageUnread}</p>}
          {flow.cautions.map((c) => (
            <div key={c.pose} className="group" data-severity={c.severity}>
              <strong>{c.pose}</strong>
              <span className="caption">{c.note}</span>
            </div>
          ))}
        </section>
      )}
      <details className="card guide">
        <summary className="tapline">{S.extras.routine(flow.poses.length)}</summary>
        <ul className="list">
          {flow.poses.map((p, i) => (
            <li key={`${p.name}-${i}`} className="kv"><span>{p.name}</span><span className="caption">{S.extras.poseHold(p.hold_seconds ?? null)}</span></li>
          ))}
        </ul>
      </details>
      {!sentId ? (
        <>
          <label className="group">
            <span className="caption">{S.extras.yogaNote}</span>
            <textarea className="field field--area" placeholder={S.extras.yogaNoteHint} value={note}
              onChange={(e) => setNote(e.target.value)} />
          </label>
          <button className="btn btn--primary btn--wide" onClick={() => void complete()}>{S.extras.complete}</button>
        </>
      ) : (
        <section className="card group" role="status" data-testid="yoga-state" data-state={sent?.state ?? 'waiting'}>
          <p>
            {sent?.state === 'refused' ? S.session.refused
              : sent?.state === 'answered' ? (logged === false ? S.extras.yogaAlready(flow.name) : S.extras.yogaLogged(flow.name))
                : S.session.savedPhone}
          </p>
          <button className="btn btn--primary btn--wide" onClick={() => go('/training')}>{S.extras.done}</button>
        </section>
      )}
    </div>
  )
}

// ── Outdoor ──────────────────────────────────────────────────────────────────

const OUTDOOR = '/api/training/outdoor'
type Search = { state: 'idle' } | { state: 'searching' } | { state: 'found'; date: string; activities: Activity[] }
  | { state: 'failed'; why: string }

/** A day's Garmin activities (T111), then the one picked, rated and logged (T112). */
export function Outdoor() {
  const { store, ctx, go } = useApp()
  const today = localDay()
  const [day, setDay] = useState(today)
  const [search, setSearch] = useState<Search>({ state: 'idle' })
  const [picked, setPicked] = useState(0)
  const [rpe, setRpe] = useState(3)
  const [sentId, setSentId] = useState<string | null>(null)
  const sending = useRef(false)
  const sent = useSent(sentId)
  const find = async () => {
    setSearch({ state: 'searching' })
    try {
      const out = await api<Schemas['OutdoorListOut']>(`${OUTDOOR}?date=${day}`, {
        key: ctx.key, engineDown: ctx.engineDown, timeoutMs: 45_000,
      })
      setPicked(0)
      setSearch({ state: 'found', date: day, activities: out.activities })
    } catch (err) {
      const e = err instanceof ApiError ? err : null
      setSearch({ state: 'failed', why: e?.code === 'sync_running' ? S.extras.outdoorBusy
        : e?.kind === 'offline' || e?.kind === 'engine_unavailable' ? S.extras.outdoorOffline : S.extras.outdoorFailed })
    }
  }
  const act = search.state === 'found' ? search.activities[picked] : undefined
  const log = async () => {
    if (!act || search.state !== 'found' || sending.current) return
    sending.current = true
    const id = await enqueue(store, { kind: 'outdoor', method: 'POST', path: OUTDOOR, body: {
      date: search.date, activity_id: act.activity_id, rpe,
      session_id: newSessionId(search.date), exercise_id: newExerciseIds(1)[0],
    } })
    setSentId(id)
  }
  const answer = sent?.state === 'answered' ? (sent.answer as Schemas['OutdoorLogOut'] | undefined) : undefined
  return (
    <div className="screen train" data-testid="outdoor">
      <div className="sky" aria-hidden="true" />
      <Head title={S.extras.outdoorTitle} back={S.nav.training} onBack={() => go('/training')} />
      {!sentId && (
        <section className="card group">
          <label className="group">
            <span className="caption">{S.extras.outdoorDay}</span>
            <input type="date" className="field" value={day} max={today}
              onChange={(e) => { setDay(e.target.value || today); setSearch({ state: 'idle' }) }} />
          </label>
          <button className="btn btn--primary btn--wide" disabled={search.state === 'searching'} onClick={() => void find()}>
            {search.state === 'searching' ? S.extras.searching : S.extras.search}
          </button>
        </section>
      )}
      {!sentId && search.state === 'idle' && <p className="caption">{S.extras.outdoorHelp}</p>}
      {!sentId && search.state === 'failed' && <p className="alert" role="status">{search.why}</p>}
      {!sentId && search.state === 'found' && search.activities.length === 0 && (
        <p className="caption" role="status">{S.extras.outdoorNone(longDate(search.date))}</p>
      )}
      {!sentId && search.state === 'found' && act && (
        <>
          <section className="card group" role="radiogroup" aria-label={S.extras.outdoorTitle}>
            {search.activities.map((a, i) => (
              <button key={a.activity_id} role="radio" aria-checked={i === picked}
                className={`chip${i === picked ? ' chip--on' : ''}`} onClick={() => setPicked(i)}>
                {S.extras.activity(a.name, a.type, a.duration_minutes ?? null, a.distance_km ?? null, a.avg_hr ?? null)}
              </button>
            ))}
          </section>
          {!act.in_family && <p className="note" data-testid="not-family">{S.extras.notFamily(act.type, act.logs_as)}</p>}
          <section className="card group">
            <label className="group">
              <span className="kv"><span>{S.extras.outdoorEffort}</span><span className="num">{S.session.effortValue(rpe)}</span></span>
              <input type="range" className="slider" min={1} max={10} step={1} value={rpe} aria-label={S.extras.outdoorEffort}
                onChange={(e) => setRpe(Number(e.target.value))} />
            </label>
            <p className="caption">{S.extras.outdoorEffortHelp}</p>
          </section>
          <p className="caption" data-testid="outdoor-preview">
            {S.extras.outdoorPreview(act.logs_as, longDate(search.date), act.minutes, rpe, act.au_by_rpe[rpe - 1] ?? 0)}
          </p>
          <button className="btn btn--primary btn--wide" onClick={() => void log()}>{S.extras.logTo(act.logs_as)}</button>
        </>
      )}
      {sentId && act && search.state === 'found' && (
        <section className="card group" role="status" data-testid="outdoor-state" data-state={sent?.state ?? 'waiting'}>
          <p>
            {sent?.state === 'refused' ? S.session.refused
              : answer ? (answer.logged ? S.extras.outdoorLogged(answer.logs_as, longDate(search.date), answer.au)
                : S.extras.outdoorAlready(answer.logs_as, longDate(search.date)))
                : S.session.savedPhone}
          </p>
          <button className="btn btn--primary btn--wide" onClick={() => go('/training')}>{S.extras.done}</button>
        </section>
      )}
    </div>
  )
}

// ── The accessory session ────────────────────────────────────────────────────

/** The accessory session before Start (T105, T106): what the engine chose and why. Start
 *  hands it to the same guided flow as the plan session (T107); its save is T108. */
export function AccessoryOverview() {
  const { store, ctx, go } = useApp()
  const view = useCached<Plan>(store, '/api/training/accessory', null, ctx)
  const busy = useLiveQuery(async () => (await store.session.get('current')) !== undefined, [store], false)
  const [starting, setStarting] = useState(false)
  const today = localDay()
  const plan = view.data && view.data.date === today && view.data.kind === 'accessory' ? view.data : null
  const start = async () => {
    if (!plan || starting) return
    setStarting(true)
    try {
      // One session at a time: a plan session already kept on this phone is never replaced.
      if (await store.session.get('current')) return
      await startSession(store, startSessionState(plan, newSessionId(plan.date), newExerciseIds(plan.exercises.length)))
      go('/training')
    } finally {
      setStarting(false)
    }
  }
  return (
    <div className="screen train" data-testid="accessory">
      <div className="sky" aria-hidden="true" />
      <Head title={plan?.objective || S.extras.accessory} back={S.nav.training} onBack={() => go('/training')}
        caption={plan ? S.extras.accessoryMeta(plan.phase, plan.rpe_target ?? null) : undefined} />
      <Freshness view={view} />
      {busy && <p className="alert" data-testid="accessory-blocked">{S.extras.blocked}</p>}
      {!plan ? (
        view.state !== 'loading' && <p className="caption">{S.extras.accessoryNeedsEngine}</p>
      ) : (
        <>
          <p className="caption">{S.extras.accessoryItems(plan.exercises.length, plan.model_minutes)}</p>
          <Timeline title={S.session.workout} items={plan.exercises.map((e) => ({
            name: e.name, type: e.type, icon: e.icon, prescription: e.prescription, laterality: e.laterality ?? null, mechanics: e.mechanics,
          }))} />
          {plan.reasons.length > 0 && (
            <details className="card guide" data-testid="accessory-why">
              <summary className="tapline">{S.extras.why}</summary>
              <ul className="list">{plan.reasons.map((r) => <li key={r} className="caption">{r}</li>)}</ul>
            </details>
          )}
          <div className="pair">
            <button className="btn btn--glass btn--gym" onClick={() => go('/training')}>{S.extras.cancel}</button>
            <button className="btn btn--primary btn--gym" disabled={busy || starting} onClick={() => void start()}>{S.extras.start}</button>
          </div>
        </>
      )}
    </div>
  )
}
