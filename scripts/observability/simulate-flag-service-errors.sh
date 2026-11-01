#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Send authenticated simulated HTTP 500 requests to flag-service every five seconds.

Usage:
  FLAG_SERVICE_API_KEY=... ERROR_SIMULATION_DURATION_SECONDS=60 \
    scripts/observability/simulate-flag-service-errors.sh

Environment:
  FLAG_SERVICE_API_KEY                  Existing flag-service API key (required)
  ERROR_SIMULATION_DURATION_SECONDS     Run duration in seconds (required)
  FLAG_SERVICE_SIMULATOR_URL            Simulator endpoint
                                        (default: http://localhost:8002/__test__/error)
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

api_key="${FLAG_SERVICE_API_KEY:-}"
duration="${ERROR_SIMULATION_DURATION_SECONDS:-}"
simulator_url="${FLAG_SERVICE_SIMULATOR_URL:-http://localhost:8002/__test__/error}"

if [[ -z "$api_key" ]]; then
  printf 'FLAG_SERVICE_API_KEY must be set.\n' >&2
  exit 1
fi

if [[ ! "$duration" =~ ^[1-9][0-9]*$ ]]; then
  printf 'ERROR_SIMULATION_DURATION_SECONDS must be a positive integer.\n' >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  printf 'Required command not found: curl\n' >&2
  exit 1
fi

request_count=0
deadline=$((SECONDS + duration))

report_interrupted() {
  trap - INT TERM
  printf '\nSimulation interrupted after %s expected HTTP 500 response(s).\n' \
    "$request_count" >&2
  exit 130
}

trap report_interrupted INT TERM

printf 'Simulating flag-service errors for %s second(s).\n' "$duration"

while (( SECONDS < deadline )); do
  remaining=$((deadline - SECONDS))
  if (( remaining <= 0 )); then
    break
  fi

  if ! status_code="$(
    curl --silent --show-error \
      --output /dev/null \
      --write-out '%{http_code}' \
      --max-time "$remaining" \
      --request POST \
      --header "Authorization: ${api_key}" \
      "$simulator_url"
  )"; then
    printf 'Simulator request failed after %s expected HTTP 500 response(s).\n' \
      "$request_count" >&2
    exit 1
  fi

  if [[ "$status_code" != "500" ]]; then
    printf 'Expected HTTP 500 but received HTTP %s; stopping after %s expected response(s).\n' \
      "$status_code" "$request_count" >&2
    exit 1
  fi

  request_count=$((request_count + 1))
  printf '[%s] HTTP 500 (expected)\n' "$request_count"

  remaining=$((deadline - SECONDS))
  if (( remaining > 0 )); then
    sleep_seconds=5
    if (( remaining < sleep_seconds )); then
      sleep_seconds=$remaining
    fi
    sleep "$sleep_seconds"
  fi
done

printf 'Simulation finished: %s expected HTTP 500 response(s) in %s second(s).\n' \
  "$request_count" "$duration"
