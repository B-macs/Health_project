// Development and the browser tests only (`vite --mode mock`, `vite preview --mode mock`):
// the engine's API answered locally, so the shell can be tested without Cloudflare or
// Cloud Run. The access key is "dev". It is never part of a build.
// - a cookie `e2e_engine=down` makes every /api answer the Worker's "engine unavailable";
// - GET /api/dev/received lists the writes the mock received (the outbox tests);
// - a saved session is stored by its session id, as the engine stores it (rebuild rule 4),
//   and GET /api/dev/sessions lists what is stored; a cookie `e2e_lose_answer=1` stores a
//   save and then answers "engine unavailable", as when the answer is lost on the way
//   back, so the phone sends it again;
// - GET /api/training/session answers the engine-made session (dev/session_fixture.json)
//   on the caller's day, and POST /api/training/completion made-up loads;
// - the watch: GET .../garmin/open-activity finds a made-up workout (a cookie
//   `e2e_watch=missing` finds none), GET .../garmin/activity-minutes gives a walk 31 min,
//   and POST /api/training/heart-rate answers a made-up match (`e2e_hr=choose` asks which
//   activity, `e2e_hr=none` finds no match);
// - the timer alerts: GET /api/push/key answers "not set up" (a test browser has no push
//   service); a PUT or DELETE of /api/push/alert is received like any write;
// - the data check answers as the Worker does: GET .../last (null until a check ran) and
//   POST .../run (a made-up clean result);
// - Today, its week, the day's plan, the three detail screens and the check-in answer
//   made-up numbers (dev/fixtures.ts); a saved check-in is kept for the next read, apart for
//   each `e2e_run` cookie (a day saved by one test never opens another test's sheet as done).
// - the training week (Phase 7): GET /api/training/week and /day answer a made-up block
//   (dev/fixtures.ts); a cookie `e2e_week` names what a test asks for, joined by dots
//   (carry, carry_in_order, shift, redo, gate1, retest, gap, unreadable, rest_today,
//   blocked, refuse, garmin_busy, accessory_yesterday), and a cookie `e2e_run` keeps one
//   test's answers apart from the others' (GET /api/dev/week-run shows them). A move is
//   applied once per id, as the engine applies it; `e2e_lose_answer=1` applies it and then
//   answers "engine unavailable", so the phone sends it again;
// - the "+" menu: the accessory session (the engine-made session as its own kind), one
//   yoga flow, and two Garmin activities; a yoga flow or an activity is logged once (the
//   same save sent again answers as it did, another save is told it is already logged).
// - Insights (Phase 8): the engine's own answers over made-up data (dev/insights_fixture.json,
//   made by scripts/make_insights_fixture.py): Strength for each series (`e2e_week` with
//   no_reference: the engine's refusal before the reference is stored), Metabolism for each
//   measure and period (the nearest answer), Flexibility empty, capturing or finished per run
//   (the capture walks the engine's own answers step by step, then its early stop), Engine data,
//   the warnings calendar, Trends (trends_closed: before the data gate opens), Sleep
//   architecture (sleep_empty: no fused night), the data tables, the session checks, Settings.
import type { IncomingMessage, ServerResponse } from 'node:http'
import type { Plugin } from 'vite'
import * as fx from './fixtures.ts'
import sessionFixture from './session_fixture.json' with { type: 'json' }
import insightsFixture from './insights_fixture.json' with { type: 'json' }

const KEY = 'dev'
const received: { method: string; path: string; body: unknown; day: string | null }[] = []
// Sessions saved through the mock, by session id: a save sent again replaces itself.
const sessions = new Map<string, { session_id: string; notes: string; exercises: unknown[] }>()
// Check-ins saved through the mock, by date.
// Each week test's answers, by its `e2e_run` cookie.
const runs = new Map<string, fx.WeekRun>()
const runOf = (req: IncomingMessage) => {
  const tag = cookie(req, 'e2e_run') ?? 'default'
  if (!runs.has(tag)) runs.set(tag, fx.newRun())
  return runs.get(tag)!
}
const scenarioOf = (req: IncomingMessage) => new Set((cookie(req, 'e2e_week') ?? '').split('.').filter(Boolean))
const SCHEDULE = new Set(['/api/training/swap', '/api/training/carry', '/api/training/shift', '/api/training/redo',
  '/api/training/gate1/reason', '/api/training/gate1/flare'])

/** A schedule answer, as the engine answers it: applied once per id; refused when there is
 *  nothing to move (or when the test asks for a refusal). */
function answerSchedule(path: string, body: Record<string, unknown> | null, run: fx.WeekRun,
  scenario: Set<string>): [number, unknown] {
  const id = typeof body?.action_id === 'string' ? body.action_id : null
  if (id && run.applied.includes(id)) return [200, { stored: true }]
  const apply = (): [number, unknown] => {
    if (id) run.applied.push(id)
    return [200, { stored: true }]
  }
  if (path === '/api/training/swap') {
    if (scenario.has('refuse')) return [409, { error: 'refused: made-up: the day would land in the next week' }]
    run.swaps.push(String(body?.date))
    return apply()
  }
  if (path === '/api/training/carry') {
    if (run.carry || !(scenario.has('carry') || scenario.has('carry_in_order'))) return [409, { error: 'nothing_to_carry' }]
    run.carry = true
    return apply()
  }
  if (path === '/api/training/shift') {
    if (run.shift || !scenario.has('shift')) return [409, { error: 'nothing_to_shift' }]
    run.shift = true
    return apply()
  }
  if (path === '/api/training/redo') {
    if (run.redo || !scenario.has('redo')) return [409, { error: 'not_repeated: already set to run again' }]
    run.redo = true
    return apply()
  }
  if (path === '/api/training/gate1/reason') {
    run.reasons[String(body?.monday)] = String(body?.reason)
    return [200, { stored: true }]
  }
  run.flare = true
  return [200, { stored: true }]
}

const insights = insightsFixture as unknown as {
  strength: Record<string, unknown>; metabolism: Record<string, unknown>
  flexibility_empty: unknown; flexibility_capturing: Record<string, unknown>; flexibility_populated: unknown
  capture: { states: unknown[] }; engine: unknown; queue: unknown; warnings: unknown; trends: unknown; trends_closed: unknown
  sleep_architecture: unknown; sleep_architecture_empty: unknown; tables: Record<string, unknown>
  session_checks: unknown; settings: unknown
}
const STRENGTH_DEFAULT = 'Overall Strength Score'

/** The flexibility screen as one run has reached it: finished, capturing, or empty. */
function flexibilityOf(run: fx.WeekRun, scenario: Set<string>): unknown {
  if (run.flexFinished || scenario.has('flex_populated')) return insights.flexibility_populated
  if (run.flexStep !== null) return { ...insights.flexibility_capturing, capture: insights.capture.states[run.flexStep] }
  return insights.flexibility_empty
}

/** A yoga flow or an outdoor activity, logged once a day: the same save sent again answers
 *  as it did; another save of it is told it is already logged. */
function logOnce(kept: Record<string, string>, key: string, sessionId: string): boolean {
  if (!(key in kept)) kept[key] = sessionId
  return kept[key] === sessionId
}
const checkins = new Map<string, ReturnType<typeof fx.checkinForm>['values']>()
// The daily data check as the Worker keeps it: none until one runs ("Check now").
let lastCheck: unknown = null
const sampleCheck = () => ({
  checked_at: new Date().toISOString(),
  backup_name: 'health-2026-10-19.db.gz',
  backup_day: '2026-10-19',
  backup_stale: false,
  missing_rows: 0,
  tables: [{ table: 'training_sessions', backup_rows: 40, store_rows: 41, missing: 0, examples: [] }],
})

const cookie = (req: IncomingMessage, name: string) =>
  new RegExp(`(?:^|;\\s*)${name}=([^;]*)`).exec(String(req.headers.cookie ?? ''))?.[1] ?? null

export function mockApi(): Plugin {
  return {
    name: 'health-mock-api',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use(handler)
    },
    configurePreviewServer(server) {
      server.middlewares.use(handler)
    },
  }
}

async function readBody(req: IncomingMessage): Promise<unknown> {
  const chunks: Buffer[] = []
  for await (const chunk of req) chunks.push(chunk as Buffer)
  const text = Buffer.concat(chunks).toString('utf-8')
  try {
    return text ? JSON.parse(text) : null
  } catch {
    return text
  }
}

function handler(req: IncomingMessage, res: ServerResponse, next: () => void): void {
  const url = new URL(req.url ?? '/', 'http://localhost')
  if (url.pathname === '/oura/callback') {
    // The Worker's return page (worker/src/index.ts), made up: the login always succeeds.
    res.statusCode = 302
    res.setHeader('Location', '/#/oura-done?result=ok')
    res.end()
    return
  }
  if (!url.pathname.startsWith('/api/')) return next()
  const send = (status: number, body: unknown) => {
    res.statusCode = status
    res.setHeader('Content-Type', 'application/json')
    res.setHeader('Cache-Control', 'no-store')
    res.end(JSON.stringify(body))
  }
  if (url.pathname === '/api/dev/received') return send(200, received)
  if (url.pathname === '/api/dev/sessions') return send(200, [...sessions.values()])
  if (url.pathname === '/api/dev/week-run') return send(200, runOf(req))
  if (url.pathname === '/api/push/key' && req.headers.authorization === `Bearer ${KEY}`) {
    return send(503, { error: 'push_not_configured' })
  }
  if (cookie(req, 'e2e_engine') === 'down') return send(503, { error: 'engine_unavailable' })
  if (req.headers.authorization !== `Bearer ${KEY}`) return send(401, { error: 'unauthorized' })
  const day = (req.headers['x-local-date'] as string | undefined) ?? null
  if (url.pathname === '/api/health' && req.method === 'GET') {
    return send(200, {
      status: 'ok',
      build: { version: '0.0.0', commit: 'mock', built: null },
      python: '3.12',
      server_tz: 'Europe/Berlin',
      server_local_date: day,
      started_at: null,
      cache_rebuilt: true,
      cache: {},
      timings: {},
    })
  }
  if (url.pathname === '/api/data/check/last' && req.method === 'GET') return send(200, lastCheck)
  if (url.pathname === '/api/data/check/run' && req.method === 'POST') {
    lastCheck = sampleCheck()
    return send(200, lastCheck)
  }
  const local = day ?? new Date().toISOString().slice(0, 10)
  const asked = url.searchParams.get('date')
  const shown = fx.opening(asked, url.searchParams.get('picked_on'), local)
  if (req.method === 'GET') {
    if (url.pathname === '/api/today') return send(200, fx.today(shown, local))
    if (url.pathname === '/api/today/week') return send(200, fx.week(shown, local))
    if (url.pathname === '/api/today/readiness') return send(200, fx.readinessDetail(shown, local))
    if (url.pathname === '/api/today/sleep') return send(200, fx.sleepDetail(shown, local))
    if (url.pathname === '/api/today/strain') {
      return send(200, fx.strainDetail(shown, local, url.searchParams.get('week') === 'true'))
    }
    if (url.pathname === '/api/training/day') return send(200, fx.trainingDay(asked ?? local, local, scenarioOf(req)))
    if (url.pathname === '/api/training/week') {
      return send(200, fx.trainingWeek(local, url.searchParams.get('week_start'), scenarioOf(req), runOf(req)))
    }
    if (url.pathname === '/api/insights/strength') {
      if (scenarioOf(req).has('no_reference')) return send(409, { error: 'strength_reference_missing' })
      const metric = url.searchParams.get('metric') ?? STRENGTH_DEFAULT
      return send(200, insights.strength[metric] ?? insights.strength[STRENGTH_DEFAULT])
    }
    if (url.pathname === '/api/insights/metabolism') {
      const metric = url.searchParams.get('metric') ?? 'Weight'
      const kind = url.searchParams.get('kind') ?? 'all'
      const offset = url.searchParams.get('offset') ?? '0'
      const m = insights.metabolism
      return send(200, m[`${metric}|${kind}|${offset}`] ?? m[`${metric}|${kind}|0`] ?? m[`${metric}|all|0`] ?? m['Weight|all|0'])
    }
    if (url.pathname === '/api/insights/flexibility') return send(200, flexibilityOf(runOf(req), scenarioOf(req)))
    if (url.pathname === '/api/insights/engine') return send(200, insights.engine)
    if (url.pathname === '/api/insights/queue') return send(200, insights.queue)
    if (url.pathname === '/api/insights/warnings') {
      const w = insights.warnings as { year: number; month: number }
      const year = Number(url.searchParams.get('year') ?? w.year)
      const month = Number(url.searchParams.get('month') ?? w.month)
      const step = (d: number) => ({ year: year + Math.floor((month - 1 + d) / 12), month: ((month - 1 + d) % 12 + 12) % 12 + 1 })
      return send(200, { ...w, year, month, previous: step(-1), next: step(1) })
    }
    if (url.pathname === '/api/insights/trends') {
      return send(200, scenarioOf(req).has('trends_closed') ? insights.trends_closed : insights.trends)
    }
    if (url.pathname === '/api/insights/sleep-architecture') {
      return send(200, scenarioOf(req).has('sleep_empty') ? insights.sleep_architecture_empty : insights.sleep_architecture)
    }
    if (url.pathname.startsWith('/api/data/tables/')) {
      const table = url.pathname.slice('/api/data/tables/'.length)
      return table in insights.tables ? send(200, insights.tables[table]) : send(404, { error: 'unknown_table' })
    }
    if (url.pathname === '/api/data/session-checks') return send(200, insights.session_checks)
    if (url.pathname === '/api/settings') {
      // Phase 9: with e2e_week writer_engine the engine runs the syncs (the sync buttons are on).
      return send(200, scenarioOf(req).has('writer_engine') ? { ...(insights.settings as Record<string, unknown>), writer: 'engine' } : insights.settings)
    }
    if (url.pathname === '/api/training/accessory') {
      // `accessory_yesterday`: an answer kept from the day before, which is never today's.
      return send(200, fx.accessoryPlan(scenarioOf(req).has('accessory_yesterday') ? fx.addDays(local, -1) : local))
    }
    if (url.pathname === '/api/training/yoga') return send(200, fx.yogaCatalogue())
    if (url.pathname === '/api/training/outdoor') {
      if (scenarioOf(req).has('garmin_busy')) return send(409, { error: 'sync_running' })
      return send(200, fx.outdoorList(asked ?? local))
    }
    if (url.pathname === '/api/training/session') return send(200, { ...sessionFixture, date: local })
    if (url.pathname === '/api/training/garmin/open-activity') {
      if (cookie(req, 'e2e_watch') === 'missing') return send(200, { found: false, activity: null })
      return send(200, { found: true, activity: { activity_id: '1', name: 'Made-up strength', type: 'strength', duration_minutes: 41 } })
    }
    if (url.pathname === '/api/training/garmin/activity-minutes') {
      return send(200, { minutes: 31, detail: { activities: 1 }, window: [0, 6] })
    }
    if (url.pathname === '/api/status') {
      // Phase 9: with e2e_week writer_engine the engine is the background writer, and a sync
      // is due until this run has had one; offline_copy: the engine reads a saved copy.
      const scenario = scenarioOf(req)
      const run = runOf(req)
      const engine = scenario.has('writer_engine')
      const lastSync = run.syncedAt
        ? { day: local, at: run.syncedAt, results: { oura: [true, null], garmin: [true, null], failed_week: [true, null] }, error: null }
        : null
      return send(200, {
        writer: engine ? 'engine' : 'streamlit',
        offline: scenario.has('offline_copy'),
        datastore_built_at: scenario.has('offline_copy') ? '2026-10-20 06:00' : null,
        oura: engine ? { kind: 'oauth', state: 'ok', needs_authorisation: false, expires_at: '2026-10-21T06:00:00+00:00', seconds_remaining: 80000, oauth_configured: true } : null,
        last_sync: lastSync, notices: [],
        sync_due: engine && !run.syncedAt ? 'first_open' : null,
      })
    }
    if (url.pathname === '/api/checkin') {
      const d = asked ?? local
      return send(200, fx.checkinForm(d, local, checkins.get(`${cookie(req, 'e2e_run') ?? ''}|${d}`)))
    }
  }
  if (req.method === 'PUT' || req.method === 'POST' || req.method === 'DELETE') {
    void readBody(req).then((body) => {
      received.push({ method: req.method!, path: url.pathname, body, day })
      if (url.pathname === '/api/training/completion') {
        const b = body as { model_minutes: number; start_ts: number; end_ts: number; rpe: number }
        const clock = Math.max(5, Math.floor((b.end_ts - b.start_ts) / 60))
        const choice = (minutes: number, source: string) => ({
          minutes, source, au: b.rpe * minutes, au_by_rpe: Array.from({ length: 10 }, (_, i) => (i + 1) * minutes),
        })
        const ask = clock > 1.5 * b.model_minutes
        return send(200, { clock_minutes: clock, model_minutes: b.model_minutes, ask_length: ask,
          choices: ask ? [choice(b.model_minutes, 'plan'), choice(clock, 'clock')] : [choice(clock, 'clock')] })
      }
      if (url.pathname === '/api/training/heart-rate' && req.method === 'POST') {
        const b = body as { reported_rpe: number | null; duration_minutes: number; activity_id?: string }
        const hr = cookie(req, 'e2e_hr')
        if (hr === 'none') return send(200, { state: 'no_match', reason: 'no activity today', candidates: [], comparison: null })
        if (hr === 'choose' && !b.activity_id) {
          return send(200, { state: 'choose', reason: 'no activity lines up with the session', comparison: null,
            candidates: [{ activity_id: '7', name: 'Made-up strength', type: 'strength',
              start_time_local: '2026-10-20 07:05:00', duration_minutes: 52, shift_hours: -1, quality: 0.8 }] })
        }
        const rpe = b.reported_rpe ?? 5
        return send(200, { state: 'matched', reason: '', candidates: [], comparison: {
          measured_rpe: 6.2, measured_au: 6.2 * b.duration_minutes, active_minutes: b.duration_minutes - 2,
          rpe_delta: 6.2 - rpe, au_delta: (6.2 - rpe) * b.duration_minutes, verdict: Math.abs(6.2 - rpe) < 0.5 ? 'exact' : 6.2 > rpe ? 'under' : 'over',
          coverage: 0.95, low_coverage: false, activity: 'Made-up strength', covered_exercises: 8, total_exercises: 9 } })
      }
      if (url.pathname.startsWith('/api/data/sync/')) {
        if (!scenarioOf(req).has('writer_engine')) return send(409, { error: 'not_the_writer' })
        return send(200, { kind: url.pathname.slice('/api/data/sync/'.length), result: { count: 1 } })
      }
      if (url.pathname === '/api/oura/login') {
        // The made-up login goes straight to the made-up return page (below), as Oura would.
        if (!scenarioOf(req).has('writer_engine')) return send(409, { error: 'not_the_writer' })
        return send(200, { authorize_url: '/oura/callback?code=made-up&state=made-up' })
      }
      if (url.pathname === '/api/sync') {
        const run = runOf(req)
        if (!scenarioOf(req).has('writer_engine')) return send(409, { error: 'not_the_writer' })
        run.syncedAt = new Date().toISOString()
        return send(200, { ran: true, reason: 'first_open',
          status: { day: local, at: run.syncedAt, results: { oura: [true, null] }, error: null } })
      }
      if (url.pathname.startsWith('/api/insights/flexibility')) {
        const run = runOf(req)
        const last = insights.capture.states.length - 1
        if (url.pathname === '/api/insights/flexibility/capture') {
          if (req.method === 'POST') run.flexStep = run.flexStep ?? 0
          else if (req.method === 'PUT') run.flexStep = Math.min((run.flexStep ?? 0) + 1, last)
          else if (req.method === 'DELETE') {
            run.flexStep = null
            return send(200, { cleared: true })
          }
          return send(200, insights.capture.states[run.flexStep ?? 0])
        }
        if (url.pathname === '/api/insights/flexibility/capture/finish') {
          if (run.flexStep === null) return send(409, { error: 'no_capture' })
          run.flexStep = null
          run.flexFinished = true
          return send(200, insights.flexibility_populated)
        }
        if (url.pathname === '/api/insights/flexibility/missing') return send(200, insights.flexibility_populated)
      }
      if (SCHEDULE.has(url.pathname) && req.method === 'POST') {
        const [status, payload] = answerSchedule(url.pathname, body as Record<string, unknown> | null, runOf(req), scenarioOf(req))
        if (status === 200 && cookie(req, 'e2e_lose_answer') === '1') return send(503, { error: 'engine_unavailable' })
        return send(status, payload)
      }
      if (url.pathname === '/api/training/yoga' && req.method === 'POST') {
        const b = body as { slug: string; session_id: string }
        return send(200, { logged: logOnce(runOf(req).yoga, `${day}|${b.slug}`, b.session_id) })
      }
      if (url.pathname === '/api/training/outdoor' && req.method === 'POST') {
        const b = body as { date: string; activity_id: string; rpe: number; session_id: string }
        const act = fx.outdoorList(b.date).activities.find((a) => a.activity_id === b.activity_id)
        if (!act) return send(422, { error: 'unknown_activity' })
        const logged = logOnce(runOf(req).outdoor, b.activity_id, b.session_id)
        return send(200, { logged, au: act.au_by_rpe[b.rpe - 1], logs_as: act.logs_as })
      }
      if (url.pathname === '/api/training/sessions' && req.method === 'POST') {
        const b = body as { session_id: string; notes: string; exercises: unknown[] }
        sessions.set(b.session_id, b)
        if (cookie(req, 'e2e_lose_answer') === '1') return send(503, { error: 'engine_unavailable' })
        return send(200, { session_id: b.session_id, exercises: b.exercises.length })
      }
      if (url.pathname === '/api/checkin' && req.method === 'PUT') {
        const b = body as { date: string; values: ReturnType<typeof fx.checkinForm>['values'] }
        checkins.set(`${cookie(req, 'e2e_run') ?? ''}|${b.date}`, b.values)
        return send(200, fx.checkinForm(b.date, local, b.values))
      }
      send(200, { saved: true })
    })
    return
  }
  send(404, { error: 'not_found' })
}
