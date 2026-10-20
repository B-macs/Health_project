// Insights and Settings › Data (rebuild Phase 8, I1-I93), drawn without a browser from the
// engine's own answers over made-up data (dev/insights_fixture.json, made by
// scripts/make_insights_fixture.py through the engine itself). Each screen is drawn in its
// states: a saved answer while the engine is asked, the engine's fresh answer, not enough data
// (or the engine's refusal), and the engine down (the saved answer kept, with why).
import type { ReactNode } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import fixture from '../../dev/insights_fixture.json'
import type { components } from '../generated/api'
import { HealthDB } from '../db/schema'
import { AppStateProvider } from '../lib/appState'
import type { View } from '../lib/cache'
import { S } from '../strings'
import { ChecksCard, ParseQueueCard, ShadowCard, SyncsCard, TableRows, type Shadow } from './DataTables'
import { InsightsHub } from './Insights'
import { EngineBody } from './InsightsEngine'
import { FlexibilityBody } from './InsightsFlexibility'
import { ColdGate, EarlyAnswer, Step } from './InsightsFlexibilityCapture'
import type { Guide } from './FlexibilityShared'
import { MetabolismBody } from './InsightsMetabolism'
import { SleepArchBody } from './InsightsSleep'
import { REFERENCE_MISSING, StrengthBody } from './InsightsStrength'
import { TrendsBody } from './InsightsTrends'
import { WarningsBody } from './InsightsWarnings'

type Schemas = components['schemas']
const F = fixture as unknown as {
  strength: Record<string, Schemas['StrengthOut']>
  metabolism: Record<string, Schemas['MetabolismOut']>
  flexibility_empty: Schemas['FlexibilityOut']
  flexibility_capturing: Schemas['FlexibilityOut']
  flexibility_populated: Schemas['FlexibilityOut']
  capture: { states: Schemas['FlexCapture'][] }
  engine: Schemas['EngineDataOut']
  queue: Schemas['QueueOut']
  trends: Schemas['TrendsOut']
  trends_closed: Schemas['TrendsOut']
  sleep_architecture: Schemas['SleepArchitectureOut']
  sleep_architecture_empty: Schemas['SleepArchitectureOut']
  tables: Record<string, Schemas['DataTableOut']>
  session_checks: Schemas['SessionChecksOut']
  settings: Schemas['SettingsOut']
}

const draw = (node: ReactNode) => renderToStaticMarkup(
  <AppStateProvider value={{
    store: new HealthDB(`insights-${Math.random()}`), ctx: { key: 'k', engineDown: false }, reduced: true, pick: null,
    showDay: () => undefined, go: () => undefined,
  }}>{node}</AppStateProvider>)
const text = (html: string) => html.replace(/<[^>]+>/g, ' ').replace(/&#x27;/g, "'").replace(/&quot;/g, '"')
  .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&').replace(/\s+/g, ' ')
const none = () => undefined

// The four states a card is drawn in.
const savedAt = '2026-10-20T06:00:00Z'
const saved = <T,>(data: T): View<T> => ({ data, fetchedAt: savedAt, state: 'loading' })
const fresh = <T,>(data: T): View<T> => ({ data, fetchedAt: new Date().toISOString(), state: 'fresh' })
const down = <T,>(data: T | undefined): View<T> => ({ data, fetchedAt: data ? savedAt : null, state: 'engine_unavailable' })
const refused = <T,>(code: string): View<T> => ({ data: undefined, fetchedAt: null, state: 'rejected', code })

const STRENGTH = F.strength['Overall Strength Score']!
const WEIGHT = F.metabolism['Weight|all|0']!

describe('the Insights page', () => {
  it('shows each screen\'s headline as the engine sends it, and opens the engine views', () => {
    const html = text(draw(<InsightsHub strength={fresh(STRENGTH)} metab={fresh(WEIGHT)} flex={fresh(F.flexibility_empty)} go={none} />))
    expect(html).toContain(`${S.ins.strength} ${STRENGTH.overall!.toFixed(1)} ${S.ins.points} · ${S.ins.calibrating}`)
    expect(html).toContain(`${S.ins.metabolism} ${WEIGHT.latest!.weight_kg.toFixed(1)} kg`)
    expect(html).toContain(`${S.ins.flexibility} ${S.ins.none} ${S.ins.notMeasured}`)
    expect(html).toContain(S.ins.cardioSoon)
    for (const label of [S.ins.engine, S.ins.warnings, S.ins.trends, S.ins.sleepArch]) expect(html).toContain(label)
  })

  it('names the pattern an assessment found, or that it found none', () => {
    const populated = F.flexibility_populated
    const found = text(draw(<InsightsHub strength={fresh(STRENGTH)} metab={fresh(WEIGHT)} flex={fresh(populated)} go={none} />))
    expect(found).toContain(`${S.ins.flexibility} ${populated.report!.pattern} ${populated.report!.pattern_label}`)
    const nothing = { ...populated, report: { ...populated.report!, pattern: null, pattern_label: '' } }
    expect(text(draw(<InsightsHub strength={fresh(STRENGTH)} metab={fresh(WEIGHT)} flex={fresh(nothing)} go={none} />)))
      .toContain(`${S.ins.flexibility} ${S.ins.none} ${S.flex.noPattern}`)
  })

  it('says the strength reference is missing, and keeps the saved answers when the engine is down', () => {
    const missing = text(draw(<InsightsHub strength={refused(REFERENCE_MISSING)} metab={fresh(WEIGHT)} flex={fresh(F.flexibility_empty)} go={none} />))
    expect(missing).toContain(`${S.ins.strength} ${S.ins.none} ${S.ins.notMeasured}`)
    const off = text(draw(<InsightsHub strength={down(STRENGTH)} metab={down(WEIGHT)} flex={down(F.flexibility_empty)} go={none} />))
    expect(off).toContain(S.fresh.saved)
    expect(off).toContain(S.fresh.why.engine_unavailable)
    expect(off).toContain(STRENGTH.overall!.toFixed(1))
  })
})

describe('Strength', () => {
  it('draws the headline, the readout, the regions and the imbalances from a fresh answer', () => {
    const raw = draw(<StrengthBody view={fresh(STRENGTH)} reduced onMetric={none} />)
    const html = text(raw)
    expect(html).toContain(`${S.ins.overall} ${STRENGTH.overall!.toFixed(1)} ${S.ins.calibrating}`)
    expect(html).toContain(S.ins.thisWeek(STRENGTH.readout.labels[0]!))
    expect(raw).toContain(`aria-label="${S.ins.scoreChart}"`)
    for (const r of STRENGTH.regions) expect(html).toContain(S.ins.region[r.region]!)
    expect(html).toContain(`${S.ins.imbalances} ${STRENGTH.imbalance_count}`)
    for (const m of STRENGTH.metrics) expect(html).toContain(m.label)
  })

  it('draws a sector\'s tonnage as its own chart, never beside the score', () => {
    const sector = Object.values(F.strength).find((d) => d.metrics.find((m) => m.label === d.metric)?.key !== 'score')!
    const raw = draw(<StrengthBody view={fresh(sector)} reduced onMetric={none} />)
    expect(raw).toContain(`aria-label="${S.ins.tonnageChart(sector.metric)}"`)
    expect(raw).not.toContain(`aria-label="${S.ins.scoreChart}"`)
  })

  it('says why there are no figures before the reference is stored, and nothing saved when the engine is down', () => {
    expect(text(draw(<StrengthBody view={refused(REFERENCE_MISSING)} reduced onMetric={none} />))).toContain(S.ins.referenceMissing)
    const off = text(draw(<StrengthBody view={down<Schemas['StrengthOut']>(undefined)} reduced onMetric={none} />))
    expect(off).toContain(S.fresh.nothingSaved)
    expect(off).not.toContain(S.ins.overall)
    expect(text(draw(<StrengthBody view={saved(STRENGTH)} reduced onMetric={none} />))).toContain(STRENGTH.overall!.toFixed(1))
  })
})

describe('Metabolism', () => {
  it('draws the composition, the split, the series, the gym scan and the analysis cards', () => {
    const html = text(draw(<MetabolismBody view={fresh(WEIGHT)} kept={WEIGHT} onMetric={none} onKind={none} onStep={none} />))
    expect(html).toContain(`${WEIGHT.latest!.fat_mass_kg!.toFixed(1)} ${S.ins.fat}`)
    expect(html).toContain(S.ins.splitFat(WEIGHT.split!.fat, WEIGHT.split!.fat_pct))
    expect(html).toContain(WEIGHT.series.window.label)
    expect(html).toContain(S.ins.cellularNote(WEIGHT.cellular!.device))
    expect(html).toContain(S.ins.daysOld(WEIGHT.cellular!.days_old))
    expect(html).toContain(S.ins.source.derived!)
    expect(html).toContain(S.ins.source.absent!)
    for (const g of WEIGHT.analysis as { group: string }[]) expect(html).toContain(g.group)
  })

  it('steps only where the engine allows, and says so when a period has no reading', () => {
    const week = F.metabolism['Weight|week|-1']!
    const html = draw(<MetabolismBody view={fresh(week)} kept={week} onMetric={none} onKind={none} onStep={none} />)
    expect(html).toMatch(new RegExp(`aria-label="${S.ins.nextPeriod}"(?![^>]*disabled)`))
    const emptySeries = { ...week, series: { ...week.series, points: [], runs: [], first: null, last: null, change: null, axis: null } }
    const empty = text(draw(<MetabolismBody view={fresh(emptySeries)} kept={emptySeries} onMetric={none} onKind={none} onStep={none} />))
    expect(empty).toContain(S.ins.noReadingIn(week.series.window.label))
  })

  it('keeps the saved answer when the engine is down, and names a failed read', () => {
    const off = text(draw(<MetabolismBody view={down(WEIGHT)} kept={WEIGHT} onMetric={none} onKind={none} onStep={none} />))
    expect(off).toContain(S.fresh.why.engine_unavailable)
    expect(off).toContain(S.ins.composition)
    const failed = { ...WEIGHT, load_error: 'made-up failure' }
    expect(text(draw(<MetabolismBody view={fresh(failed)} kept={failed} onMetric={none} onKind={none} onStep={none} />)))
      .toContain(S.ins.readFailed('made-up failure'))
  })
})

describe('Flexibility', () => {
  const flex = (data: Schemas['FlexibilityOut'], view = fresh(data)) =>
    text(draw(<FlexibilityBody view={view} reduced onAnswer={none} onResume={none} onAssess={none} />))

  it('opens empty with one button, what it produces, the slots and the tests held back', () => {
    const html = flex(F.flexibility_empty)
    const guide = F.flexibility_empty.guide as unknown as Guide
    expect(html).toContain(S.flex.notMeasured)
    expect(html).toContain(S.flex.start)
    expect(html).toContain(S.flex.producesTitle)
    expect(html).toContain(S.flex.heldTitle(guide.held_back.length))
    expect(html).toContain(guide.cluster_label)
  })

  it('offers the assessment in progress back', () => {
    const c = F.flexibility_capturing
    expect(flex({ ...c, capture: F.capture.states[1]! })).toContain(S.flex.resume)
  })

  it('leads with the pattern, then the ladder, the stack, the trail, the readings and the retest', () => {
    const r = F.flexibility_populated.report!
    const html = flex(F.flexibility_populated)
    expect(html).toContain(r.pattern_label)
    expect(html).toContain(S.flex.patternIs(r.pattern!))
    expect(html).toContain(S.flex.slotsRun(r.slots.length, r.slots_total))
    expect(html).toContain(S.flex.stopping)
    expect(html).toContain(S.flex.ladderTitle)
    expect(html).toContain(S.flex.rung.unmeasured)
    expect(html).toContain(S.flex.trailTitle(r.slots.length))
    expect(html).toContain(S.flex.readingsTitle)
    expect(html).toContain(S.flex.reassess)
    if (!r.trusted) expect(html).toContain('hypothesis, not a verdict')
    const stack = r.stack as { pattern: string; limiter: string; items: { exercise: string }[] }
    expect(html).toContain(S.flex.stackTitle(stack.pattern, stack.limiter))
    for (const item of stack.items) expect(html).toContain(item.exercise)
  })

  it('with no pattern says a missing reading is not a pass and asks for the readings it waits on', () => {
    const base = F.flexibility_populated
    const noPattern = {
      ...base,
      report: { ...base.report!, pattern: null, pattern_label: '', stack: null,
        missing: [{ test_key: 'made_up', side: 'left', setup: false, label: 'Made-up reading', hint: 'in cm' }] },
    }
    const html = flex(noPattern)
    expect(html).toContain(S.flex.noPattern)
    expect(html).toContain(S.flex.notAPass)
    expect(html).toContain(S.flex.missingWhy(1))
    expect(html).toContain(S.flex.addRerun)
  })

  it('names a record it could not read, and keeps the saved one when the engine is down', () => {
    const unreadable = { ...F.flexibility_empty, state: 'unreadable', load_error: 'made-up failure' }
    expect(flex(unreadable)).toContain(S.flex.unreadable('made-up failure'))
    expect(flex(F.flexibility_populated, down(F.flexibility_populated))).toContain(S.fresh.saved)
  })
})

describe('the capture', () => {
  const guide = F.flexibility_empty.guide as unknown as Guide

  it('asks cold or warm, warns after a leg day, and explains the protocol before the first test', () => {
    const html = text(draw(<ColdGate guide={guide} legs busy={false} onBegin={none} />))
    expect(html).toContain(S.flex.coldChoice)
    expect(html).toContain(S.flex.warmChoice)
    expect(html).toContain(S.flex.legDay)
    expect(html).toContain(S.flex.threeNumbers)
    expect(html).toContain(S.flex.begin)
    expect(text(draw(<ColdGate guide={guide} legs={false} busy={false} onBegin={none} />))).not.toContain(S.flex.legDay)
  })

  it('shows the engine\'s test at the owner\'s place: its LOCK first, its place, its form', () => {
    const c = F.capture.states[0]!
    for (const at of [0, 1]) {
      const test = c.order[at]!
      const html = text(draw(<Step c={c} at={at} busy={false} onSave={none} onMove={none} />))
      expect(html).toContain(test.label)
      expect(html).toContain(S.flex.stepOf(at + 1, c.order.length, test.slot, test.slot_label))
      expect(html).toContain(S.flex.lock)
      expect(html).toContain(at === c.order.length - 1 ? S.flex.saveFinish : S.flex.saveNext)
    }
    expect(draw(<Step c={c} at={0} busy={false} onSave={none} onMove={none} />))
      .toMatch(new RegExp(`disabled=""[^>]*>${S.flex.back}<`))
  })

  it('offers a reading already taken back in its field', () => {
    const c = F.capture.states[1]!
    const reading = c.readings[0]!
    const at = c.order.findIndex((t) => t.key === reading.test_key)
    expect(draw(<Step c={c} at={at} busy={false} onSave={none} onMove={none} />)).toContain(`value="${reading.value}"`)
  })

  it('stops at the engine\'s early answer, with its reason, and offers to keep going', () => {
    const c = F.capture.states[F.capture.states.length - 1]!
    expect(c.early_pattern).toBeTruthy()
    const html = text(draw(<EarlyAnswer c={c} busy={false} onSave={none} onKeepGoing={none} />))
    expect(html).toContain(S.flex.yourAnswer)
    expect(html).toContain(S.flex.patternLine(c.early_pattern!, c.early_pattern_label))
    expect(html).toContain(c.early_reason!)
    expect(html).toContain(S.flex.keepGoing)
  })
})

describe('Engine data', () => {
  it('draws the directive in Home\'s words, the stage, the light and the workload', () => {
    const e = F.engine
    const html = text(draw(<EngineBody view={fresh(e)} reduced onRefresh={none} />))
    const d = e.directive as { words: string; engine_label: string }
    expect(html).toContain(d.words)
    expect(html).toContain(S.eng.engineLabel(d.engine_label).replace(/\s+/g, ' '))
    expect(html).toContain((e.stage as { stage_label: string }).stage_label)
    expect(html).toContain('Overall: GREEN')
    for (const c of (e.traffic_light as { cards: { label: string }[] }).cards) expect(html).toContain(c.label)
    expect(html).toContain(S.eng.auChart)
    expect(html).toContain(S.eng.volume)
  })

  it('names a failed read, and keeps the saved answer when the engine is down', () => {
    const failed = { today: '2026-10-20', load_error: 'made-up failure' } as Schemas['EngineDataOut']
    const html = text(draw(<EngineBody view={fresh(failed)} reduced onRefresh={none} />))
    expect(html).toContain(S.eng.unreadable('made-up failure'))
    expect(html).not.toContain(S.eng.directive)
    expect(text(draw(<EngineBody view={down(F.engine)} reduced onRefresh={none} />))).toContain(S.fresh.saved)
  })
})

describe('Warnings', () => {
  it('draws the month with its marked days, and a tapped day\'s entries', () => {
    const q = F.queue
    const marked = q.weeks.flat().find((d) => d.entries.length > 0)!
    const html = draw(<WarningsBody view={fresh(q)} data={q} picked={marked.date} onPick={none} onMonth={none} />)
    expect(html).toContain(`data-level="${marked.level}"`)
    expect(text(html)).toContain(S.warn.level[marked.entries[0]!.level]!)
    expect(text(html)).toContain(S.warn.areas(marked.entries[0]!.parts))
    expect(text(draw(<WarningsBody view={fresh(q)} data={q} picked={null} onPick={none} onMonth={none} />)))
      .not.toContain(S.warn.areas(marked.entries[0]!.parts))
  })
})

describe('Trends', () => {
  it('draws the regions, the timeline, the levels and the analysis once the gate opens', () => {
    const html = text(draw(<TrendsBody view={fresh(F.trends)} reduced />))
    expect(html).toContain(S.trend.regions)
    expect(html).toContain(S.trend.timeline)
    expect(html).toContain(S.trend.levels)
    expect(html).toContain(S.trend.reading)
    expect(html).not.toContain(S.trend.needMore(14, 0).slice(0, 30))
  })

  it('says how much more data the analysis needs, when there is no check-in, and when no note was parsed', () => {
    const closed = F.trends_closed
    const gate = closed.gate as { needed: number; bio_days: number }
    expect(text(draw(<TrendsBody view={fresh(closed)} reduced />))).toContain(S.trend.needMore(gate.needed, gate.bio_days))
    const empty = { ...closed, regions: [], timeline: [], timeline_axis: null, levels: {} }
    const none = text(draw(<TrendsBody view={fresh(empty)} reduced />))
    expect(none).toContain(S.trend.noCheckins)
    expect(none).toContain(S.trend.noParsed)
    // Every check-in is on the timeline, also when no note was parsed (the owner, 2026-10-20).
    const unread = { ...F.trends, levels: { none: [], monitor: [], flag: [] } }
    const html = text(draw(<TrendsBody view={fresh(unread)} reduced />))
    expect(html).toContain(S.trend.timeline)
    expect(html).toContain(S.trend.noParsed)
    expect(html).not.toContain(S.trend.levels)
  })
})

describe('Sleep architecture', () => {
  it('draws the counts and a night\'s three strips, and says when nothing is fused', () => {
    const a = F.sleep_architecture
    const html = text(draw(<SleepArchBody view={fresh(a)} data={a} onNight={none} />))
    for (const s of (a.night as { strips: { label: string }[] }).strips) expect(html).toContain(s.label)
    expect(html).toContain(S.arch.fused)
    const empty = F.sleep_architecture_empty
    expect(text(draw(<SleepArchBody view={fresh(empty)} data={empty} onNight={none} />))).toContain(S.arch.empty)
    const failed = { load_error: 'made-up failure' } as Schemas['SleepArchitectureOut']
    expect(text(draw(<SleepArchBody view={fresh(failed)} data={failed} onNight={none} />))).toContain(S.arch.unreadable('made-up failure'))
  })
})

describe('Settings > Data', () => {
  it('shows what waits for the parse, and the button only when something waits', () => {
    const q = F.queue
    expect(text(draw(<ParseQueueCard data={q} busy={false} result={null} error={null} onProcess={none} />))).toContain(S.data.queueNone)
    const waiting = { ...q, pending_notes: 2 }
    expect(text(draw(<ParseQueueCard data={waiting} busy={false} result={null} error={null} onProcess={none} />))).toContain(S.data.process)
  })

  it('draws the session checks, a table\'s rows, the shadow report and the syncs, off until the switch', () => {
    expect(text(draw(<ChecksCard data={F.session_checks} />))).toContain(S.data.checksNone)
    expect(text(draw(<ChecksCard data={{ warnings: ['Made-up warning'] }} />))).toContain('Made-up warning')
    const table = F.tables.metrics_history!
    expect(text(draw(<TableRows table="metrics_history" data={table} />))).toContain(S.data.rows(table.rows.length))
    const shadow = F.sleep_architecture.shadow as unknown as Shadow
    expect(text(draw(<ShadowCard shadow={shadow} />))).toContain(S.data.shadowNights(shadow.nights_compared))
    const syncs = draw(<SyncsCard settings={F.settings} />)
    expect(text(syncs)).toContain(S.data.syncsWait)
    expect(syncs.match(/disabled=""/g)?.length).toBe(F.settings.manual_syncs.length)
    for (const kind of F.settings.manual_syncs) expect(text(syncs)).toContain(S.data.syncButtons[kind]!)
  })

  it('turns the sync buttons on once the engine runs the syncs, and says how each one went', () => {
    const on = draw(<SyncsCard settings={{ ...F.settings, writer: 'engine' }} results={{ sleep_fusion: S.data.syncDone }} />)
    expect(text(on)).toContain(S.data.autoEngine)
    expect(text(on)).not.toContain(S.data.syncsWait)
    expect(on.match(/disabled=""/g)).toBeNull()
    expect(text(on)).toContain(S.data.syncDone)
    const running = draw(<SyncsCard settings={{ ...F.settings, writer: 'engine' }} results={{ oura_weekly: S.data.syncRunning }} />)
    expect(running.match(/disabled=""/g)?.length).toBe(F.settings.manual_syncs.length)
  })
})
