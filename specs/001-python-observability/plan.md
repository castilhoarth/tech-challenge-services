# Implementation Plan: Python Observability

**Branch**: `001-python-observability` | **Date**: 2026-10-07 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-python-observability/spec.md`

## Summary

Add no-code observability to the Python microservices by using OpenTelemetry auto-instrumentation and routing all telemetry to New Relic. The implementation standardizes runtime configuration across the monorepo and updates the affected Dockerfiles so each Python service can emit traces, logs, and metrics without custom application instrumentation.

## Technical Context

**Language/Version**: Python 3.11 (confirmed by the existing Python service Dockerfiles: `python:3.11-slim` in `services/**/Dockerfile`)

**Primary Dependencies**: Flask, gunicorn, OpenTelemetry Python SDK/auto-instrumentation, New Relic OTLP-compatible exporter, dotenv, boto3

**Storage**: N/A for runtime telemetry; backend is New Relic for centralized observability data

**Testing**: pytest for service-level validation; smoke tests via Docker health checks and request validation in runtime environment

**Target Platform**: Linux containerized microservices executed via Docker and Docker Compose

**Project Type**: monorepo web-service / Python microservices

**Performance Goals**: retain low latency overhead, capture 95%+ of critical request telemetry, and preserve service health checks without requiring custom app instrumentation

**Constraints**: no application code changes for core tracing logic; must keep credentials outside source control; container startup must load observability config from environment variables

**Scale/Scope**: all three Python services in the monorepo: `services/analytics-service-main`, `services/flag-service-main`, and `services/targeting-service-main`; Go services are out of scope

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- The repository does not currently define a project-specific constitution beyond the default template. No blocking policies or hard constraints were found in `.specify/memory/constitution.md`.
- The plan remains within the repository scope and does not introduce a separate subsystem or unsupported architecture.
- The feature is constrained to the Python microservices and Docker runtime layer, which matches the existing monorepo structure.
- Result: pass, with no unjustified constitution violations.

## Project Structure

### Documentation (this feature)

```text
specs/001-python-observability/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── observability-runtime-contract.md
├── checklists/
│   └── requirements.md
└── spec.md              # Feature specification
```

### Source Code (repository root)

```text
services/
├── analytics-service-main/
│   ├── app.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── test_app.py
├── flag-service-main/
│   ├── app.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── test_app.py
├── targeting-service-main/
│   ├── app.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── test_app.py
├── auth-service-main/
│   ├── Dockerfile
├── evaluation-service-main/
│   ├── Dockerfile
└── docker-compose.yml
```

**Structure Decision**: Use the existing monorepo service layout and apply a shared observability runtime contract to the analytics, flag, and targeting Python services, which each have Dockerfiles and runtime startup paths. No new application framework is introduced; only the runtime and container configuration are extended.

## Complexity Tracking

> No constitution violations require special justification for this feature.
