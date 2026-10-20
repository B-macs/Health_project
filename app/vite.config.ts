// The health app (rebuild Phase 4): React, the service worker (vite-plugin-pwa with
// injectManifest: src/sw/sw.ts), and the build stamp (Lauscher's pattern: package
// version, git commit, build time) for the version line in Settings.
import { execSync } from 'node:child_process'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'
import { mockApi } from './dev/mockApi.ts'
import pkg from './package.json' with { type: 'json' }

function commit(): string {
  try {
    return execSync('git rev-parse --short HEAD', { encoding: 'utf-8' }).trim()
  } catch {
    return 'dev'
  }
}

export default defineConfig(({ mode }) => ({
  plugins: [
    react(),
    // `--mode mock`: the engine's API answered locally, for the browser tests (dev/mockApi.ts)
    mode === 'mock' ? mockApi() : null,
    // The service worker. The web manifest is a static file (public/manifest.webmanifest);
    // iOS fetches the splash screens and icons itself, so the precache holds the shell only.
    VitePWA({
      strategies: 'injectManifest',
      srcDir: 'src/sw',
      filename: 'sw.ts',
      injectRegister: false,
      manifest: false,
      injectManifest: {
        globPatterns: ['**/*.{js,css,html,svg,webmanifest}'],
        globIgnores: ['**/apple-splash-*', '**/eruda-*.js'], // Eruda loads on demand
      },
      devOptions: { enabled: false },
    }),
  ],
  define: {
    __APP_BUILD__: JSON.stringify({ number: pkg.version, commit: commit(), built: new Date().toISOString() }),
  },
}))
