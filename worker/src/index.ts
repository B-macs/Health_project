// The health Worker: the app's files, and /api passed on to the engine.
//
// /api/* is checked here twice before anything leaves Cloudflare: the request must come
// from this origin, and it must carry the owner's access key (Hono's bearerAuth compares
// in constant time). Only then is it sent to the engine, with the engine's own key added
// and only three of the phone's headers kept: the engine never sees the owner's key, a
// cookie or anything else from the phone. Every /api answer is `no-store`.
//
// The Worker holds no rule (CLAUDE.md, rebuild rule 1): it passes the engine's answer
// through unchanged, and turns a network failure into one JSON error the app can show.
//
// Rebuild Phase 6 adds THE TIMER ALERTS (src/alerts.ts): /api/push/* is answered here, with
// a Durable Object that sends a Web Push when a rest or a hold ends while the phone is
// locked. It holds the phone's push subscription and one alert; it never calls the engine.
//
// Rebuild Phase 4 adds two things:
// - THE DAILY DATA CHECK. A Cron Trigger (wrangler.jsonc) asks the engine once a day
//   which rows of the newest backup the store no longer holds (GET /api/data/check, read
//   only), and keeps the answer in KV, so Settings shows the last result even while the
//   engine sleeps (GET /api/data/check/last). Settings' "Check now" runs the same
//   (POST /api/data/check/run). The daily request also keeps the free Supabase project
//   from pausing after 7 quiet days.
// - THE SYNC SWITCH, OFF. Until the switch-over (Phase 9) the Streamlit app is the one
//   background writer (rebuild rule 2: Oura spends its refresh token at each refresh, so
//   two syncers break the login). The engine refuses a sync and the Oura login on its own
//   (background_writer); SYNC_ENABLED is a second lock at the edge that no row in the
//   store can open by accident. No Cron Trigger syncs: the owner chose ONE sync a day, at
//   the first app open (2026-10-19), and a trigger has no phone to give it the day.
import { Hono, type Context } from 'hono'
import { bearerAuth } from 'hono/bearer-auth'
import { type AlertEnv, alertRoutes } from './alerts'

export { TimerAlerts } from './alerts'

export type Bindings = AlertEnv & {
  ASSETS: Fetcher
  ACCESS_KEY: string
  ENGINE_KEY: string
  ENGINE_URL: string
  STATE: KVNamespace
  SYNC_ENABLED: string
}

// The phone's headers the engine may see. X-Local-Date is the phone's day: the
// engine never decides "today" itself (rebuild rule 3).
export const FORWARDED_HEADERS = ['accept', 'content-type', 'x-local-date'] as const

// Long enough for a cold start that rebuilds the cache; short of the engine's own
// request timeout, so a hung engine answers 504 here rather than hanging the phone.
// One budget for every try below.
export const ENGINE_TIMEOUT_MS = 60_000

// A device sync (and the Oura login) runs the device calls inside one request: the old app
// measured about 77 s for Oura and Garmin alone (2026-08-01), past the 60 s above. A request
// cut off mid-sync could leave Oura's refresh token spent and the new one unsaved, so these
// paths wait longer: short of the phone's own 300 s and of Cloud Run's 900 s. Cloudflare sets
// no wall-clock limit on an HTTP request while the client stays connected (checked
// 2026-10-20, developers.cloudflare.com/workers/platform/limits).
export const SYNC_TIMEOUT_MS = 280_000

// Google refuses a request before the engine sees it when the engine is still
// starting from zero: "The request was aborted because there was no available
// instance" (HTTP 500 with Google's own page; seen 2026-10-19 on the first request
// after the engine slept). Google's troubleshooting guide asks the client to retry
// with backoff. The engine answers JSON for every error, its own crashes included,
// so a 429 or 5xx that is NOT JSON never reached it and a retry cannot run anything
// twice.
export const RETRY_DELAYS_MS = [1_000, 2_000, 4_000, 8_000] as const

// The paths that run a device sync or the Oura login: closed unless SYNC_ENABLED is "true".
export const SYNC_PATHS = /^\/api\/(sync(\/|$)|data\/sync\/|oura\/)/

// Where the last data check is kept.
export const LAST_CHECK = 'data_check:last'

export function isGoogleRefusal(response: Response): boolean {
  const type = response.headers.get('content-type') ?? ''
  return (response.status === 429 || response.status >= 500) && !type.includes('application/json')
}

// An object, so a test can replace the wait without waiting.
export const timing = {
  wait: (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms)),
}

const NO_STORE = { 'Cache-Control': 'no-store' }

function jsonError(error: string, status: number): Response {
  return new Response(JSON.stringify({ error }), {
    status,
    headers: { 'content-type': 'application/json', ...NO_STORE },
  })
}

/** One request to the engine, with the engine's key, the retries and the JSON errors. */
export async function toEngine(env: Bindings, method: string, pathAndQuery: string,
  headers: Headers, body?: ArrayBuffer, timeoutMs: number = ENGINE_TIMEOUT_MS): Promise<Response> {
  if (!env.ENGINE_URL || !env.ENGINE_KEY) return jsonError('not_configured', 503)
  headers.set('X-Engine-Key', env.ENGINE_KEY)
  const init: RequestInit = {
    method,
    headers,
    redirect: 'manual',
    signal: AbortSignal.timeout(timeoutMs),
  }
  if (body !== undefined) init.body = body
  const target = new URL(pathAndQuery, env.ENGINE_URL)

  let response: Response
  for (let attempt = 0; ; attempt++) {
    try {
      response = await fetch(target, init)
    } catch (err) {
      const timedOut = err instanceof Error && err.name === 'TimeoutError'
      return jsonError(timedOut ? 'engine_timeout' : 'engine_unavailable', timedOut ? 504 : 503)
    }
    if (!isGoogleRefusal(response) || attempt >= RETRY_DELAYS_MS.length) break
    await response.body?.cancel()
    await timing.wait(RETRY_DELAYS_MS[attempt])
  }
  const type = response.headers.get('content-type') ?? ''
  if (response.status >= 500 && !type.includes('application/json')) {
    // Google's own error page while the engine starts or fails: never shown as is.
    await response.body?.cancel()
    return jsonError('engine_unavailable', 503)
  }
  const out = new Headers(NO_STORE)
  if (type) out.set('content-type', type)
  return new Response(response.body, { status: response.status, headers: out })
}

/** The data check: ask the engine, keep a good answer in KV, return the answer. */
export async function runDataCheck(env: Bindings): Promise<Response> {
  const response = await toEngine(env, 'GET', '/api/data/check', new Headers({ accept: 'application/json' }))
  if (response.status !== 200) return response
  const text = await response.text()
  await env.STATE.put(LAST_CHECK, text)
  return new Response(text, { status: 200, headers: { 'content-type': 'application/json', ...NO_STORE } })
}

const app = new Hono<{ Bindings: Bindings }>()

app.use('/api/*', async (c, next) => {
  const origin = c.req.header('origin')
  if (origin && origin !== new URL(c.req.url).origin) {
    return c.json({ error: 'cross_origin' }, 403, NO_STORE)
  }
  if (!c.env.ACCESS_KEY) return c.json({ error: 'not_configured' }, 503, NO_STORE)
  const unauthorized = { error: 'unauthorized' }
  // The middleware is typed for a plain context; ours only adds the bindings.
  return bearerAuth({
    token: c.env.ACCESS_KEY,
    noAuthenticationHeaderMessage: unauthorized,
    invalidAuthenticationHeaderMessage: unauthorized,
    invalidTokenMessage: unauthorized,
  })(c as unknown as Context, next)
})

// The last data check, from KV: it answers while the engine sleeps. null until one ran.
app.get('/api/data/check/last', async (c) => c.json((await c.env.STATE.get(LAST_CHECK, 'json')) ?? null, 200, NO_STORE))

// Settings' "Check now".
app.post('/api/data/check/run', (c) => runDataCheck(c.env))

// Rebuild Phase 6: the timer alerts (src/alerts.ts). Answered here, never by the engine.
alertRoutes(app)

app.all('/api/*', async (c) => {
  const incoming = new URL(c.req.url)
  if (SYNC_PATHS.test(incoming.pathname) && c.env.SYNC_ENABLED !== 'true') {
    return c.json({ error: 'sync_disabled' }, 409, NO_STORE)
  }
  const headers = new Headers()
  for (const name of FORWARDED_HEADERS) {
    const value = c.req.header(name)
    if (value) headers.set(name, value)
  }
  const body = c.req.method !== 'GET' && c.req.method !== 'HEAD' ? await c.req.arrayBuffer() : undefined
  const timeout = SYNC_PATHS.test(incoming.pathname) ? SYNC_TIMEOUT_MS : ENGINE_TIMEOUT_MS
  return toEngine(c.env, c.req.method, incoming.pathname + incoming.search, headers, body, timeout)
})

// Where Oura sends the owner back after the login (rebuild Phase 9). The Worker hands the
// code to the engine itself, so the login finishes wherever iOS opens this page (the Home
// Screen app or Safari, which do not share the access key); the engine checks the state it
// issued, so a made-up call changes nothing. Behind the same switch as the syncs. Then the
// app's result page says how it went (app/src/screens/OuraDone.tsx).
app.get('/oura/callback', async (c) => {
  const query = new URL(c.req.url).searchParams
  const code = query.get('code') ?? ''
  const state = query.get('state') ?? ''
  let result = 'denied'
  if (c.env.SYNC_ENABLED !== 'true') {
    result = 'sync_disabled'
  } else if (code && state) {
    const body = new TextEncoder().encode(JSON.stringify({ code, state }))
    const answer = await toEngine(c.env, 'POST', '/api/oura/callback',
      new Headers({ 'content-type': 'application/json', accept: 'application/json' }), body.buffer as ArrayBuffer)
    if (answer.ok) {
      result = 'ok'
    } else {
      const err = (await answer.json().catch(() => ({}))) as { error?: string }
      result = err.error ?? 'refused'
    }
  }
  return c.redirect(`/#/oura-done?result=${encodeURIComponent(result)}`, 302)
})

// Anything else is the app (run_worker_first only sends /api/* and /oura/* here in production).
app.all('*', (c) => c.env.ASSETS.fetch(c.req.raw))

export { app }
export default {
  fetch: app.fetch,
  // The daily data check (wrangler.jsonc: triggers.crons). It only reads.
  async scheduled(_controller, env, ctx) {
    ctx.waitUntil(
      runDataCheck(env).then(async (response) => {
        if (response.status !== 200) console.error('data check: no answer', response.status, await response.text())
      }),
    )
  },
} satisfies ExportedHandler<Bindings>
