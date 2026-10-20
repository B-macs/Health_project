import { webcrypto } from 'node:crypto'
import { cloudflareTest } from '@cloudflare/vitest-plugin'
import { defineConfig } from 'vitest/config'

// A throwaway VAPID key pair for the timer-alert tests, made fresh on every run and never
// stored: the alert's Durable Object reads its keys from its own bindings, as it does live.
const pair = await webcrypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, true, ['sign', 'verify'])
const VAPID_PRIVATE_KEY = (await webcrypto.subtle.exportKey('jwk', pair.privateKey)).d as string
const VAPID_PUBLIC_KEY = Buffer.from(await webcrypto.subtle.exportKey('raw', pair.publicKey)).toString('base64url')

export default defineConfig({
  plugins: [
    cloudflareTest({
      wrangler: { configPath: './wrangler.jsonc' },
      miniflare: {
        bindings: {
          ACCESS_KEY: 'test-access-key',
          ENGINE_KEY: 'test-engine-key',
          ENGINE_URL: 'https://engine.test',
          VAPID_PUBLIC_KEY,
          VAPID_PRIVATE_KEY,
          VAPID_SUBJECT: 'https://health.test',
        },
      },
    }),
  ],
})
