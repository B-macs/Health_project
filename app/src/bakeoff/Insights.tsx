// Insights, Oura-style: the Strength card on glass — one thin number, the change with
// its period, a soft area chart, the body areas as contributor bars, and the week's
// work — above the list of the other insights (not part of the preview).
import type { Mock, Region } from '../mock/generate'
import { S } from '../strings'
import { IconForward } from './icons'
import { AreaChart, Contributor, DayBars } from './parts'

type Props = { mock: Mock; reduced: boolean }

function regionValue(r: Region): string {
  return r.value == null ? S.insights.none : String(r.value)
}

function regionNote(r: Region): string {
  if (r.value == null) return S.insights.noMeasure
  return r.learning ? S.insights.learning : ''
}

export function Insights({ mock, reduced }: Props) {
  const st = mock.strength
  const down = st.change4w < 0
  return (
    <div className="screen insights">
      <div className="sky sky--quiet" aria-hidden="true" />
      <header className="pagehead">
        <h1 className="pagehead__title">{S.insights.title}</h1>
      </header>

      <article className="glass strength">
        <div className="strength__head">
          <span className="eyebrow">{S.insights.strength}</span>
          <IconForward />
        </div>
        <div className="strength__score">
          <span className="num strength__value">{st.score.toFixed(1)}</span>
          <span className="strength__unit">{S.insights.points}</span>
        </div>
        <span className={`chip-status tone-${down ? 'fair' : 'good'}`}>{S.insights.change(st.change4w)}</span>
        <AreaChart values={st.weekly} kind="readiness" label={`${S.insights.overall}, ${S.insights.weeks}`} className="area--wide" />
        <div className="caption">{S.insights.weeks}</div>

        <div className="eyebrow strength__sub">{S.insights.byArea}</div>
        {st.regions.map((r) => (
          <Contributor key={r.key} name={S.insights.regions[r.key]} value={regionValue(r)}
            fraction={r.value == null ? null : r.value / 100} note={regionNote(r)} tone="good" reduced={reduced} />
        ))}

        <div className="work">
          <div className="work__head">
            <span className="eyebrow">{S.insights.work}</span>
            <span className="num work__kg">{S.insights.workKg(st.workKg)}</span>
          </div>
          <DayBars values={st.workByDay} days={S.insights.days} label={S.insights.work} />
        </div>
        <p className="caption">{S.insights.scale}</p>
      </article>

      <ul className="more">
        {S.insights.more.map((title) => (
          <li key={title} className="glass more__item">
            <span>{title}</span>
            <IconForward />
          </li>
        ))}
      </ul>
    </div>
  )
}
