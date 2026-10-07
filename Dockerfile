# The health engine for Google Cloud Run (rebuild Phase 0; docs/rebuild/).
# Built by Cloud Build from `gcloud run deploy --source .`; .gcloudignore is an
# allow-list, so only the files this image needs ever leave the PC.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app:/app/api \
    HEALTH_DATASTORE_MODE=cache \
    HEALTH_DATASTORE_PATH=/tmp/health/datastore.db \
    HEALTH_SECRETS_FILE=/secrets/health/secrets.toml

# The OS time zone database: without it TZ silently falls back to UTC, and
# the services/ code that still reads date.today() would get the UTC day.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements-engine.txt .
RUN pip install -r requirements-engine.txt

# The engine: services/ and the root modules its import chain needs
# (training_plan, training_constants, the Cluster A trio, flexibility_baselines).
COPY services/ services/
COPY training_plan.py training_constants.py cluster_a_battery.py \
     cluster_a_mechanics.py cluster_a_prescription.py flexibility_baselines.py ./
COPY api/ api/

# A non-root user that owns /app: services/clients/local_cache.py writes
# .sync_state.json next to services/, and the cache lives under /tmp/health.
RUN useradd --create-home --uid 10001 engine \
    && mkdir -p /tmp/health \
    && chown -R engine:engine /app /tmp/health
USER engine

# Cloud Run sets PORT (8080 by default).
CMD ["sh", "-c", "exec uvicorn healthapi.main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --no-server-header"]
