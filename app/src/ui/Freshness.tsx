// How fresh the shown data is (rebuild Phase 4): quiet when the engine answered, and
// "Showing saved data" with the reason when it did not. A screen shows this under the
// data it read cache-first (lib/cache.ts); it never replaces the data.
import { ageMinutes, type View } from '../lib/cache'
import { S } from '../strings'

type Shown = Pick<View<unknown>, 'data' | 'fetchedAt' | 'state'> & { code?: string; again?: () => void }

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
  return (
    <p className={`fresh${failed ? ' fresh--warn' : ''}`} role="status" data-state={view.state}>
      {freshnessText(view)}
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
