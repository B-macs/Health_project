// The in-app console for the iPhone (rebuild Phase 4, Lauscher's pattern): Eruda (MIT),
// loaded only after seven taps on the version line in Settings and kept out of the
// offline precache. A short log of what the app did is kept across reloads (the phone's
// database) and printed into the console when it opens. It holds no reading and no key.
import { db as realDb, type HealthDB } from '../db/schema'

const MAX_LINES = 300
const TAPS = 7
const TAP_WINDOW_MS = 4000

let lines: string[] = []

/** Read the saved log at start. */
export async function loadLog(store: HealthDB = realDb): Promise<void> {
  try {
    const rows = await store.debuglog.orderBy('id').reverse().limit(MAX_LINES).toArray()
    lines = [...rows.reverse().map((r) => r.line), ...lines]
  } catch {
    // no database (a private window): the log stays in memory
  }
}

/** One line in the log (time of day, what happened, the details), also on the console. */
export function debugLog(kind: string, detail: Record<string, unknown> = {}, store: HealthDB = realDb): void {
  const at = new Date().toISOString()
  const line = `${at.slice(11, 23)} ${kind} ${JSON.stringify(detail)}`
  lines = [...lines.slice(-(MAX_LINES - 1)), line]
  console.debug('[health]', line)
  void (async () => {
    try {
      await store.debuglog.add({ at, line })
      const count = await store.debuglog.count()
      if (count > MAX_LINES) {
        const old = await store.debuglog.orderBy('id').limit(count - MAX_LINES).primaryKeys()
        await store.debuglog.bulkDelete(old)
      }
    } catch {
      // full or blocked storage: the line stays in memory
    }
  })()
}

export function debugLines(): readonly string[] {
  return lines
}

/** True on the seventh tap within a few seconds; slower taps start the count again. */
export function tapCounter(now: () => number = Date.now): () => boolean {
  let taps: number[] = []
  return () => {
    const at = now()
    taps = [...taps.filter((t) => at - t < TAP_WINDOW_MS), at]
    if (taps.length < TAPS) return false
    taps = []
    return true
  }
}

let opened: Promise<void> | null = null

/** Loads Eruda (a separate file, fetched only now) and prints the saved log into it. */
export function openConsole(): Promise<void> {
  opened ??= import('eruda').then(({ default: eruda }) => {
    eruda.init()
    console.info(`[health] ${lines.length} log lines before the console opened:`)
    for (const line of lines) console.info(line)
    eruda.show()
  })
  return opened
}
