// Development and the browser tests only (`vite --mode mock`, `vite preview --mode mock`):
// the engine's API answered locally, so the shell can be tested without Cloudflare or
// Cloud Run. The access key is "dev". It is never part of a build.
// - a cookie `e2e_engine=down` makes every /api answer the Worker's "engine unavailable";
// - GET /api/dev/received lists the writes the mock received (the outbox tests);
// - the data check answers as the Worker does: GET .../last (null until a check ran) and
//   POST .../run (a made-up clean result).
import type { IncomingMessage, ServerResponse } from 'node:http'
import type { Plugin } from 'vite'

const KEY = 'dev'
const received: { method: string; path: string; body: unknown; day: string | null }[] = []
// The daily data check as the Worker keeps it: none until one runs ("Check now").
let lastCheck: unknown = null
const sampleCheck = () => ({
  checked_at: new Date().toISOString(),
  backup_name: 'health-2026-10-19.db.gz',
  backup_day: '2026-10-19',
  backup_stale: false,
  missing_rows: 0,
  tables: [{ table: 'training_sessions', backup_rows: 40, store_rows: 41, missing: 0, examples: [] }],
})

const cookie = (req: IncomingMessage, name: string) =>
  new RegExp(`(?:^|;\\s*)${name}=([^;]*)`).exec(String(req.headers.cookie ?? ''))?.[1] ?? null

export function mockApi(): Plugin {
  return {
    name: 'health-mock-api',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use(handler)
    },
    configurePreviewServer(server) {
      server.middlewares.use(handler)
    },
  }
}

async function readBody(req: IncomingMessage): Promise<unknown> {
  const chunks: Buffer[] = []
  for await (const chunk of req) chunks.push(chunk as Buffer)
  const text = Buffer.concat(chunks).toString('utf-8')
  try {
    return text ? JSON.parse(text) : null
  } catch {
    return text
  }
}

function handler(req: IncomingMessage, res: ServerResponse, next: () => void): void {
  const url = new URL(req.url ?? '/', 'http://localhost')
  if (!url.pathname.startsWith('/api/')) return next()
  const send = (status: number, body: unknown) => {
    res.statusCode = status
    res.setHeader('Content-Type', 'application/json')
    res.setHeader('Cache-Control', 'no-store')
    res.end(JSON.stringify(body))
  }
  if (url.pathname === '/api/dev/received') return send(200, received)
  if (cookie(req, 'e2e_engine') === 'down') return send(503, { error: 'engine_unavailable' })
  if (req.headers.authorization !== `Bearer ${KEY}`) return send(401, { error: 'unauthorized' })
  const day = (req.headers['x-local-date'] as string | undefined) ?? null
  if (url.pathname === '/api/health' && req.method === 'GET') {
    return send(200, {
      status: 'ok',
      build: { version: '0.0.0', commit: 'mock', built: null },
      python: '3.12',
      server_tz: 'Europe/Berlin',
      server_local_date: day,
      started_at: null,
      cache_rebuilt: true,
      cache: {},
      timings: {},
    })
  }
  if (url.pathname === '/api/data/check/last' && req.method === 'GET') return send(200, lastCheck)
  if (url.pathname === '/api/data/check/run' && req.method === 'POST') {
    lastCheck = sampleCheck()
    return send(200, lastCheck)
  }
  if (req.method === 'PUT' || req.method === 'POST' || req.method === 'DELETE') {
    void readBody(req).then((body) => {
      received.push({ method: req.method!, path: url.pathname, body, day })
      send(200, { saved: true })
    })
    return
  }
  send(404, { error: 'not_found' })
}
