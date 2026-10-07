// The health app (rebuild Phase 0: a placeholder; the PWA shell comes in Phase 4).
// The build stamp is Lauscher's pattern: package version, git commit, build time.
import { execSync } from 'node:child_process'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import pkg from './package.json' with { type: 'json' }

function commit(): string {
  try {
    return execSync('git rev-parse --short HEAD', { encoding: 'utf-8' }).trim()
  } catch {
    return 'dev'
  }
}

export default defineConfig({
  plugins: [react()],
  define: {
    __APP_BUILD__: JSON.stringify({
      number: pkg.version,
      commit: commit(),
      built: new Date().toISOString(),
    }),
  },
})
