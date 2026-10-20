// "Read again" for every screen (rebuild Phase 9): after the engine's sync has written new
// data, each screen on show asks the engine again (lib/cache.ts useCached listens), so the
// numbers update when the sync ends (the old app kept its reads for 30 minutes after one).
let epoch = 0
const listeners = new Set<() => void>()

/** Every screen reads again. */
export function bump(): void {
  epoch += 1
  for (const listener of listeners) listener()
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

export const currentEpoch = (): number => epoch
