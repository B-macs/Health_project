// The check-in in the browser (rebuild Phase 5): made with no connection, it waits in the
// outbox and is sent once the phone is back online; the next open shows it as saved.
// The gate (rebuild_gate.py p5 check_in_lost) adds up this test's check_in_lost count.
import type { Page } from '@playwright/test'
import { S } from '../src/strings'
import { controlled, expect, hook, onboard, openTab, test } from './helpers'

type Received = { method: string; path: string; body: { date: string; opened_entry: boolean; values: { pain_score: number; sensation_tags: string[] } } }

async function checkins(page: Page): Promise<Received[]> {
  const all = (await (await page.request.get('/api/dev/received')).json()) as Received[]
  return all.filter((r) => r.path === '/api/checkin' && r.method === 'PUT')
}

test('a check-in made offline is sent later, and opens as saved @outbox', async ({ page, context }) => {
  await onboard(page)
  await controlled(page)
  await hook(page)
  const before = (await checkins(page)).length
  // Opened once online (the form comes from the engine), then the connection goes.
  await openTab(page, S.nav.checkin)
  const sheet = page.getByRole('dialog', { name: S.checkin.title })
  await expect(sheet.getByRole('slider', { name: S.checkin.fields.pain_score.label })).toBeVisible()
  await context.setOffline(true)
  await sheet.getByRole('slider', { name: S.checkin.fields.pain_score.label }).fill('3')
  await sheet.getByRole('button', { name: 'Sore' }).click()
  await sheet.getByRole('button', { name: S.checkin.save }).click()
  await expect(sheet.getByText(S.checkin.saved)).toBeVisible()
  expect(await page.evaluate(async () => (await window.__health!.outbox()).length)).toBe(1)
  expect((await checkins(page)).length).toBe(before)

  await context.setOffline(false)
  await expect.poll(async () => (await checkins(page)).length, { timeout: 20_000 }).toBe(before + 1)
  const sent = (await checkins(page)).at(-1)!
  expect(sent.body.values.pain_score).toBe(3)
  expect(sent.body.values.sensation_tags).toEqual(['Sore'])
  const lost = 1 - (await checkins(page)).length + before - (await page.evaluate(async () => (await window.__health!.outbox()).length))
  test.info().annotations.push({ type: 'check_in_lost', description: String(lost) })
  expect(lost).toBe(0)

  // Opened again: the day's entry, as the engine now holds it.
  await sheet.getByRole('button', { name: S.checkin.close }).click()
  await openTab(page, S.nav.checkin)
  await expect(page.getByRole('dialog', { name: S.checkin.title }).getByText(S.checkin.existing)).toBeVisible()
})

test('the check-in sheet offers today and the three days before', async ({ page }) => {
  await onboard(page)
  await openTab(page, S.nav.checkin)
  const dates = page.getByRole('radiogroup', { name: S.checkin.date }).getByRole('radio')
  await expect(dates).toHaveCount(4)
  await expect(dates.first()).toHaveText(S.checkin.today)
  await expect(dates.first()).toHaveAttribute('aria-checked', 'true')
})

test('the bottom bar stays on screen over the check-in, and a tab leaves it', async ({ page }) => {
  // The owner, 2026-10-20: "Check in is an option at the bottom bar but when pressed I can no
  // longer see the bottom bar". The sheet sat over the whole app, bar included.
  await onboard(page)
  await openTab(page, S.nav.checkin)
  const sheet = page.getByRole('dialog', { name: S.checkin.title })
  await expect(sheet).toBeVisible()
  const bar = page.getByRole('navigation', { name: S.app })
  await expect(bar).toBeInViewport()
  const box = (await bar.boundingBox())!
  const onTop = await page.evaluate(([x, y]) => !!document.elementFromPoint(x!, y!)?.closest('.tabbar'),
    [box.x + box.width / 2, box.y + box.height / 2])
  expect(onTop).toBe(true)
  // Opening it moves nothing: the app is not scrolled up under the status bar.
  expect(await page.evaluate(() => document.querySelector('.app')!.scrollTop)).toBe(0)
  // A tap on the bar reaches it: Training opens and the check-in closes.
  await openTab(page, S.nav.training)
  await expect(sheet).toHaveCount(0)
  await expect(page).toHaveURL(/#\/training/)
})
