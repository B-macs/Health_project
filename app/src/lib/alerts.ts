// Timer alerts on the phone (rebuild Phase 6, inventory T87; the owner's choice, 2026-10-20:
// "Yes id like a push alert"). An iPhone web app runs no code while the phone is locked, so a
// rest or a hold that ends then cannot ring by itself.
//
// - Switched on from a tap in Settings: iOS asks for permission only after a tap, and only in
//   the app opened from the Home Screen. The phone subscribes for Web Push with the Worker's
//   public key and gives the Worker its subscription.
// - During a session, when a countdown runs and the app goes to the background, the phone asks
//   for an alert at the countdown's end (worker/src/alerts.ts keeps it and sends it on the
//   second); when the app comes back first, it cancels it. Both requests are "keepalive", so
//   they finish after the page stops.
// - iOS has no pushsubscriptionchange event, so every app start sends the subscription again,
//   and a changed server key means subscribing again (Lauscher's client is the model).
//
// The words of an alert are the app's own strings; what comes next (the bell's ending, the
// next entry) is what the engine's walk already says. No rule is decided here.
import { getSetting, KEYS, setSetting, type HealthDB } from '../db/schema'
import { S } from '../strings'
import { api, ApiError } from './api'
import type { Ctx } from './cache'
import { isStandalone } from './standalone'
import { endsAt, isRunning, type Timer } from './timers'
import { currentStep, exerciseOf, type TrainingState } from './training'

export type AlertSupport = 'ready' | 'install-first' | 'denied' | 'unsupported'
export type EnableResult = 'on' | 'denied' | 'not-configured' | 'failed'

/** What the Worker keeps for one countdown (worker/src/alerts.ts parseAlert). */
export interface TimerAlert {
  at: number
  title: string
  body: string
  tag: 'rest' | 'hold' | 'activity'
}

export interface Host {
  userAgent: string
  standalone: boolean
  push: boolean
  permission: NotificationPermission | null
}

/** The phone as this module sees it. */
export function host(): Host {
  const push = typeof navigator !== 'undefined' && 'serviceWorker' in navigator
    && typeof window !== 'undefined' && 'PushManager' in window && 'Notification' in window
  return {
    userAgent: typeof navigator === 'undefined' ? '' : navigator.userAgent,
    standalone: isStandalone(),
    push,
    permission: push ? Notification.permission : null,
  }
}

export function alertSupport(h: Host = host()): AlertSupport {
  if (/iPhone|iPad|iPod/.test(h.userAgent) && !h.standalone) return 'install-first'
  if (!h.push) return 'unsupported'
  return h.permission === 'denied' ? 'denied' : 'ready'
}

function keyBytes(base64url: string): Uint8Array<ArrayBuffer> {
  const text = atob(base64url.replace(/-/g, '+').replace(/_/g, '/').padEnd(Math.ceil(base64url.length / 4) * 4, '='))
  return Uint8Array.from(text, (c) => c.charCodeAt(0))
}

async function serverKey(ctx: Ctx): Promise<string | null | 'not-configured'> {
  try {
    return (await api<{ key: string }>('/api/push/key', { key: ctx.key, engineDown: false })).key
  } catch (err) {
    return err instanceof ApiError && err.code === 'push_not_configured' ? 'not-configured' : null
  }
}

async function subscribed(key: string, stored: string | null): Promise<PushSubscription> {
  const registration = await navigator.serviceWorker.ready
  let current = await registration.pushManager.getSubscription()
  if (current && stored !== key) {
    await current.unsubscribe()
    current = null
  }
  return current ?? registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(key) })
}

async function sendSubscription(ctx: Ctx, sub: PushSubscription): Promise<boolean> {
  const { endpoint, keys } = sub.toJSON()
  try {
    await api('/api/push/subscription', { method: 'PUT', key: ctx.key, engineDown: false, body: { endpoint, keys } })
    return true
  } catch {
    return false
  }
}

/** From a tap in Settings. */
export async function enableAlerts(store: HealthDB, ctx: Ctx): Promise<EnableResult> {
  if ((await Notification.requestPermission()) !== 'granted') return 'denied'
  const key = await serverKey(ctx)
  if (key === 'not-configured') return 'not-configured'
  if (!key) return 'failed'
  try {
    const sub = await subscribed(key, await getSetting<string | null>(store, KEYS.pushKey, null))
    if (!(await sendSubscription(ctx, sub))) return 'failed'
  } catch {
    return 'failed'
  }
  await setSetting(store, KEYS.pushKey, key)
  await setSetting(store, KEYS.alerts, true)
  return 'on'
}

export async function disableAlerts(store: HealthDB, ctx: Ctx): Promise<void> {
  await setSetting(store, KEYS.alerts, false)
  try {
    await (await (await navigator.serviceWorker.ready).pushManager.getSubscription())?.unsubscribe()
  } catch {
    // already gone
  }
  await api('/api/push/subscription', { method: 'DELETE', key: ctx.key, engineDown: false }).catch(() => undefined)
}

export async function sendTestAlert(ctx: Ctx): Promise<boolean> {
  try {
    await api('/api/push/test', {
      method: 'POST', key: ctx.key, engineDown: false, body: { title: S.app, body: S.settings.alertsTestBody },
    })
    return true
  } catch {
    return false
  }
}

/** At every app start while the alerts are on: the subscription again, and a new one when the
 *  server key changed or iOS dropped it; a permission taken away turns the alerts off. */
export async function refreshAlerts(store: HealthDB, ctx: Ctx): Promise<void> {
  if (!(await getSetting(store, KEYS.alerts, false))) return
  if (alertSupport() !== 'ready' || Notification.permission !== 'granted') {
    if (alertSupport() === 'denied') await setSetting(store, KEYS.alerts, false)
    return
  }
  const key = await serverKey(ctx)
  if (!key || key === 'not-configured') return
  try {
    const sub = await subscribed(key, await getSetting<string | null>(store, KEYS.pushKey, null))
    if (await sendSubscription(ctx, sub)) await setSetting(store, KEYS.pushKey, key)
  } catch {
    // the next start tries again
  }
}

/** What the alert says when countdown `t`, on the flow's current entry, ends; null for a
 *  timer that does not end by itself (the stopwatch) or is not running. */
export function alertFor(s: TrainingState, t: Timer): TimerAlert | null {
  const step = currentStep(s)
  const ex = exerciseOf(s, step)
  const at = endsAt(t)
  if (!step || !ex || at == null || !isRunning(t)) return null
  if (t.kind === 'rest') {
    const next = s.plan.steps[s.step + 1]
    const nextEx = next ? exerciseOf(s, next) : null
    const what = next && nextEx
      ? S.session.alertNext(`${S.session.setN(next.set_num)}${nextEx.laterality === 'unilateral' ? ` · ${S.session.side[next.side]}` : ''}`, nextEx.name)
      : ex.name
    return { at, title: S.session.alertRest, body: what, tag: 'rest' }
  }
  if (t.kind === 'hold') {
    return { at, title: S.session.alertHold[step.ending ?? 'continue'] ?? S.session.alertHold.continue, body: ex.name, tag: 'hold' }
  }
  if (t.kind === 'duration') return { at, title: S.session.alertActivity, body: ex.name, tag: 'activity' }
  return null
}

/** Ask for the alert (the app goes to the background). Never fails the session. */
export function scheduleAlert(ctx: Ctx, alert: TimerAlert, fetchImpl?: typeof fetch): Promise<void> {
  return api('/api/push/alert', { method: 'PUT', key: ctx.key, engineDown: false, body: alert, keepalive: true, fetchImpl })
    .then(() => undefined, () => undefined)
}

/** Cancel it (the app is back before the countdown ended, or it ended here). */
export function cancelAlert(ctx: Ctx, fetchImpl?: typeof fetch): Promise<void> {
  return api('/api/push/alert', { method: 'DELETE', key: ctx.key, engineDown: false, keepalive: true, fetchImpl })
    .then(() => undefined, () => undefined)
}
