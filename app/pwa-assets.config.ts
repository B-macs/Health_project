// Icons and iOS splash screens from public/logo.svg (rebuild Phase 4, Lauscher's setup):
// `pnpm --filter @health/app icons`. The logo is full-bleed with its own margins, so the
// maskable and Apple icons need no extra padding.
import { createAppleSplashScreens, defineConfig, minimal2023Preset } from '@vite-pwa/assets-generator/config'

const NIGHT = '#07090E'

export default defineConfig({
  headLinkOptions: { preset: '2023' },
  preset: {
    ...minimal2023Preset,
    maskable: { sizes: [512], padding: 0, resizeOptions: { background: NIGHT } },
    apple: { sizes: [180], padding: 0, resizeOptions: { background: NIGHT } },
    appleSplashScreens: createAppleSplashScreens(
      {
        padding: 0.35,
        resizeOptions: { background: NIGHT, fit: 'contain' },
        darkResizeOptions: { background: NIGHT, fit: 'contain' },
        linkMediaOptions: { log: true, addMediaScreen: true, xhtml: false },
        png: { compressionLevel: 9, quality: 70 },
      },
      ['iPhone 17 Pro Max'],
    ),
  },
  images: ['public/logo.svg'],
})
