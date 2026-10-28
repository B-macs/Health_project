// The training session in the browser (rebuild Phase 6), on the mock engine's made-up
// session (dev/session_fixture.json, made by the engine's own walk). Chromium, and WebKit
// with the iPhone profile:
// - a whole session from Start to Save, offline in the middle: nothing needs the network
//   until Save, the save waits in the outbox, goes out once the phone is online again, and
//   the engine stores it once, with every set;
// - a save whose answer is lost is sent again with the same ids, and the engine keeps one;
// - an app kill in the middle opens the session again at the same place, with its numbers;
// - with a Garmin workout started: the walk takes its minutes from the watch (or, with no
//   connection, its planned minutes), the save screen checks the watch, and the heart-rate
//   match shows after the engine has the save.
// The gate (rebuild_gate.py p6) adds up three annotations of these tests:
// duplicate_sessions, fields_missing and warning_shown_when_not_due.
import type { Page } from '@playwright/test'
import fixture from '../dev/session_fixture.json' with { type: 'json' }
import { stepWeight } from '../src/lib/training'
import { S } from '../src/strings'
import { expect, hook, leaveSession, onboard, ORIGIN, startTraining, test, openTraining } from './helpers'

type Side = { reps: number | null; weight_kg: number | null; seconds: number | null } | null
type RawSet = {
  set_num: number
  completed_at: string
  right: Side
  left: Side
  band_tier?: string | null
  rest_started_at?: number
  rest_ended_at?: number
}
type SaveBody = {
  session_id: string
  notes: string
  session_rpe: number
  duration_minutes: number
  exercises: { exercise_id: string; raw_sets: RawSet[]; garmin_minutes: number | null }[]
}
type Sent = { method: string; path: string; body: SaveBody }

/** The flow's screen (the save screen has no position). */
const flow = (page: Page) => page.locator('.screen.train[data-step]')

async function position(page: Page): Promise<number | 'save'> {
  return (await flow(page).count()) ? Number(await flow(page).getAttribute('data-step')) : 'save'
}

/** One tap of the main button, as the athlete would: the seconds typed first on the timed
 *  test; waits until the flow has moved. */
async function tap(page: Page): Promise<void> {
  const at = await position(page)
  const seconds = page.getByRole('spinbutton')
  if (await seconds.count()) await seconds.fill('30')
  await page.locator('.controls .btn--primary').click()
  await expect.poll(() => position(page)).not.toBe(at)
}

/** Tap through to the save screen. `atExercise` runs at each exercise's first entry. Returns
 *  the warnings shown on an exercise the engine sent none for, and those it did send. */
async function walk(page: Page, atExercise?: (index: number) => Promise<void>) {
  let shownNotDue = 0
  let shownDue = 0
  let seen = -1
  for (let taps = 0; taps <= fixture.steps.length; taps++) {
    const at = await position(page)
    if (at === 'save') return { shownNotDue, shownDue }
    const exIdx = fixture.steps[at].ex_idx
    if (exIdx !== seen) {
      seen = exIdx
      await expect(page.locator('.exercise__name')).toHaveText(fixture.exercises[exIdx].name)
      await atExercise?.(exIdx)
      const shown = await page.getByTestId('warning').count()
      if (fixture.exercises[exIdx].warning) shownDue += shown
      else shownNotDue += shown
    }
    await tap(page)
  }
  throw new Error('the session never reached the save screen')
}

/** Raw facts a set's record needs (the engine's build_set_record, the rule the Streamlit
 *  save uses) that the phone's save left out: the gate's fields_missing. */
function missingFacts(body: SaveBody): string[] {
  const missing: string[] = []
  body.exercises.forEach((e, i) => {
    const ex = fixture.exercises[i]
    for (const set of e.raw_sets) {
      const at = `${ex.name} set ${set.set_num}`
      if (!/[+-]\d\d:\d\d$/.test(set.completed_at)) missing.push(`${at}: time with its offset`)
      if (ex.type === 'reps' && set.right?.reps == null) missing.push(`${at}: reps`)
      if (ex.type === 'reps' && ex.laterality === 'unilateral' && set.left?.reps == null) missing.push(`${at}: left reps`)
      if (ex.equipment_type && ex.equipment_type !== 'band' && set.right?.weight_kg == null) missing.push(`${at}: weight`)
      if (ex.equipment_type === 'band' && !set.band_tier) missing.push(`${at}: band`)
      if (ex.timer === 'stopwatch' && set.right?.seconds == null) missing.push(`${at}: seconds`)
    }
  })
  // Every set the engine's walk says a rest follows carries the rest's two clock readings.
  for (const st of fixture.steps.filter((x) => x.rest_begins && x.record_set != null)) {
    const set = body.exercises[st.ex_idx].raw_sets.find((r) => r.set_num === st.record_set)
    if (set && (set.rest_started_at == null || set.rest_ended_at == null)) {
      missing.push(`${fixture.exercises[st.ex_idx].name} set ${st.record_set}: rest`)
    }
  }
  return missing
}

async function sends(page: Page, tag: string): Promise<SaveBody[]> {
  const all = (await (await page.request.get(`${ORIGIN}/api/dev/received`)).json()) as Sent[]
  return all.filter((r) => r.path === '/api/training/sessions' && r.body.notes === tag).map((r) => r.body)
}

async function stored(page: Page, tag: string): Promise<SaveBody[]> {
  const all = (await (await page.request.get(`${ORIGIN}/api/dev/sessions`)).json()) as SaveBody[]
  return all.filter((b) => b.notes === tag)
}

async function saveWithNotes(page: Page, tag: string): Promise<void> {
  await expect(page.getByRole('heading', { name: S.session.complete(fixture.day_num) })).toBeVisible()
  await page.getByRole('textbox', { name: S.session.sessionNotes }).fill(tag)
  await page.getByRole('button', { name: S.session.save }).click()
}

test('a whole session runs from Start to Save, offline in the middle, and is stored once', async ({ page, context }) => {
  const tag = `e2e-session-${Date.now()}`
  await onboard(page)
  await startTraining(page, { garmin: true })
  // Offline from the fourth exercise to the save: the session needs no network.
  const warnings = await walk(page, async (i) => {
    if (i === 3) await context.setOffline(true)
  })
  test.info().annotations.push({ type: 'warning_shown_when_not_due', description: String(warnings.shownNotDue) })
  expect(warnings.shownNotDue).toBe(0)
  expect(warnings.shownDue).toBe(fixture.exercises.filter((e) => e.warning).length)

  // Offline, the load is worked out when the save is sent, and the watch cannot be asked:
  // the walk keeps its planned minutes.
  await expect(page.getByText(S.session.loadLater)).toBeVisible()
  await expect(page.getByTestId('watch-check')).toHaveAttribute('data-state', 'offline')
  await expect(page.getByTestId('review-line')).toHaveCount(fixture.exercises.length)
  await saveWithNotes(page, tag)
  const state = page.getByTestId('save-state')
  await expect(state).toHaveAttribute('data-state', 'waiting')
  await expect(state).toContainText(S.session.savedPhone)
  await hook(page)
  expect(await page.evaluate(async () => (await window.__health!.outbox()).length)).toBe(1)
  expect(await sends(page, tag)).toEqual([])

  await context.setOffline(false)
  await expect(state).toHaveAttribute('data-state', 'confirmed', { timeout: 20_000 })
  await expect(state).toContainText(S.session.saved)
  // The engine has the session: the heart-rate match runs.
  await expect(page.getByTestId('hr')).toHaveAttribute('data-state', 'matched')

  const sent = await sends(page, tag)
  const kept = await stored(page, tag)
  test.info().annotations.push({ type: 'duplicate_sessions', description: String(Math.max(0, kept.length - 1)) })
  expect(sent).toHaveLength(1)
  expect(kept).toHaveLength(1)
  await expect(page.getByRole('heading', { name: S.session.congrats })).toBeVisible()
  await expect(page.getByText(S.session.tomorrow(fixture.next_day!.day_num, fixture.next_day!.objective))).toBeVisible()
  const body = sent[0]
  expect(body.session_rpe).toBe(5)
  const lacking = missingFacts(body)
  test.info().annotations.push({ type: 'fields_missing', description: String(lacking.length) })
  expect(lacking).toEqual([])
  expect(body.session_id).toMatch(new RegExp(`^${fixture.date.slice(0, 4)}-\\d\\d-\\d\\d-[0-9a-f]{8}$`))
  expect(body.exercises.map((e) => e.raw_sets.length)).toEqual(fixture.exercises.map((e) => e.sets))
  // Every set carries the phone's clock with its UTC offset; every rest that began ended.
  for (const set of body.exercises.flatMap((e) => e.raw_sets)) {
    expect(set.completed_at).toMatch(/T\d\d:\d\d:\d\d[+-]\d\d:\d\d$/)
    if (set.rest_started_at != null) expect(set.rest_ended_at).toBeGreaterThanOrEqual(set.rest_started_at)
  }
  const timed = fixture.exercises.findIndex((e) => e.timer === 'stopwatch')
  expect(body.exercises[timed].raw_sets[0].right?.seconds).toBe(30)
  const walked = fixture.exercises.findIndex((e) => e.garmin_pull)
  expect(body.exercises[walked].garmin_minutes).toBeNull()

  await page.getByRole('button', { name: S.session.done }).click()
  await expect(page.getByRole('heading', { name: S.today.title })).toBeVisible()
  expect(await page.evaluate(() => window.__health!.sessionActive())).toBe(false)
})

test('a save whose answer is lost is sent again with the same ids, and the engine keeps one', async ({ page, context }) => {
  const tag = `e2e-replay-${Date.now()}`
  await onboard(page)
  await startTraining(page, { garmin: true })
  await walk(page)
  // Online: the walk took its minutes from the watch, and the watch check found the workout.
  const walked = fixture.exercises.findIndex((e) => e.garmin_pull)
  await expect(page.getByTestId('notice')).toHaveText(S.session.garminPulled(31, fixture.exercises[walked].name))
  await expect(page.getByTestId('review-line').nth(walked)).toContainText(S.session.timeGarmin(31))
  await expect(page.getByTestId('watch-check')).toHaveAttribute('data-state', 'found')
  // The engine stores the save, and its answer is lost on the way back: the phone tries again.
  await context.addCookies([{ name: 'e2e_lose_answer', value: '1', url: ORIGIN }])
  await saveWithNotes(page, tag)
  await expect.poll(() => sends(page, tag).then((s) => s.length), { timeout: 30_000 }).toBeGreaterThanOrEqual(2)
  await context.clearCookies({ name: 'e2e_lose_answer' })
  await expect(page.getByTestId('save-state')).toHaveAttribute('data-state', 'confirmed', { timeout: 40_000 })

  const sent = await sends(page, tag)
  const kept = await stored(page, tag)
  test.info().annotations.push({ type: 'duplicate_sessions', description: String(Math.max(0, kept.length - 1)) })
  expect(sent.length).toBeGreaterThanOrEqual(3)
  expect(new Set(sent.map((b) => b.session_id)).size).toBe(1)
  expect(new Set(sent.map((b) => b.exercises.map((e) => e.exercise_id).join(','))).size).toBe(1)
  expect(kept).toHaveLength(1)
  expect(sent[0].exercises[walked].garmin_minutes).toBe(31)
  const lacking = [...missingFacts(sent[0]), ...(sent[0].exercises[walked].garmin_minutes == null ? ['the walk: Garmin minutes'] : [])]
  test.info().annotations.push({ type: 'fields_missing', description: String(lacking.length) })
  expect(lacking).toEqual([])
  await expect(page.getByTestId('hr')).toHaveAttribute('data-state', 'matched')
})

test('the overview offers the adapt dialog; a running watch is named; a session the watch cannot place asks which', async ({ page, context }) => {
  const tag = `e2e-choose-${Date.now()}`
  await onboard(page)
  await openTraining(page)
  // The overview: plan start, today and the day; the load banner; the workout card; the
  // lists; the at-home item and its how-to; the first side.
  await expect(page.getByRole('region', { name: S.session.blockProgress })).toContainText(S.session.planStart)
  await expect(page.locator('[data-kind="warning"]')).toBeVisible()
  await expect(page.getByTestId('workout-card')).toContainText(S.session.dayBig(fixture.day_num))
  await expect(page.getByTestId('workout-card')).toContainText(S.session.sessionsOf(fixture.day_num, fixture.plan_days))
  await expect(page.getByRole('region', { name: S.session.workout }).locator('.timeline__item')).toHaveCount(fixture.exercises.length)
  await page.getByRole('region', { name: S.session.atHome }).getByText('Made-up home stretch', { exact: false }).click()
  await expect(page.getByText('Made-up how-to for the tests.')).toBeVisible()
  await expect(page.getByText('Start each one-side exercise on the left side today.')).toBeVisible()
  await page.getByRole('button', { name: S.session.adapt }).click()
  const sheet = page.getByRole('dialog', { name: S.session.adapt })
  await expect(sheet.getByText(S.session.adaptNone)).toBeVisible()
  await sheet.getByRole('button', { name: S.session.close }).last().click()
  await expect(sheet).toBeHidden()
  // The watch is still running when the save screen opens: it says so, and checks again.
  await context.addCookies([{ name: 'e2e_watch', value: 'missing', url: ORIGIN },
    { name: 'e2e_hr', value: 'choose', url: ORIGIN }])
  await page.getByRole('switch', { name: S.session.garminDeclare }).check()
  await page.getByRole('button', { name: S.session.start }).click()
  await expect(page.locator('.exercise__name')).toBeVisible()
  await walk(page)
  const watch = page.getByTestId('watch-check')
  await expect(watch).toHaveAttribute('data-state', 'missing')
  await expect(watch).toContainText(S.session.watchStop)
  await context.clearCookies({ name: 'e2e_watch' })
  await watch.getByRole('button', { name: S.session.watchAgain }).click()
  await expect(watch).toHaveAttribute('data-state', 'found')
  // The engine cannot line the session up with the watch: the athlete picks the activity.
  await saveWithNotes(page, tag)
  const hr = page.getByTestId('hr')
  await expect(hr).toHaveAttribute('data-state', 'choose', { timeout: 20_000 })
  await hr.getByRole('radio').first().click()
  await hr.getByRole('button', { name: S.session.hrUse }).click()
  await expect(hr).toHaveAttribute('data-state', 'matched')
  await context.clearCookies({ name: 'e2e_hr' })
})

type AlertWrite = { method: string; path: string; body: { at: number; title: string; body: string; tag: string } | null }

async function alertWrites(page: Page): Promise<AlertWrite[]> {
  const all = (await (await page.request.get(`${ORIGIN}/api/dev/received`)).json()) as AlertWrite[]
  return all.filter((r) => r.path === '/api/push/alert')
}

/** The app goes to the background, or comes back (a test cannot lock the phone). */
async function visibility(page: Page, state: 'hidden' | 'visible'): Promise<void> {
  await page.evaluate((to) => {
    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => to })
    document.dispatchEvent(new Event('visibilitychange'))
  }, state)
}

test('with the alerts on, a rest that runs as the app goes to the background asks for an alert, and coming back cancels it', async ({ page }) => {
  await onboard(page)
  await hook(page)
  await page.evaluate(() => window.__health!.setSetting('timer_alerts', true))
  await startTraining(page)
  const rest = fixture.steps.findIndex((st) => st.phase === 'resting')
  while ((await position(page)) !== rest) await tap(page)
  const seen = (await alertWrites(page)).length
  const before = Date.now()
  await visibility(page, 'hidden')
  await expect.poll(async () => (await alertWrites(page)).length - seen).toBe(1)
  const asked = (await alertWrites(page))[seen]
  expect(asked.method).toBe('PUT')
  expect(asked.body?.tag).toBe('rest')
  expect(asked.body?.title).toBe(S.session.alertRest)
  const restMs = (fixture.exercises[fixture.steps[rest].ex_idx].rest_seconds ?? 0) * 1000
  expect(asked.body!.at).toBeGreaterThan(before)
  expect(asked.body!.at).toBeLessThanOrEqual(Date.now() + restMs)
  // Back before the rest ended: the alert is cancelled.
  await visibility(page, 'visible')
  await expect.poll(async () => (await alertWrites(page)).slice(seen).map((w) => w.method)).toEqual(['PUT', 'DELETE'])
})

test('Settings offers the timer alerts: on an iPhone from the Home Screen only; and it says when the server is not set up', async ({ page, browserName }) => {
  if (browserName === 'chromium') {
    // A test browser always reports notifications as blocked; this stands in for a phone
    // that asks and gets a yes.
    await page.addInitScript(() => {
      Object.defineProperty(Notification, 'permission', { configurable: true, get: () => 'default' })
      Object.defineProperty(Notification, 'requestPermission', { configurable: true, value: async () => 'granted' })
    })
  }
  await onboard(page)
  await page.getByRole('navigation', { name: S.app }).getByRole('button', { name: S.nav.settings }).click()
  const card = page.getByTestId('alerts')
  if (browserName === 'webkit') {
    // The iPhone profile in a browser tab, not from the Home Screen: iOS would refuse.
    await expect(card).toHaveAttribute('data-state', 'install-first')
    await expect(card).toContainText(S.settings.alertsInstall)
    return
  }
  await expect(card).toHaveAttribute('data-state', 'ready')
  await card.getByRole('button', { name: S.settings.alertsTurnOn }).click()
  await expect(card.getByRole('status')).toHaveText(S.settings.alertsNotReady)
})

test('an app kill in the middle opens the session again at the same place, with its numbers', async ({ page }) => {
  await onboard(page)
  await startTraining(page)
  const ramp = fixture.steps.findIndex((s) => s.ex_idx === 1)
  while ((await position(page)) !== ramp) await tap(page)
  const ex = fixture.exercises[1]
  const more = page.getByRole('button', { name: S.session.more(S.session.weight) })
  await more.click()
  await more.click()
  const weight = stepWeight(stepWeight(ex.entry?.weight_kg ?? ex.weight_kg, 1, ex.increment_size), 1, ex.increment_size)
  await expect(page.locator('.bigstep__value').filter({ hasText: S.session.kg(weight) })).toBeVisible()
  await page.getByRole('textbox', { name: S.session.note }).fill('made-up note')
  await hook(page)
  await expect.poll(() => page.evaluate(async () =>
    ((await window.__health!.session()) as { notes: Record<number, string> }).notes[1])).toBe('made-up note')

  // The app is killed and opened again: the session, its place and its numbers come back.
  await page.goto('/')
  await expect(page.locator('.exercise__name')).toHaveText(ex.name)
  expect(await position(page)).toBe(ramp)
  await expect(page.locator('.bigstep__value').filter({ hasText: S.session.kg(weight) })).toBeVisible()
  await expect(page.getByRole('textbox', { name: S.session.note })).toHaveValue('made-up note')
  // Back still knows the taps before the kill.
  await tap(page)
  await page.getByRole('button', { name: S.session.back }).click()
  await expect.poll(() => position(page)).toBe(ramp)
  await leaveSession(page)
  await expect(page.getByRole('heading', { name: S.today.title })).toBeVisible()
})
