# Rebuild stack: pinned versions, limits, prices and their sources

Every entry was checked on the date shown. Versions, limits and prices change: check the live
source again before relying on one (rebuild rule 10).

## Toolchains on the owner's PC (checked 2026-10-07)

| Tool | Version | Notes |
|---|---|---|
| Node.js | 24.14.0 | LTS line |
| pnpm | 12.9.1 | the `packageManager` pin in package.json |
| uv | 0.12.23 | builds `.venv-engine` only; NO pyproject.toml or uv.lock at the repo root (see below) |
| Python (Streamlit app, `venv/`) | 3.11.9 | unchanged |
| Python (engine, `.venv-engine/`, container) | 3.12.9 locally, `python:3.12-slim` in the image | garminconnect 0.3.17 and numpy 2.5.3 need 3.12 or newer |
| Google Cloud CLI | installed 2026-10-19 with Google's own installer | `winget` was not on this PC's user PATH; gcloud is at `%LOCALAPPDATA%\Google\Cloud SDK\google-cloud-sdk\bin` |
| Docker | not installed, not needed | Cloud Build builds the image from source |
| gitleaks | not installed | the gate uses its own pattern scan (scripts/rebuild_gate.py) |

## Python packages (requirements-engine.txt, exact pins, checked on PyPI 2026-10-07)

| Package | Version | Python | Source |
|---|---|---|---|
| fastapi | 0.142.2 | >=3.10 | https://pypi.org/project/fastapi/ |
| uvicorn | 0.54.0 | >=3.10 | https://pypi.org/project/uvicorn/ |
| gspread | 6.2.1 | >=3.8 | https://pypi.org/project/gspread/ |
| notion-client | 2.2.1 | | the repo's own pin; 3.1.0 exists and is not evaluated |
| requests | 2.34.2 | >=3.10 | https://pypi.org/project/requests/ |
| garminconnect | 0.3.17 | >=3.12 | https://pypi.org/project/garminconnect/ (needs curl_cffi, requests, ua-generator) |
| numpy | 2.5.3 | >=3.12 | https://pypi.org/project/numpy/ (services/stats.py) |
| pandas | 3.0.6 | >=3.11 | https://pypi.org/project/pandas/ (services/stats.py) |
| tzdata | 2026.5 | | https://pypi.org/project/tzdata/ (zoneinfo data in a slim image) |
| pytest (dev) | 9.1.1 | >=3.10 | https://pypi.org/project/pytest/ |
| httpx (dev) | 0.28.1 | >=3.8 | https://pypi.org/project/httpx/ (FastAPI's TestClient). Starlette 1.7 warns that TestClient on httpx is deprecated in favour of httpx2 (2.13.1); a warning only, revisit in Phase 2 |

## npm packages (checked with `npm view` 2026-10-07)

| Package | Version | Used in | Notes |
|---|---|---|---|
| hono | 4.13.13 | worker | `bearerAuth` compares with SHA-256 + constant-time equality (checked in Lauscher's node_modules) |
| wrangler | 4.147.0 | worker | 4.148.0 is the newest, but pnpm's minimum-release-age check held it (released days ago); 4.147.0 is the version Lauscher runs |
| @cloudflare/vitest-plugin | 1.3.6 | worker | peer: vitest ^4.1.0, so the Worker stays on vitest 4.1 (Lauscher's finding); 1.3.7 was held by the same release-age check |
| vitest | 4.1.11 (worker), 5.0.3 (app) | | |
| typescript | 7.0.2 (app, worker), 5.9.3 (root) | | openapi-typescript needs typescript ^5 (peer), so the ROOT package pins 5.9.3 for it alone |
| vite | 8.3.3 | app | |
| @vitejs/plugin-react | 6.1.2 | app | |
| react, react-dom, @types/react, @types/react-dom | 19.3.0 | app | |
| openapi-typescript | 7.13.0 | root | shared/openapi.json -> app/src/generated/api.ts |

## Free tiers and limits (checked 2026-10-07)

- **Google Cloud Run, request-based billing, Tier 1 regions:** 2 million requests, 180,000 vCPU-seconds and 360,000 GiB-seconds a month per billing account; 1 GB of outbound data from North America. Tier 2 regions use up the free tier faster. A billing account is necessary. https://docs.cloud.google.com/free/docs/free-cloud-features and https://cloud.google.com/run/pricing
- **Artifact Registry:** 0.5 GB of storage free a month. Same source.
- **Cloud Build:** 2,500 build-minutes a month free (e2-standard-2). https://cloud.google.com/build/pricing
- **Secret Manager:** 6 active secret versions and 10,000 access operations a month free. https://cloud.google.com/secret-manager/pricing
- **Cloudflare Workers, free plan:** 10 ms of CPU per request (network waits do not count), 100,000 requests a day; static asset requests are free. https://developers.cloudflare.com/workers/platform/limits
- **Cloudflare Containers (rejected, the fallback):** Workers Paid at $5 a month, generally available since 2026-04-13. https://developers.cloudflare.com/containers/pricing/

## Decisions and notes

- **No pyproject.toml or uv.lock at the repo root.** Streamlit Community Cloud picks its dependency file by priority, and a uv.lock or pyproject.toml can win over requirements.txt. That would install the engine's pins into the hosted Streamlit app. `.venv-engine` is built with `uv venv` + `uv pip install -r requirements-engine-dev.txt`, which writes no project file.
- **Engine auth: a shared key, not Cloud Run IAM.** The Worker sends `X-Engine-Key`; the engine compares it with `hmac.compare_digest`. IAM would make Google reject strangers before the container starts, but the Worker would then hold a long-lived Google service-account key and sign a JWT for an ID token every hour. A 32-byte random key is not guessable, and the Cloud Run address is not published. Revisit if scanners wake the engine (Phase 0 M8 shows it).
- **One secret holds the engine's keys** (`health-engine-secrets`, mounted as a file), and one holds the engine key (`health-engine-key`, an environment variable). Two active versions, inside the free six. **Trimmed, not the whole secrets.toml** (2026-10-19): `scripts/rebuild_secrets.py engine-secrets` uploads only `ENGINE_SECRET_KEYS` — the Supabase address and key, the Garmin login and the Oura app — because with Supabase as the only store the engine never calls Notion or Google Sheets; their token, the service-account key, the old Oura token and the Voice Training keys stay on the PC. `load_config` in Supabase mode treats them as optional (tested).
- **Google Cloud project** (2026-10-19): `health-project-512108` (number 230738513464), created by the owner in the console on a business billing account with a €1 budget alert. `gcloud init` had refused the ID `health_project`: an ID and a display name cannot hold `_`.
- **The Worker's ENGINE_URL is a secret, not a `vars` entry,** so the engine's address is not in this public repo.
- **The account's workers.dev subdomain is `lauscher-worker`.** The Worker named `health` is `health.lauscher-worker.workers.dev`. Changing the subdomain would also change Lauscher's address.
- **Region:** europe-west1 (Belgium), **Tier 1**, checked on https://cloud.google.com/run/pricing on 2026-10-19 (Frankfurt, europe-west3, and Berlin, europe-west10, are Tier 2).

## Deployed (2026-10-19)

- **At the Phase 0 gate the engine is revision `health-engine-00006-bzf`**: the image of commit 2ff03cf (revision 5, precompiled .pyc) with `HEALTH_PROBES` removed. Revisions 1-4 are 84c88c6 (first), 6dd2fcf (gzip), 5f772c4 (never started: Supabase PGRST303) and 7291d6c (retries).
- **Max instances stays 1 on purpose**: each instance keeps its own local copy of the database, and a write through one would not reach another's copy. Google's refusal of a request while that one instance starts ("no available instance", HTTP 500) is handled by the Worker's retry (1, 2, 4, 8 s), not by more instances.
- **Cloud Run service `health-engine`**, europe-west1, first deployed as revision `health-engine-00001-9sq` from commit 84c88c6: min 0 / max 1 instance, 1 vCPU, 1 GiB, timeout 900 s, concurrency 80, request-based billing. **Startup CPU boost is ON** — gcloud 2026 sets it by default on a new service (`run.googleapis.com/startup-cpu-boost: true`); it was not asked for. `--allow-unauthenticated`, and every request is checked against `X-Engine-Key`: no key or a wrong key gives 401, and /docs, /redoc and /openapi.json give 404 (checked live). The address is NOT written in this repo; read it with `gcloud run services describe health-engine --region=europe-west1 --format="value(status.url)"`.
- **Runtime identity: `health-engine@health-project-512108.iam.gserviceaccount.com`**, made for the engine, with NO project role — only Secret Accessor on its two secrets. The Compute Engine default account (project Editor) is left as Cloud Build's build account only.
- **Secrets are PINNED to version 1** (`/secrets/health/secrets.toml=health-engine-secrets:1`, `HEALTH_ENGINE_KEY=health-engine-key:1`). Google discourages `latest` for an environment variable, and a mounted `latest` is fetched from Secret Manager at every read of the file (https://docs.cloud.google.com/run/docs/configuring/services/secrets, 2026-10-19). The engine reads the file once per start (`engine.startup`). A new secret version therefore needs a redeploy that names it — deliberate.
- **Environment:** `HEALTH_TIMEZONE=Europe/Berlin`, `TZ=Europe/Berlin` (the owner's zone, 2026-10-19), `HEALTH_BUILD_COMMIT`, `HEALTH_BUILD_TIME`. `HEALTH_PROBES=1` ran during Phase 0 only and is removed (revision 6; /api/probe/* answers 404).
- **Free amounts re-checked on the live pages 2026-10-19:** Artifact Registry 0.5 GiB-month per billing account, same-location transfer free (the Container Scanning API is NOT enabled; it bills per image); Cloud Build 2,500 build-minutes a month (e2-standard-2, default pool; a build here takes 1.2 min); Secret Manager 6 active versions, 10,000 accesses, 3 rotation notifications a month; Premium-tier data out of europe-west1 $0.12/GiB with no free amount; Supabase Free 5 GB uncached + 5 GB cached egress a month, no charge over it but a grace period and then restrictions.
- **Logs** (checked 2026-10-19): the startup timings and uvicorn's request lines (method, path, status) only — no address, no key, no value.
- **Image:** 115.1 MB in Artifact Registry `cloud-run-source-deploy` (europe-west1). Clean-up policy: keep the 2 newest, delete the rest after a day (`--no-dry-run`; it runs about once a day).
- **Uploaded source:** `gs://run-sources-health-project-512108-europe-west1`, 687 KiB a deploy, deleted after 7 days by a lifecycle rule. Cloud Storage's free tier covers US regions only, so this costs about $0.00002 a month.
- **Data out:** Cloud Run's free 1 GiB covers traffic within North America only; from Belgium it is billed at Google's Premium network rates. The engine sends little out (a few KB per answer), so this is a fraction of a cent a month (M8).
- **Cloudflare Worker `health`:** https://health.lauscher-worker.workers.dev, version 639a4530 (2026-10-19, with the retry). All three secrets are set: `ENGINE_URL` by `rebuild_secrets.py worker-engine-url`, `ACCESS_KEY` and `ENGINE_KEY` by the owner. Checked end to end: the access key is accepted, the engine answers through the Worker.
- **Cloudflare answers Python's default User-Agent (`Python-urllib/3.x`) with a 403 challenge page** before the Worker runs. Any script that calls the Worker sends its own User-Agent (`scripts/rebuild_p0_measure.py`).
- **This PC's Python refuses the workers.dev certificate** ("certificate has expired"): the Windows store leads OpenSSL through ISRG Root X2's cross-signature of Let's Encrypt's Root YE, which expired 2025-09-15. Windows itself and Safari accept it. Scripts use certifi's roots.

- **pnpm's minimum release age is kept on.** On the first install pnpm added `minimumReleaseAgeExclude` entries for three packages released days earlier (wrangler 4.148.0, @cloudflare/vitest-plugin 1.3.7, a miniflare alpha). They were removed and the Worker pinned to Lauscher's proven versions instead: a bad release is usually caught in its first days. `pnpm install` now reports that the lockfile passes the supply-chain policies with no exception.
- **The engine runs with PYTHONPATH=<root>:<root>/api** (Dockerfile). `uvicorn --app-dir api` alone would put only api/ on the path, and `services` would not import.

## Phase 2 (2026-10-19)
- **Engine revision `health-engine-00007-fs7`** from commit 5c05933, deployed with `gcloud run deploy health-engine --source . --region europe-west1 --update-env-vars HEALTH_BUILD_COMMIT=<sha>,HEALTH_BUILD_TIME=<utc>`: every other setting of the service unchanged (min 0 / max 1, 1 vCPU, 1 GiB, the two pinned secrets, Europe/Berlin). Start: imports 5.6 s, config 0.09 s, the copy rebuilt from Supabase in 3.45 s. Upload list: 116 files, no personal file.
- **Image store:** six images on 2026-10-19 (115-120 MB each, sharing layers), 455.5 MB in all after revision 7, measured with `gcloud artifacts repositories list`; the free amount is 0.5 GiB-month. The clean-up keeps the two newest once the rest are a day old (about 190 MB). Check the size before the next deploy.
- **New settings, both optional:** `HEALTH_CACHE_MAX_AGE_MINUTES` (default 15: a local copy older than this is pulled again; `services/cache_freshness.py`) and `HEALTH_PROCESS` (each process names itself: "streamlit" in repo.py, "engine" in the API; `services/background_writer.py`).
- **The store's config rows the engine reads:** `background_writer` (absent = "streamlit"), `engine_sync_status` (the engine's last sync run), `oura_login_state` (a login in progress), `strength_reference` (the Strength screen's personal reference; written by `scripts/upload_strength_reference.py --apply`).
- **FastAPI wraps an included router** (`_IncludedRouter`), so `app.routes` lists five entries; read the contract (`create_app(...).openapi()["paths"]`) to see the routes.

## Phase 3 (2026-10-19 and 20)
- **No new package.** Atkinson Hyperlegible Next (`@fontsource-variable/atkinson-hyperlegible-next` 5.3.0, Lauscher's) was added for direction C and removed with it.
- **The preview**: `pnpm exec wrangler versions upload --preview-alias design` (in worker/) uploads a Worker VERSION with the app's files; it answers at `https://design-health.<account subdomain>.workers.dev`, and the production version is untouched (`wrangler versions deploy` would change that).
- **Report pictures**: Microsoft Edge (already on the PC) headless — `msedge --headless=new --screenshot=<file> --window-size=… --force-device-scale-factor=2 --virtual-time-budget=4000 <url>`. Two traps: a headless window is never narrower than about 485 px, so the app goes in an exact 390 × 844 iframe and the picture is cropped; and the launcher returns before the browser writes the file, so the script waits for it. The app's `&still` address switch turns motion off for the pictures.
- **Node 24 runs `app/scripts/make-mock.ts` directly** (type stripping); the script uses no TypeScript-only syntax. `--check` compares instead of writing (the p3 gate's real_data_in_app).
- **Contrast** is a test, not a promise: `app/src/design/tokens.test.ts` checks every family's strongest shade at 4.5:1 and its middle shade at 3:1 on the page and on a card, in both modes.


## Phase 4 (2026-10-20)
- **App packages, Lauscher's versions** (publish dates checked on npm 2026-10-20: the newest is vite-plugin-pwa 2.0.0 of 2026-10-03; all at least two weeks old except @types/node): dexie 4.4.6, dexie-react-hooks 4.4.0, wouter 3.13.0, eruda 3.4.3 (MIT; loaded only after seven taps and kept out of the precache), workbox-core / workbox-precaching / workbox-routing 7.4.1; dev: vite-plugin-pwa 2.0.0 (injectManifest), @vite-pwa/assets-generator 2.0.0, fake-indexeddb 6.2.5, @playwright/test 1.63.0 (its Chromium and WebKit builds were already on the PC from Lauscher), and **@types/node 24.19.2** (published 2026-10-09, 11 days old: under the two weeks, kept because a type file runs no code; Node 24.14 runs here) — new: Lauscher's config files type-check only because another package pulls Node's types into its store; here they are named, and the config files have their own `tsconfig.node.json`, so the app's own code never sees Node's types.
- **Icons and splash screens** come from one file, `app/public/logo.svg`, through `pnpm --filter @health/app icons` (`app/pwa-assets.config.ts`: the 2023 preset, the night colour #07090E, iPhone 17 Pro Max splash screens light and dark). `app/scripts/make_icons.py` (Phase 0) is gone.
- **The precache holds the shell only** (5 files, 383 KiB: index.html, the CSS, the JS, the manifest, the logo); iOS fetches the icons and splash screens itself, and Eruda (491 KB) is fetched only when the console opens.
- **Routes are #hashes** (wouter 3's `useHashLocation`): every page load is "/", which the service worker answers from the precache. The screenshot switches `?t=` and `&still` stay in the query.
- **Browser tests**: `pnpm --filter @health/app exec playwright test` builds the app in mock mode (`dev/mockApi.ts`, key "dev"; the test hook `window.__health` exists only in that build) into `reports/rebuild/e2e-dist` and serves it on port 4175; results go to `reports/rebuild/e2e-results` (both ignored by git). Chromium runs everything; the iPhone 17 Pro Max WebKit profile skips @offline, @install, @outbox and @update (Playwright 1.63's WebKit cannot answer from a service worker offline, Lauscher's finding).
- **Cloudflare free plan, checked 2026-10-20** on developers.cloudflare.com/workers/platform/limits (updated 2026-10-12): 5 Cron Triggers per account, 10 ms CPU per Cron Trigger run, 50 subrequests per invocation, 15 min wall time for a scheduled run. KV (developers.cloudflare.com/kv/platform/limits, updated 2026-10-08): 100,000 reads and 1,000 writes to different keys a day, 1 write per second to one key, 1 GB.
- **KV namespace `health-state`** (id in worker/wrangler.jsonc; not a secret): the last data check under `data_check:last`. One write a day plus one per "Check now".
- **One Cron Trigger, `15 4 * * *`** (04:15 UTC): the daily data check. Lauscher's trigger is the account's other one (2 of 5).
- **Engine revision `health-engine-00008-gk6`** from commit 5a9b5eb (GET /api/data/check), deployed the Phase 2 way. Upload list: 117 files, none personal.
- **Image store before that deploy: 455.5 MiB** (six images of 2026-10-19; the clean-up had not run yet, the oldest was 22 hours old). One more image adds about 70 MiB, about 525 MiB for a day against the free 0.5 GiB-month; billed as an average over the month (the store started on 2026-10-19), that stays inside the free amount. The clean-up keeps the two newest and deletes the rest once a day old.
- **Worker version `be3cb6b4`** (2026-10-20): the Phase 4 app, the data check routes and trigger, SYNC_ENABLED "false". Checked live without the key: the app files answer 200, /api answers 401 JSON without the key, 403 from another origin; the service worker controls the page and precaches the shell.

## Phase 5 (2026-10-20)
- **No new package.** The screens use what Phase 4 installed.
- **The chart approach: hand-drawn SVG, no chart library** (`app/src/ui/charts.tsx`). The engine already computes everything a chart needs — the rounded value axis (`dashboard.value_axis`), the tick labels as fractions, and one tap band per slot with the reading under it (`dashboard.hit_bands`, merged above 48) — so the phone draws one path and lays buttons over the plot. Evidence for the choice: a library would recompute the scale and the ticks and could disagree with the Streamlit charts the owner compares against (uPlot is about 50 KB, Recharts over 100 KB minified, each a second source of axes); the Phase 3 design already draws its rings and area chart as SVG; the precache stays at 420 KiB (5 files). A tap is a button, never a link (Key Rule 17's spirit): no page load, and the reading shows below the chart.
- **Engine revision `health-engine-00009-wwr`** from commit 5c00178: GET /api/today/week and `picked_on` on the four day endpoints. **Worker version `f249a9d9`** with the Phase 5 screens.
- **Parity, 2026-10-20 09:30 (owner's day)**: `scripts/rebuild_parity.py` over the 14 days to 2026-10-20 — 0 differences, 0 sleep-rule violations, 0 unanswered requests.

## Phase 6 (2026-10-20)
- **No new package.** The session uses Dexie, the outbox and the Phase 4 shell; the timers run on timestamps (`lib/timers.ts`), the bells on Web Audio (`lib/sounds.ts`).
- **Screen Wake Lock in a Home Screen app**: broken in standalone mode on iOS 16.4 to 18.4 (WebKit bug 254545, https://webkit.org/b/254545; MDN's compatibility table names the same range), working from 18.4 (https://progressier.com/pwa-capabilities/screen-wake-lock, checked 2026-10-20; not confirmed against Apple's notes). The owner's iPhone is on iOS 26: the real session confirms it (`owner_checks.json` p6 `screen_on`). `lib/wakelock.ts` asks again each time the app comes back to the front, and a refusal only clears the "Screen stays on" note.
- **Bells with the silent switch on**: `navigator.audioSession.type = 'playback'` (Safari 17+; https://bugs.webkit.org/show_bug.cgi?id=264473, https://developer.mozilla.org/docs/Web/API/AudioSession/type, checked 2026-10-20). The default type, ambient, is muted by the switch. **"playback" pauses other audio on the phone**: if the owner plays music while training, the first bell can stop it. **The owner's choice, 2026-10-20: *"Yes always play the bells over everything"*: "playback" stays** (the other choice, "ambient", mixes with music but is silent with the switch on).
- **A timer that ends while the app is hidden** cannot ring or notify by itself on iOS: the page runs no code in the background. **The owner chose Web Push timer alerts (2026-10-20: *"Yes id like a push alert"*), built the same day:** as the app goes to the background with a countdown running, the phone asks the Worker for an alert at its end (a keepalive PUT /api/push/alert); coming back cancels it. One **Durable Object** (`TimerAlerts`, SQLite-backed, binding ALERTS, migration v1) keeps the subscription and one alert, and its alarm sends it on the second. Free plan: SQLite-backed Durable Objects only, 100,000 requests and 13,000 GB-s a day, 5 GB stored; past a limit an operation fails and nothing is billed (https://developers.cloudflare.com/durable-objects/platform/pricing/, updated 2026-10-18; alarms: https://developers.cloudflare.com/durable-objects/api/alarms/, updated 2026-04-21: one alarm per object, at-least-once with retries). A session uses a few dozen requests.
- **Web Push library: `@block65/webcrypto-web-push` 2.0.0** (npm, published 2026-09-03; the version Lauscher pins): RFC 8291 aes128gcm and RFC 8292 VAPID on WebCrypto, so it runs in the Worker. Sent with urgency high, a 300 s time to live (a late timer alert is of no use), no Topic header (Apple refuses it), never retried, as a declarative message iOS shows by itself (iOS 18.4+, Lauscher's format).
- **The VAPID key pair** was made by `worker/scripts/vapid-keygen.mjs` (2026-10-20): the private key went straight into the Worker secret `VAPID_PRIVATE_KEY` on wrangler's standard input and exists nowhere else; the public key is in `worker/wrangler.jsonc` (public by design). Run the script again to change the pair; the phone subscribes again at its next start.
- **iOS Web Push needs the app opened from the Home Screen and a tap** to ask for permission (iOS 16.4+): Settings > Timer alerts. iOS has no pushsubscriptionchange event, so every app start sends the subscription again.
- **Worker version `deed0fd2`** (2026-10-20): the alert routes and the Durable Object. Checked live: the key route answers 200 with the configured key, a cancel 204, a malformed alert 400. The flow shows, at the next open, when the timer ended, and moves on only on a tap (inventory T87, the owner's decision).
