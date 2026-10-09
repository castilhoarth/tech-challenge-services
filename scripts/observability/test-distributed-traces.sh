#!/usr/bin/env bash

set -euo pipefail
umask 077

usage() {
  cat <<'EOF'
Generate an evaluation request and verify that New Relic reports a distributed trace.

Usage:
  scripts/observability/test-distributed-traces.sh

Required:
  NEW_RELIC_ACCOUNT_ID       New Relic account ID
  NEW_RELIC_USER_API_KEY     New Relic user/query API key (not the ingest license key)

Environment:
  EVALUATION_URL             Evaluation endpoint (default: http://localhost:8004/evaluate)
  EVALUATION_HEALTH_URL      Health endpoint (default: http://localhost:8004/health)
  FLAG_NAME                  Existing feature flag (default: enable-new-dashboard)
  USER_ID                    Evaluation user ID (default: generated unique ID)
  MIN_SERVICE_COUNT          Minimum distinct services in the trace (default: 2)
  TRACE_WAIT_SECONDS         How long to wait for New Relic (default: 120)
  TRACE_POLL_INTERVAL_SECONDS Poll interval (default: 5)
  NEW_RELIC_GRAPHQL_URL      NerdGraph endpoint (default: https://api.newrelic.com/graphql)
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

for command_name in curl jq openssl; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    printf 'Required command not found: %s\n' "$command_name" >&2
    exit 1
  fi
done

account_id="${NEW_RELIC_ACCOUNT_ID:-}"
if [[ ! "$account_id" =~ ^[0-9]+$ ]]; then
  printf 'Set NEW_RELIC_ACCOUNT_ID to your numeric New Relic account ID.\n' >&2
  exit 1
fi

user_api_key="${NEW_RELIC_USER_API_KEY:-}"
if [[ -z "$user_api_key" ]]; then
  printf 'New Relic user/query API key (not the ingest license key): '
  read -r -s user_api_key
  printf '\n'
fi
if [[ -z "$user_api_key" ]]; then
  printf 'New Relic user/query API key must not be empty.\n' >&2
  exit 1
fi

evaluation_url="${EVALUATION_URL:-http://localhost:8004/evaluate}"
health_url="${EVALUATION_HEALTH_URL:-http://localhost:8004/health}"
flag_name="${FLAG_NAME:-enable-new-dashboard}"
user_id="${USER_ID:-otel-trace-$(date +%s)-$(openssl rand -hex 4)}"
min_service_count="${MIN_SERVICE_COUNT:-2}"
wait_seconds="${TRACE_WAIT_SECONDS:-120}"
poll_interval="${TRACE_POLL_INTERVAL_SECONDS:-5}"
graphql_url="${NEW_RELIC_GRAPHQL_URL:-https://api.newrelic.com/graphql}"

for value_name in MIN_SERVICE_COUNT TRACE_WAIT_SECONDS TRACE_POLL_INTERVAL_SECONDS; do
  case "$value_name" in
    MIN_SERVICE_COUNT) value="$min_service_count" ;;
    TRACE_WAIT_SECONDS) value="$wait_seconds" ;;
    TRACE_POLL_INTERVAL_SECONDS) value="$poll_interval" ;;
  esac
  if [[ ! "$value" =~ ^[0-9]+$ ]]; then
    printf '%s must be a non-negative integer.\n' "$value_name" >&2
    exit 1
  fi
done

if (( min_service_count < 2 || wait_seconds < 1 || poll_interval < 1 )); then
  printf 'MIN_SERVICE_COUNT must be at least 2; wait and poll intervals must be positive.\n' >&2
  exit 1
fi

headers_file="$(mktemp)"
response_file="$(mktemp)"
trap 'rm -f "$headers_file" "$response_file"' EXIT
printf 'API-Key: %s\n' "$user_api_key" >"$headers_file"
unset user_api_key

if ! curl --silent --show-error --fail --max-time 5 "$health_url" >/dev/null; then
  printf 'evaluation-service is not healthy at %s. Start the stack first.\n' "$health_url" >&2
  exit 1
fi

trace_id="$(openssl rand -hex 16)"
parent_span_id="$(openssl rand -hex 8)"
if [[ "$trace_id" == "00000000000000000000000000000000" ||
  "$parent_span_id" == "0000000000000000" ]]; then
  printf 'Failed to generate a valid W3C trace context. Run the script again.\n' >&2
  exit 1
fi

printf 'Sending one evaluation request for flag "%s" (user_id=%s)\n' "$flag_name" "$user_id"

status_code="$(
  curl --silent --show-error \
    --output "$response_file" \
    --write-out '%{http_code}' \
    --max-time 20 \
    --get \
    --data-urlencode "user_id=$user_id" \
    --data-urlencode "flag_name=$flag_name" \
    --header "traceparent: 00-${trace_id}-${parent_span_id}-01" \
    "$evaluation_url"
)"

case "$status_code" in
  2??)
    printf 'Evaluation returned HTTP %s; trace_id=%s\n' "$status_code" "$trace_id"
    ;;
  *)
    printf 'Evaluation failed with HTTP %s; response:\n' "$status_code" >&2
    cat "$response_file" >&2
    printf '\nCheck that FLAG_NAME exists and SERVICE_API_KEY is valid in the running services.\n' >&2
    exit 1
    ;;
esac

nrql="SELECT uniques(service.name) AS serviceNames FROM Span WHERE trace.id = '${trace_id}' SINCE 30 minutes ago"
graphql_query="{ actor { account(id: ${account_id}) { nrql(query: $(jq -Rn --arg value "$nrql" '$value')) { results } } } }"
graphql_payload="$(jq -cn --arg query "$graphql_query" '{query: $query}')"
deadline=$(( $(date +%s) + wait_seconds ))

printf 'Waiting up to %s seconds for a distributed trace in New Relic...\n' "$wait_seconds"

while :; do
  query_status="$(
    curl --silent --show-error \
      --output "$response_file" \
      --write-out '%{http_code}' \
      --max-time 15 \
      --header "@${headers_file}" \
      --header 'Content-Type: application/json' \
      --data-binary "$graphql_payload" \
      "$graphql_url"
  )"

  if [[ "$query_status" != "200" ]]; then
    printf 'New Relic NerdGraph returned HTTP %s. Response:\n' "$query_status" >&2
    cat "$response_file" >&2
    printf '\nCheck the account ID, user/query API key, and NerdGraph endpoint.\n' >&2
    exit 1
  fi

  if jq -e '.errors != null' "$response_file" >/dev/null; then
    printf 'New Relic NerdGraph reported an error:\n' >&2
    jq -r '.errors[].message' "$response_file" >&2
    exit 1
  fi

  services_json="$(
    jq -c '
      .data.actor.account.nrql.results[0] as $row
      | ($row.serviceNames // $row.services // [])
      | if type == "array" then . else [] end
    ' "$response_file"
  )"
  service_count="$(jq 'length' <<<"$services_json")"

  if (( service_count >= min_service_count )) &&
    jq -e 'index("evaluation-service") != null' <<<"$services_json" >/dev/null; then
    printf 'Distributed trace verified in New Relic.\n'
    printf 'Trace ID: %s\n' "$trace_id"
    printf 'Services observed (%s): %s\n' "$service_count" "$(jq -r 'join(", ")' <<<"$services_json")"
    exit 0
  fi

  if (( $(date +%s) >= deadline )); then
    printf 'No distributed trace with at least %s services appeared in New Relic before timeout.\n' \
      "$min_service_count" >&2
    printf 'Trace ID: %s\n' "$trace_id" >&2
    printf 'Services observed: %s\n' "$(jq -r 'join(", ")' <<<"$services_json")" >&2
    printf 'Check New Relic ingestion, service credentials, and whether the selected flag caused downstream calls.\n' >&2
    exit 1
  fi

  sleep "$poll_interval"
done
