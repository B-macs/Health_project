// The engine's sync from the phone (rebuild Phase 9, H57, T5, T6, H2) in the browser, on the
// mock engine: with the Streamlit app as the background writer (until the switch-over) the
// phone sends no sync; with the engine as the writer, the first open runs one sync from
// whatever screen opens first, Settings shows it, and a reopen within the minute asks
// nothing. The engine reading a saved copy shows on every page.
import type { BrowserContext, Page } from '@playwright/test'
import { S } from '../src/strings'
import { expect, onboard, openTab, ORIGIN, test } from './helpers'

type Received = { method: string; path: string }

async function scenario(context: BrowserContext, tag: string, week = ''): Promise<void> {
  await context.addCookies([{ name: 'e2e_run', value: tag, url: ORIGIN }])
  if (week) await context.addCookies([{ name: 'e2e_week', value: week, url: ORIGIN }])
}

async function syncs(page: Page): Promise<number> {
  const all: Received[] = await page.evaluate(async () => (await fetch('/api/dev/received')).json())
  return all.filter((r) => r.method === 'POST' && r.path === '/api/sync').length
}

test('the phone sends no sync while the old app is the background writer', async ({ page, context }) => {
  await scenario(context, `e2e-nosync-${Date.now()}`)
  await onboard(page)
  const before = await syncs(page)
  await page.goto('/#/insights')
  await expect(page.getByTestId('insights-hub')).toBeVisible()
  await openTab(page, S.nav.settings)
  await expect(page.getByTestId('sync-card')).toContainText(S.settings.writer.streamlit!)
  expect(await syncs(page)).toBe(before)
})

test('with the engine as the writer the first open runs one sync, whatever the screen', async ({ page, context }) => {
  // Set up as the old app's writer (no sync), then the switch: the next open of the app
  // starts on Insights, not on Today, and the sync runs all the same.
  await scenario(context, `e2e-sync-${Date.now()}`)
  await onboard(page)
  const before = await syncs(page)
  await context.addCookies([{ name: 'e2e_week', value: 'writer_engine', url: ORIGIN }])
  await page.goto('/#/insights')
  await page.reload()
  await expect(page.getByTestId('insights-hub')).toBeVisible()
  await expect.poll(() => syncs(page)).toBe(before + 1)
  await openTab(page, S.nav.settings)
  const card = page.getByTestId('sync-card')
  await expect(card).toContainText(S.settings.writer.engine!)
  await expect(card).toContainText(S.settings.lastSync('').trim())
  await expect(card).toContainText(S.settings.syncNotDue)
  // Coming back to the front within the minute asks nothing more.
  await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')))
  await page.waitForTimeout(500)
  expect(await syncs(page)).toBe(before + 1)
})

test('the engine reading a saved copy shows on every page', async ({ page, context }) => {
  await scenario(context, `e2e-offline-${Date.now()}`, 'offline_copy')
  await onboard(page)
  await expect(page.getByTestId('engine-offline')).toContainText(S.status.offline('2026-10-20 06:00'))
  await openTab(page, S.nav.insights)
  await expect(page.getByTestId('engine-offline')).toBeVisible()
})
