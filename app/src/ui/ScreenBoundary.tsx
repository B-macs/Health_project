// A screen that fails to draw shows a short message instead of taking the whole app down
// with it (rebuild Phase 4: never a blank screen). The tab bar stays, the other screens
// still work, and the reason goes to the debug log. A new address starts it again.
import { Component, type ErrorInfo, type ReactNode } from 'react'
import { debugLog } from '../debug/console'
import { S } from '../strings'

type Props = { title: string; children: ReactNode }

export class ScreenBoundary extends Component<Props, { failed: boolean }> {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    debugLog('screen: failed', { screen: this.props.title, error: String(error), where: info.componentStack?.slice(0, 300) })
  }

  render() {
    if (!this.state.failed) return this.props.children
    return (
      <div className="screen" role="alert">
        <div className="sky sky--quiet" aria-hidden="true" />
        <header className="head">
          <h1 className="head__title">{this.props.title}</h1>
        </header>
        <p className="caption">{S.screenFailed}</p>
      </div>
    )
  }
}
