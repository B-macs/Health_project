// The design preview (rebuild Phase 3): four Oura-style styles of Today, Training,
// Insights and the tab bar, on seeded mock data. The first screen picks the style;
// Settings changes it. Each page keeps its one colour family (PAGE_FAMILY): the app's
// root carries the page's family class, so the tab bar takes the page's colour too.
//
// The style and the appearance are remembered on this phone only (localStorage,
// wrapped: a private window has none). The address can carry them too, for the
// screenshot report:  ?v=1|2|3|4  &s=today|training|insights|checkin|settings|picker
// &t=auto|light|dark  &still (motion off, as with Reduce Motion, so a picture never
// catches a ring half-drawn)
import { useEffect, useMemo, useRef, useState, type CSSProperties, type ReactElement } from 'react'
import { PAGE_FAMILY, STYLE_IDS, STYLES, type StyleId } from '../design/tokens'
import { cssVars, lookClasses, useMode, useReducedMotion, type ThemePref } from '../design/theme'
import { MOCK } from '../mock/data'
import { S } from '../strings'
import { versionLine } from '../version'
import { IconCheckin, IconForward, IconInsights, IconSettings, IconToday, IconTraining } from './icons'
import { Insights } from './Insights'
import { Ring } from './parts'
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
  const v = q.get('v') ?? read('preview.style')
  const t = q.get('t') ?? read('preview.theme')
  const s = q.get('s')
  const style = STYLE_IDS.includes(v as StyleId) ? (v as StyleId) : null
  const theme = THEMES.includes(t as ThemePref) ? (t as ThemePref) : 'auto'
  const tab = TABS.some((x) => x.key === s) ? (s as Tab) : 'today'
  return { style: s === 'picker' ? null : style, theme, tab, still: q.has('still') }
}

function Segmented<T extends string>(p: { name: string; value: T; options: readonly T[]; label: (v: T) => string; onChange: (v: T) => void }) {
  return (
    <div className="segmented" role="radiogroup" aria-label={p.name}>
      {p.options.map((o) => (
        <button key={o} role="radio" aria-checked={o === p.value}
          className={`segmented__item${o === p.value ? ' segmented__item--on' : ''}`}
          onClick={() => p.onChange(o)}>
          {p.label(o)}
        </button>
      ))}
    </div>
  )
}

function Picker(p: { theme: ThemePref; onTheme: (t: ThemePref) => void; onPick: (id: StyleId) => void; reduced: boolean }) {
  return (
    <div className="screen picker">
      <div className="sky" aria-hidden="true" />
      <header className="pagehead">
        <h1 className="pagehead__title">{S.styles.pick}</h1>
        <p className="caption pagehead__lead">{S.styles.lead}</p>
      </header>
      <div className="picker__list">
        {STYLE_IDS.map((id) => (
          <button key={id} className="card picker__card" onClick={() => p.onPick(id)}>
            <Ring className="ring--mini" fraction={0.72} reduced={p.reduced} label={S.styles.names[id]}>
              <span className="num mini__value">{id}</span>
            </Ring>
            <span className="picker__text">
              <span className="picker__name">{S.styles.names[id]}</span>
              <span className="caption">{S.styles.ideas[id]}</span>
            </span>
            <IconForward />
          </button>
        ))}
      </div>
      <section className="card group">
        <div className="eyebrow">{S.settings.appearance}</div>
        <Segmented name={S.settings.appearance} value={p.theme} options={THEMES}
          label={(t) => S.settings.themes[t]} onChange={p.onTheme} />
      </section>
      <section className="card group">
        <div className="eyebrow">{S.styles.howTitle}</div>
        <ol className="how">
          {S.styles.how.map((line) => <li key={line}>{line}</li>)}
        </ol>
      </section>
      <p className="caption">{versionLine(__APP_BUILD__)}</p>
    </div>
  )
}

function Settings(p: { style: StyleId; theme: ThemePref; onStyle: (id: StyleId) => void; onTheme: (t: ThemePref) => void; onPicker: () => void }) {
  return (
    <div className="screen settings">
      <div className="sky sky--quiet" aria-hidden="true" />
      <header className="pagehead">
        <h1 className="pagehead__title">{S.settings.title}</h1>
      </header>
      <section className="card group">
        <div className="eyebrow">{S.styles.label}</div>
        <Segmented name={S.styles.label} value={p.style} options={STYLE_IDS}
          label={(id) => S.styles.names[id]} onChange={p.onStyle} />
        <button className="btn btn--glass btn--wide" onClick={p.onPicker}>{S.styles.pick}</button>
      </section>
      <section className="card group">
        <div className="eyebrow">{S.settings.appearance}</div>
        <Segmented name={S.settings.appearance} value={p.theme} options={THEMES}
          label={(t) => S.settings.themes[t]} onChange={p.onTheme} />
      </section>
      <section className="card group">
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
  const [styleId, setStyleId] = useState<StyleId | null>(start.style)
  const [theme, setTheme] = useState<ThemePref>(start.theme)
  const [tab, setTab] = useState<Tab>(start.tab)
  const [dayIndex, setDayIndex] = useState(MOCK.days.length - 1)
  const mode = useMode(theme)
  const reduced = useReducedMotion() || start.still
  const scroller = useRef<HTMLElement>(null)
  const style = STYLES[styleId ?? '1']
  const vars = useMemo(() => cssVars(style, mode, reduced), [style, mode, reduced])

  // The page behind the app, the status bar and the browser chrome take the app's colours.
  useEffect(() => {
    const root = document.documentElement
    root.style.background = vars['--bg']
    root.style.colorScheme = mode
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', vars['--bg'])
  }, [vars, mode])

  const toTop = () => scroller.current?.scrollTo(0, 0)
  const go = (t: Tab) => {
    setTab(t)
    toTop()
  }
  const pick = (id: StyleId) => {
    setStyleId(id)
    write('preview.style', id)
    setTab('today')
    toTop()
  }
  const chooseTheme = (t: ThemePref) => {
    setTheme(t)
    write('preview.theme', t)
  }

  const picking = styleId === null
  const inSession = !picking && tab === 'training'
  const family = picking ? 'teal' : PAGE_FAMILY[tab]
  const classes = `app app--${mode} fam-${family} ${lookClasses(style)}${inSession ? ' app--session' : ''}`
  return (
    <div className={classes} style={vars as CSSProperties}>
      <main className="scroller" ref={scroller}>
        {picking && <Picker theme={theme} onTheme={chooseTheme} onPick={pick} reduced={reduced} />}
        {!picking && tab === 'today' && (
          <Today layout={style.look.today} day={MOCK.days[dayIndex]} mock={MOCK} reduced={reduced}
            canPrev={dayIndex > 0} canNext={dayIndex < MOCK.days.length - 1}
            onPrev={() => setDayIndex((i) => Math.max(0, i - 1))}
            onNext={() => setDayIndex((i) => Math.min(MOCK.days.length - 1, i + 1))}
            onStart={() => go('training')} />
        )}
        {!picking && tab === 'training' && <Training mock={MOCK} reduced={reduced} onClose={() => go('today')} />}
        {!picking && tab === 'insights' && <Insights mock={MOCK} reduced={reduced} />}
        {!picking && tab === 'checkin' && <NotInPreview title={S.nav.checkin} />}
        {!picking && tab === 'settings' && styleId && (
          <Settings style={styleId} theme={theme} onStyle={pick} onTheme={chooseTheme}
            onPicker={() => setStyleId(null)} />
        )}
      </main>
      {!picking && !inSession && <TabBar tab={tab} onTab={go} />}
    </div>
  )
}
