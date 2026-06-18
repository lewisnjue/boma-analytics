#!/usr/bin/env bash
set -euo pipefail

cd /action

cmd=("./scripts/run_parallel_ingest_db.sh")

if [[ -n "${INPUT_CONFIG_PATH:-}" ]]; then
  cmd+=("--config" "${INPUT_CONFIG_PATH}")
fi

if [[ -n "${INPUT_OUTPUT_DIR:-}" ]]; then
  cmd+=("--output-dir" "${INPUT_OUTPUT_DIR}")
fi

if [[ -n "${INPUT_BUYRENT_MAX_PAGES:-}" ]]; then
  cmd+=("--buyrent-max-pages" "${INPUT_BUYRENT_MAX_PAGES}")
fi

if [[ "${INPUT_BUYRENT_NO_DETAILS:-false}" == "true" ]]; then
  cmd+=("--buyrent-no-details")
fi

if [[ -n "${INPUT_BUYRENT_LISTING_TYPE:-}" ]]; then
  cmd+=("--buyrent-listing-type" "${INPUT_BUYRENT_LISTING_TYPE}")
fi

if [[ -n "${INPUT_PROP24_MAX_PAGES:-}" ]]; then
  cmd+=("--prop24-max-pages" "${INPUT_PROP24_MAX_PAGES}")
fi

if [[ "${INPUT_PROP24_NO_DETAILS:-false}" == "true" ]]; then
  cmd+=("--prop24-no-details")
fi

if [[ "${INPUT_VERBOSE:-false}" == "true" ]]; then
  cmd+=("-v")
fi

exec "${cmd[@]}"
