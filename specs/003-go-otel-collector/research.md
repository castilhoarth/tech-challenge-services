# Research: Go OpenTelemetry and New Relic Collector

**Date**: 2026-10-07

## Decisions

### Central Collector and release

- **Decision**: Use the standard OpenTelemetry Collector Contrib image pinned to `otel/opentelemetry-collector-contrib:0.162.0`.
- **Rationale**: It provides the standard Collector pipeline model and includes the OTLP receiver, OTLP/HTTP exporter, memory limiter and batch processors, and health-check extension required by the design. The official Contrib manifest at tag `v0.162.0` lists `otlphttpexporter`, `memorylimiterprocessor`, `batchprocessor`, and `healthcheckextension`; core OTLP receiver and resource processor are part of the Collector distribution.
- **Alternatives considered**: Core Collector image would be smaller, but Contrib's explicit component inventory simplifies operational health checks and future extension. `latest` is rejected to keep the deployment reproducible.
- **Sources**:
  - https://github.com/open-telemetry/opentelemetry-collector-releases/blob/v0.162.0/distributions/otelcol-contrib/manifest.yaml
  - https://opentelemetry.io/docs/collector/configuration/
  - https://opentelemetry.io/docs/collector/architecture/

### New Relic export

- **Decision**: Use the Collector OTLP/HTTP exporter with protobuf encoding, regional New Relic endpoint, and an `api-key` header supplied by runtime environment substitution.
- **Rationale**: New Relic recommends OTLP/HTTP protobuf and documents `api-key` as the required header. The credential belongs in the Collector runtime environment, not application containers or committed config.
- **Alternatives considered**: Direct app-to-New Relic exporters are rejected because the requested architecture makes the Collector central. Prometheus and Loki are deferred per the user's current scope.
- **Sources**:
  - https://docs.newrelic.com/docs/opentelemetry/best-practices/opentelemetry-otlp/
  - https://opentelemetry.io/docs/collector/configuration/

### Go application instrumentation

- **Decision**: Use OpenTelemetry Go API/SDK `v1.28.0`, `otelhttp v0.53.0`, and OTLP/HTTP trace and metric exporters from the `v1.28.0` release family. Establish global W3C Trace Context propagation and distinct `service.name` resources.
- **Rationale**: The services use standard `net/http`; official OpenTelemetry Go guidance documents SDK initialization, resource service naming, propagation, and handler/client instrumentation. The inspected `otelhttp v0.53.0` module declares Go 1.21 and requires OTel `v1.28.0`, matching the current container toolchain.
- **Alternatives considered**: OBI/eBPF was removed at the user's request; direct-to-New-Relic Go exporters bypass the required Collector.
- **Sources**:
  - https://opentelemetry.io/docs/languages/go/instrumentation/
  - https://pkg.go.dev/go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp
  - https://proxy.golang.org/go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp/@v/v0.53.0.mod
  - https://proxy.golang.org/go.opentelemetry.io/otel/sdk/@v/v1.28.0.mod

### Go database, Redis, and SQS paths

- **Decision**: Instrument auth PostgreSQL through the existing `database/sql` pgx driver using `github.com/XSAM/otelsql v0.32.0`, whose module metadata aligns with OpenTelemetry Go `v1.28.0` and Go 1.21; add the go-redis v8 tracing hook from the matching `github.com/go-redis/redis/extra/redisotel/v8 v8.11.5` package. Keep SQS trace correlation unclaimed until both producer and consumer instrumentation and a real trace prove linkage.
- **Rationale**: Auth uses pgx v4 through `database/sql`, while evaluation uses `github.com/go-redis/redis/v8` and AWS SDK Go v1. The documented Redis v8 hook matches the current major version. SQL instrumentation must wrap the existing `database/sql` driver without changing the pgx major version. No assumption is made about SQS correlation.
- **Alternatives considered**: Adding unsupported client middleware or replacing major dependency versions is rejected. If no compatible instrumentation exists, use narrowly scoped manual spans around operations where safe and document the limitation; do not force a client migration solely for telemetry.
- **Sources**:
  - https://opentelemetry.io/docs/languages/go/instrumentation/
  - https://pkg.go.dev/github.com/go-redis/redis/extra/redisotel/v8
  - https://opentelemetry.io/docs/languages/python/instrumentation/

### Application log export

- **Decision**: Preserve Python log instrumentation and route its OTLP logs to the Collector. For Go, use `otelslog v0.3.0` with OpenTelemetry Go `v1.28.0`, log API/SDK `v0.4.0`, and OTLP/HTTP log exporter `v0.4.0`; their module manifests declare Go 1.21. Bridge standard Go log calls through `log/slog` while preserving console diagnostics.
- **Rationale**: Python currently configures the logging instrumentation package and OTLP logs exporter. Go services use the standard `log` package, which does not become OTLP logs merely by enabling a Collector logs pipeline. The official OTel Go documentation warns the logs signal remains experimental; the Go 1.21-compatible module family and explicit runtime validation keep that risk visible.
- **Alternatives considered**: Docker log scraping is platform-dependent in Docker Desktop and risks collecting unrelated container/host logs; environment variables alone do not bridge standard Go logs. If the compatible Go bridge cannot be verified, the implementation must report the blocker rather than claiming Go logs are exported.
- **Sources**:
  - https://opentelemetry.io/docs/languages/go/getting-started/
  - https://pkg.go.dev/go.opentelemetry.io/contrib/bridges/otelslog
  - https://proxy.golang.org/go.opentelemetry.io/contrib/bridges/otelslog/@v/v0.3.0.mod
  - https://proxy.golang.org/go.opentelemetry.io/otel/sdk/log/@v/v0.4.0.mod
  - https://proxy.golang.org/go.opentelemetry.io/otel/exporters/otlp/otlplog/otlploghttp/@v/v0.4.0.mod
  - https://opentelemetry.io/docs/languages/python/exporters/

### Python instrumentation

- **Decision**: Keep the existing Python OpenTelemetry dependencies and `opentelemetry-instrument` entrypoints for flag, targeting, and analytics; set the OTLP endpoint to the Collector service and preserve distinct service names/environment attributes.
- **Rationale**: Existing instrumentation covers Flask and, depending on the service, requests/psycopg2 or Botocore. Python OTel docs recommend OTLP export to a Collector. Logs must be verified as OTLP records after enabling the logging bridge.
- **Alternatives considered**: Adding another instrumentation layer or leaving direct New Relic export would cause duplicate or bypassed paths and is rejected.
- **Sources**:
  - https://opentelemetry.io/docs/languages/python/exporters/
  - https://opentelemetry.io/docs/zero-code/python/configuration/

### Scope and success verification

- **Decision**: New Relic is the only telemetry backend in this iteration; Prometheus and Loki are deferred. Validate config and syntax separately from live signal delivery.
- **Rationale**: User explicitly clarified “For now just New Relic.” Service-map edges require actual representative traffic and context propagation. SQS uses Go AWS SDK v1 on producer and Python Botocore on consumer, so trace linkage cannot be presumed.
- **Alternatives considered**: Adding Prometheus/Loki now contradicts the clarified scope. Treating Compose config success as proof of exported telemetry is rejected.

## Validation Decisions

- Database instrumentation must use `database/sql` integration and must not capture SQL parameter values; instrument low-cardinality operation metadata and errors only.
- Redis instrumentation must use the v8 hook matching the existing `github.com/go-redis/redis/v8 v8.11.5` dependency; do not migrate the client major version for observability.
- All OpenTelemetry Go modules must use one compatible API/SDK release family, and both Docker builds must remain on Go 1.21.
- Go logs must continue to appear on stderr while a separate OTel log record is exported. If safe dual-output cannot be preserved, do not claim Go log export.
- The pinned Collector image's `validate` command, New Relic endpoint/environment interpolation, Compose merge, actual signal receipt, and service edges are runtime validation gates. Component presence in a manifest is not proof that the finished configuration works.
