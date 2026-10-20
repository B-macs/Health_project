// A sheet over the page (rebuild Phase 4; the check-in opens as one). The page behind
// dims and stays where it was; the close button, a tap on the dim, and Escape close it.
import { useEffect, useRef, type ReactNode } from 'react'
import { IconClose } from './icons'

export function Sheet(p: { title: string; closeLabel: string; onClose: () => void; children: ReactNode }) {
  const close = useRef<HTMLButtonElement>(null)
  const onClose = p.onClose
  useEffect(() => {
    close.current?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <div className="sheet">
      <div className="sheet__scrim" aria-hidden="true" onClick={onClose} />
      <section className="sheet__panel" role="dialog" aria-modal="true" aria-labelledby="sheet-title">
        <div className="sheet__grip" aria-hidden="true" />
        <header className="sheet__head">
          <h2 id="sheet-title" className="sheet__title">{p.title}</h2>
          <button ref={close} className="iconbtn" aria-label={p.closeLabel} onClick={onClose}>
            <IconClose />
          </button>
        </header>
        {p.children}
      </section>
    </div>
  )
}
