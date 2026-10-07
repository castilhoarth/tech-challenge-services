# Telemetry Runtime Contract

This contract describes the internal OTLP interface between the five application services and the OpenTelemetry Collector, and the Collector's external New Relic export.

## Application-to-Collector

- **Protocol**: OTLP over HTTP with protobuf encoding.
- **Compose endpoint**: `http://otel-collector:4318`.
- **Signal paths**: `/v1/traces`, `/v1/metrics`, and `/v1/logs`.
- **Service identity**: Each process supplies a distinct `service.name`; all include the configured deployment environment resource attribute.
- **Trace propagation**: W3C Trace Context (`traceparent`, `tracestate` when present) across supported inbound/outbound HTTP paths.
- **Authentication**: None on the private Compose network; the New Relic license key is never sent to application containers.
- **Failure behavior**: SDK exporters retry/batch according to supported SDK behavior and surface diagnostics; telemetry export must not change endpoint or business results.

## Collector-to-New Relic

- **Protocol**: OTLP/HTTP protobuf over TLS.
- **Endpoint**: Runtime-configurable New Relic regional OTLP endpoint, defaulting to `https://otlp.nr-data.net`; the exporter config supplies signal paths as required by its endpoint semantics.
- **Authentication**: `api-key` header resolved from the Collector's `NEW_RELIC_LICENSE_KEY` runtime environment.
- **Signals**: traces, metrics, and logs only when received and supported by the upstream service instrumentation.
- **Security**: The key must not be passed to application containers, baked into images, included in source-controlled files, emitted to logs, or shown by Compose inspection.

## Service/Dependency Trace Contract

- Supported synchronous HTTP requests preserve W3C trace context between instrumented client and server.
- Service and dependency spans identify the emitting service and safe operation metadata.
- SQS message parent-child correlation is outside the guaranteed contract until the actual Go AWS SDK v1 producer and Python Botocore consumer path has been exercised and verified in New Relic.
- No service-map dependency is guaranteed merely because a Compose dependency or URL exists; representative traffic and received telemetry are required.
