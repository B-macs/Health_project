// The design preview (rebuild Phase 3): Today, Training, Insights and the tab bar in
// the Oura-style design, on seeded mock data.
//
// The appearance is remembered on this phone only (localStorage, wrapped: a private
// window has none). The address can carry the screen and the appearance too, for the
// screenshot report:  ?s=today|training|insights|checkin|settings  &t=auto|light|dark
import { useEffect, useMemo, useRef, useState, type CSSProperties, type ReactElement } from 'react'
import { DESIGN } from '../design/tokens'
import { cssVars, useMode, useReducedMotion, type ThemePref } from '../design/theme'
import { MOCK } from '../mock/data'
import { S } from '../strings'
import { versionLine } from '../version'
import { IconCheckin, IconInsights, IconSettings, IconToday, IconTraining } from './icons'
import { Insights } from './Insights'
import { Today } from './Today'
import { Training } from './Training'

type Tab = 'today' | 'checkin' | 'training' | 'insights' | 'settings'
const TABS: { key: Tab; icon: () => ReactElement }[] = [
  { key: 'today', icon: IconToday },
  { key: 'checkin', icon: IconCheckin },
  { key: 'training', icon: IconTraining },
  { key: 'insights', icon: IconInsights },
  { key: 'settings', icon: IconSettings },
]
const THEMES: ThemePref[] = ['auto', 'light', 'dark']

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
  const t = q.get('t') ?? read('preview.theme')
  const s = q.get('s')
  const theme = THEMES.includes(t as ThemePref) ? (t as ThemePref) : 'auto'
  const tab = TABS.some((x) => x.key === s) ? (s as Tab) : 'today'
  return { theme, tab }
}

function Settings(p: { theme: ThemePref; onTheme: (t: ThemePref) => void }) {
  return (
    <div className="screen settings">
      <div className="sky sky--quiet" aria-hidden="true" />
      <header className="pagehead">
        <h1 className="pagehead__title">{S.settings.title}</h1>
      </header>
      <section className="glass group">
        <div className="eyebrow">{S.settings.appearance}</div>
        <div className="segmented" role="radiogroup" aria-label={S.settings.appearance}>
          {THEMES.map((t) => (
            <button key={t} role="radio" aria-checked={t === p.theme}
              className={`segmented__item${t === p.theme ? ' segmented__item--on' : ''}`}
              onClick={() => p.onTheme(t)}>
              {S.settings.themes[t]}
            </button>
          ))}
        </div>
      </section>
      <section className="glass group">
        <div className="eyebrow">{S.settings.version}</div>
        <div className="caption">{versionLine(__APP_BUILD__)}</div>
        <div className="caption">{S.settings.preview}</div>
      </section>
    </div>
  )
}

function NotInPreview({ title }: { title: string }) {
  return (
    <div className="screen">
      <div className="sky sky--quiet" aria-hidden="true" />
      <header className="pagehead">
        <h1 className="pagehead__title">{title}</h1>
      </header>
      <p className="caption">{S.notInTest}</p>
    </div>
  )
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

export function BakeOff() {
  const start = useMemo(initial, [])
  const [theme, setTheme] = useState<ThemePref>(start.theme)
  const [tab, setTab] = useState<Tab>(start.tab)
  const [dayIndex, setDayIndex] = useState(MOCK.days.length - 1)
  const mode = useMode(theme)
  const reduced = useReducedMotion()
  const scroller = useRef<HTMLElement>(null)
  const vars = useMemo(() => cssVars(DESIGN, mode, reduced), [mode, reduced])

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
    write('preview.theme', t)
  }

  const inSession = tab === 'training'
  return (
    <div className={`app app--${mode}${inSession ? ' app--session' : ''}`} style={vars as CSSProperties}>
      <main className="scroller" ref={scroller}>
        {tab === 'today' && (
          <Today day={MOCK.days[dayIndex]} mock={MOCK} reduced={reduced}
            canPrev={dayIndex > 0} canNext={dayIndex < MOCK.days.length - 1}
            onPrev={() => setDayIndex((i) => Math.max(0, i - 1))}
            onNext={() => setDayIndex((i) => Math.min(MOCK.days.length - 1, i + 1))}
            onStart={() => go('training')} />
        )}
        {tab === 'training' && <Training mock={MOCK} reduced={reduced} onClose={() => go('today')} />}
        {tab === 'insights' && <Insights mock={MOCK} reduced={reduced} />}
        {tab === 'checkin' && <NotInPreview title={S.nav.checkin} />}
        {tab === 'settings' && <Settings theme={theme} onTheme={chooseTheme} />}
      </main>
      {!inSession && <TabBar tab={tab} onTab={go} />}
    </div>
  )
}
