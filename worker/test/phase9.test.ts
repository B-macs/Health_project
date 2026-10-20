// Rebuild Phase 9: the Oura login's return page (GET /oura/callback). The engine is never
// called for real: global fetch is replaced, so each test sees what would leave Cloudflare.
import { env } from 'cloudflare:workers'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { app } from '../src/index'

const ON = { ...env, SYNC_ENABLED: 'true' } as never

function engineAnswers(body: unknown, status = 200) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(
    async () => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } }),
  )
}

afterEach(() => vi.restoreAllMocks())

describe('the Oura return page', () => {
  it('hands the code to the engine with its key, and opens the app\'s result page', async () => {
    const spy = engineAnswers({ kind: 'oauth', state: 'ok' })
    const res = await app.request('/oura/callback?code=the-code&state=the-state', {}, ON)
    expect(res.status).toBe(302)
    expect(res.headers.get('location')).toBe('/#/oura-done?result=ok')
    expect(spy).toHaveBeenCalledTimes(1)
    const [target, init] = spy.mock.calls[0]!
    expect(String(target)).toMatch(/\/api\/oura\/callback$/)
    expect(init!.method).toBe('POST')
    expect(new Headers(init!.headers).get('X-Engine-Key')).toBeTruthy()
    expect(JSON.parse(new TextDecoder().decode(init!.body as ArrayBuffer))).toEqual({ code: 'the-code', state: 'the-state' })
  })

  it('passes the engine\'s refusal on as the result', async () => {
    engineAnswers({ error: 'state_mismatch' }, 409)
    const res = await app.request('/oura/callback?code=old&state=used', {}, ON)
    expect(res.headers.get('location')).toBe('/#/oura-done?result=state_mismatch')
  })

  it('a cancelled login asks the engine nothing', async () => {
    const spy = engineAnswers({})
    const res = await app.request('/oura/callback?error=access_denied', {}, ON)
    expect(res.headers.get('location')).toBe('/#/oura-done?result=denied')
    expect(spy).not.toHaveBeenCalled()
  })

  it('stays shut, like the syncs, until the switch-over turns them on', async () => {
    const spy = engineAnswers({})
    const res = await app.request('/oura/callback?code=c&state=s', {}, env as never)
    expect(res.headers.get('location')).toBe('/#/oura-done?result=sync_disabled')
    expect(spy).not.toHaveBeenCalled()
  })
})
