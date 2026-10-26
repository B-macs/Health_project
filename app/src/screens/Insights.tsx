// Insights (rebuild Phase 8, inventory I1-I4): the long view, opened from one page. Four
// cards carry each screen's headline as the engine sends it (strength, flexibility, body
// composition, and cardio, which comes later), then the engine's own views and the trends.
// Each card opens its screen in the app (Key Rule 17); every figure is read cache-first, so
// the page shows the last answer with no connection.
import { useApp } from '../lib/appState'
import { useCached, type View } from '../lib/cache'
import { shortDate } from '../lib/dates'
import { S } from '../strings'
import { Freshness } from '../ui/Freshness'
import { InsightsHead } from '../ui/InsightsHead'
import { FLEXIBILITY, type FlexibilityAnswer } from './FlexibilityShared'
import { METABOLISM, type MetabolismAnswer } from './InsightsMetabolism'
import { REFERENCE_MISSING, STRENGTH, type StrengthAnswer } from './InsightsStrength'


function Tile({ title, value, note, testId, onOpen }: {
  title: string; value: string; note: string; testId: string; onOpen: () => void
}) {
  return (
    <button className="card tile tile--button" data-testid={testId} onClick={onOpen}>
      <span className="eyebrow">{title}</span>
      <span className="num tile__value">{value}</span>
      <span className="caption">{note}</span>
    </button>
  )
}

/** The hub drawn from its three reads (cache-first): the tests draw it in each state. */
export function InsightsHub({ strength, metab, flex, go }: {
  strength: View<StrengthAnswer>; metab: View<MetabolismAnswer>; flex: View<FlexibilityAnswer>; go: (path: string) => void
}) {
  const st = strength.data
  // The newest weight from either device, the SECA scan included (WP-37).
  const latest = metab.data?.headline ?? metab.data?.latest
  const report = flex.data?.report
  return (
    <div className="screen insights" data-testid="insights-hub">
      <div className="sky sky--quiet" aria-hidden="true" />
      <header className="head">
        <h1 className="head__title">{S.insights.title}</h1>
      </header>
      <Freshness view={strength.data ? strength : metab} />
      <section className="pair">
        <Tile title={S.ins.strength} testId="tile-strength" onOpen={() => go('/insights/strength')}
          value={st?.overall != null ? S.ins.pct(st.overall) : S.ins.none}
          note={st ? S.ins.ofBest : strength.code === REFERENCE_MISSING ? S.ins.notMeasured : ''} />
        <Tile title={S.ins.flexibility} testId="tile-flexibility" onOpen={() => go('/insights/flexibility')}
          value={report?.pattern ?? S.ins.none}
          note={report ? (report.pattern ? report.pattern_label : S.flex.noPattern) : S.ins.notMeasured} />
      </section>
      <section className="pair">
        <Tile title={S.ins.metabolism} testId="tile-metabolism" onOpen={() => go('/insights/metabolism')}
          value={latest ? latest.weight_kg.toFixed(1) : S.ins.none}
          note={latest ? `kg · ${S.ins.measuredOn(shortDate(latest.date))}${
            metab.data?.headline?.source === 'seca' ? ` · ${S.ins.fromSeca}` : ''}` : S.ins.noWeighIn} />
        <Tile title={S.ins.cardio} testId="tile-cardio" onOpen={() => go('/insights/cardio')}
          value={S.ins.none} note={S.ins.cardioSoon} />
      </section>
      <section className="card group" aria-label={S.ins.engineSection}>
        <h2 className="eyebrow">{S.ins.engineSection}</h2>
        {([['engine', S.ins.engine], ['warnings', S.ins.warnings], ['trends', S.ins.trends],
          ['sleep', S.ins.sleepArch]] as const).map(([path, label]) => (
          <button key={path} className="tapline kv" onClick={() => go(`/insights/${path}`)}>
            <span>{label}</span>
            <span className="caption">{S.ins.open}</span>
          </button>
        ))}
      </section>
    </div>
  )
}

export function Insights() {
  const { store, ctx, go } = useApp()
  const strength = useCached<StrengthAnswer>(store, STRENGTH, null, ctx)
  const metab = useCached<MetabolismAnswer>(store, METABOLISM, null, ctx)
  const flex = useCached<FlexibilityAnswer>(store, FLEXIBILITY, null, ctx)
  return <InsightsHub strength={strength} metab={metab} flex={flex} go={go} />
}

/** Cardio (I4): kept for later; the owner will add it (2026-10-19). */
export function CardioScreen() {
  return (
    <div className="screen insights" data-testid="cardio">
      <div className="sky sky--quiet" aria-hidden="true" />
      <InsightsHead title={S.ins.cardio} />
      <p className="caption">{S.ins.cardioText}</p>
    </div>
  )
}
