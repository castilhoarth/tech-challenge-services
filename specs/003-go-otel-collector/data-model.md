# Data Model: Go OpenTelemetry and New Relic Collector

This feature adds no business persistence schema. The following telemetry entities describe runtime data and validation requirements.

## Service Telemetry Resource

Represents one instrumented application process.

| Field | Type | Required | Validation |
|---|---|---:|---|
| `service.name` | string | Yes | One of `auth-service`, `flag-service`, `targeting-service`, `evaluation-service`, `analytics-service`; must remain distinct. |
| `deployment.environment` | string | Yes | Non-empty environment supplied at runtime (for example, `development`). |
| `service.version` | string | Recommended | Build/release identifier where available; must not contain credentials. |

Each signal emitted by the same service should carry consistent identity attributes.

## Span

Represents an observed operation in a service request or dependency call.

| Field | Type | Required | Validation |
|---|---|---:|---|
| Trace ID | 16-byte identifier | Yes | Non-zero; stable across a propagated synchronous request. |
| Span ID | 8-byte identifier | Yes | Non-zero and unique within trace. |
| Parent span ID | 8-byte identifier or absent | Conditional | Present only when valid remote/local context is propagated. |
| Name and kind | string / enum | Yes | Operation name does not expose secret headers, credentials, or sensitive request data. |
| Status and timing | status / timestamps | Yes | Reflect operation result and duration; request behavior is unchanged. |
| Resource attributes | key/value set | Yes | Includes the correct service identity and deployment environment. |

## Collector Pipeline

Represents the configured receive-process-export route for a telemetry signal.

| Field | Type | Required | Validation |
|---|---|---:|---|
| Signal | traces, metrics, or logs | Yes | Only a configured and validated pipeline may be described as supported. |
| Receiver | OTLP transport configuration | Yes | Listens only on intended Compose network interfaces and ports. |
| Processors | ordered processor list | Yes | Includes memory protection, resource handling where needed, and batching. |
| Exporter | New Relic OTLP/HTTP configuration | Yes | Uses regional endpoint and runtime-only `api-key`. |
| Health state | ready / unhealthy | Yes | Collector readiness and export errors are observable without exposing secrets. |

## Dependency Edge

Represents a service relationship demonstrated by telemetry rather than inferred from deployment configuration.

| Field | Type | Required | Validation |
|---|---|---:|---|
| Source service | service name | Yes | Must be one of the five named services. |
| Destination | service/dependency name | Yes | Must be observed from a span or correlated trace. |
| Protocol/path | string | Yes | Corresponds to the actual HTTP/database/cache/message operation. |
| Correlation | linked trace context or uncorrelated observation | Yes | Parent/child relationship is claimed only when propagated and observed. |
| Evidence | test request and New Relic observation | Yes | Required before documentation calls the edge verified. |

## Runtime Credential

The New Relic license key is an external secret provided to the Collector at runtime. It is not a telemetry attribute, persisted application field, or configuration literal. It must not be logged, displayed in rendered Compose output, included in image layers, or committed.
