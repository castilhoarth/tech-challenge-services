# Observability Runtime Contract

## Purpose

Document the runtime contract for analytics, flag, and targeting service telemetry export to New Relic. The contract is intentionally environment-driven so the application code remains largely unchanged while the platform config controls observability behavior.

## Required runtime configuration

### Environment variables

| Name | Required | Description |
| --- | --- | --- |
| `NEW_RELIC_LICENSE_KEY` | Yes | Secret used to authenticate exports to New Relic |
| `OTEL_SERVICE_NAME` | Yes | Service identity reported in telemetry |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | No | Defaults to the New Relic US endpoint `https://otlp.nr-data.net:4318`; override for another New Relic region |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | Yes | Must be `http/protobuf` |
| `OTEL_EXPORTER_OTLP_HEADERS` | Yes | Must contain `api-key=<New Relic license key>`; Docker Compose interpolates the key from the environment |
| `OTEL_TRACES_EXPORTER` | Yes | Must be `otlp` |
| `OTEL_METRICS_EXPORTER` | Yes | Must be `otlp` |
| `OTEL_LOGS_EXPORTER` | Yes | Must be `otlp` |
| `OTEL_RESOURCE_ATTRIBUTES` | No | Includes deployment environment metadata |
| `OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED` | Yes | Enables export of standard Python log records through the OpenTelemetry logs pipeline |

### Docker contract

Each in-scope Python service Dockerfile and its Docker Compose service configuration must:
- install OpenTelemetry Python packages needed for auto-instrumentation
- set the OTLP endpoint, protocol, and enabled signal exporters
- receive the license key through runtime configuration, never a Dockerfile build argument or committed file
- launch the app via an instrumented command path so telemetry begins at process startup
- set a distinct `OTEL_SERVICE_NAME` for analytics, flag, and targeting

## Behavioral expectations

- Telemetry is emitted without application-level custom tracing code
- Service startup logs include the active telemetry configuration
- Requests and dependency calls are captured under the service identity in New Relic
- Runtime errors surface as actionable telemetry in the centralized backend

## Failure handling

If `NEW_RELIC_LICENSE_KEY` is missing, Docker Compose must fail with an explicit configuration error instead of starting containers that appear to be exporting telemetry.
