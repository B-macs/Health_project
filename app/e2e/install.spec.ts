// Installability and the first open (rebuild Phase 4). Chromium's own check, through the
// DevTools protocol: the web app manifest parses and nothing would stop an install. iOS
// reads the same manifest and the apple-touch-icon; the real iPhone checks the install
// itself (the owner's checklist).
import { expect, test } from '@playwright/test'
import { S } from '../src/strings'
import { controlled, keyField, onboard } from './helpers'

test('the app can be installed: a valid manifest, its icons, no installability errors @install', async ({ page }) => {
  await page.goto('/')
  await controlled(page)
  const cdp = await page.context().newCDPSession(page)
  const manifest = await cdp.send('Page.getAppManifest')
  expect(manifest.errors).toEqual([])
  const parsed = JSON.parse(manifest.data ?? '{}') as {
    name?: string
    display?: string
    start_url?: string
    icons?: { src: string; purpose?: string }[]
  }
  expect(parsed.name).toBe('Health')
  expect(parsed.display).toBe('standalone')
  expect(parsed.start_url).toBe('/')
  expect(parsed.icons?.some((icon) => icon.purpose === 'maskable')).toBe(true)
  const { installabilityErrors } = await cdp.send('Page.getInstallabilityErrors')
  expect(installabilityErrors).toEqual([])
  const touchIcon = await page.locator('link[rel="apple-touch-icon"]').getAttribute('href')
  expect((await page.request.get(touchIcon!)).status()).toBe(200)
  for (const icon of parsed.icons ?? []) expect((await page.request.get(icon.src)).status()).toBe(200)
})

test('in the browser, the first open shows the Home Screen steps, then the key', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: S.welcome.installTitle })).toBeVisible()
  for (const step of S.welcome.installSteps) await expect(page.getByText(step)).toBeVisible()
  await page.getByRole('button', { name: S.welcome.installSkip }).click()
  await expect(keyField(page)).toBeVisible()
  // The key never travels in the address.
  expect(page.url()).not.toContain('dev')
})

test('a wrong key is refused and not kept', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: S.welcome.installSkip }).click()
  await keyField(page).fill('not-the-key')
  await page.getByRole('button', { name: S.welcome.keySave }).click()
  await expect(page.getByText(S.welcome.keyWrong)).toBeVisible()
  await page.reload()
  await expect(keyField(page)).toBeVisible()
})

test('the right key opens the app, and stays after a reload', async ({ page }) => {
  await onboard(page)
  await page.reload()
  await expect(page.getByRole('navigation', { name: S.app })).toBeVisible()
  expect(page.url()).not.toContain('dev')
})
