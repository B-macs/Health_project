// How fresh the shown data is (rebuild Phase 4): quiet when the engine answered, and
// "Showing saved data" with the reason when it did not. A screen shows this under the
// data it read cache-first (lib/cache.ts); it never replaces the data. A turning ring and
// "Reading…" show while a read asked for by a tap is on its way (the owner, 2026-10-21: a tap
// on Read again showed nothing until the answer came), and while a screen with nothing saved
// loads. The screen's own checks are quiet: the saved answer stays as it is, and only a
// different answer changes it (his next message the same day: "a back ground check can
// happen to see if there is new data but on the front end it should be the same").
import { ageMinutes, type View } from '../lib/cache'
import { S } from '../strings'
import { Spinner } from './parts'

type Shown = Pick<View<unknown>, 'data' | 'fetchedAt' | 'state'> & { code?: string; pressed?: boolean; again?: () => void }

export function freshnessText(view: Shown, now: Date = new Date()): string {
  const age = ageMinutes(view.fetchedAt, now)
  const updated = age === null ? '' : age === 0 ? S.fresh.justNow : S.fresh.ago(age)
  if (view.state === 'loading' || view.state === 'fresh') {
    return view.data === undefined ? S.fresh.loading : updated
  }
  // A read that ran out of time (lib/cache.ts READ_TIMEOUT_MS) says so, not "no connection".
  const why = view.state === 'offline' && view.code === 'timeout' ? S.fresh.timeout : S.fresh.why[view.state]
  if (view.data === undefined) return `${S.fresh.nothingSaved} ${why}`
  return `${S.fresh.saved} · ${updated}. ${why}`
}

export function Freshness({ view }: { view: Shown }) {
  const failed = view.state !== 'loading' && view.state !== 'fresh'
  const reading = view.state === 'loading' && (view.data === undefined || !!view.pressed)
  return (
    <p className={`fresh${failed ? ' fresh--warn' : ''}`} role="status" data-state={view.state}>
      {freshnessText(view)}
      {reading && view.data !== undefined && (
        <span className="fresh__reading" data-testid="reading">
          <Spinner />
          {S.fresh.reading}
        </span>
      )}
      {reading && view.data === undefined && <Spinner />}
      {failed && view.again && (
        <>
          {' '}
          <button type="button" className="fresh__again" data-testid="read-again" onClick={view.again}>
            {S.fresh.again}
          </button>
        </>
      )}
    </p>
  )
}
