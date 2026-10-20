// The page Oura's login ends on (rebuild Phase 9). Oura sends the owner to the Worker's
// /oura/callback, which hands the code to the engine and then opens this app at
// #/oura-done?result=<ok | a refusal code>. It needs no access key: on iOS the login can come
// back in Safari, which does not share the Home Screen app's storage, so the page only says
// how it went and how to get back.
import { S } from '../strings'

const PREFIX = '#/oura-done'

/** The login's result from the address, or null when this is not the result page. */
export function ouraDoneResult(hash: string): string | null {
  if (!hash.startsWith(PREFIX)) return null
  const query = hash.slice(PREFIX.length).replace(/^\?/, '')
  return new URLSearchParams(query).get('result') ?? ''
}

export function OuraDone({ result, onDone }: { result: string; onDone: () => void }) {
  const ok = result === 'ok'
  return (
    <main className="scroller">
      <div className="screen settings" data-testid="oura-done" data-result={result}>
        <h1 className="head__title">{S.ouraDone.title}</h1>
        <p className={ok ? 'notice' : 'alert'} role="status">{S.ouraDone.result[result] ?? S.ouraDone.failed}</p>
        <p className="caption">{S.ouraDone.safari}</p>
        <button className="btn btn--primary btn--wide" onClick={onDone}>{S.ouraDone.open}</button>
      </div>
    </main>
  )
}
