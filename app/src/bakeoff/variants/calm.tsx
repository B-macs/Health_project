// Style 2, Calm — the relaxed Oura look (the owner: "Make one of them a relaxed easy
// oura look"). One thing at a time: a big greeting, one soft glowing orb with today's
// readiness, a plain sentence, two quiet rows for sleep and strain, and the session as a
// summary with its exercises one tap away. The timer is an orb with one big button.
import { useState } from 'react'
import type { Mock, Region } from '../../mock/generate'
import { S } from '../../strings'
import { clock } from '../hooks'
import { IconBack, IconClose, IconForward, IconPause, IconPlay } from '../icons'
import { AreaChart, Contributor, DayBars, Orb, longDate } from '../parts'
import { ExerciseRows, greeting, useSwipe, type TodayProps } from '../Today'
import { phaseWord, useSession, type TrainingProps } from '../Training'

export function CalmToday(p: TodayProps) {
  const [open, setOpen] = useState(false)
  const { readiness: r, sleep: s, strain: t } = p.day
  const hrv = p.mock.hrv[p.mock.hrv.length - 1]
  const rhr = p.mock.rhr[p.mock.rhr.length - 1]
  return (
    <div className={`screen today calm tone-${r.tone}`} {...useSwipe(p)}>
      <div className="sky" aria-hidden="true" />
      <header className="calm-head">
        <div>
          <div className="calm-head__date">{longDate(p.day.date)}</div>
          <h1 className="calm-head__greeting">{greeting()}</h1>
        </div>
        <div className="calm-head__arrows">
          <button className="plainbtn" onClick={p.onPrev} disabled={!p.canPrev} aria-label={S.today.previousDay}>
            <IconBack />
          </button>
          <button className="plainbtn" onClick={p.onNext} disabled={!p.canNext} aria-label={S.today.nextDay}>
            <IconForward />
          </button>
        </div>
      </header>

      <Orb fraction={r.value / 100} reduced={p.reduced} label={`${S.today.readiness} ${r.value}, ${r.label}`}>
        <span className="calm-orb__label">{S.today.readiness}</span>
        <span className="num calm-orb__value">{r.value}</span>
        <span className="calm-orb__word">{r.label}</span>
      </Orb>
      <p className="calm-line">{S.today.readinessLine[r.tone]}</p>

      <section className="card calm-day">
        <Contributor name={S.today.sleep} value={String(s.value)} fraction={s.value / 100}
          note={`${s.label} · ${S.today.asleep(s.minutes)}`} reduced={p.reduced} />
        <Contributor name={S.today.strain} value={t.value.toFixed(1)} fraction={t.value / 21}
          note={`${t.label} · ${t.soFar ? S.today.soFar : S.today.outOf(21)}`} reduced={p.reduced} />
      </section>

      <section className="card calm-vitals">
        <div className="calm-vital">
          <span className="caption">{S.today.hrv}</span>
          <span><span className="num calm-vital__value">{hrv}</span> <span className="unit">{S.today.ms}</span></span>
        </div>
        <div className="calm-vital">
          <span className="caption">{S.today.rhrShort}</span>
          <span><span className="num calm-vital__value">{rhr}</span> <span className="unit">{S.today.bpm}</span></span>
        </div>
        <div className="calm-vital">
          <span className="caption">{S.today.sleep}</span>
          <span className="num calm-vital__value">{S.today.sleepClock(s.minutes)}</span>
        </div>
      </section>

      <section className="card calm-session">
        <div className="eyebrow">{S.today.session}</div>
        <h2 className="calm-session__title">{p.mock.session.title}</h2>
        <div className="caption">
          {S.today.sessionMeta(p.mock.session.exercises.length, p.mock.session.minutes)}
        </div>
        <button className="btn btn--primary btn--wide calm-session__start" onClick={p.onStart}>
          {S.today.start}
        </button>
        <button className="plainbtn plainbtn--text" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
          {open ? S.calm.hide : S.calm.show(p.mock.session.exercises.length)}
        </button>
        {open && <ExerciseRows mock={p.mock} />}
      </section>
    </div>
  )
}

export function CalmTraining({ mock, onClose, reduced }: TrainingProps) {
  const s = useSession(mock)
  const { timer } = s
  const resting = s.resting
  return (
    <div className={`screen train calm ${resting ? 'train--rest' : 'train--hold'}`}>
      <div className="sky" aria-hidden="true" />
      <header className="calm-trainhead">
        <button className="plainbtn" onClick={onClose} aria-label={S.training.close}>
          <IconClose />
        </button>
        <span className="caption">{s.counter}</span>
        <span className="caption calm-trainhead__on">{s.held ? S.training.screenOn : ''}</span>
      </header>

      <div className="calm-train__title">
        <h1 className="calm-train__name">{s.ex.name}</h1>
        <div className="calm-train__meta">
          {s.step && !s.finished
            ? `${S.training.setOf(s.step.set, s.ex.sets)}${s.step.side ? ` · ${S.training.side[s.step.side]}` : ''}`
            : S.training.exerciseDone}
        </div>
      </div>

      <Orb className="orb--timer" fraction={1 - timer.fraction} reduced={reduced}
        label={`${phaseWord(timer)} ${clock(s.seconds)}`}>
        <span className="num calm-timer">{clock(s.seconds)}</span>
        <span className="calm-orb__word">{phaseWord(timer)}</span>
      </Orb>

      <div className="calm-controls">
        {timer.phase === 'finished' ? (
          <button className="btn btn--primary btn--gym btn--wide" onClick={timer.restart}>{S.training.again}</button>
        ) : timer.phase === 'ready' ? (
          <button className="btn btn--primary btn--gym btn--wide" onClick={timer.start}>
            {timer.step?.side ? S.training.startSide(timer.step.side) : S.training.startSet}
          </button>
        ) : (
          <>
            <button className="btn btn--primary btn--gym btn--wide" onClick={timer.finishStep}>
              {resting ? S.training.skip : S.training.done}
            </button>
            <div className="calm-controls__row">
              {timer.phase === 'paused' ? (
                <button className="plainbtn plainbtn--text" onClick={timer.resume}><IconPlay /> {S.training.resume}</button>
              ) : (
                <button className="plainbtn plainbtn--text" onClick={timer.pause}><IconPause /> {S.training.pause}</button>
              )}
              {resting && (
                <button className="plainbtn plainbtn--text" onClick={() => timer.extend(15)}>{S.training.plus15}</button>
              )}
            </div>
          </>
        )}
      </div>

      <p className="calm-next">
        {S.training.next} · {s.nextText}
      </p>
    </div>
  )
}

function regionValue(r: Region): string {
  return r.value == null ? S.insights.none : String(r.value)
}

function regionNote(r: Region): string {
  if (r.value == null) return S.insights.noMeasure
  return r.learning ? S.insights.learning : ''
}

export function CalmInsights({ mock, reduced }: { mock: Mock; reduced: boolean }) {
  const st = mock.strength
  return (
    <div className="screen insights calm">
      <div className="sky" aria-hidden="true" />
      <header className="calm-head">
        <h1 className="calm-head__greeting">{S.insights.title}</h1>
      </header>

      <Orb fraction={st.score / 100} reduced={reduced} label={`${S.insights.overall} ${st.score}`}>
        <span className="calm-orb__label">{S.insights.strength}</span>
        <span className="num calm-orb__value">{st.score.toFixed(1)}</span>
        <span className="calm-orb__word">{S.insights.change(st.change4w)}</span>
      </Orb>
      <p className="calm-line">{S.insights.scale}</p>

      <section className="card calm-chart">
        <div className="eyebrow">{S.insights.weeks}</div>
        <AreaChart values={st.weekly} level={1} label={`${S.insights.overall}, ${S.insights.weeks}`} className="area--wide" />
      </section>

      <section className="card calm-day">
        <div className="eyebrow">{S.insights.byArea}</div>
        {st.regions.map((r) => (
          <Contributor key={r.key} name={S.insights.regions[r.key]} value={regionValue(r)}
            fraction={r.value == null ? null : r.value / 100} note={regionNote(r)} reduced={reduced} />
        ))}
      </section>

      <section className="card calm-chart">
        <div className="work__head">
          <span className="eyebrow">{S.insights.work}</span>
          <span className="num work__kg">{S.insights.workKg(st.workKg)}</span>
        </div>
        <DayBars values={st.workByDay} days={S.insights.days} label={S.insights.work} />
      </section>
    </div>
  )
}
