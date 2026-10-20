// The parts the three detail screens share (rebuild Phase 5): the frame with the back
// button and the day arrows (H9), the big figure and its word, the contributor rows, the
// key figures, the overnight panels and the 30-day trend. Every number, label and caption
// is the engine's; these draw it in the design's components.
import { Fragment, type ReactNode } from 'react'
import type { components } from '../generated/api'
import { useApp } from '../lib/appState'
import type { View } from '../lib/cache'
import { S } from '../strings'
import { LineChart, slotBands } from './charts'
import { Freshness } from './Freshness'
import { IconBack, IconForward } from './icons'

type Schemas = components['schemas']

/** What every detail answer carries for its frame. */
export interface DayAnswer {
  date: string
  previous: string
  next: string | null
  title: string
  masthead: Schemas['Masthead']
}

export function DetailFrame<T extends DayAnswer>(p: {
  heading: string
  view: View<T>
  children: (data: T) => ReactNode
}) {
  const { go, showDay } = useApp()
  const data = p.view.data
  return (
    <div className="screen detail">
      <div className="sky sky--quiet" aria-hidden="true" />
      <header className="topbar">
        <button className="backlink" aria-label={S.detail.back} onClick={() => go('/')}>
          <IconBack />
          <span>{S.nav.today}</span>
        </button>
        <h1 className="topbar__title">{p.heading}</h1>
        <span />
      </header>
      <nav className="dayarrows" aria-label={S.detail.days}>
        <button className="iconbtn" aria-label={S.detail.previous} disabled={!data}
          onClick={() => data && showDay(data.previous)}>
          <IconBack />
        </button>
        <span className="dayarrows__label">{data ? data.title : S.fresh.loading}</span>
        <button className="iconbtn" aria-label={S.detail.next} disabled={!data?.next}
          onClick={() => data?.next && showDay(data.next)}>
          <IconForward />
        </button>
      </nav>
      {data && (
        <section className="masthead" aria-label={data.title}>
          <span className="num masthead__value">{data.masthead.display}</span>
          <span className="word">{data.masthead.label}</span>
        </section>
      )}
      <Freshness view={p.view} />
      {/* Keyed by the day: a new day starts with no chart point selected. */}
      {data && <Fragment key={data.date}>{p.children(data)}</Fragment>}
    </div>
  )
}

export function Section({ title, children, testId }: { title: string; children: ReactNode; testId?: string }) {
  return (
    <section className="card group" aria-label={title} data-testid={testId}>
      <h2 className="eyebrow">{title}</h2>
      {children}
    </section>
  )
}

export function ContributorList({ contributors }: { contributors: Schemas['Contributors'] }) {
  return (
    <Section title={S.detail.contributors} testId="contributors">
      {contributors.unscored_reason && <p className="caption">{contributors.unscored_reason}</p>}
      <ul className="list">
        {contributors.rows.map((row) => (
          <li key={row.key ?? row.label} className={`contrib${row.scored ? '' : ' contrib--off'}`}>
            <div className="contrib__top">
              <span>{row.label}</span>
              <span className="contrib__value">{row.value_display}</span>
            </div>
            <div className="contrib__track" aria-hidden="true">
              <span className="contrib__fill" style={{ width: `${Math.max(0, Math.min(100, row.bar_pct))}%` }} />
            </div>
            {row.weight_display && <span className="contrib__note">{S.detail.weight(row.weight_display)}</span>}
          </li>
        ))}
      </ul>
      {contributors.caption && <p className="caption">{contributors.caption}</p>}
    </Section>
  )
}

export function KeyFigures({ title, items }: { title: string; items: readonly Schemas['LabelValue'][] }) {
  if (!items.length) return null
  return (
    <Section title={title}>
      <div className="figures">
        {items.map((item) => (
          <div key={item.label} className="figure">
            <span className="caption">{item.label}</span>
            <span className="figure__value">{item.value}</span>
          </div>
        ))}
      </div>
    </Section>
  )
}

export function OvernightPanels({ panels }: { panels: readonly Schemas['OvernightPanel'][] }) {
  return (
    <>
      {panels.map((panel) => (
        <Section key={panel.key} title={panel.title}>
          <div className="kv">
            <span className="num figure__big">{`${Math.round(panel.headline)} ${panel.unit}`}</span>
            <span className="caption">{`${panel.secondary_label} ${Math.round(panel.secondary)} ${panel.unit}`}</span>
          </div>
          <LineChart label={panel.title} values={panel.values} axis={panel.axis} x={panel.x_labels}
            y={panel.y_labels} bands={panel.bands} average={panel.average} />
        </Section>
      ))}
    </>
  )
}

export function TrendSection({ trend }: { trend: Schemas['TrendChart'] }) {
  const { showDay } = useApp()
  return (
    <Section title={trend.title} testId="trend">
      {trend.subtitle && <p className="caption">{trend.subtitle}</p>}
      {trend.headline && <span className="num figure__big">{trend.headline}</span>}
      {trend.empty ? (
        <p className="caption">{S.charts.empty}</p>
      ) : (
        <LineChart label={trend.title} values={trend.values} axis={trend.axis} x={trend.x_labels}
          y={trend.y_labels} bands={slotBands(trend.points)} onOpen={(day) => showDay(day)} />
      )}
    </Section>
  )
}
