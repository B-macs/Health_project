// Makes the VAPID key pair for the timer alerts (Web Push, rebuild Phase 6). Run it once,
// from worker/:
//   node scripts/vapid-keygen.mjs
// The PRIVATE key goes straight into the Worker secret VAPID_PRIVATE_KEY through
// `wrangler secret put`, on wrangler's standard input: it is never printed, never written to
// a file and never in this repo. The PUBLIC key (public by design: the phone needs it to
// subscribe) is written into wrangler.jsonc's VAPID_PUBLIC_KEY and printed. Run it again to
// change the pair; the phone then subscribes again at its next start (src/lib/alerts.ts).
import { spawn } from 'node:child_process'
import { webcrypto } from 'node:crypto'
import { readFileSync, writeFileSync } from 'node:fs'

const pair = await webcrypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, true, ['sign', 'verify'])
const privateKey = (await webcrypto.subtle.exportKey('jwk', pair.privateKey)).d
const publicKey = Buffer.from(await webcrypto.subtle.exportKey('raw', pair.publicKey)).toString('base64url')

const stored = await new Promise((resolve) => {
  // One fixed command line (no arguments from anywhere): the shell finds pnpm on Windows too.
  const wrangler = spawn('pnpm exec wrangler secret put VAPID_PRIVATE_KEY',
    { stdio: ['pipe', 'inherit', 'inherit'], shell: true, env: { ...process.env, CI: '1' } })
  wrangler.on('close', (code) => resolve(code === 0))
  wrangler.stdin.end(privateKey)
})
if (!stored) {
  console.error('wrangler did not store the private key: nothing changed.')
  process.exit(1)
}

const config = readFileSync('wrangler.jsonc', 'utf-8')
const line = /"VAPID_PUBLIC_KEY": "[^"]*"/
if (!line.test(config)) {
  console.error('wrangler.jsonc has no VAPID_PUBLIC_KEY line: write this public key there by hand.')
}
writeFileSync('wrangler.jsonc', config.replace(line, `"VAPID_PUBLIC_KEY": "${publicKey}"`))
console.log(`VAPID public key (public by design), now in wrangler.jsonc: ${publicKey}`)
console.log('Deploy the Worker (pnpm exec wrangler deploy) so it sends with the new pair.')
