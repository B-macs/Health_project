// The offline boot and the engine-down screens (rebuild Phase 4).
// - In airplane mode the app opens from the service worker's precache, and Settings shows
//   the engine's last answer, saved in the phone's database, with why it is not new.
// - The service worker never answers /api: offline, /api fails at the network.
// - With the engine down, no screen is blank: each tab renders, and the saved answer
//   shows with "Showing saved data".
import type { Page } from '@playwright/test'
import { S } from '../src/strings'
import { controlled, expect, onboard, openTab, setEngineDown, test, openTraining } from './helpers'

async function engineCard(page: Page) {
  const card = page.getByTestId('engine')
  await expect(card.getByText(/^Version /)).toBeVisible()
  return card
}

test('the app opens in airplane mode and shows the saved data @offline', async ({ page, context }) => {
  await onboard(page)
  await controlled(page)
  await openTab(page, S.nav.settings)
  await expect((await engineCard(page)).getByText(S.settings.engineUp)).toBeVisible()

  await context.setOffline(true)
  await page.goto('/')
  await expect(page.getByRole('navigation', { name: S.app })).toBeVisible()
  await expect(page.getByRole('heading', { name: S.today.title })).toBeVisible()
  await openTab(page, S.nav.settings)
  const card = await engineCard(page)
  await expect(card.getByText(S.fresh.saved, { exact: false })).toBeVisible()
  await expect(card.getByText(S.fresh.why.offline, { exact: false })).toBeVisible()

  // The service worker keeps no /api answer: offline, the request fails.
  const api = await page.evaluate(() => fetch('/api/health').then((r) => r.status, () => 'network error'))
  expect(api).toBe('network error')
  await context.setOffline(false)
})

test('the service worker caches no /api answer @offline', async ({ page }) => {
  await onboard(page)
  await controlled(page)
  await openTab(page, S.nav.settings)
  await engineCard(page)
  const cached = await page.evaluate(async () => {
    const urls: string[] = []
    for (const name of await caches.keys()) {
      for (const request of await (await caches.open(name)).keys()) urls.push(new URL(request.url).pathname)
    }
    return urls
  })
  expect(cached.length).toBeGreaterThan(0)
  expect(cached.filter((path) => path.startsWith('/api/'))).toEqual([])
})

// One test per screen, so the gate counts the screens that render nothing
// (rebuild_gate.py p4 blank_screen_with_engine_down reads these titles).
const SCREENS: {
  name: string
  path: string
  shows: (page: Page) => Promise<void>
  /** A visit while the engine is up, so the phone has the screen's answer saved. */
  before?: (page: Page) => Promise<void>
}[] = [
  {
    name: S.nav.settings,
    path: '/#/settings',
    shows: async (page) => {
      const card = await engineCard(page)
      await expect(card.getByText(S.settings.engineDown)).toBeVisible()
      await expect(card.getByText(S.fresh.saved, { exact: false })).toBeVisible()
      await expect(card.getByText(S.fresh.why.engine_unavailable, { exact: false })).toBeVisible()
    },
  },
  { name: S.nav.today, path: '/#/', shows: (page) => expect(page.getByRole('heading', { name: S.today.title })).toBeVisible() },
  { name: S.nav.insights, path: '/#/insights', shows: (page) => expect(page.getByRole('heading', { name: S.insights.title })).toBeVisible() },
  { name: S.nav.checkin, path: '/#/checkin', shows: (page) => expect(page.getByRole('dialog', { name: S.checkin.title })).toBeVisible() },
  {
    name: S.nav.training,
    path: '/#/training/day',
    before: async (page) => {
      await openTraining(page)
      await expect(page.getByRole('button', { name: S.session.start })).toBeVisible()
    },
    shows: async (page) => {
      await expect(page.getByRole('button', { name: S.session.start })).toBeVisible()
      await expect(page.getByText(S.fresh.why.engine_unavailable, { exact: false }).first()).toBeVisible()
    },
  },
]

for (const screen of SCREENS) {
  test(`with the engine down, ${screen.name} renders and shows the saved data`, async ({ page, context }) => {
    await onboard(page)
    await openTab(page, S.nav.settings)
    await engineCard(page)
    await screen.before?.(page)
    await setEngineDown(context, true)
    // A fresh start on the screen (a hash change alone would not load the app again).
    await page.goto(screen.path)
    await page.reload()
    await screen.shows(page)
    // Nothing on the screen is blank: it carries words, not only a frame.
    expect((await page.locator('.scroller').innerText()).trim().length).toBeGreaterThan(10)
    await setEngineDown(context, false)
  })
}

test('the "act as if the engine is down" switch shows the saved data without a request', async ({ page }) => {
  await onboard(page)
  await openTab(page, S.nav.settings)
  await engineCard(page)
  const on = page.getByRole('radiogroup', { name: S.settings.engineDownTest }).getByRole('radio', { name: S.settings.on })
  await on.click()
  // Checked once the phone's database holds it: only then is it kept across a reload.
  await expect(on).toHaveAttribute('aria-checked', 'true')
  await page.reload()
  const card = await engineCard(page)
  await expect(card.getByText(S.fresh.why.engine_unavailable, { exact: false })).toBeVisible()
  await page.getByRole('radiogroup', { name: S.settings.engineDownTest }).getByRole('radio', { name: S.settings.off }).click()
  await expect(card.getByText(S.settings.engineUp)).toBeVisible()
})
