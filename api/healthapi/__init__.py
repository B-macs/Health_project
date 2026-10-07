"""The engine's HTTP layer for the phone app (the rebuild in docs/rebuild/).

FastAPI over the unchanged services/. This package holds NO training, readiness
or safety rule of its own: each route asks services/ and returns the answer
(CLAUDE.md, rebuild rule 1). Runs on Google Cloud Run behind the Cloudflare
Worker, which adds the shared X-Engine-Key header.
"""

__version__ = "0.1.0"
