// Rebuild Phase 0 placeholder: proves the Worker serves the app on the phone.
// The design comes from the Phase 3 bake-off; nothing here is final.
import type { CSSProperties } from 'react'
import { versionLine } from './version'

const page: CSSProperties = {
  minHeight: '100dvh',
  margin: 0,
  padding: 'max(24px, env(safe-area-inset-top)) 16px 24px',
  boxSizing: 'border-box',
  display: 'flex',
  flexDirection: 'column',
  justifyContent: 'center',
  alignItems: 'center',
  gap: 12,
  fontFamily: 'system-ui, -apple-system, sans-serif',
  background: 'Canvas',
  color: 'CanvasText',
}

export function App() {
  return (
    <main style={page}>
      <h1 style={{ fontSize: 34, margin: 0 }}>Health</h1>
      <p style={{ margin: 0, opacity: 0.7 }}>The new app is being built.</p>
      <p style={{ margin: 0, fontSize: 13, opacity: 0.5 }}>{versionLine(__APP_BUILD__)}</p>
    </main>
  )
}
