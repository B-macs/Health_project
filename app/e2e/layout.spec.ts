// Nothing drawn wider than its card (the owner's iPhone, 2026-10-20: "Both graphs go off the
// page"). On every screen with a chart or a strip, each chart, strip and card must sit inside
// the screen's width, and the page must not scroll sideways. WebKit runs this with the iPhone
// profile, which is where Safari's layout differed from the desktop browsers.
import type { Page } from '@playwright/test'
import { expect, onboard, test } from './helpers'

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
