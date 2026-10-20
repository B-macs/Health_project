// Settings (slate): the appearance and the version line. Phase 4 adds the access key,
// the sync status, the data tables and the debug console.
import type { ThemePref } from '../design/theme'
import { S } from '../strings'
import { versionLine } from '../version'

const THEMES: ThemePref[] = ['auto', 'light', 'dark']

export function Settings(p: { theme: ThemePref; onTheme: (t: ThemePref) => void }) {
  return (
    <div className="screen settings">
      <div className="sky sky--quiet" aria-hidden="true" />
      <header className="head">
        <h1 className="head__title">{S.settings.title}</h1>
      </header>
      <section className="card group">
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
      <section className="card group">
        <div className="eyebrow">{S.settings.version}</div>
        <div className="caption">{versionLine(__APP_BUILD__)}</div>
        <div className="caption">{S.settings.preview}</div>
      </section>
    </div>
  )
}

export function NotYet({ title }: { title: string }) {
  return (
    <div className="screen">
      <div className="sky sky--quiet" aria-hidden="true" />
      <header className="head">
        <h1 className="head__title">{title}</h1>
      </header>
      <p className="caption">{S.notYet}</p>
    </div>
  )
}

export { THEMES }
