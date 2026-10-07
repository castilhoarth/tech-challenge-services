# Feature Specification: Go OpenTelemetry and New Relic Collector

**Feature Branch**: `003-go-otel-collector`

**Created**: 2026-10-07

**Status**: Draft

**Input**: User description: "Implement OpenTelemetry instrumentation for this repository’s Go microservices and add a centralized OpenTelemetry Collector that routes telemetry to New Relic. For now just New Relic."

## User Scenarios & Testing

### User Story 1 - See Go service requests in New Relic (Priority: P1)

As an operator, I want the Go authentication and evaluation services to emit request telemetry so I can diagnose their behavior alongside the already instrumented Python services.

**Why this priority**: The Go services currently have no OpenTelemetry instrumentation, leaving important services absent from application traces and New Relic's service map.

**Independent Test**: Start the Go services with the Collector, send requests to their existing HTTP endpoints, and verify that New Relic receives traces with distinct `auth-service` and `evaluation-service` identities without changing endpoint behavior.

**Acceptance Scenarios**:

1. **Given** the Go services and Collector are configured with a runtime New Relic license key, **When** a client calls `/health` on each Go service, **Then** New Relic receives a server span associated with the correct service identity.
2. **Given** the evaluation service calls flag and targeting services while handling an evaluation, **When** the downstream requests carry supported trace context, **Then** the trace shows the connected request path across the participating services.
3. **Given** instrumentation is enabled, **When** existing API requests and tests are run, **Then** route paths, response formats, status behavior, and business outcomes remain unchanged.

### User Story 2 - Centralize telemetry export (Priority: P1)

As an operator, I want all five microservices to send telemetry through one Collector so I can manage New Relic export and credentials centrally.

**Why this priority**: A common collection and export path is a required assignment outcome and avoids maintaining separate direct-to-backend configuration across applications.

**Independent Test**: Configure each application to send supported signals to the Collector, start the stack, generate representative activity in all five services, and verify those signals appear in New Relic under distinct service identities.

**Acceptance Scenarios**:

1. **Given** the Collector is available, **When** any instrumented service emits supported telemetry, **Then** the Collector receives and exports it to the configured New Relic regional endpoint.
2. **Given** the New Relic credential is supplied at runtime, **When** the Collector exports telemetry, **Then** the credential is not embedded in application images, Collector configuration, Compose literals, or committed environment files.
3. **Given** New Relic is unavailable or rejects credentials, **When** export is attempted, **Then** the failure is observable in Collector diagnostics and is not reported as successful delivery.

### User Story 3 - Follow service and message dependencies (Priority: P2)

As an operator, I want distributed traces and a service map to show real dependencies across the five services so I can understand a request as it crosses service boundaries.

**Why this priority**: End-to-end visibility is the assignment's main demonstration goal, but coverage depends on actual traffic, supported propagation, and asynchronous messaging behavior.

**Independent Test**: Generate representative traffic through evaluation, flag, targeting, auth, and analytics; inspect New Relic traces and service-map relationships, recording only edges demonstrated by received telemetry.

**Acceptance Scenarios**:

1. **Given** an evaluation request calls flag and targeting, and those services validate credentials through auth, **When** all participating services propagate W3C trace context, **Then** the resulting trace links the supported synchronous HTTP requests.
2. **Given** evaluation publishes an event to SQS and analytics consumes it, **When** the selected instrumentation demonstrates context propagation for the actual AWS SDK and message path, **Then** New Relic shows the producer/consumer relationship; otherwise, the relationship is explicitly reported as unsupported or unverified.
3. **Given** representative traffic reaches all five services, **When** telemetry is received by New Relic, **Then** the service map can identify each service distinctly and shows only dependencies observed from that traffic.

## Edge Cases

- The Collector is unavailable at application startup or during export; applications retain their existing business behavior while telemetry failures are reported through operational diagnostics.
- The New Relic key is missing, empty, invalid, or rejected; telemetry export fails explicitly and no key value is logged.
- A service receives a request without trace context; it starts a new trace and does not fabricate a parent relationship.
- An outbound library does not propagate trace context or has no supported instrumentation; its edge is not represented as correlated unless demonstrated.
- The evaluation SQS producer and analytics SQS consumer may not support linked trace context for the repository's AWS SDK Go v1 and Python Botocore paths; the service relationship must not be claimed without an end-to-end trace.
- A service has no generated traffic; it may not appear in the service map until it emits telemetry.
- OTLP telemetry arrives with missing or conflicting service/environment metadata; it must not be silently merged into another service identity.
- Metrics or logs are unavailable from an instrumentation library; the implementation reports the gap rather than presenting a configured exporter as proof of collection.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST instrument `auth-service` and `evaluation-service` to emit OpenTelemetry traces and supported metrics while preserving existing application routes, responses, and business behavior.
- **FR-002**: The system MUST preserve instrumentation for `flag-service`, `targeting-service`, and `analytics-service`, and configure all five services to send supported OpenTelemetry signals to a centralized Collector rather than exporting directly to New Relic.
- **FR-003**: The Collector MUST receive traces, metrics, and logs using protocols supported by the participating services and MUST export supported signals to New Relic using the account's regional endpoint.
- **FR-004**: The Collector and application telemetry MUST identify `auth-service`, `flag-service`, `targeting-service`, `evaluation-service`, and `analytics-service` distinctly and associate them with the configured deployment environment.
- **FR-005**: Synchronous HTTP client and server instrumentation MUST propagate W3C trace context on supported paths so New Relic can display connected spans across participating services.
- **FR-006**: The implementation MUST instrument database, cache, and messaging operations only where supported by the actual client libraries and versions in the repository.
- **FR-007**: The implementation MUST NOT claim SQS producer-to-consumer trace correlation unless the actual AWS SDK Go v1 and Python Botocore paths support it and the relationship is verified in received telemetry.
- **FR-008**: The New Relic license key MUST be supplied only at runtime to the Collector, MUST NOT be written into source-controlled configuration or application images, and MUST NOT appear in logs or validation output.
- **FR-009**: The Collector MUST use an explicitly pinned release and only components available in that release; configuration MUST include batching, memory protection, and operational health reporting.
- **FR-010**: Docker Compose MUST provide an opt-in or otherwise clearly wired Collector deployment for local development without removing existing application services, changing their business behavior, or deleting persistent data.
- **FR-011**: For this feature, New Relic is the only configured telemetry backend. Prometheus and Loki export and deployment are outside the current scope; the Collector configuration MUST NOT claim routing to them.
- **FR-012**: The system MUST provide instructions to start and stop the stack, generate representative request and message traffic, and verify received signals, service identities, and observed service dependencies in New Relic.
- **FR-013**: Documentation MUST distinguish configuration validation from end-to-end telemetry verification and identify unverified protocols, dependencies, or signal types.
- **FR-014**: The implementation MUST include a supported mechanism for exporting application logs from all five services to the Collector, or document a specific unsupported path and the minimum change required before claiming those logs are collected.
- **FR-015**: Validation MUST include existing Go and Python tests, Collector configuration validation with the pinned image, safe Compose validation, and traffic-based verification where runtime credentials and a supported environment are available.

### Key Entities

- **Service telemetry identity**: A distinct service name and deployment environment associated with each of the five microservices' emitted signals.
- **Distributed trace**: A set of related spans representing a request across services and supported dependencies, with parent/child relationships derived from propagated context.
- **Collector pipeline**: The centralized ingress, processing, and New Relic export path for supported traces, metrics, and logs.
- **Observed dependency edge**: A service or dependency relationship evidenced by telemetry generated from real traffic; it is not inferred solely from Compose configuration.
- **Runtime credential**: The New Relic license key provided to the Collector at runtime and excluded from source-controlled configuration and application images.

## Success Criteria

### Measurable Outcomes

- **SC-001**: All five services appear as distinct service identities in New Relic after each has emitted representative telemetry.
- **SC-002**: At least 90% of 100 representative evaluation HTTP requests that complete successfully are visible in New Relic with the correct service identity.
- **SC-003**: For supported synchronous HTTP paths exercised by test traffic, traces show the correct cross-service parent/child relationships for at least 95% of 100 sampled requests.
- **SC-004**: Existing Go and Python automated test suites pass without changes to expected application behavior.
- **SC-005**: No New Relic license key value is present in committed files, application image configuration, Collector configuration, or emitted application/Collector logs.
- **SC-006**: The deployment guide enables an operator to start the stack, generate sample traffic, and locate traces for each service without exposing the New Relic credential.
- **SC-007**: Every service edge and signal described as verified in the guide is backed by telemetry observed in New Relic; unsupported or unverified paths are explicitly listed.

## Assumptions

- The five application services are `auth-service` (Go, port 8001), `evaluation-service` (Go, port 8004), `flag-service` (Python, port 8002), `targeting-service` (Python, port 8003), and `analytics-service` (Python, port 8005).
- Go auth uses `net/http` and PostgreSQL through pgx via `database/sql`; Go evaluation uses `net/http`, go-redis v8, and AWS SDK for Go v1 SQS.
- Python flag and targeting use Flask, `requests`, and psycopg2; Python analytics uses Flask and Botocore/Boto3 to interact with SQS and DynamoDB.
- Python services already have OpenTelemetry auto-instrumentation dependencies and export directly to New Relic; implementation will preserve that instrumentation and change its destination to the Collector.
- The current Compose setup has no OpenTelemetry Collector, Prometheus, or Loki service. Only New Relic will be configured as a backend for this feature; Prometheus and Loki may be introduced in a later feature.
- A supported New Relic account and regional OTLP endpoint are available to the operator; actual ingestion cannot be verified without a valid runtime credential and generated traffic.
- SQS producer/consumer correlation and some dependency-level instrumentation may depend on library support and must remain an explicit validation outcome rather than an assumed capability.
