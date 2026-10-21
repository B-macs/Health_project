// Settings' sync card and the plan's first-run setup (rebuild Phase 9, H57, T29): which app
// syncs the devices, the last sync with each step, the Oura login (never a token), whether a
// sync is due; and the plan's start only while no plan is stored.
import type { ReactNode } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { components } from '../generated/api'
import { HealthDB } from '../db/schema'
import { AppStateProvider } from '../lib/appState'
import { S } from '../strings'
import { OuraLoginCard, PlanStartCard, SyncCard, clockTime, ouraRedirect } from './SettingsSync'

type Status = components['schemas']['StatusOut']
type SettingsAnswer = components['schemas']['SettingsOut']

const draw = (node: ReactNode) => renderToStaticMarkup(
  <AppStateProvider value={{
    store: new HealthDB(`sync-${Math.random()}`), ctx: { key: 'k', engineDown: false }, reduced: true, pick: null,
    showDay: () => undefined, go: () => undefined,
  }}>{node}</AppStateProvider>)
const text = (html: string) => html.replace(/<[^>]+>/g, ' ').replace(/&#x27;/g, "'").replace(/&amp;/g, '&').replace(/\s+/g, ' ')
const none = () => undefined

const BEFORE: Status = { writer: 'streamlit', offline: false, datastore_built_at: null, oura: null, last_sync: null, notices: [], sync_due: null }
const AFTER: Status = {
  writer: 'engine', offline: false, datastore_built_at: null,
  oura: { kind: 'oauth', state: 'ok', needs_authorisation: false, expires_at: '2026-10-21T06:00:00+00:00', seconds_remaining: 80000, oauth_configured: true },
  last_sync: { day: '2026-10-20', at: '2026-10-20T05:12:00+00:00', results: { oura: [true, null], garmin: [false, 'Garmin did not answer'] }, error: null },
  notices: [], sync_due: 'last_night_missing',
}

describe('the sync card', () => {
  it('says the old app syncs the devices before the switch, with no sync of its own', () => {
    const html = text(draw(<SyncCard status={BEFORE} />))
    expect(html).toContain(S.settings.writer.streamlit)
    expect(html).toContain(S.settings.noSync)
    expect(html).not.toContain(S.settings.syncNotDue)
  })

  it('after the switch shows the last sync with each step, the Oura login and whether a sync is due', () => {
    const html = text(draw(<SyncCard status={AFTER} />))
    expect(html).toContain(S.settings.writer.engine)
    expect(html).toContain(S.settings.lastSync(clockTime(AFTER.last_sync!.at!)))
    expect(html).toContain(`${S.settings.steps.oura} ${S.settings.stepOk}`)
    expect(html).toContain(`${S.settings.steps.garmin} ${S.settings.stepFailed}: Garmin did not answer`)
    expect(html).toContain(S.settings.oura(S.settings.ouraState.ok!, clockTime(AFTER.oura!.expires_at!)))
    expect(html).toContain(S.settings.syncDue.last_night_missing!)
  })

  it('draws nothing before the engine has answered', () => {
    expect(draw(<SyncCard status={undefined} />)).toBe('')
  })

  it('a step that did nothing on purpose says why, and a refused Garmin sign-in has its own line', () => {
    // 2026-10-21, 09:57: Garmin refused the engine's sign-in and every Garmin step read "done".
    const paused: Status = { ...AFTER, last_sync: { day: '2026-10-21', at: '2026-10-21T07:57:00+00:00', error: null, results: {
      garmin: [true, 'Garmin is paused after a refusal; next try after 15:57'],
      garmin_sign_in: [false, 'Garmin refused (too many requests); next try after 15:57'],
    } } }
    const html = text(draw(<SyncCard status={paused} />))
    expect(html).toContain(`${S.settings.steps.garmin} Garmin is paused after a refusal; next try after 15:57`)
    expect(html).not.toContain(`${S.settings.steps.garmin} ${S.settings.stepOk}`)
    expect(html).toContain(`${S.settings.steps.garmin_sign_in} ${S.settings.stepFailed}: Garmin refused (too many requests); next try after 15:57`)
  })
})

describe('the plan start (first run)', () => {
  const settings = (running: boolean): SettingsAnswer => ({
    plan_start_date: null, plan_running: running, writer: 'streamlit', garmin_configured: true, oura_configured: true,
    manual_syncs: [],
  })

  it('asks for the start day only while no plan is stored', () => {
    expect(text(draw(<PlanStartCard settings={settings(false)} busy={false} done={null} error={null} onStart={none} />)))
      .toContain(S.settings.planStart)
    expect(draw(<PlanStartCard settings={settings(true)} busy={false} done={null} error={null} onStart={none} />)).toBe('')
    expect(draw(<PlanStartCard settings={undefined} busy={false} done={null} error={null} onStart={none} />)).toBe('')
  })

  it('says the plan runs once started, and why the engine refused', () => {
    const done = { ...settings(true), seeded: true, active_phase: 'Made-up block' }
    expect(text(draw(<PlanStartCard settings={settings(false)} busy={false} done={done} error={null} onStart={none} />)))
      .toContain(S.settings.planStarted('Made-up block'))
    expect(text(draw(<PlanStartCard settings={settings(false)} busy={false} done={null}
      error={S.settings.planRefused.plan_already_running!} onStart={none} />))).toContain(S.settings.planRefused.plan_already_running!)
  })
})

describe('the Oura login (Phase 9)', () => {
  const card = (writer: string, error: string | null = null) =>
    draw(<OuraLoginCard writer={writer} busy={false} error={error} onLogin={none} />)

  it('is on only while the engine runs the syncs, and says why before', () => {
    expect(text(card('streamlit'))).toContain(S.settings.ouraLoginLater)
    expect(card('streamlit')).toMatch(/<button[^>]*disabled=""/)
    expect(text(card('engine'))).toContain(S.settings.ouraLoginWhy)
    expect(card('engine')).not.toMatch(/<button[^>]*disabled=""/)
  })

  it('says why the engine refused, and comes back to this app\'s own address', () => {
    expect(text(card('engine', S.settings.ouraLoginRefused.sync_disabled!))).toContain(S.settings.ouraLoginRefused.sync_disabled!)
    expect(ouraRedirect('https://health.example')).toBe('https://health.example/oura/callback')
  })
})
