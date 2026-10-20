// The training session in the browser (rebuild Phase 6), on the mock engine's made-up
// session (dev/session_fixture.json, made by the engine's own walk). Chromium, and WebKit
// with the iPhone profile:
// - a whole session from Start to Save, offline in the middle: nothing needs the network
//   until Save, the save waits in the outbox, goes out once the phone is online again, and
//   the engine stores it once, with every set;
// - a save whose answer is lost is sent again with the same ids, and the engine keeps one;
// - an app kill in the middle opens the session again at the same place, with its numbers.
// The gate (rebuild_gate.py p6) adds up two annotations of these tests:
// duplicate_sessions and warning_shown_when_not_due.
import type { Page } from '@playwright/test'
import fixture from '../dev/session_fixture.json' with { type: 'json' }
import { stepWeight } from '../src/lib/training'
import { S } from '../src/strings'
import { expect, hook, leaveSession, onboard, ORIGIN, startTraining, test } from './helpers'

type RawSet = {
  set_num: number
  completed_at: string
  right: { reps: number | null; weight_kg: number | null; seconds: number | null } | null
  rest_started_at?: number
  rest_ended_at?: number
}
type SaveBody = {
  session_id: string
  notes: string
  session_rpe: number
  duration_minutes: number
  exercises: { exercise_id: string; raw_sets: RawSet[] }[]
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
  await startTraining(page)
  // Offline from the fourth exercise to the save: the session needs no network.
  const warnings = await walk(page, async (i) => {
    if (i === 3) await context.setOffline(true)
  })
  test.info().annotations.push({ type: 'warning_shown_when_not_due', description: String(warnings.shownNotDue) })
  expect(warnings.shownNotDue).toBe(0)
  expect(warnings.shownDue).toBe(fixture.exercises.filter((e) => e.warning).length)

  // Offline, the load is worked out when the save is sent.
  await expect(page.getByText(S.session.loadLater)).toBeVisible()
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

  const sent = await sends(page, tag)
  const kept = await stored(page, tag)
  test.info().annotations.push({ type: 'duplicate_sessions', description: String(Math.max(0, kept.length - 1)) })
  expect(sent).toHaveLength(1)
  expect(kept).toHaveLength(1)
  const body = sent[0]
  expect(body.session_id).toMatch(new RegExp(`^${fixture.date.slice(0, 4)}-\\d\\d-\\d\\d-[0-9a-f]{8}$`))
  expect(body.exercises.map((e) => e.raw_sets.length)).toEqual(fixture.exercises.map((e) => e.sets))
  // Every set carries the phone's clock with its UTC offset; every rest that began ended.
  for (const set of body.exercises.flatMap((e) => e.raw_sets)) {
    expect(set.completed_at).toMatch(/T\d\d:\d\d:\d\d[+-]\d\d:\d\d$/)
    if (set.rest_started_at != null) expect(set.rest_ended_at).toBeGreaterThanOrEqual(set.rest_started_at)
  }
  const timed = fixture.exercises.findIndex((e) => e.timer === 'stopwatch')
  expect(body.exercises[timed].raw_sets[0].right?.seconds).toBe(30)

  await page.getByRole('button', { name: S.session.done }).click()
  await expect(page.getByRole('heading', { name: S.today.title })).toBeVisible()
  expect(await page.evaluate(() => window.__health!.sessionActive())).toBe(false)
})

test('a save whose answer is lost is sent again with the same ids, and the engine keeps one', async ({ page, context }) => {
  const tag = `e2e-replay-${Date.now()}`
  await onboard(page)
  await startTraining(page)
  await walk(page)
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
