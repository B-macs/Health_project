// A sheet over the page (rebuild Phase 4; the check-in opens as one). The page behind
// dims and stays where it was; the close button, a tap on the dim, and Escape close it.
import { useEffect, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { IconClose } from './icons'

/** A sheet over the screen. `contained` keeps it inside the screen area, above the bottom
 *  bar, for a sheet that IS a tab (Check-in; the owner, 2026-10-20: "when pressed I can no
 *  longer see the bottom bar"); other sheets cover the whole app.
 *
 *  A sheet that covers the whole app is drawn on the app's frame (`.app`), outside the
 *  scrolling area. On the iPhone a fixed box inside the scrolling area is cut at that area's
 *  edges: the bottom bar covered the "+" menu's last item, the EGYM circuit (the owner,
 *  2026-11-08: "I can't see the training as a choice"). */
export function Sheet(p: { title: string; closeLabel: string; onClose: () => void; children: ReactNode; contained?: boolean }) {
  const close = useRef<HTMLButtonElement>(null)
  const onClose = p.onClose
  // The newest close, for Escape: a parent drawn again hands a new one each time.
  const latest = useRef(onClose)
  useEffect(() => {
    latest.current = onClose
  }, [onClose])
  // Once, when the sheet opens. Run again on every new `onClose`, it took the focus back to
  // Close each time the app was drawn again, and that jumped the sheet to its top: on
  // 2026-10-21 the check-in's "Check-in complete" went out of view the moment it showed.
  useEffect(() => {
    // No scroll on focus: the panel starts below its box while it slides up, and a focus
    // that scrolls to it moved the whole app up 16 px over a contained sheet.
    close.current?.focus({ preventScroll: true })
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') latest.current()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
  const sheet = (
    <div className={p.contained ? 'sheet sheet--contained' : 'sheet'}>
      <div className="sheet__scrim" aria-hidden="true" onClick={onClose} />
      <section className="sheet__panel" role="dialog" aria-modal={!p.contained} aria-labelledby="sheet-title">
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
  const frame = p.contained ? null : document.querySelector('.app')
  return frame ? createPortal(sheet, frame) : sheet
}
