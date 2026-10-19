// The Worker inside workerd (Cloudflare's vitest plugin). The engine is never called:
// global fetch is replaced, so each test sees exactly what would leave Cloudflare.
import { exports } from 'cloudflare:workers'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { app, RETRY_DELAYS_MS, timing } from '../src/index'

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
    vi.spyOn(timing, 'wait').mockResolvedValue()
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

// Google's refusal page while the engine starts from zero (2026-10-19: HTTP 500,
// "The request was aborted because there was no available instance").
function refusal(status = 500) {
  return new Response('<html>Error: Server Error</html>', {
    status,
    headers: { 'content-type': 'text/html; charset=UTF-8' },
  })
}

function engineOk() {
  return new Response(JSON.stringify({ status: 'ok' }), {
    status: 200,
    headers: { 'content-type': 'application/json' },
  })
}

describe('when Google refuses a request while the engine starts', () => {
  it('tries again after a second, and answers once the engine is up', async () => {
    const wait = vi.spyOn(timing, 'wait').mockResolvedValue()
    const spy = vi.spyOn(globalThis, 'fetch')
      .mockImplementationOnce(async () => refusal())
      .mockImplementationOnce(async () => engineOk())
    const res = await call('/api/health', { headers: ACCESS })
    expect(res.status).toBe(200)
    expect(await res.json()).toEqual({ status: 'ok' })
    expect(spy).toHaveBeenCalledTimes(2)
    expect(wait.mock.calls).toEqual([[1_000]])
  })

  it('also tries again on a 429 refusal', async () => {
    vi.spyOn(timing, 'wait').mockResolvedValue()
    const spy = vi.spyOn(globalThis, 'fetch')
      .mockImplementationOnce(async () => refusal(429))
      .mockImplementationOnce(async () => engineOk())
    expect((await call('/api/health', { headers: ACCESS })).status).toBe(200)
    expect(spy).toHaveBeenCalledTimes(2)
  })

  it('gives up after four tries more, with growing waits, and answers 503 JSON', async () => {
    const wait = vi.spyOn(timing, 'wait').mockResolvedValue()
    const spy = vi.spyOn(globalThis, 'fetch').mockImplementation(async () => refusal())
    const res = await call('/api/health', { headers: ACCESS })
    expect(res.status).toBe(503)
    expect(await res.json()).toEqual({ error: 'engine_unavailable' })
    expect(spy).toHaveBeenCalledTimes(RETRY_DELAYS_MS.length + 1)
    expect(wait.mock.calls.map(([ms]) => ms)).toEqual([...RETRY_DELAYS_MS])
  })

  it('never retries an answer from the engine itself, a JSON 500 included', async () => {
    const wait = vi.spyOn(timing, 'wait').mockResolvedValue()
    const spy = engineAnswers({ error: 'internal' }, 500)
    const res = await call('/api/health', { headers: ACCESS })
    expect(res.status).toBe(500)
    expect(await res.json()).toEqual({ error: 'internal' })
    expect(spy).toHaveBeenCalledTimes(1)
    expect(wait).not.toHaveBeenCalled()
  })

  it('sends a POST body again on the second try', async () => {
    vi.spyOn(timing, 'wait').mockResolvedValue()
    const spy = vi.spyOn(globalThis, 'fetch')
      .mockImplementationOnce(async () => refusal())
      .mockImplementationOnce(async () => engineOk())
    await call('/api/probe/garmin', {
      method: 'POST',
      headers: { ...ACCESS, 'content-type': 'application/json' },
      body: JSON.stringify({ confirm: 'owner-approved' }),
    })
    for (const [, init] of spy.mock.calls as [URL, RequestInit][]) {
      expect(new TextDecoder().decode(init.body as ArrayBuffer)).toBe('{"confirm":"owner-approved"}')
    }
  })
})
