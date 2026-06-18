FROM python:3.14-slim

WORKDIR /action

# Install build dependencies and the package.
COPY pyproject.toml pyproject.toml
COPY src/ src/
COPY scripts/ scripts/
COPY config/ config/

RUN python -m pip install --upgrade pip && \
    python -m pip install --no-cache-dir . && \
    chmod +x scripts/run_parallel_ingest_db.sh

COPY .github/actions/run-db-ingest/entrypoint.sh /action/entrypoint.sh
RUN chmod +x /action/entrypoint.sh

ENTRYPOINT ["/action/entrypoint.sh"]
