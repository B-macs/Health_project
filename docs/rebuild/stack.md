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
| Google Cloud CLI | not installed | the owner installs it (`winget install --id Google.CloudSDK -e`) |
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
| httpx (dev) | 0.28.1 | >=3.8 | https://pypi.org/project/httpx/ (FastAPI's TestClient) |

## npm packages (checked with `npm view` 2026-10-07)

| Package | Version | Used in | Notes |
|---|---|---|---|
| hono | 4.13.13 | worker | `bearerAuth` compares with SHA-256 + constant-time equality (checked in Lauscher's node_modules) |
| wrangler | 4.148.0 | worker | Lauscher pins 4.147.0 |
| @cloudflare/vitest-plugin | 1.3.7 | worker | peer: vitest ^4.1.0, so the Worker stays on vitest 4.1 (Lauscher's finding) |
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
- **One secret holds the whole secrets.toml** (`health-engine-secrets`, mounted as a file), and one holds the engine key (`health-engine-key`, an environment variable). Two active versions, inside the free six.
- **The Worker's ENGINE_URL is a secret, not a `vars` entry,** so the engine's address is not in this public repo.
- **The account's workers.dev subdomain is `lauscher-worker`.** The Worker named `health` is `health.lauscher-worker.workers.dev`. Changing the subdomain would also change Lauscher's address.
- **Region:** europe-west1 (Belgium) is planned as a Tier 1 European region. Checked again at the deploy (M4) and recorded in p0_proof.json.
