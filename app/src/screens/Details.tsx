// The three detail screens behind Today's cards (rebuild Phase 5; inventory H25-H56), in
// Today's colour family. Each reads its engine answer cache-first for the day shown and
// draws it; the rules (what is scored, what shows on a night with no score, the wake-time
// limits, the region split) are the engine's.
//
// THE SLEEP SCREEN'S ALL-OR-NOTHING RULE (tests/test_sleep_screen_is_all_or_nothing.py, H35):
// with no Sleep Score there are no night panels and no wake stepper, only the reason line
// and the day arrows. The engine sends `night` and `wake` only for a scored night, and
// `watch_only` for a night only the watch recorded (which says in its own words that there
// is no score). This screen draws what it is sent and adds nothing.
import { useLiveQuery } from 'dexie-react-hooks'
import { useEffect, useState } from 'react'
import type { components } from '../generated/api'
import { useApp } from '../lib/appState'
import { useCached } from '../lib/cache'
import { dayPath } from '../lib/day'
import { enqueue } from '../lib/outbox'
import { S } from '../strings'
import { MovementStrip, StageStrip } from '../ui/charts'
import { ContributorList, DetailFrame, KeyFigures, OvernightPanels, Section, TrendSection } from '../ui/detail'

type Schemas = components['schemas']
type ReadinessDetail = Schemas['ReadinessDetailOut']
type SleepDetail = Schemas['SleepDetailOut']
type StrainDetail = Schemas['StrainDetailOut']

function useDetail<T>(base: string, extra: Record<string, string> = {}) {
  const { store, ctx, pick } = useApp()
  return useCached<T>(store, dayPath(base, pick, extra), null, ctx)
}

export function ReadinessBody({ d }: { d: ReadinessDetail }) {
  return (
    <>
      <ContributorList contributors={d.contributors} />
      <KeyFigures title={S.detail.keyMetrics} items={d.key_metrics} />
      <OvernightPanels panels={d.overnight} />
      <TrendSection trend={d.trend} />
    </>
  )
}

export function ReadinessScreen() {
  const view = useDetail<ReadinessDetail>('/api/today/readiness')
  return (
    <DetailFrame heading={S.detail.readiness} view={view}>
      {(d) => <ReadinessBody d={d} />}
    </DetailFrame>
  )
}

// ── Sleep ───────────────────────────────────────────────────────────────────

function Debt({ debt }: { debt: NonNullable<Schemas['SleepDebt']> }) {
  return (
    <Section title={S.detail.debt} testId="sleep-debt">
      <div className="kv">
        <span className="num figure__big">{debt.value_display}</span>
        <span className="word">{debt.band}</span>
      </div>
      <div className="segments" aria-hidden="true">
        {[0, 1, 2, 3].map((i) => <span key={i} className={`segments__one${i < debt.filled ? ' segments__one--on' : ''}`} />)}
      </div>
      <p className="caption">{S.detail.debtRest(debt.threshold)}</p>
    </Section>
  )
}

function Stages({ hypnogram, stages, asleep, inBed }: {
  hypnogram: Schemas['Hypnogram']
  stages: readonly { key: string; label: string; duration: string; pct: string | null }[]
  asleep?: string
  inBed?: string
}) {
  return (
    <Section title={hypnogram.title || S.detail.timeAsleep} testId="hypnogram">
      {asleep && (
        <div className="kv">
          <span className="num figure__big">{asleep}</span>
          {inBed && <span className="caption">{S.detail.inBed(inBed)}</span>}
        </div>
      )}
      {hypnogram.stages && !hypnogram.empty && (
        <StageStrip label={hypnogram.title} strip={hypnogram.stages} x={hypnogram.x_labels} />
      )}
      {hypnogram.movement && (
        <>
          <span className="eyebrow">{hypnogram.movement.title}</span>
          <MovementStrip strip={hypnogram.movement} />
          {hypnogram.movement.details.map((line) => <p key={line} className="caption">{line}</p>)}
        </>
      )}
      <p className="caption">{hypnogram.source}</p>
      <ul className="list">
        {stages.map((stage) => (
          <li key={stage.key} className="kv">
            <span>{stage.label}</span>
            <span>{stage.pct ? `${stage.duration} · ${stage.pct}` : stage.duration}</span>
          </li>
        ))}
      </ul>
    </Section>
  )
}

function Naps({ naps }: { naps: NonNullable<Schemas['Naps']> }) {
  return (
    <Section title={S.detail.dayTotal} testId="naps">
      <div className="kv"><span className="num figure__big">{naps.day_total}</span></div>
      <div className="kv"><span className="caption">{S.detail.night}</span><span>{naps.night_total}</span></div>
      {naps.rows.map((nap) => (
        <div key={nap.label} className="kv">
          <span className="caption">{nap.label}</span>
          <span>{`${nap.duration} · ${nap.efficiency}`}</span>
        </div>
      ))}
    </Section>
  )
}

/** The wake-time correction (Key Rule 4's one manual correction): − and + in the engine's
 *  steps, saved through the outbox, so it works offline and goes out in order. The night
 *  is read again once the engine has confirmed the save; a refusal is said here and kept
 *  in Settings with the engine's reason. */
function Wake({ wake, day, onSaved }: { wake: Schemas['WakeControl']; day: string; onSaved: () => void }) {
  const { store } = useApp()
  const [pending, setPending] = useState<{ id: string; minutes: number } | null>(null)
  // 'gone' once the engine confirmed the save (it leaves the outbox); undefined while reading.
  const item = useLiveQuery(async () => {
    if (!pending) return 'idle' as const
    return (await store.outbox.where('id').equals(pending.id).first()) ?? ('gone' as const)
  }, [store, pending?.id])
  useEffect(() => {
    if (!pending) return
    if (item === 'gone') {
      setPending(null)
      onSaved()
    }
  }, [item, pending, onSaved])
  const refused = typeof item === 'object' && item.state === 'failed'
  const save = async (minutes: number) => {
    const id = await enqueue(store, {
      kind: 'wake', method: 'PUT', path: '/api/sleep/wake-adjustment', body: { date: day, minutes },
    })
    setPending({ id, minutes })
  }
  const busy = pending != null && !refused
  const shown = pending?.minutes ?? wake.minutes
  return (
    <Section title={wake.label} testId="wake">
      <div className="stepper">
        <button className="iconbtn" aria-label={S.detail.wakeLess} disabled={!wake.editable || busy}
          onClick={() => void save(wake.decrease_to)}>{S.detail.minus}</button>
        <span className="num figure__big">{shown ? S.detail.wakeMinutes(shown) : S.detail.wakeNone}</span>
        <button className="iconbtn" aria-label={S.detail.wakeMore} disabled={!wake.editable || busy}
          onClick={() => void save(wake.increase_to)}>{S.detail.plus}</button>
      </div>
      {busy && <p className="caption" role="status">{S.detail.saving}</p>}
      {refused && <p className="caption" role="status">{S.detail.refused}</p>}
      <p className="caption">{wake.caption}</p>
    </Section>
  )
}

export function SleepBody({ d, onSaved }: { d: SleepDetail; onSaved: () => void }) {
  return (
    <>
      {d.watch_only && (
        <Stages hypnogram={d.watch_only.hypnogram}
          stages={d.watch_only.stages.map((s) => ({ key: s.stage, label: s.name, duration: s.duration, pct: s.pct == null ? null : `${s.pct}%` }))} />
      )}
      {!d.night && !d.watch_only && d.contributors.unscored_reason && (
        <p className="caption" data-testid="sleep-reason">{d.contributors.unscored_reason}</p>
      )}
      {d.night && (
        <>
          <ContributorList contributors={d.contributors} />
          <KeyFigures title={S.detail.keyMetrics} items={d.night.key_metrics} />
          {d.night.fusion_caption && <p className="caption">{d.night.fusion_caption}</p>}
          {d.night.debt && <Debt debt={d.night.debt} />}
          <Stages hypnogram={d.night.hypnogram} stages={d.night.stages} asleep={d.night.asleep} inBed={d.night.in_bed} />
          {d.night.naps && <Naps naps={d.night.naps} />}
          <KeyFigures title={S.detail.vitals} items={d.night.vitals} />
          <OvernightPanels panels={d.night.overnight} />
        </>
      )}
      {d.wake && <Wake wake={d.wake} day={d.date} onSaved={onSaved} />}
      {d.nights_adjusted > 0 && <p className="caption">{S.detail.nightsAdjusted(d.nights_adjusted)}</p>}
      <TrendSection trend={d.trend} />
    </>
  )
}

export function SleepScreen() {
  const view = useDetail<SleepDetail>('/api/today/sleep')
  return (
    <DetailFrame heading={S.detail.sleep} view={view}>
      {(d) => <SleepBody d={d} onSaved={view.again} />}
    </DetailFrame>
  )
}

// ── Strain ──────────────────────────────────────────────────────────────────

function Regions({ panel, onWeek }: { panel: NonNullable<Schemas['RegionPanel']>; onWeek: (week: boolean) => void }) {
  return (
    <Section title={S.detail.byArea} testId="regions">
      {panel.state !== 'split' ? (
        <p className="caption">{panel.reason ?? S.detail.noSplit}</p>
      ) : (
        <>
          <div className="share" aria-hidden="true">
            {panel.regions.map((r) => (
              <span key={r.id} className={`share__part share__part--${r.id}`} style={{ width: `${r.au_pct}%` }} />
            ))}
          </div>
          <ul className="list">
            {panel.regions.map((r) => (
              <li key={r.id} className="contrib">
                <div className="contrib__top">
                  <span>{r.name}</span>
                  <span className="contrib__value">{r.strain == null ? '—' : r.strain.toFixed(1)}</span>
                </div>
                <div className="contrib__track" aria-hidden="true">
                  <span className="contrib__fill" style={{ width: `${r.fill_pct ?? 0}%` }} />
                </div>
                <span className="contrib__note">
                  {S.detail.share(Math.round(r.au_pct), r.au == null ? null : Math.round(r.au))}
                  {r.acwr ? ` · ${S.detail.acwr(r.acwr.value)}` : ''}
                </span>
                {r.acwr?.reason && <span className="contrib__note">{r.acwr.reason}</span>}
              </li>
            ))}
          </ul>
          {panel.non_additive_note && <p className="caption">{panel.non_additive_note}</p>}
          {panel.unmapped_names.length > 0 && <p className="caption">{S.detail.unmapped(panel.unmapped_names)}</p>}
        </>
      )}
      {panel.can_show_window && (
        <button className="btn btn--glass btn--wide" onClick={() => onWeek(!panel.showing_week)}>
          {panel.showing_week ? S.detail.hideWeek : S.detail.showWeek}
        </button>
      )}
    </Section>
  )
}

function Source({ source }: { source: NonNullable<Schemas['StrainSource']> }) {
  return (
    <Section title={S.detail.source} testId="strain-source">
      <span className="word">{source.label}</span>
      {source.hr_rows.map((row) => (
        <div key={row.label} className="kv"><span className="caption">{row.label}</span><span>{row.value}</span></div>
      ))}
      {source.blend && (
        <p className="caption">{S.detail.blend(source.blend.hr_weight_pct, source.blend.hr_strain, source.blend.rpe_strain)}</p>
      )}
    </Section>
  )
}

export function StrainBody({ d, onWeek }: { d: StrainDetail; onWeek: (week: boolean) => void }) {
  return (
    <>
      {d.stage_unread && <p className="caption">{d.stage_unread}</p>}
      {d.region && <Regions panel={d.region} onWeek={onWeek} />}
      {d.source && <Source source={d.source} />}
      <TrendSection trend={d.hrv_7d} />
      <TrendSection trend={d.rhr_7d} />
      <TrendSection trend={d.trend} />
    </>
  )
}

export function StrainScreen() {
  const [week, setWeek] = useState(false)
  const view = useDetail<StrainDetail>('/api/today/strain', week ? { week: 'true' } : {})
  return (
    <DetailFrame heading={S.detail.strain} view={view}>
      {(d) => <StrainBody d={d} onWeek={setWeek} />}
    </DetailFrame>
  )
}
