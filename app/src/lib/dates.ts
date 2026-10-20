// How the screens write a date (an ISO day, read as that calendar day wherever the phone is).
const LONG = new Intl.DateTimeFormat('en-GB', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'UTC' })
const NARROW = new Intl.DateTimeFormat('en-GB', { weekday: 'narrow', timeZone: 'UTC' })
const SHORT = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' })
const YEAR = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' })
const MONTH = new Intl.DateTimeFormat('en-GB', { month: 'long', year: 'numeric', timeZone: 'UTC' })
const FULL = new Intl.DateTimeFormat('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' })
const at = (iso: string) => new Date(`${iso}T00:00:00Z`)

/** "Tuesday 20 October". */
export const longDate = (iso: string) => LONG.format(at(iso))
/** "T". */
export const narrowDay = (iso: string) => NARROW.format(at(iso))
/** "20". */
export const dayOfMonth = (iso: string) => String(Number(iso.slice(8, 10)))
/** "12 Oct". */
export const shortDate = (iso: string) => SHORT.format(at(iso))
/** "12 Oct 2026". */
export const yearDate = (iso: string) => YEAR.format(at(iso))
/** "October 2026". */
export const monthName = (year: number, month: number) => MONTH.format(new Date(Date.UTC(year, month - 1, 1)))
/** "Tuesday 20 October 2026". */
export const fullDate = (iso: string) => FULL.format(at(iso))
