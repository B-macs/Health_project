// Insights and Settings › Data in the browser (rebuild Phase 8), on the mock engine's answers,
// which are the engine's own over made-up data (dev/insights_fixture.json, made through the
// engine by scripts/make_insights_fixture.py). Chromium, and WebKit with the iPhone profile:
// - the Insights page opens each screen in the app, and each screen draws the engine's answer;
// - Strength before the reference is stored says why there are no figures;
// - Metabolism steps through the periods the engine allows;
// - the flexibility capture: the cold gate, each step the engine's order at the owner's place,
//   the engine's early answer, keep going and back, and the saved assessment;
// - with the engine down, each screen keeps its saved answer and says why;
// - Settings › Data: a table opens, and the syncs stay off until the switch-over.
// The gate (rebuild_gate.py p8) adds up one annotation: battery_disagreement. Every test sets
// its own `e2e_run` cookie, so the mock keeps its answers apart from the other tests'.
import type { BrowserContext, Page } from '@playwright/test'
import fixture from '../dev/insights_fixture.json' with { type: 'json' }
import { S } from '../src/strings'
import { expect, onboard, openTab, ORIGIN, setEngineDown, test } from './helpers'

type Received = { method: string; path: string; body: Record<string, unknown> }
type Test = { key: string; label: string; bilateral: boolean; setup_input: string }
type CaptureState = { order: Test[]; early_pattern: string | null; early_pattern_label: string }

const F = fixture as unknown as {
  strength: Record<string, { overall: number }>
  metabolism: Record<string, { latest: { fat_mass_kg: number }; series: { window: { label: string } } }>
  capture: { states: CaptureState[] }
  engine: { directive: { words: string } }
  trends: { regions: { region: string }[] }
}

async function scenario(context: BrowserContext, tag: string, week = ''): Promise<void> {
  await context.addCookies([{ name: 'e2e_run', value: tag, url: ORIGIN }])
  if (week) await context.addCookies([{ name: 'e2e_week', value: week, url: ORIGIN }])
}

async function received(page: Page): Promise<Received[]> {
  return page.evaluate(async () => (await fetch('/api/dev/received')).json())
}

const back = (page: Page) => page.getByRole('button', { name: S.ins.backTo(S.ins.back) })

test('Insights opens each screen in the same page, each drawn from the engine\'s answer', async ({ page, context }) => {
  await onboard(page)
  await scenario(context, `e2e-insights-${Date.now()}`)
  await page.evaluate(() => {
    ;(window as unknown as { __kept: string }).__kept = 'same page'
  })
  await openTab(page, S.nav.insights)
  const overall = S.ins.pct(F.strength['Overall Strength Score']!.overall)
  await expect(page.getByTestId('tile-strength')).toContainText(overall)
  await page.getByTestId('tile-strength').click()
  await expect(page.getByTestId('overall')).toHaveText(overall)
  await expect(page.getByTestId('body-parts')).toBeVisible()
  // The redone page (2026-10-20): the whole page from one answer, no button per series.
  await expect(page.getByTestId('volume')).toBeVisible()
  await expect(page.getByRole('radio')).toHaveCount(0)
  await back(page).click()
  await page.getByRole('button', { name: S.ins.engine }).click()
  await expect(page.getByTestId('directive')).toContainText(F.engine.directive.words)
  await back(page).click()
  await page.getByRole('button', { name: S.ins.trends }).click()
  await expect(page.getByTestId('regions')).toContainText(F.trends.regions[0]!.region)
  await back(page).click()
  await page.getByRole('button', { name: S.ins.warnings }).click()
  await expect(page.getByTestId('calendar')).toBeVisible()
  // The days the app lowered the load (2026-10-21): a rest day names what it was.
  await expect(page.getByTestId('warnings-key')).toContainText(S.warn.load.rest!)
  await page.getByTestId('calendar').getByRole('button', { name: new RegExp(S.warn.load.rest!) }).first().click()
  await expect(page.getByTestId('day-entries')).toContainText(S.warn.load.rest!)
  await back(page).click()
  await page.getByRole('button', { name: S.ins.sleepArch }).click()
  await expect(page.getByTestId('arch-counts')).toBeVisible()
  expect(await page.evaluate(() => (window as unknown as { __kept?: string }).__kept)).toBe('same page')
})

test('Strength before the 2025 reference is stored says why there are no figures', async ({ page, context }) => {
  await onboard(page)
  await scenario(context, `e2e-strength-${Date.now()}`, 'no_reference')
  await page.goto('/#/insights/strength')
  await expect(page.getByTestId('reference-missing')).toHaveText(S.ins.referenceMissing)
  await expect(page.getByTestId('overall')).toHaveCount(0)
})

test('Metabolism steps back a week as the engine allows, and keeps the composition meanwhile', async ({ page, context }) => {
  await onboard(page)
  await scenario(context, `e2e-metab-${Date.now()}`)
  await openTab(page, S.nav.insights)
  await page.getByTestId('tile-metabolism').click()
  await expect(page.getByTestId('composition')).toContainText(F.metabolism['Weight|all|0']!.latest.fat_mass_kg.toFixed(1))
  await page.getByRole('radio', { name: 'Week' }).click()
  await expect(page.getByTestId('metab-period')).toContainText(F.metabolism['Weight|week|0']!.series.window.label)
  await page.getByRole('button', { name: S.ins.previousPeriod }).click()
  await expect(page.getByTestId('metab-period')).toContainText(F.metabolism['Weight|week|-1']!.series.window.label)
  await expect(page.getByTestId('composition')).toBeVisible()
})

test('The capture shows the engine\'s order at the owner\'s place and stops at its early answer', async ({ page, context }) => {
  await onboard(page)
  await scenario(context, `e2e-capture-${Date.now()}`)
  const states = F.capture.states
  let disagreements = 0
  // The step the screen shows must become the engine's test at the owner's place.
  const shows = async (expected: Test) => {
    try {
      await expect(page.getByTestId('step-head')).toContainText(expected.label, { timeout: 10_000 })
    } catch {
      disagreements += 1
    }
  }
  await openTab(page, S.nav.insights)
  await page.getByTestId('tile-flexibility').click()
  await page.getByRole('button', { name: S.flex.start }).click()
  await expect(page.getByTestId('cold-gate')).toBeVisible()
  // Each save is for the test the engine's order holds at the owner's place (the mock keeps
  // every test's writes, so this test counts from what was there before it).
  const puts = async () => (await received(page)).filter((r) => r.method === 'PUT' && r.path.endsWith('/flexibility/capture'))
  const before = (await puts()).length
  await page.getByRole('button', { name: S.flex.begin }).click()
  let at = 0
  for (const state of states.slice(0, -1)) {
    const test = state.order[at]!
    await shows(test)
    const form = page.getByTestId('step-form')
    const fields = form.locator('input[inputmode="decimal"]')
    const n = await fields.count()
    for (let i = 0; i < n; i += 1) await fields.nth(i).fill(String(30 + i))
    await form.getByRole('button', { name: S.flex.saveNext }).click()
    at += 1
    await expect.poll(async () => (await puts()).length).toBe(before + at)
    if ((await puts()).at(-1)?.body.test_key !== test.key) disagreements += 1
  }
  // The engine answered early: the screen stops, never shows the next test by itself.
  const last = states[states.length - 1]!
  expect(last.early_pattern).toBeTruthy()
  await expect(page.getByTestId('early-answer')).toContainText(S.flex.patternLine(last.early_pattern!, last.early_pattern_label))
  if (await page.getByTestId('step-form').isVisible()) disagreements += 1
  // Keep going shows the engine's order at the place reached; Back steps one back.
  await page.getByRole('button', { name: S.flex.keepGoing }).click()
  await shows(last.order[at]!)
  await page.getByRole('button', { name: S.flex.back, exact: true }).click()
  await shows(last.order[at - 1]!)
  test.info().annotations.push({ type: 'battery_disagreement', description: String(disagreements) })
  expect(disagreements).toBe(0)
  // Pause keeps the assessment, and Resume opens it at the same place.
  await page.getByRole('button', { name: S.flex.pause }).click()
  await expect(page.getByTestId('flex-resume')).toBeVisible()
  await page.getByRole('button', { name: S.flex.resume }).click()
  await shows(last.order[at - 1]!)
  // A new start of the app asks the engine again, and its early answer shows; saving it
  // stores the report the engine gives back.
  const finishes = async () => (await received(page)).filter((r) => r.path.endsWith('/flexibility/capture/finish')).length
  const saved = await finishes()
  await page.reload()
  await expect(page.getByTestId('early-answer')).toBeVisible()
  await page.getByRole('button', { name: S.flex.saveAssessment }).click()
  await expect(page.getByTestId('flex-pattern')).toContainText(last.early_pattern_label)
  await expect.poll(finishes).toBe(saved + 1)
})

test('Engine data and the other screens keep their saved answers with the engine down', async ({ page, context }) => {
  await onboard(page)
  await scenario(context, `e2e-down-${Date.now()}`)
  await page.goto('/#/insights/engine')
  await expect(page.getByTestId('directive')).toBeVisible()
  await page.goto('/#/insights/trends')
  await expect(page.getByTestId('regions')).toBeVisible()
  await setEngineDown(context, true)
  await page.goto('/#/insights/engine')
  await page.reload()
  await expect(page.getByTestId('directive')).toContainText(F.engine.directive.words)
  await expect(page.getByText(S.fresh.why.engine_unavailable, { exact: false })).toBeVisible()
  await page.goto('/#/insights/trends')
  await expect(page.getByTestId('regions')).toBeVisible()
  await expect(page.getByText(S.fresh.saved, { exact: false })).toBeVisible()
  await setEngineDown(context, false)
})

test('Settings > Data opens a table and keeps the syncs off until the switch-over', async ({ page, context }) => {
  await onboard(page)
  await scenario(context, `e2e-data-${Date.now()}`)
  await openTab(page, S.nav.settings)
  await page.getByRole('button', { name: S.data.open }).click()
  await expect(page.getByTestId('data')).toBeVisible()
  await page.getByText(S.data.table.metrics_history!).click()
  await expect(page.getByTestId('table-metrics_history').locator('table')).toBeVisible()
  const syncs = page.getByTestId('syncs')
  await expect(syncs).toContainText(S.data.syncsWait)
  for (const label of Object.values(S.data.syncButtons)) await expect(syncs.getByRole('button', { name: label })).toBeDisabled()
})
