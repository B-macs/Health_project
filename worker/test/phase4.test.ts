// Rebuild Phase 4: the daily data check and the sync switch, inside workerd. The engine
// is never called: global fetch is replaced, so each test sees exactly what would leave
// Cloudflare.
import { createExecutionContext, createScheduledController, waitOnExecutionContext } from 'cloudflare:test'
import { env, exports } from 'cloudflare:workers'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import worker, { app, ENGINE_TIMEOUT_MS, LAST_CHECK, SYNC_PATHS, SYNC_TIMEOUT_MS, type Bindings } from '../src/index'

// The secrets are test bindings (vitest.config.ts), not in the generated Env type.
const ENV = env as unknown as Bindings

const ACCESS = { authorization: 'Bearer test-access-key' }

const CHECK = {
  checked_at: '2026-10-20T04:15:03Z',
  backup_name: 'health-2026-10-19.db.gz',
  backup_day: '2026-10-19',
  backup_stale: false,
  missing_rows: 0,
  tables: [],
}

function call(path: string, init: RequestInit = {}): Promise<Response> {
  return exports.default.fetch(new Request(`https://health.test${path}`, init))
}

function engineAnswers(body: unknown, status = 200) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(
    async () => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } }),
  )
}

beforeEach(async () => {
  await env.STATE.delete(LAST_CHECK)
})

afterEach(() => vi.restoreAllMocks())

describe('the last data check', () => {
  it('is null until a check ran, and needs the key', async () => {
    const spy = engineAnswers(CHECK)
    expect((await call('/api/data/check/last')).status).toBe(401)
    const res = await call('/api/data/check/last', { headers: ACCESS })
    expect(res.status).toBe(200)
    expect(await res.json()).toBeNull()
    expect(res.headers.get('cache-control')).toBe('no-store')
    expect(spy).not.toHaveBeenCalled()
  })

  it('is answered from KV, with the engine asleep', async () => {
    await env.STATE.put(LAST_CHECK, JSON.stringify(CHECK))
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('network'))
    const res = await call('/api/data/check/last', { headers: ACCESS })
    expect(await res.json()).toEqual(CHECK)
  })
})

describe('running the check', () => {
  it('"Check now" asks the engine with its key, keeps the answer, and returns it', async () => {
    const spy = engineAnswers(CHECK)
    const res = await call('/api/data/check/run', { method: 'POST', headers: ACCESS })
    expect(res.status).toBe(200)
    expect(await res.json()).toEqual(CHECK)
    const [target, init] = spy.mock.calls[0] as [URL, RequestInit]
    expect(String(target)).toBe('https://engine.test/api/data/check')
    expect(init.method).toBe('GET')
    expect(new Headers(init.headers).get('x-engine-key')).toBe('test-engine-key')
    expect(await env.STATE.get(LAST_CHECK, 'json')).toEqual(CHECK)
  })

  it('with the engine down, the last good check stays', async () => {
    await env.STATE.put(LAST_CHECK, JSON.stringify(CHECK))
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('network'))
    const res = await call('/api/data/check/run', { method: 'POST', headers: ACCESS })
    expect(res.status).toBe(503)
    expect(await res.json()).toEqual({ error: 'engine_unavailable' })
    expect(await env.STATE.get(LAST_CHECK, 'json')).toEqual(CHECK)
  })

  it('an engine refusal is passed on and nothing is kept', async () => {
    engineAnswers({ error: 'store_unavailable' }, 503)
    const res = await call('/api/data/check/run', { method: 'POST', headers: ACCESS })
    expect(res.status).toBe(503)
    expect(await res.json()).toEqual({ error: 'store_unavailable' })
    expect(await env.STATE.get(LAST_CHECK)).toBeNull()
  })

  it('the daily trigger runs the same check and keeps its answer', async () => {
    const spy = engineAnswers(CHECK)
    const ctx = createExecutionContext()
    await worker.scheduled(createScheduledController({ cron: '15 4 * * *' }), ENV, ctx)
    await waitOnExecutionContext(ctx)
    expect(spy).toHaveBeenCalledTimes(1)
    expect(String((spy.mock.calls[0] as [URL])[0])).toBe('https://engine.test/api/data/check')
    expect(await env.STATE.get(LAST_CHECK, 'json')).toEqual(CHECK)
  })

  it('the daily trigger never syncs: it sends one read and nothing else', async () => {
    const spy = engineAnswers(CHECK)
    const ctx = createExecutionContext()
    await worker.scheduled(createScheduledController({ cron: '15 4 * * *' }), ENV, ctx)
    await waitOnExecutionContext(ctx)
    const methods = (spy.mock.calls as [URL, RequestInit][]).map(([url, init]) => `${init.method} ${new URL(url).pathname}`)
    expect(methods).toEqual(['GET /api/data/check'])
  })
})

// The switch-over turned the syncs on (2026-10-21, switch step 4). The lock itself is still
// tested: with the switch off in the test's own bindings, every sync path stays shut.
const OFF = { ...env, SYNC_ENABLED: 'false' } as never

describe('the sync switch', () => {
  it('is on in the config since the switch-over (2026-10-21)', () => {
    expect(env.SYNC_ENABLED).toBe('true')
  })

  it('lets a sync through the Worker as deployed', async () => {
    const spy = engineAnswers({ ran: true })
    const res = await call('/api/sync', { method: 'POST', headers: ACCESS })
    expect(res.status).toBe(200)
    expect(spy).toHaveBeenCalledTimes(1)
  })

  it.each([
    ['POST', '/api/sync'],
    ['POST', '/api/data/sync/garmin_daily'],
    ['POST', '/api/oura/login'],
    ['POST', '/api/oura/callback'],
  ])('closes %s %s while off, and the engine is never called', async (method, path) => {
    const spy = engineAnswers({ ok: true })
    const res = await app.request(path, { method, headers: { ...ACCESS, 'content-type': 'application/json' }, body: '{}' }, OFF)
    expect(res.status).toBe(409)
    expect(await res.json()).toEqual({ error: 'sync_disabled' })
    expect(spy).not.toHaveBeenCalled()
  })

  it('names only the syncs and the Oura login', () => {
    for (const path of ['/api/sync', '/api/sync/x', '/api/data/sync/oura_weekly', '/api/oura/login']) {
      expect(SYNC_PATHS.test(path), path).toBe(true)
    }
    for (const path of ['/api/status', '/api/syncs', '/api/data/check', '/api/data/session-checks', '/api/health']) {
      expect(SYNC_PATHS.test(path), path).toBe(false)
    }
  })

  it('opens when it is "true" (the switch-over)', async () => {
    const spy = engineAnswers({ ran: true })
    const on = { ...env, SYNC_ENABLED: 'true' } as never
    const res = await app.request('/api/sync', { method: 'POST', headers: ACCESS }, on)
    expect(res.status).toBe(200)
    expect(spy).toHaveBeenCalledTimes(1)
  })

  it('gives a sync the longer wait, and every other path the usual one', async () => {
    const timeouts: number[] = []
    const real = AbortSignal.timeout.bind(AbortSignal)
    vi.spyOn(AbortSignal, 'timeout').mockImplementation((ms: number) => {
      timeouts.push(ms)
      return real(ms)
    })
    engineAnswers({ ran: true })
    const on = { ...env, SYNC_ENABLED: 'true' } as never
    await app.request('/api/sync', { method: 'POST', headers: ACCESS }, on)
    await app.request('/api/status', { headers: ACCESS }, on)
    expect(timeouts).toEqual([SYNC_TIMEOUT_MS, ENGINE_TIMEOUT_MS])
    expect(SYNC_TIMEOUT_MS).toBeGreaterThan(77_000)
    expect(SYNC_TIMEOUT_MS).toBeLessThan(300_000)
  })
})
