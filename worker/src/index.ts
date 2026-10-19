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
import { Hono, type Context } from 'hono'
import { bearerAuth } from 'hono/bearer-auth'

export type Bindings = {
  ASSETS: Fetcher
  ACCESS_KEY: string
  ENGINE_KEY: string
  ENGINE_URL: string
}

// The phone's headers the engine may see. X-Local-Date is the phone's day: the
// engine never decides "today" itself (rebuild rule 3).
export const FORWARDED_HEADERS = ['accept', 'content-type', 'x-local-date'] as const

// Long enough for a cold start that rebuilds the cache; short of the engine's own
// request timeout, so a hung engine answers 504 here rather than hanging the phone.
// One budget for every try below.
export const ENGINE_TIMEOUT_MS = 60_000

// Google refuses a request before the engine sees it when the engine is still
// starting from zero: "The request was aborted because there was no available
// instance" (HTTP 500 with Google's own page; seen 2026-10-19 on the first request
// after the engine slept). Google's troubleshooting guide asks the client to retry
// with backoff. The engine answers JSON for every error, its own crashes included,
// so a 429 or 5xx that is NOT JSON never reached it and a retry cannot run anything
// twice.
export const RETRY_DELAYS_MS = [1_000, 2_000, 4_000, 8_000] as const

export function isGoogleRefusal(response: Response): boolean {
  const type = response.headers.get('content-type') ?? ''
  return (response.status === 429 || response.status >= 500) && !type.includes('application/json')
}

// An object, so a test can replace the wait without waiting.
export const timing = {
  wait: (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms)),
}

const NO_STORE = { 'Cache-Control': 'no-store' }

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

app.all('/api/*', async (c) => {
  if (!c.env.ENGINE_URL || !c.env.ENGINE_KEY) {
    return c.json({ error: 'not_configured' }, 503, NO_STORE)
  }
  const incoming = new URL(c.req.url)
  const target = new URL(incoming.pathname + incoming.search, c.env.ENGINE_URL)
  const headers = new Headers()
  for (const name of FORWARDED_HEADERS) {
    const value = c.req.header(name)
    if (value) headers.set(name, value)
  }
  headers.set('X-Engine-Key', c.env.ENGINE_KEY)
  const init: RequestInit = {
    method: c.req.method,
    headers,
    redirect: 'manual',
    signal: AbortSignal.timeout(ENGINE_TIMEOUT_MS),
  }
  if (c.req.method !== 'GET' && c.req.method !== 'HEAD') init.body = await c.req.arrayBuffer()

  let response: Response
  for (let attempt = 0; ; attempt++) {
    try {
      response = await fetch(target, init)
    } catch (err) {
      const timedOut = err instanceof Error && err.name === 'TimeoutError'
      return c.json({ error: timedOut ? 'engine_timeout' : 'engine_unavailable' },
        timedOut ? 504 : 503, NO_STORE)
    }
    if (!isGoogleRefusal(response) || attempt >= RETRY_DELAYS_MS.length) break
    await response.body?.cancel()
    await timing.wait(RETRY_DELAYS_MS[attempt])
  }
  const type = response.headers.get('content-type') ?? ''
  if (response.status >= 500 && !type.includes('application/json')) {
    // Google's own error page while the engine starts or fails: never shown as is.
    return c.json({ error: 'engine_unavailable' }, 503, NO_STORE)
  }
  const out = new Headers(NO_STORE)
  if (type) out.set('content-type', type)
  return new Response(response.body, { status: response.status, headers: out })
})

// Anything else is the app (run_worker_first only sends /api/* here in production).
app.all('*', (c) => c.env.ASSETS.fetch(c.req.raw))

export { app }
export default {
  fetch: app.fetch,
} satisfies ExportedHandler<Bindings>
