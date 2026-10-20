// Is the app open from the Home Screen (rebuild Phase 4)? iOS answers through
// navigator.standalone; other browsers through the display-mode media query.
export function isStandalone(): boolean {
  if (typeof window === 'undefined') return false
  const nav = window.navigator as Navigator & { standalone?: boolean }
  return nav.standalone === true || Boolean(window.matchMedia?.('(display-mode: standalone)').matches)
}
