// The app's frame (rebuild Phase 3, the owner's design): Today, Check-in, Training,
// Insights and Settings over one inner scroller, with the tab bar docked below. Each
// page keeps its one colour family: the root carries the page's .fam-* class, so the
// tab bar takes the page's colour too. Phase 4 turns this into the offline app shell
// (the service worker, the stored data, the outbox, the access key); until then every
// number is the seeded mock's.
//
// The appearance is remembered on this phone only (localStorage, wrapped: a private
// window has none). The address can carry the screen and the appearance too, for the
// screenshot report:  ?s=today|checkin|training|insights|settings  &t=auto|light|dark
// &still (motion off, as with Reduce Motion, so a picture never catches a ring half-drawn)
import { useEffect, useMemo, useRef, useState, type CSSProperties, type ReactElement } from 'react'
import { PAGE_FAMILY } from './design/tokens'
import { cssVars, useMode, useReducedMotion, type ThemePref } from './design/theme'
import { MOCK } from './mock/data'
import { Insights } from './screens/Insights'
import { NotYet, Settings, THEMES } from './screens/Settings'
import { Today } from './screens/Today'
import { Training } from './screens/Training'
import { S } from './strings'
import { IconCheckin, IconInsights, IconSettings, IconToday, IconTraining } from './ui/icons'

type Tab = keyof typeof PAGE_FAMILY
const TABS: { key: Tab; icon: () => ReactElement }[] = [
  { key: 'today', icon: IconToday },
  { key: 'checkin', icon: IconCheckin },
  { key: 'training', icon: IconTraining },
  { key: 'insights', icon: IconInsights },
  { key: 'settings', icon: IconSettings },
]

function read(key: string): string | null {
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}

function write(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value)
  } catch {
    // A private window or blocked storage: the choice lasts this visit only.
  }
}

function initial() {
  const q = new URLSearchParams(window.location.search)
  const t = q.get('t') ?? read('app.theme')
  const s = q.get('s')
  return {
    theme: THEMES.includes(t as ThemePref) ? (t as ThemePref) : 'auto',
    tab: TABS.some((x) => x.key === s) ? (s as Tab) : 'today',
    still: q.has('still'),
  }
}

function TabBar({ tab, onTab }: { tab: Tab; onTab: (t: Tab) => void }) {
  return (
    <nav className="tabbar" aria-label={S.app}>
      <div className="tabbar__inner">
        {TABS.map(({ key, icon: Icon }) => (
          <button key={key} className={`tab${tab === key ? ' tab--on' : ''}`}
            aria-current={tab === key ? 'page' : undefined} onClick={() => onTab(key)}>
            <Icon />
            <span className="tab__label">{S.nav[key]}</span>
          </button>
        ))}
      </div>
    </nav>
  )
}

export function App() {
  const start = useMemo(initial, [])
  const [theme, setTheme] = useState<ThemePref>(start.theme)
  const [tab, setTab] = useState<Tab>(start.tab)
  const [dayIndex, setDayIndex] = useState(MOCK.days.length - 1)
  const mode = useMode(theme)
  const reduced = useReducedMotion() || start.still
  const scroller = useRef<HTMLElement>(null)
  const vars = useMemo(() => cssVars(mode, reduced), [mode, reduced])

  // The page behind the app, the status bar and the browser chrome take the app's colours.
  useEffect(() => {
    const root = document.documentElement
    root.style.background = vars['--bg']
    root.style.colorScheme = mode
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', vars['--bg'])
  }, [vars, mode])

  const go = (t: Tab) => {
    setTab(t)
    scroller.current?.scrollTo(0, 0)
  }
  const chooseTheme = (t: ThemePref) => {
    setTheme(t)
    write('app.theme', t)
  }

  const inSession = tab === 'training'
  const classes = `app app--${mode} fam-${PAGE_FAMILY[tab]}${inSession ? ' app--session' : ''}`
  return (
    <div className={classes} style={vars as CSSProperties}>
      <main className="scroller" ref={scroller}>
        {tab === 'today' && (
          <Today day={MOCK.days[dayIndex]} dayIndex={dayIndex} mock={MOCK} reduced={reduced}
            canPrev={dayIndex > 0} canNext={dayIndex < MOCK.days.length - 1}
            onPrev={() => setDayIndex((i) => Math.max(0, i - 1))}
            onNext={() => setDayIndex((i) => Math.min(MOCK.days.length - 1, i + 1))}
            onDay={setDayIndex} onStart={() => go('training')} />
        )}
        {tab === 'training' && <Training mock={MOCK} onClose={() => go('today')} />}
        {tab === 'insights' && <Insights mock={MOCK} reduced={reduced} />}
        {tab === 'checkin' && <NotYet title={S.nav.checkin} />}
        {tab === 'settings' && <Settings theme={theme} onTheme={chooseTheme} />}
      </main>
      {!inSession && <TabBar tab={tab} onTab={go} />}
    </div>
  )
}
