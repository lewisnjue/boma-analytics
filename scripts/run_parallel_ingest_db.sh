#!/usr/bin/env bash
set -euo pipefail

# Run both ingestion jobs in parallel and save results to MongoDB.
# Usage:
#   ./scripts/run_parallel_ingest_db.sh --buyrent-listing-type apartments --buyrent-max-pages 2 --prop24-max-pages 2

python -m boma_analytics.db_ingest "$@"
