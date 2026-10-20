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
// - the data check answers as the Worker does: GET .../last (null until a check ran) and
//   POST .../run (a made-up clean result);
// - Today, its week, the day's plan, the three detail screens and the check-in answer
//   made-up numbers (dev/fixtures.ts); a saved check-in is kept for the next read.
import type { IncomingMessage, ServerResponse } from 'node:http'
import type { Plugin } from 'vite'
import * as fx from './fixtures.ts'
import sessionFixture from './session_fixture.json' with { type: 'json' }

const KEY = 'dev'
const received: { method: string; path: string; body: unknown; day: string | null }[] = []
// Sessions saved through the mock, by session id: a save sent again replaces itself.
const sessions = new Map<string, { session_id: string; notes: string; exercises: unknown[] }>()
// Check-ins saved through the mock, by date.
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
  if (!url.pathname.startsWith('/api/')) return next()
  const send = (status: number, body: unknown) => {
    res.statusCode = status
    res.setHeader('Content-Type', 'application/json')
    res.setHeader('Cache-Control', 'no-store')
    res.end(JSON.stringify(body))
  }
  if (url.pathname === '/api/dev/received') return send(200, received)
  if (url.pathname === '/api/dev/sessions') return send(200, [...sessions.values()])
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
    if (url.pathname === '/api/training/day') return send(200, fx.trainingDay(asked ?? local, local))
    if (url.pathname === '/api/training/session') return send(200, { ...sessionFixture, date: local })
    if (url.pathname === '/api/training/garmin/open-activity') {
      if (cookie(req, 'e2e_watch') === 'missing') return send(200, { found: false, activity: null })
      return send(200, { found: true, activity: { activity_id: '1', name: 'Made-up strength', type: 'strength', duration_minutes: 41 } })
    }
    if (url.pathname === '/api/training/garmin/activity-minutes') {
      return send(200, { minutes: 31, detail: { activities: 1 }, window: [0, 6] })
    }
    if (url.pathname === '/api/status') {
      return send(200, { writer: 'streamlit', offline: false, datastore_built_at: null, oura: null, last_sync: null, notices: [], sync_due: null })
    }
    if (url.pathname === '/api/checkin') {
      const d = asked ?? local
      return send(200, fx.checkinForm(d, local, checkins.get(d)))
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
      if (url.pathname === '/api/training/sessions' && req.method === 'POST') {
        const b = body as { session_id: string; notes: string; exercises: unknown[] }
        sessions.set(b.session_id, b)
        if (cookie(req, 'e2e_lose_answer') === '1') return send(503, { error: 'engine_unavailable' })
        return send(200, { session_id: b.session_id, exercises: b.exercises.length })
      }
      if (url.pathname === '/api/checkin' && req.method === 'PUT') {
        const b = body as { date: string; values: ReturnType<typeof fx.checkinForm>['values'] }
        checkins.set(b.date, b.values)
        return send(200, fx.checkinForm(b.date, local, b.values))
      }
      send(200, { saved: true })
    })
    return
  }
  send(404, { error: 'not_found' })
}
