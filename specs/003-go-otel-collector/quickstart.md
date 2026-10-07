# Quickstart: Validate Go OpenTelemetry and Collector Export

This guide becomes the end-to-end acceptance procedure after implementation. A syntax/configuration check is not evidence that New Relic received telemetry.

For the copy-ready local startup and shutdown procedure, see
[`services/otel-collector/RUNBOOK.md`](../../services/otel-collector/RUNBOOK.md).

## Prerequisites

- Docker Engine or Docker Desktop with Compose.
- Go 1.21-compatible toolchain for both Go service modules.
- Python environment or service images with the existing test dependencies.
- New Relic account and regional OTLP endpoint.
- Runtime-only New Relic license key; do not put the key in `.env`, source, Docker build args, or application containers.
- Existing application environment variables configured in `services/.env` without adding the New Relic key there.

## Configure runtime settings

From the repository root:

```sh
read -r -s -p 'New Relic license key: ' NEW_RELIC_LICENSE_KEY
printf '\n'
export NEW_RELIC_LICENSE_KEY
export NEW_RELIC_OTLP_ENDPOINT='https://otlp.nr-data.net'
export DEPLOYMENT_ENVIRONMENT='development'
```

Use the regional endpoint for the account. Only the Collector should receive `NEW_RELIC_LICENSE_KEY`.

## Run automated checks

```sh
(cd services/auth-service-main && go test ./...)
(cd services/evaluation-service-main && go test ./...)
(cd services/flag-service-main && ENVIRONMENT=test pytest -q)
(cd services/targeting-service-main && ENVIRONMENT=test pytest -q)
(cd services/analytics-service-main && ENVIRONMENT=test pytest -q)
```

The Python test suites require `ENVIRONMENT=test` so importing the applications does not initialize production database or AWS clients.

Validate Collector configuration with its pinned image and a non-secret test value; do not print environment-resolved config:

```sh
docker run --rm \
  --entrypoint /otelcol-contrib \
  -v "$PWD/services/otel-collector/config.yaml:/etc/otelcol-contrib/config.yaml:ro" \
  -e NEW_RELIC_LICENSE_KEY=validation-only \
  -e NEW_RELIC_OTLP_ENDPOINT=https://otlp.nr-data.net \
  otel/opentelemetry-collector-contrib:0.162.0 \
  validate --config=/etc/otelcol-contrib/config.yaml
```

Validate Compose syntax without printing its resolved configuration:

```sh
NEW_RELIC_LICENSE_KEY=validation-only \
NEW_RELIC_OTLP_ENDPOINT=https://otlp.nr-data.net \
DEPLOYMENT_ENVIRONMENT=validation \
docker compose --env-file services/.env -f services/docker-compose.yml config --quiet
```

## Start services and generate traffic

```sh
docker compose --env-file services/.env -f services/docker-compose.yml up --build -d
```

Check readiness and generate HTTP activity:

```sh
curl -fsS http://localhost:8001/health
curl -fsS http://localhost:8002/health
curl -fsS http://localhost:8003/health
curl -fsS http://localhost:8004/health
curl -fsS http://localhost:8005/health
curl -fsS http://localhost:13133/
curl -i 'http://localhost:8004/evaluate?user_id=otel-smoke&flag_name=<existing-flag>'
```

Replace `<existing-flag>` with an existing flag. Repeated evaluation requests exercise both Redis cache hits and misses; on a miss, evaluation makes concurrent calls to flag and targeting. Those services validate the supplied service API key through auth. If the AWS SQS URL is configured, evaluation asynchronously publishes an event and analytics consumes it.

Inspect logs without printing environment variables or rendered Compose configuration:

```sh
docker compose --env-file services/.env -f services/docker-compose.yml ps
docker compose --env-file services/.env -f services/docker-compose.yml logs --tail=100 otel-collector
```

## Verify in New Relic

- Confirm distinct telemetry identities for `auth-service`, `flag-service`, `targeting-service`, `evaluation-service`, and `analytics-service`.
- Inspect traces rooted at `evaluation-service`; confirm connected edges only for the synchronous HTTP paths actually observed (evaluation→flag, evaluation→targeting, flag→auth, targeting→auth).
- Inspect auth PostgreSQL and evaluation Redis spans/metrics only if the compatible instrumentations are enabled and the data appears in New Relic.
- Verify trace, metric, and log signals separately. Python log environment flags alone do not prove log export; Go logs require the configured OTel log bridge.
- Confirm the configured deployment environment appears consistently.
- Treat SQS producer/consumer linkage as unverified unless one trace demonstrates context crossing Go AWS SDK v1 send, SQS transport, Python Botocore receive, and analytics processing.
- The current implementation does not inject or extract trace context in SQS message attributes; the producer/consumer edge remains unverified and is not represented as a connected trace.
- Record missing services, dropped signals, exporter/auth errors, and unsupported edges as gaps. Do not use Collector startup or Compose success as proof of ingestion.

## Stop without deleting state

```sh
docker compose --env-file services/.env -f services/docker-compose.yml down
```

Do not use `down -v`; existing database/DynamoDB data volumes must be preserved.

## Verification status

Validated during implementation:

- The Collector configuration passed `otel/opentelemetry-collector-contrib:0.162.0 validate` with a dummy runtime key and the default US endpoint.
- Merged Compose syntax passed `docker compose config --quiet` with a dummy runtime key; resolved configuration was not printed.
- Both Go modules passed `go test ./...` in Go 1.21 containers.
- Python test suites passed in Python 3.11 containers with `ENVIRONMENT=test`: flag-service 23 tests, targeting-service 21 tests, analytics-service 18 tests.
- Compose built all five instrumented application images successfully.

Not verified end-to-end:

- No runtime New Relic credential was available in the implementation environment, so the full stack was not started and New Relic receipt, trace/log/metric ingestion, and service-map edges remain unverified.
- SQS context is not injected or extracted; evaluation-to-analytics trace correlation remains unverified.

Configuration and build validation do not prove telemetry was received by New Relic. Do not record a signal or service edge as verified without checking actual runtime telemetry.
