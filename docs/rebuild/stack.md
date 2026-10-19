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

