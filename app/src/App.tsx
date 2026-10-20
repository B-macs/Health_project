// The app's frame (rebuild Phases 4 and 5: the offline shell over the owner's Phase 3
// design). Today, Check-in, Training, Insights and Settings over one inner scroller, with
// the tab bar docked below. Each page keeps its one colour family: the root carries the
// page's .fam-* class, so the tab bar takes the page's colour too.
//
// - Routes are #hashes (wouter's hash location): every page load is "/", which the
//   service worker answers from the precache, so the app opens with no connection.
// - With no access key saved, the first-open screen shows instead (screens/Welcome.tsx).
// - Today and its three detail screens (/readiness, /sleep, /strain) share the day shown
//   (lib/day.ts); Check-in is a sheet over Today; the page behind keeps its own colour.
// - Training shows the week and today's session before Start, the guided flow while it runs
//   and the save at its end (screens/TrainingTab.tsx); its "+" menu's screens have their own
//   addresses under /training/. While a session runs, the tab bar hides and an app update
//   waits; a session left open (a reload, an app kill) opens again at the next start.
// - The outbox sends what waits whenever the app is open (lib/outbox.ts).
// - Insights shows the engine's long view (Phase 8): a hub of cards, each screen with its own
//   address under /insights/; the data tables and the manual syncs are under /settings/data.
//
// The address can carry the appearance and less motion for the screenshot report:
// ?t=auto|light|dark &still (motion off, so a picture never catches a ring half-drawn).
import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type ReactElement } from 'react'
import { Redirect, Route, Router, Switch, useLocation } from 'wouter'
import { useHashLocation } from 'wouter/use-hash-location'
import { KEYS, setSetting, type HealthDB } from './db/schema'
import { cssVars, useMode, useReducedMotion, type ThemePref } from './design/theme'
import { PAGE_FAMILY, type Mode } from './design/tokens'
import { AppStateProvider, type AppState } from './lib/appState'
import { refresh, type Ctx } from './lib/cache'
import { pickFor, readPick, writePick, type Pick } from './lib/day'
import { localDay } from './lib/api'
import { refreshAlerts } from './lib/alerts'
import { useOutboxLoop } from './lib/outbox'
import { useAppSettings, type AppSettings } from './lib/settings'
import { isStandalone } from './lib/standalone'
import { useLiveQuery } from 'dexie-react-hooks'
import { CheckIn, formPath } from './screens/CheckIn'
import { ReadinessScreen, SleepScreen, StrainScreen } from './screens/Details'
import { CardioScreen, Insights } from './screens/Insights'
import { DataScreen } from './screens/DataTables'
import { EngineScreen } from './screens/InsightsEngine'
import { FlexibilityScreen } from './screens/InsightsFlexibility'
import { FlexibilityCapture } from './screens/InsightsFlexibilityCapture'
import { MetabolismScreen } from './screens/InsightsMetabolism'
import { SleepArchScreen } from './screens/InsightsSleep'
import { TrendsScreen } from './screens/InsightsTrends'
import { WarningsScreen } from './screens/InsightsWarnings'
import { StrengthScreen } from './screens/InsightsStrength'
import { Settings, THEMES } from './screens/Settings'
import { Today } from './screens/Today'
import { TrainingTab } from './screens/TrainingTab'
import { Welcome } from './screens/Welcome'
import { S } from './strings'
import { IconCheckin, IconInsights, IconSettings, IconToday, IconTraining } from './ui/icons'
import { ScreenBoundary } from './ui/ScreenBoundary'

type Tab = keyof typeof PAGE_FAMILY
const TABS: { key: Tab; path: string; icon: () => ReactElement }[] = [
  { key: 'today', path: '/', icon: IconToday },
  { key: 'checkin', path: '/checkin', icon: IconCheckin },
  { key: 'training', path: '/training', icon: IconTraining },
  { key: 'insights', path: '/insights', icon: IconInsights },
  { key: 'settings', path: '/settings', icon: IconSettings },
]

/** The tab an address belongs to: the detail screens are Today's. */
export function tabOf(location: string): Tab {
  if (['/readiness', '/sleep', '/strain'].includes(location)) return 'today'
  if (location.startsWith('/training/')) return 'training'
  if (location.startsWith('/insights/')) return 'insights'
  if (location.startsWith('/settings/')) return 'settings'
  return TABS.find((t) => t.path === location)?.key ?? 'today'
}

function TabBar({ tab, onTab }: { tab: Tab; onTab: (path: string) => void }) {
  return (
    <nav className="tabbar" aria-label={S.app}>
      <div className="tabbar__inner">
        {TABS.map(({ key, path, icon: Icon }) => (
          <button key={key} className={`tab${tab === key ? ' tab--on' : ''}`}
            aria-current={tab === key ? 'page' : undefined} onClick={() => onTab(path)}>
            <Icon />
            <span className="tab__label">{S.nav[key]}</span>
          </button>
        ))}
      </div>
    </nav>
  )
}

type ShellProps = {
  store: HealthDB
  settings: AppSettings
  ctx: Ctx
  vars: Record<string, string>
  mode: Mode
  theme: ThemePref
  reduced: boolean
  resume: boolean
}

function Shell(p: ShellProps) {
  const [location, navigate] = useLocation()
  const tab = tabOf(location)
  const scroller = useRef<HTMLElement>(null)
  const [pick, setPick] = useState<Pick | null>(readPick)
  const sessionRow = useLiveQuery(() => p.store.session.get('current'), [p.store])

  // A session left open by a reload or an app kill opens again.
  useEffect(() => {
    if (p.resume) navigate('/training', { replace: true })
    // only at the start
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Today's check-in form is read at the start, so the sheet opens with no connection later.
  const { store, ctx } = p
  useEffect(() => {
    if (ctx.key) void refresh(store, formPath(localDay()), null, ctx).catch(() => undefined)
  }, [store, ctx])

  const go = useCallback((path: string) => {
    navigate(path)
    scroller.current?.scrollTo(0, 0)
  }, [navigate])
  const showDay = useCallback((day: string | null) => {
    const next = pickFor(day)
    writePick(next)
    setPick(next)
  }, [])
  const alerts = p.settings.alerts
  const state = useMemo<AppState>(() => ({ store, ctx, reduced: p.reduced, pick, showDay, go, alerts }),
    [store, ctx, p.reduced, pick, showDay, go, alerts])

  // The timer alerts' subscription again at every start (iOS has no event when it changes).
  useEffect(() => {
    if (ctx.key) void refreshAlerts(store, ctx)
    // once a start, with the key
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ctx.key])

  if (!p.settings.key) {
    return (
      <div className={`app app--${p.mode} fam-${PAGE_FAMILY.settings}`} style={p.vars as CSSProperties}>
        <main className="scroller">
          <Welcome store={p.store} standalone={isStandalone()} installSkipped={p.settings.installSkipped} />
        </main>
      </div>
    )
  }

  const today = (
    <div className={`fam-${PAGE_FAMILY.today}`}>
      <Today />
    </div>
  )
  // The tab bar hides only while a session runs (the overview before Start keeps it).
  const inSession = tab === 'training' && !!sessionRow
  const classes = `app app--${p.mode} fam-${PAGE_FAMILY[tab]}${inSession ? ' app--session' : ''}`
  return (
    <AppStateProvider value={state}>
      <div className={classes} style={p.vars as CSSProperties}>
        <main className="scroller" ref={scroller}>
          <ScreenBoundary key={location} title={S.nav[tab]}>
            <Switch>
              <Route path="/">{today}</Route>
              <Route path="/checkin">{today}</Route>
              <Route path="/readiness"><ReadinessScreen /></Route>
              <Route path="/sleep"><SleepScreen /></Route>
              <Route path="/strain"><StrainScreen /></Route>
              <Route path="/training"><TrainingTab /></Route>
              <Route path="/training/yoga"><TrainingTab extra="yoga" /></Route>
              <Route path="/training/yoga/:slug">{(params) => <TrainingTab extra="yoga" slug={params.slug} />}</Route>
              <Route path="/training/outdoor"><TrainingTab extra="outdoor" /></Route>
              <Route path="/training/accessory"><TrainingTab extra="accessory" /></Route>
              <Route path="/insights"><Insights /></Route>
              <Route path="/insights/strength"><StrengthScreen /></Route>
              <Route path="/insights/metabolism"><MetabolismScreen /></Route>
              <Route path="/insights/flexibility"><FlexibilityScreen /></Route>
              <Route path="/insights/flexibility/capture"><FlexibilityCapture /></Route>
              <Route path="/insights/cardio"><CardioScreen /></Route>
              <Route path="/insights/engine"><EngineScreen /></Route>
              <Route path="/insights/warnings"><WarningsScreen /></Route>
              <Route path="/insights/trends"><TrendsScreen /></Route>
              <Route path="/insights/sleep"><SleepArchScreen /></Route>
              <Route path="/settings/data"><DataScreen /></Route>
              <Route path="/settings">
                <Settings store={p.store} ctx={p.ctx} theme={p.theme}
                  onTheme={(t) => void setSetting(p.store, KEYS.theme, t)} />
              </Route>
              <Route>
                <Redirect to="/" replace />
              </Route>
            </Switch>
          </ScreenBoundary>
        </main>
        {!inSession && <TabBar tab={tab} onTab={go} />}
        {tab === 'checkin' && <CheckIn onClose={() => go('/')} />}
      </div>
    </AppStateProvider>
  )
}

export function App({ store, initial, resume }: { store: HealthDB; initial: AppSettings; resume: boolean }) {
  const settings = useAppSettings(store, initial)
  const query = useMemo(() => new URLSearchParams(window.location.search), [])
  const forced = query.get('t')
  const theme = THEMES.includes(forced as ThemePref) ? (forced as ThemePref) : settings.theme
  const mode = useMode(theme)
  const reduced = useReducedMotion() || query.has('still')
  const vars = useMemo(() => cssVars(mode, reduced), [mode, reduced])
  const ctx = useMemo<Ctx>(() => ({ key: settings.key, engineDown: settings.engineDown }),
    [settings.key, settings.engineDown])
  useOutboxLoop(store, ctx)

  // The page behind the app, the status bar and the browser chrome take the app's colours.
  useEffect(() => {
    const root = document.documentElement
    root.style.background = vars['--bg']
    root.style.colorScheme = mode
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', vars['--bg'])
  }, [vars, mode])

  return (
    <Router hook={useHashLocation}>
      <Shell store={store} settings={settings} ctx={ctx} vars={vars} mode={mode} theme={theme}
        reduced={reduced} resume={resume} />
    </Router>
  )
}
