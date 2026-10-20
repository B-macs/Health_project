// How the screens write a date (an ISO day, read as that calendar day wherever the phone is).
const LONG = new Intl.DateTimeFormat('en-GB', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'UTC' })
const NARROW = new Intl.DateTimeFormat('en-GB', { weekday: 'narrow', timeZone: 'UTC' })
const SHORT = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' })
const at = (iso: string) => new Date(`${iso}T00:00:00Z`)

/** "Tuesday 20 October". */
export const longDate = (iso: string) => LONG.format(at(iso))
/** "T". */
export const narrowDay = (iso: string) => NARROW.format(at(iso))
/** "20". */
export const dayOfMonth = (iso: string) => String(Number(iso.slice(8, 10)))
/** "12 Oct". */
export const shortDate = (iso: string) => SHORT.format(at(iso))
