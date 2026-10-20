// Timer alerts by Web Push (rebuild Phase 6, inventory T87; the owner's choice, 2026-10-20:
// "Yes id like a push alert"). An iPhone web app runs no code while the phone is locked, so
// a rest or a hold that ends then cannot ring by itself. When a countdown runs and the app
// goes to the background, the phone asks for an alert at the countdown's end; when the app
// comes back first, it cancels it.
//
// The alert waits in ONE Durable Object ("owner": one athlete, one phone): it keeps the
// phone's push subscription and at most one alert, and its alarm fires on the second
// (developers.cloudflare.com/durable-objects/api/alarms/). Durable Objects are on the Workers
// Free plan with SQLite storage only, 100,000 requests a day; past a limit an operation fails
// and nothing is billed (durable-objects/platform/pricing, checked 2026-10-20). A session
// needs a few dozen alarms.
//
// Pushes go out as Lauscher's do (worker/src/push/push.ts there): @block65/webcrypto-web-push
// (RFC 8291 aes128gcm, RFC 8292 VAPID), urgency high, no Topic header (Apple refuses it), as
// a declarative message that iOS shows by itself (iOS 18.4+), so an alert is never lost to a
// service worker that did not wake. A short time to live: a timer alert that arrives late is
// of no use. An alert is sent once and never retried for the same reason.
//
// The Worker holds no training rule (rebuild rule 1): the phone sends the alert's words and
// its moment; this file only checks their shape and keeps the time.
import { buildPushPayload } from '@block65/webcrypto-web-push'
import { DurableObject } from 'cloudflare:workers'
import type { Hono } from 'hono'

export type AlertEnv = {
  ALERTS: DurableObjectNamespace<TimerAlerts>
  VAPID_PUBLIC_KEY?: string
  VAPID_PRIVATE_KEY?: string
  VAPID_SUBJECT?: string
}

export interface Subscription {
  endpoint: string
  keys: { p256dh: string; auth: string }
}

export interface Alert {
  /** When to send it: epoch milliseconds, the countdown's end on the phone's clock. */
  at: number
  title: string
  body: string
  tag: string
}

export interface DeclarativeMessage {
  web_push: 8030
  notification: { title: string; body: string; lang: string; navigate: string; tag: string }
  mutable: true
}

/** The longest an alert may wait: the longest activity timer, never a stale alert. */
export const ALERT_MAX_AHEAD_MS = 3 * 60 * 60 * 1000
/** How late an alert may still be sent (the phone's clock against Cloudflare's). */
export const ALERT_LATE_MS = 60 * 1000
/** How long the push service keeps an alert the phone cannot take: late is of no use. */
export const ALERT_TTL_S = 300

const MAX_BODY = 4 * 1024
const SUBSCRIPTION_FIELDS = new Set(['endpoint', 'keys', 'expirationTime'])
const ALERT_FIELDS = new Set(['at', 'title', 'body', 'tag'])
const NO_STORE = { 'Cache-Control': 'no-store' }

export function configured(env: Partial<AlertEnv>): boolean {
  return Boolean(env.VAPID_PUBLIC_KEY && env.VAPID_PRIVATE_KEY && env.VAPID_SUBJECT)
}

const isObject = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === 'object' && !Array.isArray(value)

const onlyKnown = (body: Record<string, unknown>, known: Set<string>) => Object.keys(body).every((key) => known.has(key))

/** The phone's PushSubscription (its toJSON()), or null if anything is off. */
export function parseSubscription(body: unknown): Subscription | null {
  if (!isObject(body) || !onlyKnown(body, SUBSCRIPTION_FIELDS)) return null
  const keys = body.keys
  if (typeof body.endpoint !== 'string' || !body.endpoint.startsWith('https://') || body.endpoint.length > 2000) return null
  if (!isObject(keys) || typeof keys.p256dh !== 'string' || typeof keys.auth !== 'string' || !keys.p256dh || !keys.auth
    || keys.p256dh.length > 200 || keys.auth.length > 100) return null
  return { endpoint: body.endpoint, keys: { p256dh: keys.p256dh, auth: keys.auth } }
}

/** An alert for `now`, or null: words of a sane length and a moment that is still to come. */
export function parseAlert(body: unknown, now: number): Alert | null {
  if (!isObject(body) || !onlyKnown(body, ALERT_FIELDS)) return null
  const { at, title, tag } = body
  const text = body.body
  if (typeof at !== 'number' || !Number.isFinite(at) || at < now - ALERT_LATE_MS || at > now + ALERT_MAX_AHEAD_MS) return null
  if (typeof title !== 'string' || !title || title.length > 80) return null
  if (typeof text !== 'string' || text.length > 200) return null
  if (typeof tag !== 'string' || !/^[a-z0-9-]{1,40}$/.test(tag)) return null
  return { at, title, body: text, tag }
}

export function message(alert: Pick<Alert, 'title' | 'body' | 'tag'>, origin: string): DeclarativeMessage {
  return {
    web_push: 8030,
    notification: { title: alert.title, body: alert.body, lang: 'en', navigate: `${origin}/#/training`, tag: alert.tag },
    mutable: true,
  }
}

/** Send one push; returns the push service's status (201 sent, 404 or 410 subscription gone). */
export async function sendPush(env: AlertEnv, sub: Subscription, data: DeclarativeMessage): Promise<number> {
  const payload = await buildPushPayload({ data: data as never, options: { ttl: ALERT_TTL_S, urgency: 'high' } },
    { endpoint: sub.endpoint, expirationTime: null, keys: sub.keys },
    { subject: env.VAPID_SUBJECT!, publicKey: env.VAPID_PUBLIC_KEY!, privateKey: env.VAPID_PRIVATE_KEY! })
  const response = await fetch(sub.endpoint, payload)
  await response.body?.cancel()
  return response.status
}

type Stored = Alert & { origin: string }

/** The alarm's work, on the object's storage: send the waiting alert once, then forget it;
 *  a subscription the push service no longer knows is dropped. Returns what happened. */
export async function fire(storage: DurableObjectStorage, env: AlertEnv): Promise<string> {
  const alert = await storage.get<Stored>('alert')
  await storage.delete('alert')
  const sub = await storage.get<Subscription>('subscription')
  if (!alert) return 'no-alert'
  if (!sub) return 'no-subscription'
  if (!configured(env)) return 'not-configured'
  try {
    const status = await sendPush(env, sub, message(alert, alert.origin))
    if (status === 404 || status === 410) await storage.delete('subscription')
    return `sent:${status}`
  } catch (err) {
    console.error('timer alert: the push failed', err)
    return 'failed'
  }
}

/** The one object that keeps the subscription and the waiting alert. */
export class TimerAlerts extends DurableObject<AlertEnv> {
  async subscribe(sub: Subscription): Promise<void> {
    await this.ctx.storage.put('subscription', sub)
  }

  async unsubscribe(): Promise<void> {
    await this.ctx.storage.delete('subscription')
    await this.cancel()
  }

  async hasSubscription(): Promise<boolean> {
    return (await this.ctx.storage.get('subscription')) !== undefined
  }

  /** Keep `alert` and wake at its moment; a newer alert replaces the one waiting. */
  async schedule(alert: Alert, origin: string): Promise<void> {
    await this.ctx.storage.put('alert', { ...alert, origin } satisfies Stored)
    await this.ctx.storage.setAlarm(alert.at)
  }

  async cancel(): Promise<void> {
    await this.ctx.storage.delete('alert')
    await this.ctx.storage.deleteAlarm()
  }

  /** A test alert now (Settings). Not named "test": the call layer refuses that name. */
  async sendTest(origin: string, title: string, body: string): Promise<string> {
    await this.ctx.storage.put('alert', { at: Date.now(), title, body, tag: 'test', origin } satisfies Stored)
    return fire(this.ctx.storage, this.env)
  }

  async alarm(): Promise<void> {
    const outcome = await fire(this.ctx.storage, this.env)
    if (!outcome.startsWith('sent:2')) console.log('timer alert:', outcome)
  }
}

export function owner(env: AlertEnv): DurableObjectStub<TimerAlerts> {
  return env.ALERTS.get(env.ALERTS.idFromName('owner'))
}

async function readJson(request: Request): Promise<unknown> {
  if (Number(request.headers.get('content-length') ?? '0') > MAX_BODY) return null
  try {
    const text = await request.text()
    return text.length > MAX_BODY ? null : JSON.parse(text)
  } catch {
    return null
  }
}

/** The /api/push routes. They sit behind the app's access key like every /api route, and
 *  they never reach the engine. */
export function alertRoutes<E extends { Bindings: AlertEnv }>(app: Hono<E>): void {
  app.get('/api/push/key', (c) => (configured(c.env)
    ? c.json({ key: c.env.VAPID_PUBLIC_KEY }, 200, NO_STORE)
    : c.json({ error: 'push_not_configured' }, 503, NO_STORE)))

  app.put('/api/push/subscription', async (c) => {
    const sub = parseSubscription(await readJson(c.req.raw))
    if (!sub) return c.json({ error: 'bad_subscription' }, 400, NO_STORE)
    await owner(c.env).subscribe(sub)
    return c.body(null, 204, NO_STORE)
  })

  app.delete('/api/push/subscription', async (c) => {
    await owner(c.env).unsubscribe()
    return c.body(null, 204, NO_STORE)
  })

  app.put('/api/push/alert', async (c) => {
    if (!configured(c.env)) return c.json({ error: 'push_not_configured' }, 503, NO_STORE)
    const alert = parseAlert(await readJson(c.req.raw), Date.now())
    if (!alert) return c.json({ error: 'bad_alert' }, 400, NO_STORE)
    const stub = owner(c.env)
    if (!(await stub.hasSubscription())) return c.json({ error: 'no_subscription' }, 409, NO_STORE)
    await stub.schedule(alert, new URL(c.req.url).origin)
    return c.body(null, 204, NO_STORE)
  })

  app.delete('/api/push/alert', async (c) => {
    await owner(c.env).cancel()
    return c.body(null, 204, NO_STORE)
  })

  app.post('/api/push/test', async (c) => {
    if (!configured(c.env)) return c.json({ error: 'push_not_configured' }, 503, NO_STORE)
    const body = await readJson(c.req.raw)
    const title = isObject(body) && typeof body.title === 'string' ? body.title.slice(0, 80) : 'Health'
    const text = isObject(body) && typeof body.body === 'string' ? body.body.slice(0, 200) : ''
    const outcome = await owner(c.env).sendTest(new URL(c.req.url).origin, title, text)
    if (outcome === 'no-subscription') return c.json({ error: 'no_subscription' }, 404, NO_STORE)
    if (outcome.startsWith('sent:2')) return c.json({ sent: true }, 200, NO_STORE)
    if (outcome === 'sent:404' || outcome === 'sent:410') return c.json({ error: 'subscription_gone' }, 410, NO_STORE)
    return c.json({ error: 'push_failed' }, 502, NO_STORE)
  })
}
