// The training week and the "+" menu in the browser (rebuild Phase 7), on the mock engine's
// made-up block (dev/fixtures.ts). Chromium, and WebKit with the iPhone profile:
// - the week page: the banner, last week's line, the Monday notices, the questions, gate 1,
//   the retest, the strip with its arrows and every kind of day; browsing it writes nothing;
// - a move is asked first, and an answer whose reply is lost is sent again with the same
//   id, so the engine applies it once; a swap goes out from the day it names; a refused
//   move says why and OK clears it;
// - the "+" menu: yoga and an outdoor activity saved once however often the button is
//   pressed; the extra (accessory) session in the same flow, saved as its own kind with its
//   note; the menu is never drawn while a session runs.
// The gate (rebuild_gate.py p7) adds up two annotations of these tests: unasked_moves and
// duplicate_supplementary. Every test sets its own `e2e_run` cookie, so the mock keeps its
// answers apart from the other tests'.
import type { BrowserContext, Page } from '@playwright/test'
import { localDay } from '../src/lib/api'
import { S } from '../src/strings'
import { longDate } from '../src/lib/dates'
import { expect, leaveSession, onboard, openTab, ORIGIN, startTraining, tapToSave, test } from './helpers'

type Received = { method: string; path: string; body: Record<string, unknown> }
type Run = { applied: string[]; swaps: string[]; carry: boolean; redo: boolean; reasons: Record<string, string> }

const ULID = /^[0-9A-HJKMNP-TV-Z]{26}$/

async function received(page: Page): Promise<Received[]> {
  return page.evaluate(async () => (await fetch('/api/dev/received')).json())
}

async function weekRun(page: Page): Promise<Run> {
  return page.evaluate(async () => (await fetch('/api/dev/week-run')).json())
}

async function outboxLength(page: Page): Promise<number> {
  return page.evaluate(() => window.__health!.outbox().then((o) => o.length))
}

/** One test's own answers in the mock, and what it asks the made-up week for. */
async function scenario(context: BrowserContext, tag: string, week = ''): Promise<void> {
  await context.addCookies([{ name: 'e2e_run', value: tag, url: ORIGIN }])
  if (week) await context.addCookies([{ name: 'e2e_week', value: week, url: ORIGIN }])
}

const strip = (page: Page) => page.getByRole('navigation', { name: S.week.strip })

test('the week page shows the banner, the strip and every kind of day, and writes nothing until asked', async ({ page, context }) => {
  await onboard(page)
  await scenario(context, `e2e-week-${Date.now()}`, 'carry.shift.redo.gate1.retest')
  const before = (await received(page)).length
  await openTab(page, S.nav.training)
  await expect(page.getByTestId('rollup')).toContainText(S.week.thisWeek(1, 4))
  await expect(page.getByTestId('rollup')).toContainText(S.week.tier.failing(2))
  await expect(page.getByTestId('last-week')).toHaveText(S.week.lastWeek(S.week.verdict.failed))
  await expect(page.getByTestId('repeat-notice')).toBeVisible()
  await expect(page.getByTestId('carry')).toContainText(S.week.carry)
  await expect(page.getByTestId('shift')).toContainText(S.week.shiftMove)
  await expect(page.getByTestId('gate1-ask')).toContainText('Travel or illness')
  await expect(page.getByTestId('retest')).toBeVisible()
  // The redo asks twice: the first press says what moves, and Cancel sends nothing.
  await page.getByTestId('redo').click()
  await expect(page.getByTestId('redo-confirm')).toContainText('Next week runs this week’s sessions again.')
  await page.getByTestId('redo-confirm').getByRole('button', { name: S.week.cancel }).click()
  await expect(page.getByTestId('redo')).toBeVisible()

  // Last week: a day done, a day missed with the swap offered, a rest day; its verdict.
  await page.getByRole('button', { name: S.week.previousWeek }).click()
  await expect(page.getByTestId('week-today')).toBeVisible()
  await expect(page.getByTestId('week-status')).toContainText(S.week.verdict.normal)
  await strip(page).locator('[data-marker="done"]').first().click()
  await expect(page.getByTestId('day-logged')).toContainText(S.week.logged)
  await strip(page).locator('[data-marker="missed"]').first().click()
  await expect(page.getByTestId('not-completed')).toBeVisible()
  await expect(page.getByRole('button', { name: S.week.swapMissed })).toBeVisible()
  await strip(page).locator('[data-marker="rest"]').first().click()
  await expect(page.getByTestId('day-rest')).toContainText(S.week.rest)

  // The week after this one: a day still to come, with "Do this session today".
  await page.getByRole('button', { name: S.week.nextWeek }).click()
  await page.getByRole('button', { name: S.week.nextWeek }).click()
  await strip(page).locator('[data-marker="planned"]').first().click()
  await expect(page.getByTestId('day-future')).toContainText(S.week.swapFuture)
  // "Today" brings back this week and today's session.
  await page.getByTestId('week-today').click()
  await expect(strip(page).locator(`[data-date="${localDay()}"]`)).toHaveAttribute('aria-current', 'date')
  await expect(page.getByTestId('today-overview')).toBeVisible()

  const writes = (await received(page)).slice(before).filter((r) => r.path.startsWith('/api/training/'))
  test.info().annotations.push({ type: 'unasked_moves', description: String(writes.length) })
  expect(writes).toEqual([])
})

test('a move is asked first and sent once, even when its answer is lost', async ({ page, context }) => {
  await onboard(page)
  await scenario(context, `e2e-carry-${Date.now()}`, 'carry_in_order')
  await openTab(page, S.nav.training)
  await expect(page.getByTestId('carry')).toContainText(S.week.carryInOrder)
  const before = (await received(page)).length
  // The engine stores the answer and the reply is lost: the phone sends it again.
  await context.addCookies([{ name: 'e2e_lose_answer', value: '1', url: ORIGIN }])
  await page.getByRole('button', { name: S.week.carryRun }).click()
  await expect(page.getByTestId('answer-waiting')).toBeVisible()
  const carries = async () => (await received(page)).slice(before).filter((r) => r.path === '/api/training/carry')
  await expect.poll(async () => (await carries()).length, { timeout: 30_000 }).toBeGreaterThanOrEqual(2)
  await context.clearCookies({ name: 'e2e_lose_answer' })
  await expect.poll(() => outboxLength(page), { timeout: 45_000 }).toBe(0)
  const ids = new Set((await carries()).map((r) => r.body.action_id as string))
  test.info().annotations.push({ type: 'unasked_moves', description: String(ids.size - 1) })
  expect(ids.size).toBe(1)
  const [id] = ids
  expect(id).toMatch(ULID)
  const run = await weekRun(page)
  expect(run.carry).toBe(true)
  expect(run.applied.filter((a) => a === id)).toHaveLength(1)
  // Confirmed: the week is read again, and the question is gone.
  await expect(page.getByTestId('carry')).toHaveCount(0)
})

test('a swap with today is sent once, from the day it names, and today shows again', async ({ page, context }) => {
  await onboard(page)
  await scenario(context, `e2e-swap-${Date.now()}`)
  await openTab(page, S.nav.training)
  await page.getByRole('button', { name: S.week.nextWeek }).click()
  const day = await strip(page).locator('[data-marker="planned"]').first().getAttribute('data-date')
  await strip(page).locator(`[data-date="${day}"]`).click()
  const before = (await received(page)).length
  await page.getByRole('button', { name: S.week.swapFuture }).click()
  await expect(page.getByTestId('today-overview')).toBeVisible()
  await expect.poll(async () => (await weekRun(page)).swaps).toEqual([day])
  await expect.poll(() => outboxLength(page)).toBe(0)
  const swaps = (await received(page)).slice(before).filter((r) => r.path === '/api/training/swap')
  test.info().annotations.push({ type: 'unasked_moves', description: String(swaps.length - 1) })
  expect(swaps).toHaveLength(1)
  expect(swaps[0].body.date).toBe(day)
  expect(swaps[0].body.action_id).toMatch(ULID)
})

test('a move the engine refuses says why, and OK clears it', async ({ page, context }) => {
  await onboard(page)
  await scenario(context, `e2e-refuse-${Date.now()}`, 'refuse')
  await openTab(page, S.nav.training)
  await page.getByRole('button', { name: S.week.nextWeek }).click()
  await strip(page).locator('[data-marker="planned"]').first().click()
  await page.getByRole('button', { name: S.week.swapFuture }).click()
  const refused = page.getByTestId('answer-refused')
  await expect(refused).toContainText(S.week.refusedWhy.refused)
  expect((await weekRun(page)).swaps).toEqual([])
  test.info().annotations.push({ type: 'unasked_moves', description: '0' })
  await refused.getByRole('button', { name: S.week.clear }).click()
  await expect(refused).toHaveCount(0)
  expect(await outboxLength(page)).toBe(0)
})

test('the + menu offers yoga, an outdoor activity and the extra session, and is not drawn during a session', async ({ page, context }) => {
  await onboard(page)
  await scenario(context, `e2e-menu-${Date.now()}`)
  await openTab(page, S.nav.training)
  await page.getByTestId('plus').click()
  await expect(page.getByTestId('extras-menu').getByRole('button')).toHaveText([S.extras.yoga, S.extras.outdoor, S.extras.accessory])
  await page.getByRole('button', { name: S.extras.close }).click()
  await startTraining(page)
  await expect(page.getByTestId('plus')).toHaveCount(0)
  test.info().annotations.push({ type: 'duplicate_supplementary', description: '0' })
  await leaveSession(page)
})

test('yoga: a flow is saved once however often Complete is pressed, and a second save is told it is already logged', async ({ page, context }) => {
  await onboard(page)
  await scenario(context, `e2e-yoga-${Date.now()}`)
  const before = (await received(page)).length
  const openFlow = async () => {
    await openTab(page, S.nav.training)
    await page.getByTestId('plus').click()
    await page.getByTestId('extras-menu').getByRole('button', { name: S.extras.yoga }).click()
    await page.getByRole('button', { name: S.extras.yogaItem('Made-up hip flow', 15) }).click()
    await expect(page.getByTestId('yoga-cautions')).toContainText('Made-up form note for the tests.')
  }
  await openFlow()
  // Two taps in one moment: the page sends one save.
  await page.getByRole('button', { name: S.extras.complete }).evaluate((b: HTMLButtonElement) => { b.click(); b.click() })
  await expect(page.getByTestId('yoga-state')).toContainText(S.extras.yogaLogged('Made-up hip flow'))
  const first = (await received(page)).slice(before).filter((r) => r.path === '/api/training/yoga')
  test.info().annotations.push({ type: 'duplicate_supplementary', description: String(first.length - 1) })
  expect(first).toHaveLength(1)
  expect((first[0].body.pose_ids as string[]).length).toBe(2)
  await page.getByRole('button', { name: S.extras.done }).click()
  // The same flow again the same day: the engine writes nothing and says so.
  await openFlow()
  await page.getByRole('button', { name: S.extras.complete }).click()
  await expect(page.getByTestId('yoga-state')).toContainText(S.extras.yogaAlready('Made-up hip flow'))
})

test('an outdoor activity is logged once, with the load its rating gives', async ({ page, context }) => {
  await onboard(page)
  await scenario(context, `e2e-outdoor-${Date.now()}`)
  const today = localDay()
  await openTab(page, S.nav.training)
  await page.getByTestId('plus').click()
  await page.getByTestId('extras-menu').getByRole('button', { name: S.extras.outdoor }).click()
  await expect(page.getByText(S.extras.outdoorHelp)).toBeVisible()
  await page.getByRole('button', { name: S.extras.search }).click()
  await expect(page.getByRole('radio')).toHaveCount(2)
  // The ride is not in the walking family: it says what it logs as.
  await page.getByRole('radio').nth(1).click()
  await expect(page.getByTestId('not-family')).toContainText('cycling')
  await page.getByRole('radio').nth(0).click()
  await expect(page.getByTestId('not-family')).toHaveCount(0)
  await page.getByRole('slider', { name: S.extras.outdoorEffort }).fill('4')
  await expect(page.getByTestId('outdoor-preview')).toHaveText(S.extras.outdoorPreview('Outdoor Walk', longDate(today), 48, 4, 192))
  const before = (await received(page)).length
  await page.getByRole('button', { name: S.extras.logTo('Outdoor Walk') }).evaluate((b: HTMLButtonElement) => { b.click(); b.click() })
  await expect(page.getByTestId('outdoor-state')).toContainText(S.extras.outdoorLogged('Outdoor Walk', longDate(today), 192))
  const sent = (await received(page)).slice(before).filter((r) => r.path === '/api/training/outdoor')
  test.info().annotations.push({ type: 'duplicate_supplementary', description: String(sent.length - 1) })
  expect(sent).toHaveLength(1)
  expect(sent[0].body).toMatchObject({ date: today, activity_id: '501', rpe: 4 })
})

test('the extra session runs in the same flow and saves as its own kind, with its note', async ({ page, context }) => {
  const tag = `e2e-accessory-${Date.now()}`
  await onboard(page)
  await scenario(context, tag)
  await openTab(page, S.nav.training)
  await page.getByTestId('plus').click()
  await page.getByTestId('extras-menu').getByRole('button', { name: S.extras.accessory }).click()
  await expect(page.getByTestId('accessory-why')).toBeVisible()
  await page.getByRole('button', { name: S.extras.start }).click()
  await expect(page.locator('.exercise__name')).toBeVisible()
  await expect(page.getByTestId('plus')).toHaveCount(0)
  await tapToSave(page)
  await expect(page.getByText(S.session.accessoryEffortHelp)).toBeVisible()
  await page.getByRole('textbox', { name: S.session.sessionNotes }).fill(tag)
  await page.getByRole('button', { name: S.session.save }).click()
  await expect(page.getByRole('heading', { name: S.session.accessoryLogged })).toBeVisible()
  const stored = async () => (await page.evaluate(async () => (await fetch('/api/dev/sessions')).json()) as
    { notes: string; kind: string; plan_note: string }[]).filter((b) => b.notes === tag)
  await expect.poll(async () => (await stored()).length, { timeout: 30_000 }).toBe(1)
  const [body] = await stored()
  expect(body.kind).toBe('accessory')
  expect(body.plan_note).toBe('Made-up accessory note.')
  test.info().annotations.push({ type: 'duplicate_supplementary', description: String((await stored()).length - 1) })
  await page.getByRole('button', { name: S.session.done }).click()
  await expect(page.getByRole('heading', { name: S.today.title })).toBeVisible()
})

test('the week with no block shows the gap; damaged phases say so, and yoga still opens', async ({ page, context }) => {
  await onboard(page)
  await scenario(context, `e2e-gap-${Date.now()}`, 'gap')
  await openTab(page, S.nav.training)
  await expect(page.getByTestId('gap').first()).toContainText(S.week.gapTitle)
  await expect(page.getByRole('button', { name: S.session.start })).toHaveCount(0)
  await context.addCookies([{ name: 'e2e_week', value: 'unreadable', url: ORIGIN }])
  await page.reload()
  await expect(page.getByTestId('phases-unreadable')).toContainText(S.week.phasesUnreadable)
  await page.getByTestId('plus').click()
  await page.getByTestId('extras-menu').getByRole('button', { name: S.extras.yoga }).click()
  await expect(page.getByTestId('yoga-list')).toContainText('Made-up hip flow')
  test.info().annotations.push({ type: 'unasked_moves', description: '0' })
})

test('the week on a rest day offers its yoga flow and how to train anyway', async ({ page, context }) => {
  await onboard(page)
  await scenario(context, `e2e-rest-${Date.now()}`, 'rest_today')
  await openTab(page, S.nav.training)
  const rest = page.getByTestId('day-rest')
  await expect(rest).toContainText(S.week.restTrainAnyway)
  await rest.getByRole('button', { name: S.extras.yogaItem('Made-up hip flow', 15) }).click()
  await expect(page.getByTestId('yoga-detail')).toBeVisible()
  test.info().annotations.push({ type: 'unasked_moves', description: '0' })
})

test('a swap that cannot be done says why and offers no button; one that can carries its warning', async ({ page, context }) => {
  await onboard(page)
  await scenario(context, `e2e-blocked-${Date.now()}`, 'blocked')
  await openTab(page, S.nav.training)
  await page.getByRole('button', { name: S.week.nextWeek }).click()
  await strip(page).locator('[data-marker="planned"]').first().click()
  await expect(page.getByTestId('swap-blocked')).toContainText(S.week.swapBlocked('made-up: today already has a logged session'))
  await expect(page.getByRole('button', { name: S.week.swapFuture })).toHaveCount(0)
  // Without the block: the warning shows above the button, and nothing is sent unasked.
  await context.clearCookies({ name: 'e2e_week' })
  await page.reload()
  await page.getByRole('button', { name: S.week.nextWeek }).click()
  await strip(page).locator('[data-marker="planned"]').first().click()
  await expect(page.getByTestId('swap')).toContainText('Made-up warning: two main sessions in a row.')
  const swaps = (await weekRun(page)).swaps
  test.info().annotations.push({ type: 'unasked_moves', description: String(swaps.length) })
  expect(swaps).toEqual([])
})

test('a move declined is recorded and not asked again', async ({ page, context }) => {
  await onboard(page)
  await scenario(context, `e2e-decline-${Date.now()}`, 'shift')
  await openTab(page, S.nav.training)
  const before = (await received(page)).length
  await page.getByTestId('shift').getByRole('button', { name: S.week.keepPlanned }).click()
  await expect.poll(() => outboxLength(page)).toBe(0)
  await expect(page.getByTestId('shift')).toHaveCount(0)
  await page.reload()
  await expect(page.getByTestId('rollup')).toBeVisible()
  await expect(page.getByTestId('shift')).toHaveCount(0)
  const shifts = (await received(page)).slice(before).filter((r) => r.path === '/api/training/shift')
  expect(shifts).toHaveLength(1)
  expect(shifts[0].body.accept).toBe(false)
  test.info().annotations.push({ type: 'unasked_moves', description: String(shifts.length - 1) })
})

test('the week of a failed week offers the redo on its Monday: asked twice, sent once', async ({ page, context }) => {
  await onboard(page)
  await scenario(context, `e2e-redo-${Date.now()}`, 'redo')
  await openTab(page, S.nav.training)
  const before = (await received(page)).length
  await page.getByTestId('redo').click()
  await page.getByRole('button', { name: S.week.redoYes }).click()
  await expect.poll(() => outboxLength(page)).toBe(0)
  await expect(page.getByTestId('redo')).toHaveCount(0)
  expect((await weekRun(page)).redo).toBe(true)
  const redos = (await received(page)).slice(before).filter((r) => r.path === '/api/training/redo')
  test.info().annotations.push({ type: 'unasked_moves', description: String(redos.length - 1) })
  expect(redos).toHaveLength(1)
  expect(redos[0].body.action_id).toMatch(ULID)
})

test('the extra session left with Discard is gone, and nothing is saved', async ({ page, context }) => {
  await onboard(page)
  await scenario(context, `e2e-discard-${Date.now()}`)
  const before = (await received(page)).length
  await openTab(page, S.nav.training)
  await page.getByTestId('plus').click()
  await page.getByTestId('extras-menu').getByRole('button', { name: S.extras.accessory }).click()
  await page.getByRole('button', { name: S.extras.start }).click()
  await expect(page.locator('.exercise__name')).toBeVisible()
  await leaveSession(page)
  await expect(page.getByRole('heading', { name: S.today.title })).toBeVisible()
  expect(await page.evaluate(() => window.__health!.sessionActive())).toBe(false)
  await openTab(page, S.nav.training)
  await expect(page.getByTestId('week-page')).toBeVisible()
  const saves = (await received(page)).slice(before).filter((r) => r.path === '/api/training/sessions')
  test.info().annotations.push({ type: 'duplicate_supplementary', description: String(saves.length) })
  expect(saves).toEqual([])
})

test("the extra session kept from yesterday is never offered as today's", async ({ page, context }) => {
  await onboard(page)
  await scenario(context, `e2e-stale-${Date.now()}`, 'accessory_yesterday')
  await openTab(page, S.nav.training)
  await page.getByTestId('plus').click()
  await page.getByTestId('extras-menu').getByRole('button', { name: S.extras.accessory }).click()
  await expect(page.getByText(S.extras.accessoryNeedsEngine)).toBeVisible()
  await expect(page.getByRole('button', { name: S.extras.start })).toHaveCount(0)
  test.info().annotations.push({ type: 'duplicate_supplementary', description: '0' })
})
