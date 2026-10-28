// The frames and the navigation (rebuild Phases 4 and 6): every tab opens its frame in the
// same page (no reload), Check-in is a sheet over Today, and the training session survives
// a reload: the app opens on it again.
import { S } from '../src/strings'
import { expect, leaveSession, onboard, openTab, startTraining, test, openTraining } from './helpers'

test('every tab opens its frame in the same page', async ({ page }) => {
  await onboard(page)
  await page.evaluate(() => {
    ;(window as unknown as { __kept: string }).__kept = 'same page'
  })
  await openTab(page, S.nav.insights)
  await expect(page.getByRole('heading', { name: S.insights.title })).toBeVisible()
  await expect(page.getByTestId('insights-hub')).toBeVisible()
  await openTab(page, S.nav.settings)
  await expect(page.getByRole('heading', { name: S.settings.title })).toBeVisible()
  await openTab(page, S.nav.today)
  await expect(page.getByRole('heading', { name: S.today.title })).toBeVisible()
  expect(await page.evaluate(() => (window as unknown as { __kept?: string }).__kept)).toBe('same page')
})

test('check-in opens as a sheet over Today and closes with Escape', async ({ page }) => {
  await onboard(page)
  await openTab(page, S.nav.checkin)
  const sheet = page.getByRole('dialog', { name: S.checkin.title })
  await expect(sheet).toBeVisible()
  await expect(page.getByRole('heading', { name: S.today.title })).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(sheet).toBeHidden()
  expect(new URL(page.url()).hash).toBe('#/')
})

test('the training session survives a reload, and closing it ends it', async ({ page }) => {
  await onboard(page)
  // Before Start: today's session, with the tab bar.
  await openTraining(page)
  await expect(page.getByRole('button', { name: S.session.start })).toBeVisible()
  await expect(page.getByRole('navigation', { name: S.app })).toBeVisible()
  await startTraining(page)
  await expect(page.getByRole('navigation', { name: S.app })).toBeHidden()
  // An app kill: the app opens at "/" again, and goes back to the session.
  await page.goto('/')
  await expect(page.locator('.exercise__name')).toBeVisible()
  expect(new URL(page.url()).hash).toBe('#/training')
  await leaveSession(page)
  await expect(page.getByRole('heading', { name: S.today.title })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('heading', { name: S.today.title })).toBeVisible()
})

test('an unknown address opens Today', async ({ page }) => {
  await onboard(page)
  await page.goto('/#/nowhere')
  await expect(page.getByRole('heading', { name: S.today.title })).toBeVisible()
})
