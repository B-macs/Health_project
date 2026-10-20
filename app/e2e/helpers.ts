// Shared steps of the browser tests (rebuild Phase 4). The screen words come from the
// app's one strings file, so a reworded button cannot leave a test behind.
//
// Every spec imports `test` from here, not from @playwright/test: its browser context has
// no audio player (lib/sounds.ts then plays nothing), so the session's bells never sound
// on the PC that runs the tests, in Chromium or in WebKit.
import { test as base, expect, type BrowserContext, type Page } from '@playwright/test'
import { S } from '../src/strings'

export { expect }

export const test = base.extend({
  context: async ({ context }, use) => {
    await context.addInitScript(() => {
      const w = window as unknown as Record<string, unknown>
      w.AudioContext = undefined
      w.webkitAudioContext = undefined
    })
    await use(context)
  },
})

export const ORIGIN = 'http://127.0.0.1:4175'

// The mock build's test hook (src/debug/testHooks.ts), as the tests see it.
declare global {
  interface Window {
    __health?: {
      enqueue: (write: { kind: string; method: 'POST' | 'PUT' | 'DELETE'; path: string; body: unknown; day?: string }) => Promise<string>
      outbox: () => Promise<{ attempts: number }[]>
      sessionActive: () => boolean
      session: () => Promise<unknown>
      setSetting: (key: string, value: unknown) => Promise<void>
    }
  }
}

/** The access key field (its card's heading also names the key). */
export const keyField = (page: Page) => page.getByRole('textbox', { name: S.welcome.keyLabel, exact: true })

/** The first open in a browser tab: skip the Home Screen steps, paste the mock key. */
export async function onboard(page: Page): Promise<void> {
  await page.goto('/')
  await page.getByRole('button', { name: S.welcome.installSkip }).click()
  await keyField(page).fill('dev')
  await page.getByRole('button', { name: S.welcome.keySave }).click()
  await expect(page.getByRole('navigation', { name: S.app })).toBeVisible()
}

/** Wait until the service worker controls the page (the shell is precached). */
export async function controlled(page: Page): Promise<void> {
  await page.waitForFunction(() => navigator.serviceWorker.controller !== null, null, { timeout: 20_000 })
}

/** Make the mock API answer as the Worker does while the engine is starting or down. */
export async function setEngineDown(context: BrowserContext, down: boolean): Promise<void> {
  if (down) await context.addCookies([{ name: 'e2e_engine', value: 'down', url: ORIGIN }])
  else await context.clearCookies({ name: 'e2e_engine' })
}

/** Open a tab from the tab bar. */
export async function openTab(page: Page, name: string): Promise<void> {
  await page.getByRole('navigation', { name: S.app }).getByRole('button', { name }).click()
}

/** The mock build's test hook, once the app has started (main.tsx installs it). */
export async function hook(page: Page): Promise<void> {
  await page.waitForFunction(() => window.__health !== undefined, null, { timeout: 20_000 })
}

/** Wait until the training session is stored (Start stores it). */
export async function sessionStored(page: Page): Promise<void> {
  await hook(page)
  await expect.poll(() => page.evaluate(() => window.__health!.sessionActive())).toBe(true)
}

/** Open Training and start today's session (the mock engine's made-up one), with a Garmin
 *  workout declared when `garmin` is set. */
export async function startTraining(page: Page, options: { garmin?: boolean } = {}): Promise<void> {
  await openTab(page, S.nav.training)
  if (options.garmin) await page.getByRole('switch', { name: S.session.garminDeclare }).check()
  await page.getByRole('button', { name: S.session.start }).click()
  await expect(page.locator('.exercise__name')).toBeVisible()
  await sessionStored(page)
}

/** Leave the session without saving (the close button, then the confirmation). */
export async function leaveSession(page: Page): Promise<void> {
  await page.getByRole('button', { name: S.session.exit }).click()
  await page.getByRole('button', { name: S.session.discard }).click()
}

/** Tap through a session's flow to its save screen: the main button, once per step, the
 *  seconds typed first on a timed test; each tap waits until the flow has moved. */
export async function tapToSave(page: Page): Promise<void> {
  const flow = page.locator('.screen.train[data-step]')
  const at = async () => ((await flow.count()) ? await flow.getAttribute('data-step') : 'save')
  for (let taps = 0; taps < 400; taps++) {
    const now = await at()
    if (now === 'save') return
    const seconds = page.getByRole('spinbutton')
    if (await seconds.count()) await seconds.fill('30')
    await page.locator('.controls .btn--primary').click()
    await expect.poll(at).not.toBe(now)
  }
  throw new Error('the session never reached the save screen')
}
