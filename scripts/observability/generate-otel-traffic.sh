#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Generate evaluation requests with unique W3C trace IDs.

Usage:
  scripts/observability/generate-otel-traffic.sh

Environment:
  EVALUATION_URL             Evaluation endpoint (default: http://localhost:8004/evaluate)
  FLAG_NAME                  Existing feature flag (default: enable-new-dashboard)
  TRAFFIC_COUNT              Number of requests (default: 10)
  REQUEST_INTERVAL_SECONDS   Delay between requests (default: 1)
  USER_ID_PREFIX             Prefix for generated user IDs (default: otel-traffic)
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

evaluation_url="${EVALUATION_URL:-http://localhost:8004/evaluate}"
flag_name="${FLAG_NAME:-enable-new-dashboard}"
traffic_count="${TRAFFIC_COUNT:-10}"
request_interval="${REQUEST_INTERVAL_SECONDS:-1}"
user_id_prefix="${USER_ID_PREFIX:-otel-traffic}"

for command_name in curl openssl; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    printf 'Required command not found: %s\n' "$command_name" >&2
    exit 1
  fi
done

if [[ ! "$traffic_count" =~ ^[1-9][0-9]*$ ]]; then
  printf 'TRAFFIC_COUNT must be a positive integer.\n' >&2
  exit 1
fi

if [[ ! "$request_interval" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  printf 'REQUEST_INTERVAL_SECONDS must be a non-negative number.\n' >&2
  exit 1
fi

if [[ -z "$flag_name" || -z "$user_id_prefix" ]]; then
  printf 'FLAG_NAME and USER_ID_PREFIX must not be empty.\n' >&2
  exit 1
fi

if ! curl --silent --show-error --fail --max-time 5 \
  http://localhost:8004/health >/dev/null; then
  printf 'evaluation-service is not healthy at http://localhost:8004/health. Start the stack first.\n' >&2
  exit 1
fi

printf 'Sending %s evaluation request(s) for flag "%s" to %s\n' \
  "$traffic_count" "$flag_name" "$evaluation_url"

for ((index = 1; index <= traffic_count; index++)); do
  trace_id="$(openssl rand -hex 16)"
  parent_span_id="$(openssl rand -hex 8)"
  user_id="${user_id_prefix}-${index}"
  status_code="$(
    curl --silent --show-error \
      --output /dev/null \
      --write-out '%{http_code}' \
      --max-time 15 \
      --get \
      --data-urlencode "user_id=$user_id" \
      --data-urlencode "flag_name=$flag_name" \
      --header "traceparent: 00-${trace_id}-${parent_span_id}-01" \
      "$evaluation_url"
  )"

  case "$status_code" in
    2??)
      printf '[%s/%s] HTTP %s user_id=%s trace_id=%s\n' \
        "$index" "$traffic_count" "$status_code" "$user_id" "$trace_id"
      ;;
    *)
      printf '[%s/%s] Evaluation failed with HTTP %s; response body suppressed.\n' \
        "$index" "$traffic_count" "$status_code" >&2
      exit 1
      ;;
  esac

  if (( index < traffic_count )) && [[ "$request_interval" != "0" && "$request_interval" != "0.0" ]]; then
    sleep "$request_interval"
  fi
done

printf 'Finished. Search New Relic for the trace IDs printed above.\n'
printf 'Note: evaluation caches flag data by flag name; downstream flag/targeting/auth calls may not occur on every request.\n'
