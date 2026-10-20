// The check-in (slate), as a sheet over Today (rebuild Phase 4: the frame; Phase 5 adds
// the form). The page behind keeps its own colour; the sheet takes the check-in's.
import { PAGE_FAMILY } from '../design/tokens'
import { S } from '../strings'
import { Sheet } from '../ui/Sheet'

export function CheckIn({ onClose }: { onClose: () => void }) {
  return (
    <div className={`fam-${PAGE_FAMILY.checkin}`}>
      <Sheet title={S.checkin.title} closeLabel={S.checkin.close} onClose={onClose}>
        <p className="caption">{S.checkin.frame}</p>
      </Sheet>
    </div>
  )
}
