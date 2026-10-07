# Implementation Plan: Go OpenTelemetry and New Relic Collector

**Branch**: `003-go-otel-collector` | **Date**: 2026-10-07 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/003-go-otel-collector/spec.md`

## Summary

Add SDK instrumentation to the Go auth and evaluation services, route supported traces, metrics, and logs from all five applications through a separately configured OpenTelemetry Collector Contrib service, and export to New Relic only. Keep the existing Python auto-instrumentation, change its OTLP destination to the Collector, and make no claims about SQS trace correlation unless traffic proves it.

The planned Collector image is pinned to `otel/opentelemetry-collector-contrib:0.162.0`. Go instrumentation dependencies must remain compatible with the existing Go 1.21 builder images unless an explicit, justified toolchain change is approved.

## Technical Context

**Language/Version**: Go 1.21; Python 3.11 containers.

**Primary Dependencies**: Go `net/http`, pgx v4 registered through `database/sql`, go-redis v8, AWS SDK Go v1; Python Flask, requests, psycopg2, Botocore/Boto3, existing OpenTelemetry auto-instrumentation dependencies; OpenTelemetry Collector Contrib `0.162.0`.

**Storage**: PostgreSQL, Redis, SQS, DynamoDB Local in Compose; no telemetry-specific persistent storage planned.

**Testing**: Existing Go `go test ./...` in both Go modules; existing pytest suites for Python services; pinned Collector config validation; Compose config validation; traffic-driven New Relic verification when credentials/network are available.

**Target Platform**: Docker Compose local development on macOS Docker Desktop and Linux; New Relic regional OTLP/HTTP endpoint.

**Project Type**: Multi-service backend with two Go services, three Python services, and Docker Compose orchestration.

**Performance Goals**: Preserve API behavior and keep telemetry asynchronous/batched; do not block request handling on New Relic export.

**Constraints**: No credential in committed files, app images, or Collector config; pass the New Relic key only at Collector runtime. No Prometheus/Loki in this release. Keep Go 1.21 compatibility. Preserve current Python instrumentation and existing data volumes. Do not claim unverified SQS correlation or end-to-end delivery.

**Scale/Scope**: Five named services and their observed HTTP, database, cache, and message paths in the existing local Compose stack.

## Current-State Inventory

| Compose service | Language / entrypoint | Port | Relevant dependencies and logging | Current telemetry |
|---|---|---:|---|---|
| `auth-service` | Go 1.21, `main.go`, `net/http` | 8001 | pgx v4 through `database/sql`; standard Go `log` | None |
| `evaluation-service` | Go 1.21, `main.go`, `net/http` | 8004 | go-redis v8; HTTP client calls flag and targeting concurrently; AWS SDK Go v1 SQS; standard Go `log` | None |
| `flag-service` | Python 3.11, Flask app via `opentelemetry-instrument gunicorn` | 8002 | requests, psycopg2; Python `logging` | OpenTelemetry auto-instrumentation; currently direct OTLP to New Relic |
| `targeting-service` | Python 3.11, Flask app via `opentelemetry-instrument gunicorn` | 8003 | requests, psycopg2; Python `logging` | OpenTelemetry auto-instrumentation; currently direct OTLP to New Relic |
| `analytics-service` | Python 3.11, Flask worker via `opentelemetry-instrument gunicorn` | 8005 | Boto3/Botocore SQS and DynamoDB; Python `logging` | OpenTelemetry auto-instrumentation; currently direct OTLP to New Relic |

The Compose stack currently has no Collector service. Auth serves `/health`, `/validate`, and `/admin/keys`; evaluation serves `/health` and `/evaluate`. Evaluation performs Redis reads/writes, calls flag `/flags/{name}` and targeting `/rules/{flag}` over HTTP on cache misses, then asynchronously publishes an evaluation event to SQS. Analytics consumes SQS and stores events in DynamoDB. Flag and targeting call auth to validate API keys. Cross-process HTTP context propagation must be added/confirmed in both Go and Python client/server instrumentation. SQS producer/consumer correlation remains unproven.

## Constitution Check

The current `.specify/memory/constitution.md` contains template placeholders rather than ratified project principles. No enforceable project-specific gates can be derived from it.

| Gate | Status | Basis |
|---|---|---|
| Keep scope minimal and aligned with the assignment | PASS | One Collector and one backend (New Relic); Prometheus and Loki deferred. |
| Preserve existing service behavior | PASS | Instrumentation wraps HTTP and dependency boundaries; API contracts and data behavior remain unchanged. |
| Protect credentials | PASS | Runtime-only Collector secret; no `.env` inspection or credential output. |
| Verify integrations | PASS | Collector/Compose validation, existing suites, then traffic-based verification with honest limits. |
| Maintain supported toolchain | PASS | Dependencies must be checked against existing Go 1.21 images; do not raise the language floor implicitly. |

No known gate violations. SQS context propagation is a validation question, not a success assumption.

## Project Structure

### Documentation (this feature)

```text
specs/003-go-otel-collector/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
    └── telemetry-runtime-contract.md
```

### Source Code and Deployment

```text
services/
├── docker-compose.yml
├── otel-collector/
│   └── config.yaml
├── auth-service-main/
│   ├── main.go
│   ├── go.mod
│   └── go.sum
├── evaluation-service-main/
│   ├── main.go
│   ├── evaluator.go
│   ├── sqs.go
│   ├── go.mod
│   └── go.sum
├── flag-service-main/
│   ├── Dockerfile
│   └── requirements.txt
├── targeting-service-main/
│   ├── Dockerfile
│   └── requirements.txt
└── analytics-service-main/
    ├── Dockerfile
    └── requirements.txt
```

**Structure Decision**: Keep Collector configuration in a new `services/otel-collector/` directory outside all app images. Update the existing Compose file and only the Go initialization/request/client/messaging code and dependency manifests needed for instrumentation. Update Python runtime OTLP environment configuration without adding duplicate instrumentation. Store operational steps and the telemetry contract with the feature spec.

## Design Decisions

- Use OTLP/HTTP protobuf from all applications to the Collector's internal endpoint `http://otel-collector:4318`; expose only the ports needed for local diagnostics, not the credential-bearing upstream endpoint.
- Configure the Collector's OTLP receiver, memory limiter, resource metadata handling as needed, batch processor, health check, and OTLP/HTTP exporter. Use the New Relic regional endpoint and runtime `api-key` header. Components must be validated against the exact pinned Contrib distribution.
- Preserve Python Flask/requests/psycopg2/Botocore instrumentation. Redirect OTLP to the Collector and ensure log records are bridged to OTLP instead of assuming an exporter environment variable alone captures logs.
- Add Go SDK setup with distinct service resources and W3C Trace Context propagation. Wrap incoming `net/http` handlers and outbound HTTP transport. Instrument PostgreSQL through the existing `database/sql`/pgx path and Redis only with instrumentation compatible with the repository's actual go-redis v8 dependency.
- Preserve standard Go logging behavior while adding an OTel log bridge compatible with Go 1.21, or document any incompatibility before implementation. Do not silently claim logs are received when no bridge is active.
- Add Go SQS producer spans only if they preserve existing async behavior. Injecting context into messages and extracting it in Python Botocore must be verified before describing an SQS connected trace.
- Do not add Prometheus or Loki services/exporters now; the user explicitly narrowed the current implementation to New Relic.

## Complexity Tracking

No constitution violations or unnecessary architectural complexity identified.
