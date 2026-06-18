#!/usr/bin/env bash
set -euo pipefail

# Simple wrapper to run the parallel ingestion runner.
# Usage examples:
#  ./scripts/run_parallel_ingest.sh --buyrent-listing-type apartments --buyrent-max-pages 2
#  ./scripts/run_parallel_ingest.sh --prop24-max-pages 3 --output-dir data/raw

python -m boma_analytics.parallel_runner "$@"
