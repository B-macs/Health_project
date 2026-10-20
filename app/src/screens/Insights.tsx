// Insights (the owner's pick, 2026-10-20: Week), in the page's one colour family
// (indigo): two number tiles — strength and the week's work — then the strength over
// twelve weeks as a soft area chart, then the body areas as contributor bars.
import type { Mock, Region } from '../mock/generate'
import { S } from '../strings'
import { AreaChart, Contributor, DayBars } from '../ui/parts'

function regionValue(r: Region): string {
  return r.value == null ? S.insights.none : String(r.value)
}

function regionNote(r: Region): string {
  if (r.value == null) return S.insights.noMeasure
  return r.learning ? S.insights.learning : ''
}

export function Insights({ mock, reduced }: { mock: Mock; reduced: boolean }) {
  const st = mock.strength
  return (
    <div className="screen insights">
      <div className="sky sky--quiet" aria-hidden="true" />
      <header className="head">
        <h1 className="head__title">{S.insights.title}</h1>
      </header>
      <p className="note">{S.sample}</p>

      <section className="pair">
        <article className="card tile">
          <span className="eyebrow">{S.insights.strength}</span>
          <span className="num tile__value">{st.score.toFixed(1)}</span>
          <span className="word">{S.insights.change(st.change4w)}</span>
          <span className="caption">{S.insights.points}</span>
        </article>
        <article className="card tile">
          <span className="eyebrow">{S.insights.work}</span>
          <span className="num tile__value tile__value--long">{S.insights.workKg(st.workKg)}</span>
          <DayBars values={st.workByDay} days={S.insights.days} label={S.insights.work} />
        </article>
      </section>

      <section className="card">
        <div className="eyebrow">{S.insights.weeks}</div>
        <AreaChart values={st.weekly} label={`${S.insights.overall}, ${S.insights.weeks}`} />
      </section>

      <section className="card">
        <div className="eyebrow">{S.insights.byArea}</div>
        {st.regions.map((r) => (
          <Contributor key={r.key} name={S.insights.regions[r.key]} value={regionValue(r)}
            fraction={r.value == null ? null : r.value / 100} note={regionNote(r)} reduced={reduced} />
        ))}
      </section>
      <p className="caption">{S.insights.scale}</p>
    </div>
  )
}
