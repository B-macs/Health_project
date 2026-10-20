// The outbox in the browser (rebuild Phase 4): writes made offline, or while the engine is
// down, wait in the phone's database and go out in order once the engine can take them.
// Not one is lost: every write is either received by the engine or still in the outbox.
// Phase 4 has no screen that writes yet, so the mock build's test hook writes
// (src/debug/testHooks.ts, never part of a real build).
import type { Page } from '@playwright/test'
import { S } from '../src/strings'
import { controlled, expect, hook, onboard, openTab, setEngineDown, test } from './helpers'

type Received = { method: string; path: string; body: { n: number }; day: string | null }

async function write(page: Page, tag: string, count: number): Promise<void> {
  await hook(page)
  await page.evaluate(async ({ tag, count }) => {
    for (let n = 1; n <= count; n++) {
      await window.__health!.enqueue({ kind: 'test', method: 'POST', path: `/api/e2e/${tag}`, body: { n }, day: '2026-10-20' })
    }
  }, { tag, count })
}

async function received(page: Page, tag: string): Promise<Received[]> {
  const all = (await (await page.request.get('/api/dev/received')).json()) as Received[]
  return all.filter((item) => item.path === `/api/e2e/${tag}`)
}

/** Writes lost = written - received by the engine - still waiting in the outbox. The
 *  gate (rebuild_gate.py p4 outbox_loss) adds up this annotation over the outbox tests. */
async function recordLoss(page: Page, tag: string, written: number): Promise<number> {
  const lost = written - (await received(page, tag)).length - (await waiting(page))
  test.info().annotations.push({ type: 'outbox_loss', description: String(lost) })
  return lost
}

async function waiting(page: Page): Promise<number> {
  await hook(page)
  return page.evaluate(async () => (await window.__health!.outbox()).length)
}

test('writes made offline go out in order when the phone is back online @outbox', async ({ page, context }) => {
  const tag = `offline-${Date.now()}`
  await onboard(page)
  await controlled(page)
  await context.setOffline(true)
  await write(page, tag, 3)
  await openTab(page, S.nav.settings)
  await expect(page.getByTestId('outbox')).toHaveAttribute('data-waiting', '3')
  expect(await waiting(page)).toBe(3)

  await context.setOffline(false)
  await expect.poll(() => received(page, tag).then((r) => r.length), { timeout: 20_000 }).toBe(3)
  const got = await received(page, tag)
  expect(got.map((r) => r.body.n)).toEqual([1, 2, 3])
  expect(got.every((r) => r.method === 'POST' && r.day === '2026-10-20')).toBe(true)
  await expect(page.getByTestId('outbox')).toHaveAttribute('data-waiting', '0')
  expect(await waiting(page)).toBe(0)
  expect(await recordLoss(page, tag, 3)).toBe(0)
})

test('writes made while the engine is down wait, and nothing is lost @outbox', async ({ page, context }) => {
  const tag = `down-${Date.now()}`
  await onboard(page)
  await setEngineDown(context, true)
  await write(page, tag, 2)
  await openTab(page, S.nav.settings)
  await expect(page.getByTestId('outbox')).toHaveAttribute('data-waiting', '2')
  // The first try failed and waits; nothing reached the engine, nothing was dropped.
  await expect.poll(async () => (await page.evaluate(() => window.__health!.outbox()))[0]?.attempts ?? 0)
    .toBeGreaterThan(0)
  expect(await received(page, tag)).toEqual([])
  expect(await waiting(page)).toBe(2)

  // A reload in between (an app kill) keeps them too.
  await page.reload()
  expect(await waiting(page)).toBe(2)

  await setEngineDown(context, false)
  await page.getByRole('button', { name: S.settings.outboxSend }).click()
  await expect.poll(() => received(page, tag).then((r) => r.map((x) => x.body.n)), { timeout: 20_000 }).toEqual([1, 2])
  expect(await waiting(page)).toBe(0)
  expect(await recordLoss(page, tag, 2)).toBe(0)
})
