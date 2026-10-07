// The version line, as Lauscher shows it: "0.1.0 (abc1234) · built 7 Oct 09:41".
export type Build = { number: string; commit: string; built: string }

export function versionLine(build: Build, locale = 'en-GB', timeZone?: string): string {
  const when = new Date(build.built)
  const stamp = Number.isNaN(when.getTime())
    ? 'unknown'
    : when.toLocaleString(locale, {
        day: 'numeric',
        month: 'short',
        hour: '2-digit',
        minute: '2-digit',
        timeZone,
      })
  return `${build.number} (${build.commit}) · built ${stamp}`
}
