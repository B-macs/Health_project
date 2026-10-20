// Today and its detail screens in the browser (rebuild Phase 5), against the mock's
// made-up answers (dev/fixtures.ts): the numbers show, the day changes with the arrows and
// the week strip, a picked day survives a reload and "Back to today" returns, a card opens
// its detail screen with its own day arrows, and a night with no Sleep Score shows only the
// reason line.
import { expect, test, type Page } from '@playwright/test'
import * as fx from '../dev/fixtures'
import { S } from '../src/strings'
import { onboard } from './helpers'

/** The phone's own day, as the app sends it (the browser's local date). */
async function localDay(page: Page): Promise<string> {
  return page.evaluate(() => {
    const d = new Date()
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  })
}

const readiness = (page: Page) => page.getByRole('button', { name: S.today.openReadiness })

test('Today shows the engine numbers for today', async ({ page }) => {
  await onboard(page)
  const local = await localDay(page)
  const answer = fx.today(local, local)
  await expect(readiness(page)).toContainText(String(Math.round(answer.readiness.headline!)))
  await expect(page.getByRole('button', { name: S.today.openSleep })).toContainText(answer.sleep.display)
  await expect(page.getByRole('button', { name: S.today.openStrain })).toContainText(answer.strain.display)
  await expect(page.getByRole('navigation', { name: S.today.strip }).getByRole('button')).toHaveCount(7)
})

test('the arrows change the day, a reload keeps it, and "Back to today" returns', async ({ page }) => {
  await onboard(page)
  const local = await localDay(page)
  const yesterday = fx.addDays(local, -1)
  await page.getByRole('button', { name: S.detail.previous }).click()
  await expect(readiness(page)).toContainText(String(Math.round(fx.today(yesterday, local).readiness.headline!)))
  await expect(page.getByRole('button', { name: S.today.backToToday })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('button', { name: S.today.backToToday })).toBeVisible()
  await expect(readiness(page)).toContainText(String(Math.round(fx.today(yesterday, local).readiness.headline!)))
  await page.getByRole('button', { name: S.today.backToToday }).click()
  await expect(page.getByRole('button', { name: S.today.backToToday })).toBeHidden()
  await expect(page.getByRole('button', { name: S.detail.next })).toBeDisabled()
})

test('a day on the week strip opens that day', async ({ page }) => {
  await onboard(page)
  const local = await localDay(page)
  const day = fx.addDays(local, -3)
  const strip = page.getByRole('navigation', { name: S.today.strip })
  await strip.getByRole('button').nth(3).click()
  await expect(strip.getByRole('button').nth(3)).toHaveAttribute('aria-current', 'date')
  await expect(readiness(page)).toContainText(String(Math.round(fx.today(day, local).readiness.headline!)))
})

test('a card opens its detail screen, which has its own day arrows and a way back', async ({ page }) => {
  await onboard(page)
  const local = await localDay(page)
  await page.getByRole('button', { name: S.today.openStrain }).click()
  await expect(page.getByRole('heading', { name: S.detail.strain })).toBeVisible()
  await expect(page.getByText(`STRAIN · TODAY`)).toBeVisible()
  await page.getByRole('button', { name: S.detail.previous }).click()
  await expect(page.getByText(`STRAIN · ${fx.addDays(local, -1)}`)).toBeVisible()
  await page.getByRole('button', { name: S.detail.back }).click()
  await expect(page.getByRole('heading', { name: S.today.title })).toBeVisible()
  // The day moved in the detail screen moves Today too.
  await expect(page.getByRole('button', { name: S.today.backToToday })).toBeVisible()
})

test('a night with no Sleep Score shows only the reason line', async ({ page }) => {
  await onboard(page)
  const local = await localDay(page)
  let back = 0
  while (!fx.unscored(fx.addDays(local, -back))) back++
  await page.getByRole('button', { name: S.today.openSleep }).click()
  for (let i = 0; i < back; i++) await page.getByRole('button', { name: S.detail.previous }).click()
  const day = fx.addDays(local, -back)
  await expect(page.getByText(day === local ? 'SLEEP · TODAY' : `SLEEP · ${day}`)).toBeVisible()
  await expect(page.getByTestId('sleep-reason')).toBeVisible()
  await expect(page.getByRole('region', { name: S.detail.contributors })).toHaveCount(0)
  await expect(page.getByTestId('wake')).toHaveCount(0)
  await expect(page.getByTestId('hypnogram')).toHaveCount(0)
})

test('a chart point opens its reading, and "Open" moves to that day', async ({ page }) => {
  await onboard(page)
  await page.getByRole('button', { name: S.today.openReadiness }).click()
  const trend = page.getByTestId('trend')
  const local = await localDay(page)
  const day = fx.addDays(local, -5)
  await trend.getByRole('button', { name: day }).click()
  await expect(trend.getByRole('status')).toContainText(day)
  await trend.getByRole('button', { name: S.charts.open(day) }).click()
  await expect(page.getByText(`READINESS · ${day}`)).toBeVisible()
})
