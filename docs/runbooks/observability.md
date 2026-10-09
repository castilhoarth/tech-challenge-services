# OpenTelemetry and New Relic Runbook

This runbook starts the local microservices stack with the pinned OpenTelemetry
Collector and sends supported telemetry to New Relic. It assumes commands are
run from the repository root.

## Prerequisites

- Docker Engine or Docker Desktop with Docker Compose.
- A New Relic account and license key.
- Application configuration in `services/.env`. Do not add the New Relic key
  to that file.
- A flag already present in the application data for the evaluation request.

## Set the runtime New Relic settings

Read the key without echoing it, then export it only into the current terminal
session. The Collector is the only service configured to receive this key.

```sh
printf 'New Relic license key: '
read -r -s NEW_RELIC_LICENSE_KEY
printf '\n'
export NEW_RELIC_LICENSE_KEY
export NEW_RELIC_OTLP_ENDPOINT='https://otlp.nr-data.net'
export DEPLOYMENT_ENVIRONMENT='development'
```

The endpoint above is the US endpoint. For an EU account, use
`https://otlp.eu01.nr-data.net`. Do not paste the key into shell commands,
Compose files, application configuration, or Docker build arguments.

## Validate configuration (optional)

Validate the Collector configuration using a dummy key. This does not send
telemetry to New Relic.

```sh
docker run --rm \
  --entrypoint /otelcol-contrib \
  -v "$PWD/deploy/observability/otel-collector/config.yaml:/etc/otelcol-contrib/config.yaml:ro" \
  -e NEW_RELIC_LICENSE_KEY=validation-only \
  -e NEW_RELIC_OTLP_ENDPOINT=https://otlp.nr-data.net \
  otel/opentelemetry-collector-contrib:0.162.0 \
  validate --config=/etc/otelcol-contrib/config.yaml
```

Check merged Compose syntax without displaying the resolved configuration:

```sh
NEW_RELIC_LICENSE_KEY=validation-only \
NEW_RELIC_OTLP_ENDPOINT=https://otlp.nr-data.net \
DEPLOYMENT_ENVIRONMENT=validation \
docker compose --env-file services/.env -f deploy/local/docker-compose.yml config --quiet
```

## Start the stack

Build and start all services:

```sh
docker compose --env-file services/.env -f deploy/local/docker-compose.yml up --build -d
```

Check container status and Collector health:

```sh
docker compose --env-file services/.env -f deploy/local/docker-compose.yml ps
curl -fsS http://localhost:13133/
```

Check the HTTP service health endpoints:

```sh
curl -fsS http://localhost:8001/health
curl -fsS http://localhost:8002/health
curl -fsS http://localhost:8003/health
curl -fsS http://localhost:8004/health
curl -fsS http://localhost:8005/health
```

## Generate representative traffic

Replace `existing-flag` with a flag that exists in the configured application
data:

```sh
curl -i 'http://localhost:8004/evaluate?user_id=otel-smoke&flag_name=existing-flag'
```

Repeat the request to generate additional traffic. On an evaluation cache
miss, `evaluation-service` calls `flag-service` and `targeting-service`;
those services validate API keys through `auth-service`. If SQS is configured
and usable, evaluation events may also be processed by `analytics-service`.

To generate multiple requests with unique trace IDs, run:

```sh
scripts/observability/generate-otel-traffic.sh
```

By default it sends 10 requests for `enable-new-dashboard`, waiting one second
between requests. Ensure that flag exists in your local data. Override the
behavior with environment variables:

```sh
FLAG_NAME='your-existing-flag' \
TRAFFIC_COUNT=25 \
REQUEST_INTERVAL_SECONDS=0.5 \
scripts/observability/generate-otel-traffic.sh
```

The script prints each W3C trace ID so you can search for the exact request in
New Relic. It does not require a New Relic query API key and does not confirm
ingestion by itself.

In New Relic's query interface, search for one of the printed IDs:

```sql
SELECT count(*) FROM Span
WHERE trace.id = 'paste-printed-trace-id-here'
SINCE 30 minutes ago
```

To see the services observed in that trace:

```sql
SELECT uniques(service.name) FROM Span
WHERE trace.id = 'paste-printed-trace-id-here'
SINCE 30 minutes ago
```

If the trace appears, New Relic received it. Evaluation caches flag data by
flag name, so later requests may not include flag/targeting/auth spans; wait
for the cache TTL or use another existing flag to exercise those edges.

## Inspect runtime status

Use Compose status and Collector logs to diagnose startup or export issues.
Avoid printing environment variables or resolved Compose configuration.

```sh
docker compose --env-file services/.env -f deploy/local/docker-compose.yml ps
docker compose --env-file services/.env -f deploy/local/docker-compose.yml logs --tail=100 otel-collector
```

## Verify telemetry in New Relic

Check for these distinct service identities:

- `auth-service`
- `flag-service`
- `targeting-service`
- `evaluation-service`
- `analytics-service`

Inspect traces, metrics, and logs separately, and confirm the
`deployment.environment` attribute. With representative evaluation traffic,
look for the observed synchronous edges: evaluation to flag and targeting,
then flag and targeting to auth. Database and Redis spans should be checked
only if they appear in the received telemetry.

Collector readiness and valid configuration do not establish that New Relic
received telemetry. This setup does not inject or extract trace context across
SQS messages, so an evaluation-to-analytics trace relationship is not
configured or verified. Record any signal or service edge as verified only
after observing it in New Relic.

## Stop the stack

Stop services without deleting persistent data:

```sh
docker compose --env-file services/.env -f deploy/local/docker-compose.yml down
```

Do not use `docker compose down -v`; the existing database and DynamoDB data
volumes must be preserved.

When finished, remove the key from the current shell:

```sh
unset NEW_RELIC_LICENSE_KEY
```
