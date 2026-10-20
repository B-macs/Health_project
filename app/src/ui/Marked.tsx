// Text written with **bold** marks (the battery's protocol texts, and a few of the app's own
// lines): each marked part shows bold, as the old app showed it.
export function Marked({ text }: { text: string }) {
  return (
    <>
      {text.split('**').map((part, i) => (i % 2 === 1 ? <b key={i}>{part}</b> : <span key={i}>{part}</span>))}
    </>
  )
}

/** A number as the old app wrote it ("{:g}"): no trailing zeros. */
export const plain = (v: number) => String(Number(v.toPrecision(6)))
