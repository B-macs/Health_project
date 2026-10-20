// The head of an Insights screen (rebuild Phase 8): a back link to the page it opened from
// (an in-app move, never a page load: Key Rule 17) and the title.
import { useApp } from '../lib/appState'
import { S } from '../strings'
import { IconBack } from './icons'

export function InsightsHead({ title, back = '/insights', backLabel = S.ins.back, caption }: {
  title: string; back?: string; backLabel?: string; caption?: string
}) {
  const { go } = useApp()
  return (
    <>
      <header className="topbar">
        <button className="backlink" aria-label={S.ins.backTo(backLabel)} onClick={() => go(back)}>
          <IconBack />
          <span>{backLabel}</span>
        </button>
        <span />
        <span />
      </header>
      <header className="head">
        <h1 className="head__title">{title}</h1>
        {caption && <div className="caption">{caption}</div>}
      </header>
    </>
  )
}
