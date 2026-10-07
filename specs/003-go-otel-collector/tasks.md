---

description: "Implementation tasks for Go OpenTelemetry and New Relic Collector"

---

# Tasks: Go OpenTelemetry and New Relic Collector

**Input**: Design documents from `specs/003-go-otel-collector/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/telemetry-runtime-contract.md`, `quickstart.md`

**Tests**: No test-first workflow was requested. Validation tasks are included because the specification requires regression, configuration, and runtime verification.

**Organization**: Tasks are grouped by the three user stories and ordered by their prerequisites.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with other tasks in the phase because the files and prerequisites do not overlap.
- **[Story]**: User story served by the task (`US1`, `US2`, or `US3`).
- Each task includes the exact file or directory paths to change or validate.

## Phase 1: Setup

**Purpose**: Establish Collector configuration paths and confirm both Go modules can use a consistent Go 1.21-compatible OTel dependency family.

- [X] T001 Create `services/otel-collector/config.yaml` using only Collector Contrib `0.162.0` components confirmed in `specs/003-go-otel-collector/research.md`; define OTLP/HTTP receiver and New Relic-only pipelines for traces, metrics, and logs.
- [X] T002 [P] Add a pinned `otel/opentelemetry-collector-contrib:0.162.0` service and read-only config mount to `services/docker-compose.yml`, keeping the New Relic key available only to the Collector service at runtime.
- [X] T003 [P] Confirm OpenTelemetry Go SDK, HTTP middleware, database, Redis, and logging bridge versions build with Go 1.21; update only `services/auth-service-main/go.mod`, `services/auth-service-main/go.sum`, `services/evaluation-service-main/go.mod`, and `services/evaluation-service-main/go.sum`.

## Phase 2: Foundational

**Purpose**: Complete the shared OTLP ingress/export contract and credential-safe runtime wiring before story-specific application telemetry changes.

- [X] T004 Configure `services/otel-collector/config.yaml` with the runtime New Relic regional endpoint and `api-key` header, OTLP/HTTP protobuf export, memory limiter, batch processing, resource metadata handling, and health-check extension; do not place credential values in the file.
- [X] T005 Update `services/docker-compose.yml` to route all application OTLP traffic to `otel-collector:4318`, pass `NEW_RELIC_LICENSE_KEY` only to the Collector, and set shared `DEPLOYMENT_ENVIRONMENT` metadata without changing application behavior.
- [X] T006 Validate `services/otel-collector/config.yaml` with the pinned Collector image using dummy runtime values and validate merged `services/docker-compose.yml` with `docker compose config --quiet`; do not print resolved Compose configuration or secrets.

**Checkpoint**: The Collector configuration and Compose network path are validated; application-specific instrumentation can now send telemetry to the shared endpoint.

## Phase 3: User Story 1 - See Go service requests in New Relic (Priority: P1)

**Goal**: Instrument auth and evaluation with distinct service resources and preserve existing HTTP behavior while emitting traces and supported metrics.

**Independent Test**: Run both Go test suites, start the two Go services with the Collector, call `/health` and `/evaluate`, and confirm New Relic receives correctly named server spans without API behavior changes.

### Implementation

- [X] T007 [P] [US1] Add `services/auth-service-main/otel.go` to initialize the Go 1.21-compatible OTLP/HTTP trace and metric providers, `service.name=auth-service`, deployment environment metadata, W3C Trace Context propagation, and bounded graceful shutdown.
- [X] T008 [P] [US1] Add `services/evaluation-service-main/otel.go` to initialize the same compatible providers with `service.name=evaluation-service`, deployment environment metadata, W3C Trace Context propagation, and bounded graceful shutdown.
- [X] T009 [US1] Wrap auth routes in `services/auth-service-main/main.go` with `otelhttp` server instrumentation and instrument the existing pgx-backed `database/sql` connection in `services/auth-service-main/main.go` without capturing SQL parameter values.
- [X] T010 [US1] Wrap evaluation routes in `services/evaluation-service-main/main.go` with `otelhttp` server instrumentation and wrap the existing `http.Client` transport with `otelhttp` so outbound requests carry W3C trace context.
- [X] T011 [US1] Attach the go-redis v8 tracing hook compatible with the existing `github.com/go-redis/redis/v8 v8.11.5` client in `services/evaluation-service-main/main.go`; do not change the Redis client major version.
- [X] T012 [US1] Add runtime telemetry configuration to `services/auth-service-main/Dockerfile`, `services/evaluation-service-main/Dockerfile`, and `services/docker-compose.yml` so both Go processes export OTLP/HTTP to the Collector and receive no New Relic credential.
- [X] T013 [US1] Run `go test ./...` in `services/auth-service-main/` and `services/evaluation-service-main/`, plus exercise existing auth/evaluation routes to confirm status codes, response bodies, and evaluation decisions remain unchanged.

**Checkpoint**: Both Go services emit distinct request telemetry and their current tests and API behavior remain intact.

## Phase 4: User Story 2 - Centralize telemetry from all five services (Priority: P1)

**Goal**: Preserve existing Python instrumentation, route its supported signals through the Collector, and ensure application logs have a real OTLP path.

**Independent Test**: Start the Python services with the Collector, generate requests and worker activity, and verify each Python service's supported traces, metrics, and logs arrive in New Relic under a distinct service identity.

### Implementation

- [X] T014 [P] [US2] Update `services/flag-service-main/Dockerfile` and `services/targeting-service-main/Dockerfile` to send existing auto-instrumented OTLP signals to `http://otel-collector:4318`, retain `flag-service`/`targeting-service` identities, and attach deployment environment metadata.
- [X] T015 [P] [US2] Update `services/analytics-service-main/Dockerfile` to send existing Flask/Botocore OTLP signals to `http://otel-collector:4318`, retain `analytics-service` identity, and attach deployment environment metadata.
- [X] T016 [US2] Ensure Python logging actually emits OTLP log records from `services/flag-service-main/requirements.txt`, `services/targeting-service-main/requirements.txt`, `services/analytics-service-main/requirements.txt`, and each corresponding Docker runtime configuration; retain console logs and avoid duplicate instrumentation/export.
- [X] T017 [US2] Bridge Go standard logger records into the OTel log provider in `services/auth-service-main/otel.go` and `services/evaluation-service-main/otel.go` using the selected Go 1.21-compatible `slog` bridge, preserving stderr diagnostics and existing log messages.
- [X] T018 [US2] Verify all five services use distinct `service.name` values and consistent deployment environment metadata for supported signals through `services/docker-compose.yml`, both Go `otel.go` files, and the three Python Dockerfiles.
- [X] T019 [US2] Run existing Python suites with `pytest -q` in `services/flag-service-main/`, `services/targeting-service-main/`, and `services/analytics-service-main/`; confirm the instrumentation endpoint change does not alter application behavior.

**Checkpoint**: All five applications send supported telemetry to the Collector, and logs are described as collected only after they are observed arriving.

## Phase 5: User Story 3 - Follow real service and message dependencies (Priority: P2)

**Goal**: Demonstrate cross-service trace context through supported synchronous calls and explicitly validate the SQS producer/consumer boundary.

**Independent Test**: Generate cache-miss evaluation requests and downstream auth validation traffic, inspect their traces and service-map edges in New Relic, and separately test SQS behavior without assuming correlation.

### Implementation

- [X] T020 [US3] Ensure evaluation request contexts reach the concurrent flag and targeting calls in `services/evaluation-service-main/evaluator.go` while preserving cancellation and existing error behavior; instrument operation spans only where HTTP client middleware does not already produce dependency spans.
- [X] T021 [US3] Confirm Python Flask server and requests client instrumentation propagates W3C context for flag/targeting calls to auth; change only the relevant instrumentation dependency/configuration in `services/flag-service-main/requirements.txt`, `services/targeting-service-main/requirements.txt`, and their Dockerfiles if verification finds a missing supported instrumentor.
- [X] T022 [US3] Evaluate SQS trace-context propagation for AWS SDK Go v1 in `services/evaluation-service-main/sqs.go` and Botocore in `services/analytics-service-main/app.py`; add message context injection/extraction only if it preserves the event schema/business behavior and is supported by both paths, otherwise document the precise limitation.
- [X] T023 [US3] When a real runtime New Relic key is available, exercise evaluation→flag, evaluation→targeting, flag→auth, targeting→auth, auth→PostgreSQL, and evaluation→Redis using `specs/003-go-otel-collector/quickstart.md`; otherwise record these edges as unverified, and never claim SQS linkage without a received trace demonstrating it.

**Checkpoint**: The synchronous service-map edges and any SQS relationship are reported from observed traffic, not inferred from code or Compose.

## Phase 6: Polish & Cross-Cutting Validation

**Purpose**: Verify configuration, runtime credential handling, signals, regressions, and operator guidance.

- [X] T024 Update `specs/003-go-otel-collector/quickstart.md` with the implemented startup, shutdown, traffic-generation, Collector validation, and New Relic verification commands; distinguish config validation from actual ingestion.
- [X] T025 Audit `services/docker-compose.yml`, `services/otel-collector/config.yaml`, both Go service trees, and all three Python service trees to confirm no New Relic key is committed, baked into images, passed to app services, or written to logs.
- [X] T026 Run the full commands in `specs/003-go-otel-collector/quickstart.md`, validate the pinned Collector config and merged Compose safely, and document exact Go/Python test outcomes plus each New Relic signal and service edge verified; leave real-credential ingestion unverified if no runtime credential is available.

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001 establishes the Collector config target. T002 and T003 can proceed independently once the repository layout is confirmed.
- **Foundational (Phase 2)**: T004 depends on T001; T005 depends on T002 and T004; T006 depends on T004 and T005.
- **US1 (Phase 3)**: Go SDK setup T007/T008 depends on T003 and T006. Route/dependency instrumentation tasks depend on their corresponding SDK setup. T013 follows all US1 code changes.
- **US2 (Phase 4)**: Python destination tasks depend on T006; Go log bridging depends on T007/T008. Python tests follow Python configuration changes.
- **US3 (Phase 5)**: Trace-path work depends on Go and Python HTTP instrumentation (US1 and US2). SQS investigation can proceed independently after telemetry bootstrap exists; New Relic relationship verification follows traffic generation.
- **Polish (Phase 6)**: Depends on implementation tasks and runtime validation availability.

### User Story Dependencies

- **US1 (P1)**: Starts after the Collector and dependency foundations; delivers Go request tracing and supported database/cache visibility.
- **US2 (P1)**: Shares the Collector foundation with US1 but can configure Python destinations independently; final all-five signal check requires both stories.
- **US3 (P2)**: Depends on HTTP client/server instrumentation from US1 and US2; SQS correlation is conditional and may remain an explicitly documented limitation.

### Parallel Opportunities

- T002 and T003 are independent setup work after repository inspection.
- T007 and T008 modify different Go service modules and can proceed in parallel.
- T014 and T015 modify separate Python Dockerfiles and can proceed in parallel.
- T020 and T021 affect separate Go/Python HTTP propagation paths after their respective instrumentors exist.
- T022 can investigate the SQS boundaries separately, but changes to `sqs.go` or `app.py` must be coordinated with other edits to those same files.

## Parallel Example: Go Bootstrap and Python Export Routing

```text
Task T007: Add auth-service OTel bootstrap in services/auth-service-main/otel.go
Task T008: Add evaluation-service OTel bootstrap in services/evaluation-service-main/otel.go

After Collector validation:
Task T014: Redirect flag and targeting OTLP destinations
Task T015: Redirect analytics OTLP destination
```

## Implementation Strategy

### MVP First (User Story 1)

1. Pin and validate the Collector; wire runtime-only New Relic credentials.
2. Instrument Go HTTP server/client paths and supported PostgreSQL/Redis operations.
3. Run Go tests and verify API behavior remains unchanged.
4. Generate representative Go traffic and confirm distinct Go service identities in New Relic.

### Incremental Delivery

1. Deliver Go request telemetry first.
2. Redirect Python telemetry to the Collector and verify trace, metric, and log signals per service.
3. Validate synchronous service-map edges with traffic.
4. Test SQS context propagation only if supported by the exact SDK paths; otherwise document the boundary.
5. Complete secret audit, full regression checks, and operator documentation.

## Notes

- Every task is a strict checkbox with sequential ID, applicable story label, and exact repository paths.
- Existing database and DynamoDB volumes must be preserved; do not use `docker compose down -v`.
- Do not add Prometheus or Loki for this release; New Relic is the only telemetry backend in scope.
- Do not mark a signal, edge, or service map as verified based only on configuration or Compose startup.
