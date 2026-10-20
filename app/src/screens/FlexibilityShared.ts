// What the Flexibility screen and its assessment share (rebuild Phase 8): the engine's
// address, the guide's shape, the owner's place in an assessment, and two small helpers.
import type { components } from '../generated/api'
import { ApiError } from '../lib/api'
import { S } from '../strings'

export type FlexibilityAnswer = components['schemas']['FlexibilityOut']

export const FLEXIBILITY = '/api/insights/flexibility'
export const CAPTURE_PAGE = '/insights/flexibility/capture'

/** The protocol's fixed explanations, as the engine sends them (flexibility_screen.guide). */
export interface Guide {
  cluster_label: string
  test_count: number
  measures: { measure: string; short: string; long: string }[]
  gap: string
  lock: string
  frozen: { name: string; why: string }[]
  progression_variable: { name: string; why: string }
  nerve_check: string
  medial_knee_note: string
  slots: { slot: number; label: string; question: string; decides: string }[]
  held_back: { key: string; label: string; until: string; safety: string }[]
}

/** Where the owner is in the engine's order, and whether he chose to keep going past an
 *  early answer: kept while the app runs, as the old app kept them for its session. */
export const position = { step: 0, keepGoing: false }

/** A new assessment opens on its first test (Start, Re-assess); Resume keeps the place. */
export function freshCapture(): void {
  position.step = 0
  position.keepGoing = false
}

/** A typed reading as a number, or null when the field is empty. */
export function numberOf(text: string | undefined): number | null {
  const t = (text ?? '').trim().replace(',', '.')
  if (!t) return null
  const v = Number(t)
  return Number.isFinite(v) ? v : null
}

/** Why a write did not land, in the app's words. */
export function failure(err: unknown): string {
  return S.fresh.why[err instanceof ApiError ? err.kind : 'server']
}
