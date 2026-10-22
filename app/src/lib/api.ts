// The one way the app talks to the engine (rebuild Phase 4). Every request carries the
// access key (from the phone's database, never a URL) and the phone's own day
// (X-Local-Date: the server never decides "today", rebuild rule 3). Every failure becomes
// one ApiError with a kind the screens can word:
// - offline: no network (the request never left);
// - engine_unavailable: the Worker answered that the engine is starting or down (or the
//   debug switch "act as if the engine is down" is on);
// - unauthorized: the key is wrong (401);
// - rejected: the engine refused the request (4xx; retrying cannot help);
// - server: another 5xx (retrying can help).
export type ApiErrorKind = 'offline' | 'engine_unavailable' | 'unauthorized' | 'rejected' | 'server'

export class ApiError extends Error {
  constructor(
    readonly kind: ApiErrorKind,
    readonly status: number | null,
    readonly code: string,
  ) {
    super(`${kind}: ${code}`)
    this.name = 'ApiError'
  }
}

/** The phone's own calendar day, YYYY-MM-DD, in its own time zone. */
export function localDay(now: Date = new Date()): string {
  const y = now.getFullYear()
  const m = String(now.getMonth() + 1).padStart(2, '0')
  const d = String(now.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  body?: unknown
  key: string | null
  day?: string
  engineDown?: boolean
  fetchImpl?: typeof fetch
  /** Give up after this long (a weak signal at the gym): the request fails as offline. */
  timeoutMs?: number
  /** Let the request finish after the page stops (the timer alerts, sent as the app goes to
   *  the background). */
  keepalive?: boolean
}

const ENGINE_DOWN = new Set(['engine_unavailable', 'engine_timeout', 'not_configured'])

let writes = 0

/** How many writes (POST, PUT, DELETE) have ended in this run of the app, sent or not. A
 *  read on its way from before a write ended never answers a read asked after it
 *  (lib/cache.ts shares one read per address). */
export function writesEnded(): number {
  return writes
}

export async function api<T>(path: string, options: RequestOptions): Promise<T> {
  const writing = (options.method ?? 'GET') !== 'GET'
  try {
    return await send<T>(path, options)
  } finally {
    if (writing) writes += 1
  }
}

async function send<T>(path: string, options: RequestOptions): Promise<T> {
  if (options.engineDown) throw new ApiError('engine_unavailable', null, 'debug_engine_down')
  const headers: Record<string, string> = {
    Accept: 'application/json',
    'X-Local-Date': options.day ?? localDay(),
  }
  if (options.key) headers.Authorization = `Bearer ${options.key}`
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'
  let response: Response
  const abort = options.timeoutMs ? new AbortController() : null
  const timer = abort ? setTimeout(() => abort.abort(), options.timeoutMs) : null
  try {
    response = await (options.fetchImpl ?? fetch)(path, {
      method: options.method ?? 'GET',
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      cache: 'no-store',
      signal: abort?.signal,
      ...(options.keepalive ? { keepalive: true } : {}),
    })
  } catch {
    throw new ApiError('offline', null, abort?.signal.aborted ? 'timeout' : 'network')
  } finally {
    if (timer) clearTimeout(timer)
  }
  const text = await response.text()
  let payload: unknown = null
  try {
    payload = text ? JSON.parse(text) : null
  } catch {
    payload = null
  }
  if (response.ok) return payload as T
  const code = String((payload as { error?: unknown } | null)?.error ?? response.status)
  // The Worker answers a malformed key header with 400 and the same "unauthorized".
  if (response.status === 401 || code === 'unauthorized') throw new ApiError('unauthorized', response.status, code)
  if (ENGINE_DOWN.has(code)) throw new ApiError('engine_unavailable', response.status, code)
  if (response.status >= 500) throw new ApiError('server', response.status, code)
  throw new ApiError('rejected', response.status, code)
}
