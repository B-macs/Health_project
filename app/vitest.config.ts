// Unit tests run in Node with an in-memory IndexedDB (fake-indexeddb), so the Dexie code is
// tested as it runs on the phone (Lauscher's setup). Playwright covers the browser (e2e/).
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'node',
    setupFiles: ['fake-indexeddb/auto'],
    include: ['src/**/*.test.{ts,tsx}'],
  },
})
