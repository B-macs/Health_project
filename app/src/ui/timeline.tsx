// A day's exercises as a timeline (the overview before Start, a missed or a future day, the
// accessory session), and the items the day asks for at home. The names and doses are the
// engine's (training_screen.exercise_line); the how-to of an at-home item opens on a tap.
import type { components } from '../generated/api'
import { S } from '../strings'

type Line = components['schemas']['ExerciseLine']

export function Timeline({ title, items, warmups }: { title: string; items: Line[]; warmups?: Set<string> }) {
  return (
    <section className="card group" aria-label={title}>
      <h3 className="eyebrow">{title}</h3>
      {items.length === 0 ? <p className="caption">{S.week.noExercises}</p> : (
        <ol className="timeline">
          {items.map((ex, i) => (
            <li key={`${ex.name}-${i}`} className={`timeline__item${warmups?.has(ex.name) ? ' timeline__item--warmup' : ''}`}>
              <span className="timeline__dot" aria-hidden="true" />
              <span className="timeline__name">{ex.name}</span>
              <span className="timeline__dose">{ex.prescription}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

export function HomeItems({ items }: { items: Line[] }) {
  if (items.length === 0) return null
  return (
    <section className="card group" aria-label={S.session.atHome}>
      <h3 className="eyebrow">{S.session.atHome}</h3>
      {items.map((h) => (
        <details key={h.name} className="guide">
          <summary className="tapline">{`${h.name} · ${h.prescription}`}</summary>
          {h.mechanics && <p className="caption">{h.mechanics}</p>}
        </details>
      ))}
    </section>
  )
}
