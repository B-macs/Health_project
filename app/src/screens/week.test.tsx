// The week page (rebuild Phase 7, T8-T36), drawn without a browser from the mock's made-up
// engine answers (typed against the engine's contract): the banner and last week's line,
// the Monday notices and the redo, the questions that move a session (each asked, never
// answered by the page itself), gate 1, the retest, the strip with its markers and arrows,
// and every kind of day. An answer that waits to send replaces its question; a refused one
// says why.
import type { ReactNode } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import * as fx from '../../dev/fixtures'
import { HealthDB, type OutboxRow } from '../db/schema'
import { AppStateProvider } from '../lib/appState'
import { S } from '../strings'
import { longDate } from '../ui/parts'
import {
  DayView, Gate1, GapScreen, MovePrompts, RedoOffer, Refusals, Retest, RollupBanner, ScheduleNote, WeekStrip, waiting,
} from './Week'

const LOCAL = '2026-10-21' // a Wednesday
const MONDAY = '2026-10-19'

const draw = (node: ReactNode) => renderToStaticMarkup(
  <AppStateProvider value={{
    store: new HealthDB(`week-${Math.random()}`), ctx: { key: 'k', engineDown: false }, reduced: true, pick: null,
    showDay: () => undefined, go: () => undefined,
  }}>{node}</AppStateProvider>)
const text = (html: string) => html.replace(/<[^>]+>/g, ' ').replace(/&#x27;/g, "'").replace(/&amp;/g, '&').replace(/\s+/g, ' ')
const noop = () => Promise.resolve('id')
const answer = () => undefined
const open = () => true

const week = (scenario: string[] = [], asked: string | null = null, run = fx.newRun()) =>
  fx.trainingWeek(LOCAL, asked, new Set(scenario), run)

const outboxRow = (kind: string, state: OutboxRow['state'], path = `/api/training/${kind}`, last_error?: string): OutboxRow => ({
  id: `${kind}-${state}`, kind, method: 'POST', path, body: {}, day: LOCAL, created_at: `${LOCAL}T07:00:00Z`,
  attempts: 0, next_at: `${LOCAL}T07:00:00Z`, state, last_error,
})

describe('the banner', () => {
  it('shows the streak, this week against the plan with the next line, and the tallies', () => {
    const w = week()
    const html = text(draw(<RollupBanner banner={w.banner!} />))
    expect(html).toContain(S.week.streakWeeks(2, false))
    expect(html).toContain(S.week.thisWeek(1, 4))
    expect(html).toContain(S.week.tier.normal(2))
    expect(html).toContain(S.week.tallies(3, 1))
    expect(html).toContain(S.week.lastWeek(S.week.verdict.perfect))
  })

  it("says each tier in its words, and no last-week line when the engine sends none", () => {
    const base = week().banner!
    for (const [progress, words] of [['no_plan', S.week.tier.no_plan(0)], ['ultimate', S.week.tier.ultimate(0)],
      ['perfect', S.week.tier.perfect(1)], ['failing', S.week.tier.failing(2)]] as const) {
      const html = text(draw(<RollupBanner banner={{ ...base, progress, to_go: progress === 'failing' ? 2 : progress === 'perfect' ? 1 : 0, last_week: null }} />))
      expect(html).toContain(words)
      expect(html).not.toContain(S.week.lastWeek(''))
    }
    expect(text(draw(<RollupBanner banner={{ ...base, streak_weeks: 0 }} />))).toContain(S.week.streakNone)
  })
})

describe('the redo', () => {
  it('is a button only when the engine offers it, and says it waits once answered', () => {
    const offered = week(['redo']).redo
    expect(text(draw(<RedoOffer redo={offered} rows={[]} open answer={answer} redoWeek={noop} />))).toContain(S.week.redo)
    expect(draw(<RedoOffer redo={week().redo} rows={[]} open answer={answer} redoWeek={noop} />)).toBe('')
    expect(draw(<RedoOffer redo={offered} rows={[]} open={false} answer={answer} redoWeek={noop} />)).toBe('')
    expect(text(draw(<RedoOffer redo={offered} rows={[outboxRow('redo', 'waiting')]} open answer={answer} redoWeek={noop} />)))
      .toContain(S.week.waiting)
  })
})

describe('the questions that move a session', () => {
  it('asks the carry (in order or not) and the readiness shift, each with both answers', () => {
    const inOrder = text(draw(<MovePrompts week={week(['carry_in_order', 'shift'])} rows={[]} isOpen={open} answer={answer} carry={noop} shift={noop} />))
    expect(inOrder).toContain(S.week.carryInOrder)
    expect(inOrder).toContain(S.week.carryRun)
    expect(inOrder).toContain(S.week.keepPlanned)
    expect(inOrder).toContain(S.week.shift('made-up short sleep last night'))
    expect(inOrder).toContain(S.week.shiftMove)
    const plain = text(draw(<MovePrompts week={week(['carry'])} rows={[]} isOpen={open} answer={answer} carry={noop} shift={noop} />))
    expect(plain).toContain(S.week.carry)
    expect(plain).toContain(S.week.carryApply)
    expect(plain).toContain(S.week.carryKeep)
  })

  it('asks nothing the engine did not propose, and nothing already answered', () => {
    expect(draw(<MovePrompts week={week()} rows={[]} isOpen={open} answer={answer} carry={noop} shift={noop} />)).toBe('')
    expect(draw(<MovePrompts week={week(['carry', 'shift'])} rows={[]} isOpen={() => false} answer={answer} carry={noop} shift={noop} />)).toBe('')
    const html = text(draw(<MovePrompts week={week(['carry'])} rows={[outboxRow('carry', 'waiting')]} isOpen={open} answer={answer} carry={noop} shift={noop} />))
    expect(html).toContain(S.week.waiting)
    expect(html).not.toContain(S.week.carryApply)
  })
})

describe('gate 1', () => {
  it('asks the reason of a short week, one tap each, and shows the count and the lifts', () => {
    const card = week(['gate1']).gate1!
    const html = text(draw(<Gate1 card={card} rows={[]} isOpen={open} answer={answer} reason={noop} flare={noop} />))
    expect(html).toContain(S.week.gate1Ask('12 Oct', 2, 3, 6))
    for (const r of card.reasons) expect(html).toContain(r.label)
    expect(html).toContain(S.week.gate1Title(2, 6, 1, 2))
    expect(html).toContain(S.week.gate1Weeks(2, 6))
    expect(html).toContain(S.week.gate1Lift('Made-up squat', '80 kg', '90 kg', '88 kg'))
    expect(html).toContain(S.week.flareAsk)
    expect(html).toContain(card.how)
  })

  it('a waiting reason replaces the question; a recorded flare-up says so', () => {
    const card = week(['gate1']).gate1!
    const html = text(draw(<Gate1 card={{ ...card, flare_this_week: true }} rows={[outboxRow('gate1', 'waiting', '/api/training/gate1/reason')]}
      isOpen={open} answer={answer} reason={noop} flare={noop} />))
    expect(html).toContain(S.week.waiting)
    expect(html).not.toContain(card.reasons[0].label)
    expect(html).toContain(S.week.flareRecorded)
    expect(waiting([outboxRow('gate1', 'waiting', '/api/training/gate1/reason')], 'gate1', '/api/training/gate1/flare')).toBe(false)
  })
})

describe('the retest', () => {
  it('says the day before, due, and due but not today', () => {
    for (const status of ['tomorrow', 'ready', 'blocked']) {
      const html = text(draw(<Retest notice={{ kind: status === 'ready' ? 'info' : 'warning', status, reason: 'made-up' }} />))
      expect(html).toContain(S.week.retest[status]('made-up'))
    }
  })
})

describe('the strip', () => {
  it("draws the week's seven days with the engine's markers and labels", () => {
    const w = week()
    const html = draw(<WeekStrip week={w} selected={LOCAL} onPick={() => undefined} onWeek={() => undefined} onToday={() => undefined} />)
    expect((html.match(/data-marker=/g) ?? []).length).toBe(7)
    expect(html).toContain(`data-date="${MONDAY}" data-marker="done"`)
    expect(html).toContain(`data-date="${LOCAL}" data-marker="today"`)
    expect(html).toContain(`aria-current="date"`)
    expect(text(html)).not.toContain(S.week.today)
    expect(html).toContain(S.week.dayLabel(longDate(MONDAY), S.week.marker.done))
  })

  it('another week: "Today", its stored verdict, and the moves clamped to the block', () => {
    const before = week([], fx.addDays(MONDAY, -7))
    const html = draw(<WeekStrip week={before} selected={LOCAL} onPick={() => undefined} onWeek={() => undefined} onToday={() => undefined} />)
    expect(text(html)).toContain(S.week.today)
    expect(text(html)).toContain(S.week.weekOf(longDate(fx.addDays(MONDAY, -7)), S.week.verdict.normal))
    const first = week([], fx.addDays(MONDAY, -70))
    expect(first.week_start).toBe(fx.addDays(MONDAY, -14))
    expect(first.can_go_back).toBe(false)
    const firstHtml = draw(<WeekStrip week={first} selected={LOCAL} onPick={() => undefined} onWeek={() => undefined} onToday={() => undefined} />)
    // No arrows on screen (the owner, 2026-10-20): a swipe changes the week, and the two moves
    // a screen reader uses sit in a hidden block, clamped to the block's weeks.
    expect(firstHtml).not.toContain('dayarrows')
    expect(firstHtml).toMatch(/<button disabled="">Previous week<\/button>/)
    expect(firstHtml).toMatch(/<button>Next week<\/button>/)
  })
})

describe('a day', () => {
  const day = (date: string, scenario: string[] = []) => fx.trainingDay(date, LOCAL, new Set(scenario))

  it('a logged day shows its session', () => {
    const html = text(draw(<DayView day={day(MONDAY)} rows={[]} onSwap={() => undefined} />))
    expect(html).toContain(S.week.logged)
    expect(html).toContain(S.week.loggedLine(6, 52, 300))
    expect(html).toContain('Made-up squat')
  })

  it('a missed day says so, lists what was planned and offers the swap with today', () => {
    const html = text(draw(<DayView day={day(fx.addDays(MONDAY, 1))} rows={[]} onSwap={() => undefined} />))
    expect(html).toContain(S.week.notCompleted)
    expect(html).toContain('Made-up hack squat')
    expect(html).toContain(S.week.swapMissed)
  })

  it('a future day shows its plan, its moved note, the at-home items and "Do this session today" with its warning', () => {
    const thursday = fx.addDays(MONDAY, 3)
    const html = text(draw(<DayView day={day(thursday)} rows={[]} onSwap={() => undefined} />))
    expect(html).toContain(S.week.scheduledFor(longDate(thursday)))
    expect(html).toContain(S.week.moved('Made-up: moved from Monday for the tests.'))
    expect(html).toContain(S.session.atHome)
    expect(html).toContain('Made-up warning: two main sessions in a row.')
    expect(html).toContain(S.week.swapFuture)
  })

  it('a blocked swap says why and offers no button; a waiting swap says it waits', () => {
    const thursday = fx.addDays(MONDAY, 3)
    const blocked = text(draw(<DayView day={day(thursday, ['blocked'])} rows={[]} onSwap={() => undefined} />))
    expect(blocked).toContain(S.week.swapBlocked('made-up: today already has a logged session'))
    expect(blocked).not.toContain(S.week.swapFuture)
    const sent = text(draw(<DayView day={day(thursday)} rows={[outboxRow('swap', 'waiting')]} onSwap={() => undefined} />))
    expect(sent).toContain(S.week.waiting)
    expect(sent).not.toContain(S.week.swapFuture)
  })

  it('a rest day offers its yoga flow; today adds how to train anyway', () => {
    const rest = text(draw(<DayView day={day(fx.addDays(MONDAY, 2 + 7))} rows={[]} onSwap={() => undefined} />))
    expect(rest).toContain(S.week.rest)
    expect(rest).toContain(S.extras.yogaItem('Made-up hip flow', 15))
    expect(rest).not.toContain(S.week.restTrainAnyway)
    const today = fx.trainingDay(LOCAL, LOCAL, new Set(['rest_today']))
    expect(text(draw(<DayView day={today} rows={[]} onSwap={() => undefined} />))).toContain(S.week.restTrainAnyway)
  })

  it('no block: the gap and when the next one starts; damaged phases: says so', () => {
    const gap = text(draw(<DayView day={day(LOCAL, ['gap'])} rows={[]} onSwap={() => undefined} />))
    expect(gap).toContain(S.week.gapTitle)
    expect(gap).toContain(S.week.gapNext('Made-up next block', fx.addDays(LOCAL, 5), 5))
    const stranded = text(draw(<GapScreen gap={{ next: null, stranded: { name: 'Block B', last_date: '2026-10-18', days: [[28, 'test', '2026-10-19']] } }} />))
    expect(stranded).toContain(S.week.gapNone)
    expect(stranded).toContain(S.week.stranded('Block B', S.week.strandedDay(28, 'test', '2026-10-19'), '2026-10-18'))
    expect(text(draw(<DayView day={day(LOCAL, ['unreadable'])} rows={[]} onSwap={() => undefined} />))).toContain(S.week.phasesUnreadable)
  })

  it('a schedule note says "Session moved" only when the session moved', () => {
    expect(text(draw(<ScheduleNote note={{ text: 'made-up', moved: true }} />))).toContain(S.week.moved('made-up'))
    const kept = text(draw(<ScheduleNote note={{ text: 'Declined: left as missed by choice', moved: false }} />))
    expect(kept).toContain('Declined: left as missed by choice')
    expect(kept).not.toContain(S.week.moved(''))
  })
})

describe('refused answers', () => {
  it("each shows the engine's reason and a way to clear it", () => {
    const rows = [outboxRow('swap', 'failed', '/api/training/swap', 'refused: made-up'), outboxRow('carry', 'waiting')]
    const html = text(draw(<Refusals rows={rows} onClear={() => undefined} />))
    expect(html).toContain(S.week.refused(S.week.answerName.swap, S.week.refusedWhy.refused, 'made-up'))
    expect(html).toContain(S.week.clear)
    expect(html).not.toContain(S.week.answerName.carry)
  })
})
