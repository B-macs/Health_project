// Nothing drawn wider than its card (the owner's iPhone, 2026-10-20: "Both graphs go off the
// page"). On every screen with a chart or a strip, each chart, strip and card must sit inside
// the screen's width, and the page must not scroll sideways. WebKit runs this with the iPhone
// profile, which is where Safari's layout differed from the desktop browsers.
import type { Page } from '@playwright/test'
import { expect, onboard, ORIGIN, test } from './helpers'

const SCREENS = ['/readiness', '/sleep', '/strain', '/training', '/insights', '/insights/strength',
  '/insights/metabolism', '/insights/engine', '/insights/trends', '/insights/sleep', '/insights/warnings']

/** The elements wider than the card they sit in (or than the screen), named by class. */
async function overflowing(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const out: string[] = []
    const width = document.documentElement.clientWidth
    const selector = '.chart__plot, svg.ichart, .weekstrip, .card, .cal, .dtable'
    for (const el of Array.from(document.querySelectorAll<HTMLElement | SVGElement>(selector))) {
      const box = el.getBoundingClientRect()
      if (box.width === 0) continue
      const card = el.parentElement?.closest('.card') as HTMLElement | null
      const limit = card ? card.getBoundingClientRect().right : width
      if (box.right > limit + 1 || box.right > width + 1) {
        out.push(`${el.getAttribute('class')} ends at ${Math.round(box.right)} past ${Math.round(Math.min(limit, width))}`)
      }
    }
    const scroller = document.querySelector('.scroller') as HTMLElement | null
    if (scroller && scroller.scrollWidth > scroller.clientWidth + 1) {
      out.push(`the page scrolls sideways: ${scroller.scrollWidth} > ${scroller.clientWidth}`)
    }
    return out
  })
}

test('every chart, strip and card stays inside the screen\'s width', async ({ page }) => {
  await onboard(page)
  const found: string[] = []
  for (const path of SCREENS) {
    await page.goto(`/#${path}`)
    await page.waitForTimeout(800)
    for (const problem of await overflowing(page)) found.push(`${path}: ${problem}`)
  }
  expect(found).toEqual([])
})

/** Text drawn past the screen's left or right edge, by its first words (the owner's iPhone,
 *  2026-10-21: a yoga flow's name ran off both sides of the page, on the yoga list and on
 *  Training's rest day). Every text on the page is measured where it is drawn. */
async function textOffScreen(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const width = document.documentElement.clientWidth
    const out: string[] = []
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const words = (node.textContent ?? '').trim()
      const el = node.parentElement
      if (!words || !el || el.closest('.sr-only, [aria-hidden="true"]')) continue
      const range = document.createRange()
      range.selectNodeContents(node)
      const off = Array.from(range.getClientRects()).find((r) => r.width > 0 && (r.left < -1 || r.right > width + 1))
      if (off) out.push(`"${words.slice(0, 40)}" from ${Math.round(off.left)} to ${Math.round(off.right)} on a ${width} screen`)
    }
    return out
  })
}

test('no text runs past the screen\'s edge, on any screen', async ({ page, context }) => {
  await onboard(page)
  const found: string[] = []
  const visit = async (path: string, label = path) => {
    await page.goto(`/#${path}`)
    await page.waitForTimeout(800)
    for (const problem of await textOffScreen(page)) found.push(`${label}: ${problem}`)
  }
  for (const path of ['/', '/checkin', '/settings', '/training/yoga', ...SCREENS]) await visit(path)
  // Training on a rest day, with its yoga flow to pick.
  await context.addCookies([{ name: 'e2e_run', value: `layout-${Date.now()}`, url: ORIGIN },
    { name: 'e2e_week', value: 'rest_today', url: ORIGIN }])
  await visit('/training', '/training (rest day)')
  expect(found).toEqual([])
})
