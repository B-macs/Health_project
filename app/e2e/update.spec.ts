// An app update never reloads the app during a training session (rebuild Phase 4, a
// Lauscher lesson). The test serves a NEW service worker (the built file, one byte
// changed), lets it install and wait, and checks that the page is not reloaded while the
// session runs; once the session ends, the next return to the app takes the new version.
import { readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import { S } from '../src/strings'
import { controlled, onboard, openTab, sessionStored } from './helpers'

const SW = fileURLToPath(new URL('../../reports/rebuild/e2e-dist/sw.js', import.meta.url))

test('an update waits while a training session runs, and loads after it @update', async ({ page }) => {
  await onboard(page)
  await controlled(page)
  await openTab(page, S.nav.training)
  await expect(page.locator('.exercise__name')).toBeVisible()
  await sessionStored(page)
  await page.evaluate(() => {
    ;(window as unknown as { __mark: string }).__mark = 'not reloaded'
  })

  const original = readFileSync(SW, 'utf-8')
  try {
    writeFileSync(SW, `${original}\n// e2e: a new version ${Date.now()}\n`)
    await page.evaluate(async () => {
      const registration = await navigator.serviceWorker.getRegistration()
      await registration?.update()
    })
    await page.waitForFunction(async () => Boolean((await navigator.serviceWorker.getRegistration())?.waiting),
      null, { timeout: 20_000 })

    // Coming back to the app during the session: the update still waits.
    await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')))
    await page.waitForTimeout(4_000)
    expect(await page.evaluate(() => (window as unknown as { __mark?: string }).__mark)).toBe('not reloaded')
    expect(await page.evaluate(async () => Boolean((await navigator.serviceWorker.getRegistration())?.waiting))).toBe(true)

    // The session ends; at the next return to the app the new version takes over.
    await page.getByRole('button', { name: S.training.close }).click()
    await expect(page.getByRole('heading', { name: S.today.title })).toBeVisible()
    await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')))
    await page.waitForFunction(() => !(window as unknown as { __mark?: string }).__mark, null, { timeout: 15_000 })
    await expect(page.getByRole('heading', { name: S.today.title })).toBeVisible()
  } finally {
    writeFileSync(SW, original)
  }
})
