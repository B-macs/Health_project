// The Worker inside workerd (Cloudflare's vitest plugin). The engine is never called:
// global fetch is replaced, so each test sees exactly what would leave Cloudflare.
import { exports } from 'cloudflare:workers'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { app } from '../src/index'

const ACCESS = { authorization: 'Bearer test-access-key' }

function call(path: string, init: RequestInit = {}): Promise<Response> {
  return exports.default.fetch(new Request(`https://health.test${path}`, init))
}

// A NEW Response per call: workerd refuses to read a body made in another request's context.
function engineAnswers(body: unknown, status = 200) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(
    async () =>
      new Response(JSON.stringify(body), {
        status,
        headers: { 'content-type': 'application/json', 'set-cookie': 'x=1' },
      }),
  )
}

afterEach(() => vi.restoreAllMocks())

describe('the access key', () => {
  it('answers 401 JSON without the key or with a wrong one, and never calls the engine', async () => {
    const spy = engineAnswers({ status: 'ok' })
    const variants: [Record<string, string>, number][] = [
      [{}, 401],
      [{ authorization: 'Bearer nope' }, 401],
      // Hono's bearerAuth answers a header in another scheme with 400 (malformed).
      [{ authorization: 'Basic x' }, 400],
    ]
    for (const [headers, status] of variants) {
      const res = await call('/api/health', { headers })
      expect(res.status).toBe(status)
      expect(await res.json()).toEqual({ error: 'unauthorized' })
    }
    expect(spy).not.toHaveBeenCalled()
  })

  it('refuses another origin even with the key', async () => {
    const spy = engineAnswers({ status: 'ok' })
    const res = await call('/api/health', {
      headers: { ...ACCESS, origin: 'https://evil.example' },
    })
    expect(res.status).toBe(403)
    expect(spy).not.toHaveBeenCalled()
  })
})

describe('the pass-through', () => {
  it('sends the path and query to the engine with the engine key, and only the allowed headers', async () => {
    const spy = engineAnswers({ status: 'ok' })
    const res = await call('/api/readiness?date=2026-10-06', {
      headers: { ...ACCESS, 'x-local-date': '2026-10-07', cookie: 'secret=1' },
    })
    expect(res.status).toBe(200)
    expect(await res.json()).toEqual({ status: 'ok' })
    const [target, init] = spy.mock.calls[0] as [URL, RequestInit]
    expect(String(target)).toBe('https://engine.test/api/readiness?date=2026-10-06')
    const sent = new Headers(init.headers)
    expect(sent.get('x-engine-key')).toBe('test-engine-key')
    expect(sent.get('x-local-date')).toBe('2026-10-07')
    expect(sent.get('authorization')).toBeNull()
    expect(sent.get('cookie')).toBeNull()
  })

  it('marks every answer no-store and drops the engine\'s other headers', async () => {
    engineAnswers({ status: 'ok' })
    const res = await call('/api/health', { headers: ACCESS })
    expect(res.headers.get('cache-control')).toBe('no-store')
    expect(res.headers.get('set-cookie')).toBeNull()
  })

  it('passes a POST body through', async () => {
    const spy = engineAnswers({ ok: true })
    await call('/api/probe/garmin', {
      method: 'POST',
      headers: { ...ACCESS, 'content-type': 'application/json' },
      body: JSON.stringify({ confirm: 'owner-approved' }),
    })
    const [, init] = spy.mock.calls[0] as [URL, RequestInit]
    expect(new TextDecoder().decode(init.body as ArrayBuffer)).toBe('{"confirm":"owner-approved"}')
  })

  it('passes the engine\'s own JSON errors through unchanged', async () => {
    engineAnswers({ error: 'x_local_date_missing' }, 400)
    const res = await call('/api/readiness?date=2026-10-06', { headers: ACCESS })
    expect(res.status).toBe(400)
    expect(await res.json()).toEqual({ error: 'x_local_date_missing' })
  })
})

describe('when the engine fails', () => {
  it('answers 503 JSON when the engine cannot be reached', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('network'))
    const res = await call('/api/health', { headers: ACCESS })
    expect(res.status).toBe(503)
    expect(await res.json()).toEqual({ error: 'engine_unavailable' })
  })

  it('answers 504 JSON when the engine does not answer in time', async () => {
    const timeout = new Error('timed out')
    timeout.name = 'TimeoutError'
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(timeout)
    const res = await call('/api/health', { headers: ACCESS })
    expect(res.status).toBe(504)
    expect(await res.json()).toEqual({ error: 'engine_timeout' })
  })

  it('never shows Google\'s own error page', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(
      async () =>
        new Response('<html>Service Unavailable</html>', {
          status: 503,
          headers: { 'content-type': 'text/html' },
        }),
    )
    const res = await call('/api/health', { headers: ACCESS })
    expect(res.status).toBe(503)
    expect(await res.json()).toEqual({ error: 'engine_unavailable' })
  })

  it('answers 503 not_configured when a secret is missing', async () => {
    const env = { ACCESS_KEY: 'k', ENGINE_KEY: '', ENGINE_URL: '' } as never
    const res = await app.request('/api/health', { headers: { authorization: 'Bearer k' } }, env)
    expect(res.status).toBe(503)
    expect(await res.json()).toEqual({ error: 'not_configured' })
  })
})
