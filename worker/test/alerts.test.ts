// Rebuild Phase 6: the timer alerts (src/alerts.ts), inside workerd. The VAPID key pair is a
// throwaway one vitest.config.ts makes on every run, the phone's subscription is made here
// (WebCrypto), and the push service is a fetch spy, so nothing leaves the test and no key is
// ever stored.
import { runDurableObjectAlarm, runInDurableObject } from 'cloudflare:test'
import { env } from 'cloudflare:workers'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import {
  ALERT_LATE_MS, ALERT_MAX_AHEAD_MS, ALERT_TTL_S, type AlertEnv, fire, message, owner, parseAlert, parseSubscription,
} from '../src/alerts'
import { app, type Bindings } from '../src/index'

const ACCESS = { authorization: 'Bearer test-access-key' }
const PUSH = 'https://push.test/send/abc'
const b64 = (bytes: ArrayBuffer | Uint8Array) => {
  let text = ''
  for (const byte of new Uint8Array(bytes)) text += String.fromCharCode(byte)
  return btoa(text).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

let phone: { endpoint: string; keys: { p256dh: string; auth: string } }
const keyed = env as unknown as Bindings
const plain = keyed
const unkeyed: Bindings = { ...keyed, VAPID_PUBLIC_KEY: '', VAPID_PRIVATE_KEY: '' }

beforeAll(async () => {
  const browser = await crypto.subtle.generateKey({ name: 'ECDH', namedCurve: 'P-256' }, true, ['deriveBits']) as CryptoKeyPair
  phone = {
    endpoint: PUSH,
    keys: {
      p256dh: b64(await crypto.subtle.exportKey('raw', browser.publicKey) as ArrayBuffer),
      auth: b64(crypto.getRandomValues(new Uint8Array(16))),
    },
  }
})

afterEach(async () => {
  vi.restoreAllMocks()
  await owner(plain).unsubscribe()
})

interface Sent { url: string; headers: Headers; body: Uint8Array }

/** The push service answers `status`; returns what it got. The body is copied at once: a
 *  request made inside the object cannot be read outside it. */
function pushService(status = 201): Sent[] {
  const got: Sent[] = []
  const real = globalThis.fetch
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const request = new Request(input as RequestInfo, init)
    if (!request.url.startsWith('https://push.test/')) return real(input as RequestInfo, init)
    got.push({ url: request.url, headers: request.headers, body: new Uint8Array(await request.arrayBuffer()) })
    return new Response(null, { status })
  })
  return got
}

const call = (e: Bindings, path: string, init: RequestInit = {}) =>
  app.fetch(new Request(`https://health.test${path}`, { ...init, headers: { ...ACCESS, ...(init.headers ?? {}) } }), e)

const json = (body: unknown): RequestInit => ({ body: JSON.stringify(body), headers: { 'content-type': 'application/json' } })

describe('the shapes it accepts', () => {
  it('a subscription is the phone\'s own toJSON(), nothing else', () => {
    expect(parseSubscription({ ...phone, expirationTime: null })).toEqual(phone)
    expect(parseSubscription({ ...phone, endpoint: 'http://push.test/x' })).toBeNull()
    expect(parseSubscription({ ...phone, extra: 1 })).toBeNull()
    expect(parseSubscription({ endpoint: PUSH, keys: { p256dh: '', auth: 'a' } })).toBeNull()
  })

  it('an alert is for a moment still to come, with words of a sane length', () => {
    const now = Date.UTC(2026, 9, 20, 9, 0)
    const alert = { at: now + 90_000, title: 'Rest over', body: 'Next: set 2', tag: 'rest' }
    expect(parseAlert(alert, now)).toEqual(alert)
    expect(parseAlert({ ...alert, at: now - ALERT_LATE_MS - 1 }, now)).toBeNull()
    expect(parseAlert({ ...alert, at: now + ALERT_MAX_AHEAD_MS + 1 }, now)).toBeNull()
    expect(parseAlert({ ...alert, title: '' }, now)).toBeNull()
    expect(parseAlert({ ...alert, title: 'x'.repeat(81) }, now)).toBeNull()
    expect(parseAlert({ ...alert, tag: 'Not A Tag' }, now)).toBeNull()
    expect(parseAlert({ ...alert, why: 'no' }, now)).toBeNull()
  })

  it('the message is declarative (iOS shows it by itself) and opens Training', () => {
    expect(message({ title: 'Rest over', body: 'Next: set 2', tag: 'rest' }, 'https://health.test')).toEqual({
      web_push: 8030,
      notification: { title: 'Rest over', body: 'Next: set 2', lang: 'en', navigate: 'https://health.test/#/training', tag: 'rest' },
      mutable: true,
    })
  })
})

describe('the routes', () => {
  it('need the key, and answer 503 while no VAPID key is set', async () => {
    expect((await app.fetch(new Request('https://health.test/api/push/key'), keyed)).status).toBe(401)
    const missing = await call(unkeyed, '/api/push/key')
    expect(missing.status).toBe(503)
    expect(await missing.json()).toEqual({ error: 'push_not_configured' })
    const ready = await call(keyed, '/api/push/key')
    expect(await ready.json()).toEqual({ key: keyed.VAPID_PUBLIC_KEY })
  })

  it('never send /api/push to the engine', async () => {
    const engine = vi.spyOn(globalThis, 'fetch')
    await call(keyed, '/api/push/subscription', { method: 'PUT', ...json(phone) })
    await call(keyed, '/api/push/alert', { method: 'DELETE' })
    expect(engine).not.toHaveBeenCalled()
  })

  it('an alert needs a subscription, and waits in the object until its moment', async () => {
    const at = Date.now() + 90_000
    const alert = { at, title: 'Rest over', body: 'Next: set 2 of the squat', tag: 'rest' }
    expect((await call(keyed, '/api/push/alert', { method: 'PUT', ...json(alert) })).status).toBe(409)
    expect((await call(keyed, '/api/push/subscription', { method: 'PUT', ...json(phone) })).status).toBe(204)
    expect((await call(keyed, '/api/push/alert', { method: 'PUT', ...json({ ...alert, at: 1 }) })).status).toBe(400)
    expect((await call(keyed, '/api/push/alert', { method: 'PUT', ...json(alert) })).status).toBe(204)
    await runInDurableObject(owner(plain), async (_object, state) => {
      expect(await state.storage.getAlarm()).toBe(at)
      expect(await state.storage.get('alert')).toEqual({ ...alert, origin: 'https://health.test' })
    })
    // The phone came back first: the alert is cancelled, and nothing will be sent.
    expect((await call(keyed, '/api/push/alert', { method: 'DELETE' })).status).toBe(204)
    await runInDurableObject(owner(plain), async (_object, state) => {
      expect(await state.storage.getAlarm()).toBeNull()
      expect(await state.storage.get('alert')).toBeUndefined()
    })
  })

  it('a newer alert replaces the one waiting', async () => {
    await call(keyed, '/api/push/subscription', { method: 'PUT', ...json(phone) })
    const first = { at: Date.now() + 60_000, title: 'Rest over', body: '', tag: 'rest' }
    const second = { at: Date.now() + 120_000, title: 'Swap sides', body: '', tag: 'hold' }
    await call(keyed, '/api/push/alert', { method: 'PUT', ...json(first) })
    await call(keyed, '/api/push/alert', { method: 'PUT', ...json(second) })
    await runInDurableObject(owner(plain), async (_object, state) => {
      expect(await state.storage.getAlarm()).toBe(second.at)
      expect((await state.storage.get<{ title: string }>('alert'))?.title).toBe('Swap sides')
    })
  })

  it('a test alert goes out at once, and says when the phone has no subscription', async () => {
    expect((await call(keyed, '/api/push/test', { method: 'POST', ...json({ title: 'Health' }) })).status).toBe(404)
    await call(keyed, '/api/push/subscription', { method: 'PUT', ...json(phone) })
    const got = pushService(201)
    const response = await call(keyed, '/api/push/test', { method: 'POST', ...json({ title: 'Health', body: 'Alerts are on.' }) })
    expect(response.status).toBe(200)
    expect(got).toHaveLength(1)
  })
})

describe('the alarm', () => {
  const alert = { at: Date.now() + 90_000, title: 'Rest over', body: 'Next: set 2', tag: 'rest', origin: 'https://health.test' }

  it('sends the waiting alert once, encrypted, urgent and short-lived, then forgets it', async () => {
    const got = pushService(201)
    await runInDurableObject(owner(plain), async (_object, state) => {
      await state.storage.put('subscription', phone)
      await state.storage.put('alert', alert)
      expect(await fire(state.storage, keyed as AlertEnv)).toBe('sent:201')
      expect(await state.storage.get('alert')).toBeUndefined()
      expect(await fire(state.storage, keyed as AlertEnv)).toBe('no-alert')
    })
    expect(got).toHaveLength(1)
    const sent = got[0]
    expect(sent.url).toBe(PUSH)
    expect(sent.headers.get('content-encoding')).toBe('aes128gcm')
    expect(sent.headers.get('urgency')).toBe('high')
    expect(sent.headers.get('ttl')).toBe(String(ALERT_TTL_S))
    expect(sent.headers.get('topic')).toBeNull()
    expect(sent.headers.get('authorization')).toMatch(/^vapid t=.+, k=.+/)
    // The words are encrypted for the phone: they never travel readable.
    expect(sent.body.length).toBeGreaterThan(0)
    expect(new TextDecoder().decode(sent.body)).not.toContain('Rest over')
  })

  it('drops a subscription the push service no longer knows', async () => {
    pushService(410)
    await runInDurableObject(owner(plain), async (_object, state) => {
      await state.storage.put('subscription', phone)
      await state.storage.put('alert', alert)
      expect(await fire(state.storage, keyed as AlertEnv)).toBe('sent:410')
      expect(await state.storage.get('subscription')).toBeUndefined()
    })
  })

  it('a push service that fails is not retried: a late timer alert is of no use', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('network'))
    await runInDurableObject(owner(plain), async (_object, state) => {
      await state.storage.put('subscription', phone)
      await state.storage.put('alert', alert)
      expect(await fire(state.storage, keyed as AlertEnv)).toBe('failed')
      expect(await state.storage.get('alert')).toBeUndefined()
    })
  })

  it('fires at its moment through the object, once', async () => {
    const got = pushService(201)
    const stub = owner(plain)
    await stub.subscribe(phone)
    await stub.schedule({ at: Date.now() + 60_000, title: 'Rest over', body: '', tag: 'rest' }, 'https://health.test')
    expect(await runDurableObjectAlarm(stub)).toBe(true)
    expect(got).toHaveLength(1)
    expect(await runDurableObjectAlarm(stub)).toBe(false)
    await runInDurableObject(stub, async (_object, state) => {
      expect(await state.storage.get('alert')).toBeUndefined()
    })
  })

  it('sends nothing without the keys', async () => {
    const spy = vi.spyOn(globalThis, 'fetch')
    await runInDurableObject(owner(plain), async (_object, state) => {
      await state.storage.put('subscription', phone)
      await state.storage.put('alert', alert)
      expect(await fire(state.storage, unkeyed as AlertEnv)).toBe('not-configured')
    })
    expect(spy).not.toHaveBeenCalled()
  })
})
