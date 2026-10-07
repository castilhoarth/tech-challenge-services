# Quickstart: Validate Observability Setup

## Prerequisites

- Docker and Docker Compose are available
- Access to the New Relic backend is configured through environment secrets
- The Python services being instrumented are built from the repository container definitions

## Required environment variables

Set the New Relic license key in the shell environment before starting Compose. Do not commit the key to the repository:

```bash
export NEW_RELIC_LICENSE_KEY="<license-key>"
export DEPLOYMENT_ENVIRONMENT="development"
# Optional: override the endpoint for another New Relic region.
# export NEW_RELIC_OTLP_ENDPOINT="https://otlp.eu01.nr-data.net:4318"
```

Docker Compose configures the OTLP HTTP/protobuf protocol, per-service identities, traces, metrics, logs, and the required `api-key` header from these environment values.

## Validation steps

1. Build the affected Python service images:
   ```bash
   docker compose --env-file services/.env -f services/docker-compose.yml build analytics-service flag-service targeting-service
   ```
2. Start the services with the configured environment:
   ```bash
   docker compose --env-file services/.env -f services/docker-compose.yml up -d
   ```
3. Check the health endpoint for each Python service:
   ```bash
   curl http://localhost:8002/health
   curl http://localhost:8003/health
   curl http://localhost:8005/health
   ```
4. Verify that a trace, metric, and log event is exported to New Relic for analytics, flag, and targeting.
5. Confirm in New Relic that all three services appear with distinct service identities and the configured environment metadata.

## Expected outcome

- Each service starts without code changes to trace creation.
- Traces, metrics, and logs are visible in New Relic under the matching service identity.
- Docker environment configuration is sufficient to keep observability consistent across service restarts.
