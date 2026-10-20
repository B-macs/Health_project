// Browser tests (rebuild Phase 4): the BUILT app with its service worker, against the mock
// API (dev/mockApi.ts). Chromium checks the install, the offline boot, the outbox and the
// update rule (Playwright 1.63's WebKit cannot answer from a service worker offline —
// Lauscher's finding); WebKit with the iPhone 17 Pro Max profile checks the screens and
// the saved data with the engine down. The real iPhone checks the rest (the owner's
// checklist). Results go under reports/rebuild/, which git ignores.
// Run: pnpm --filter @health/app exec playwright test
import { defineConfig, devices } from '@playwright/test'

export const PORT = 4175
const OUT = '../reports/rebuild/e2e-dist'

export default defineConfig({
  testDir: 'e2e',
  outputDir: '../reports/rebuild/e2e-results',
  timeout: 90_000,
  workers: 1,
  reporter: [['list']],
  use: { baseURL: `http://127.0.0.1:${PORT}`, serviceWorkers: 'allow' },
  webServer: {
    command: `npx vite build --mode mock --outDir ${OUT} --emptyOutDir && npx vite preview --mode mock --outDir ${OUT} --port ${PORT} --strictPort --host 127.0.0.1`,
    url: `http://127.0.0.1:${PORT}`,
    reuseExistingServer: false,
    timeout: 180_000,
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 440, height: 956 } } },
    { name: 'webkit', use: { ...devices['iPhone 17 Pro Max'] }, grepInvert: /@offline|@install|@outbox|@update/ },
  ],
})
