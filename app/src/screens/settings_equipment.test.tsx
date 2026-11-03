// Settings › Weight steps (WP-46): the list the engine sent, edited and sent back whole.
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import fixture from '../../dev/insights_fixture.json'
import { ApiError } from '../lib/api'
import { S } from '../strings'
import { EquipmentCard, bodyOf, draftOf, refusalWords, type EquipmentAnswer } from './SettingsEquipment'

const ANSWER = (fixture as unknown as { equipment: EquipmentAnswer }).equipment

describe('the weight steps', () => {
  it('draws every item with its step and every lift with the item it is on', () => {
    const html = renderToStaticMarkup(<EquipmentCard answer={ANSWER} busy={false} error={null} saved={false} onSave={() => {}} />)
    expect(html).toContain(S.settings.equipment)
    for (const i of ANSWER.items) expect(html).toContain(`value="${i.name}"`)
    for (const e of ANSWER.exercises) expect(html).toContain(e.name)
    expect(html).toContain(S.settings.equipmentPair)
  })

  it('sends the list back whole, each step a number, and only the links that differ', () => {
    const d = draftOf(ANSWER)
    expect(d.links).toEqual({})
    const body = bodyOf({ ...d, items: d.items.map((i) => (i.id === 'machines' ? { ...i, step: '5' } : i)) })
    expect(body.items.map((i) => i.id)).toEqual(ANSWER.items.map((i) => i.id))
    expect(body.items.find((i) => i.id === 'machines')!.step).toBe(5)
    expect(body.items.every((i) => !('default' in i))).toBe(true)
  })

  it("words a refusal in the engine's own reason, and anything else as needing a connection", () => {
    const refused = new ApiError('rejected', 422, 'invalid_equipment: the default items cannot be removed')
    expect(refusalWords(refused)).toBe(S.settings.equipmentRefused('the default items cannot be removed'))
    expect(refusalWords(new ApiError('engine_unavailable', null, 'x'))).toBe(S.settings.equipmentOffline)
  })
})
