// The page the Oura login ends on (rebuild Phase 9): read from the address, in words, with
// the way back, and no key needed.
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { S } from '../strings'
import { OuraDone, ouraDoneResult } from './OuraDone'

const text = (html: string) => html.replace(/<[^>]+>/g, ' ').replace(/&#x27;/g, "'").replace(/\s+/g, ' ')
const page = (result: string) => text(renderToStaticMarkup(<OuraDone result={result} onDone={() => undefined} />))

describe('the Oura login result page', () => {
  it('reads the result from the address, and is null on any other page', () => {
    expect(ouraDoneResult('#/oura-done?result=ok')).toBe('ok')
    expect(ouraDoneResult('#/oura-done?result=state_mismatch')).toBe('state_mismatch')
    expect(ouraDoneResult('#/oura-done')).toBe('')
    expect(ouraDoneResult('#/settings')).toBeNull()
    expect(ouraDoneResult('')).toBeNull()
  })

  it('says how it went in words, and how to get back', () => {
    expect(page('ok')).toContain(S.ouraDone.result.ok!)
    expect(page('state_mismatch')).toContain(S.ouraDone.result.state_mismatch!)
    const odd = page('something_else')
    expect(odd).toContain(S.ouraDone.failed)
    expect(odd).toContain(S.ouraDone.safari)
    expect(odd).toContain(S.ouraDone.open)
  })
})
