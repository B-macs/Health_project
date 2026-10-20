// Line icons for the tab bar and the controls. They draw in currentColor at the size
// and line weight the stylesheet gives `.icon` (both tokens), so each direction sizes
// and weights them without touching this file.
import type { ReactNode } from 'react'

function Icon({ children }: { children: ReactNode }) {
  return (
    <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {children}
    </svg>
  )
}

export const IconToday = () => (
  <Icon>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 3.5a8.5 8.5 0 0 1 8.5 8.5" />
    <circle cx="12" cy="12" r="3.2" />
  </Icon>
)

export const IconCheckin = () => (
  <Icon>
    <rect x="5" y="4" width="14" height="17" rx="2.5" />
    <path d="M9 4.5V3h6v1.5" />
    <path d="M8.8 12.6l2.2 2.2 4.3-4.6" />
  </Icon>
)

export const IconTraining = () => (
  <Icon>
    <path d="M3 12h18" />
    <rect x="5.2" y="7.5" width="3" height="9" rx="1" />
    <rect x="15.8" y="7.5" width="3" height="9" rx="1" />
    <path d="M3 10v4M21 10v4" />
  </Icon>
)

export const IconInsights = () => (
  <Icon>
    <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
  </Icon>
)

export const IconSettings = () => (
  <Icon>
    <circle cx="12" cy="12" r="3" />
    <path d="M12 2.8v2.4M12 18.8v2.4M2.8 12h2.4M18.8 12h2.4M5.5 5.5l1.7 1.7M16.8 16.8l1.7 1.7M5.5 18.5l1.7-1.7M16.8 7.2l1.7-1.7" />
  </Icon>
)

export const IconBack = () => (
  <Icon>
    <path d="M15 5l-7 7 7 7" />
  </Icon>
)

export const IconForward = () => (
  <Icon>
    <path d="M9 5l7 7-7 7" />
  </Icon>
)

export const IconClose = () => (
  <Icon>
    <path d="M6 6l12 12M18 6L6 18" />
  </Icon>
)

export const IconPause = () => (
  <Icon>
    <path d="M9 5v14M15 5v14" />
  </Icon>
)

export const IconPlay = () => (
  <Icon>
    <path d="M7 4.5v15l12-7.5z" />
  </Icon>
)

export const IconCheck = () => (
  <Icon>
    <path d="M5 12.5l4.5 4.5L19 7.5" />
  </Icon>
)

export const IconPlus = () => (
  <Icon>
    <path d="M12 5v14M5 12h14" />
  </Icon>
)
