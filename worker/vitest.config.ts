import { cloudflareTest } from '@cloudflare/vitest-plugin'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [
    cloudflareTest({
      wrangler: { configPath: './wrangler.jsonc' },
      miniflare: {
        bindings: {
          ACCESS_KEY: 'test-access-key',
          ENGINE_KEY: 'test-engine-key',
          ENGINE_URL: 'https://engine.test',
        },
      },
    }),
  ],
})
