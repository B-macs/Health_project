// The day Today and its three detail screens show (rebuild Phase 5).
//
// Today, unless a past day was picked. A pick is kept for this visit only (sessionStorage:
// it survives a reload, not a new visit; WP-09, "Home opens on today and a past day lasts
// one visit") together with the day it was picked on. Which day the app actually opens on
// is the ENGINE's rule (services/home.py:opening_day, H7): the phone sends both days with
// `picked_on` and shows the day the engine answers for; when the engine answers today,
// the pick is dropped. The phone keeps no copy of the rule (rebuild rule 1).
import { useEffect, useState } from 'react'
import { localDay } from './api'

const systemNow = (): Date => new Date()

/** The phone's day, again each time the app comes to the front and once a minute: a page
 *  left open overnight shows the new day, never the day it was opened on (2026-10-22). */
export function useToday(now: () => Date = systemNow): string {
  const [day, setDay] = useState(() => localDay(now()))
  useEffect(() => {
    const check = () => setDay(localDay(now()))
    document.addEventListener('visibilitychange', check)
    const timer = setInterval(check, 60_000)
    return () => {
      document.removeEventListener('visibilitychange', check)
      clearInterval(timer)
    }
  }, [now])
  return day
}

export interface Pick {
  day: string
  pickedOn: string
}

const KEY = 'health.shownDay'

export function readPick(): Pick | null {
  try {
    const raw = window.sessionStorage.getItem(KEY)
    const pick = raw ? (JSON.parse(raw) as Pick) : null
    return pick && typeof pick.day === 'string' && typeof pick.pickedOn === 'string' ? pick : null
  } catch {
    return null
  }
}

export function writePick(pick: Pick | null): void {
  try {
    if (pick) window.sessionStorage.setItem(KEY, JSON.stringify(pick))
    else window.sessionStorage.removeItem(KEY)
  } catch {
    // A private window: the pick lasts until the page closes.
  }
}

/** A day picked now: null for today or a later day (the screens show today then). */
export function pickFor(day: string | null, now: Date = new Date()): Pick | null {
  const today = localDay(now)
  return day && day < today ? { day, pickedOn: today } : null
}

/** The address of a day's read: `base` for today, with the day and when it was picked otherwise. */
export function dayPath(base: string, pick: Pick | null, extra: Record<string, string> = {}): string {
  const query = new URLSearchParams(extra)
  if (pick) {
    query.set('date', pick.day)
    query.set('picked_on', pick.pickedOn)
  }
  const text = query.toString()
  return text ? `${base}?${text}` : base
}
