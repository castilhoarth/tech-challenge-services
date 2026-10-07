# Tasks: Python Observability

**Input**: Design documents from `/specs/001-python-observability/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the shared observability runtime contract for the Python microservices and confirm the Docker-based deployment model.

- [X] T001 Review the existing Python service runtime and deployment configuration in `services/docker-compose.yml` and the Dockerfiles for `analytics-service-main`, `flag-service-main`, and `targeting-service-main` to confirm the standard environment model for New Relic telemetry
- [X] T002 [P] Document the required New Relic and OpenTelemetry environment variables in `specs/001-python-observability/contracts/observability-runtime-contract.md`, including `NEW_RELIC_LICENSE_KEY`, `OTEL_SERVICE_NAME`, `OTEL_EXPORTER_OTLP_ENDPOINT`, and `OTEL_EXPORTER_OTLP_HEADERS`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Prepare the underlying Python runtime so the services can emit telemetry without custom per-service instrumentation.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 [P] Add the OpenTelemetry Python runtime packages needed for auto-instrumentation to `services/analytics-service-main/requirements.txt` and `services/targeting-service-main/requirements.txt`
- [X] T004 [P] Add the OpenTelemetry Python runtime packages needed for auto-instrumentation to `services/flag-service-main/requirements.txt`
- [X] T005 [P] Update `services/analytics-service-main/Dockerfile` to install the required telemetry dependencies and set the base runtime environment for New Relic export
- [X] T006 [P] Update `services/flag-service-main/Dockerfile` and `services/targeting-service-main/Dockerfile` to install the required telemetry dependencies and set the base runtime environment for New Relic export
- [X] T007 Create the standard startup path for instrumented Python execution in all three Python service Docker runtimes so each app begins under `opentelemetry-instrument` or equivalent environment-driven auto-instrumentation

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel.

---

## Phase 3: User Story 1 - Enable no-code observability for Python services (Priority: P1) 🎯 MVP

**Goal**: Provide a shared no-code telemetry layer for the Python services and route it to New Relic with minimal application code changes.

**Independent Test**: A Python service can be started with the standard container configuration and emit telemetry to New Relic without custom span creation in application code.

### Implementation for User Story 1

- [X] T008 [P] [US1] Add the New Relic and OpenTelemetry environment variables to the analytics, flag, and targeting services in `services/docker-compose.yml` so each has a distinct `OTEL_SERVICE_NAME`, all signals enabled, and the license key header configured
- [X] T009 [P] [US1] Update `services/analytics-service-main/Dockerfile` to launch the service with the OpenTelemetry auto-instrumentation wrapper and the required runtime defaults for New Relic export
- [X] T010 [P] [US1] Update `services/flag-service-main/Dockerfile` and `services/targeting-service-main/Dockerfile` to launch the services with the OpenTelemetry auto-instrumentation wrapper and the required runtime defaults for New Relic export
- [X] T011 [US1] Confirm through `services/analytics-service-main/test_app.py` and `services/targeting-service-main/test_app.py` that existing app startup and health routes remain compatible with the instrumented runtime
- [X] T012 [US1] Confirm through `services/flag-service-main/test_app.py` that the app startup and health routes remain compatible with the instrumented runtime
- [X] T013 [US1] Validate that all three images build, each image provides `opentelemetry-instrument`, all health-route test suites pass, and Compose resolves the three distinct service identities and OTLP signal settings; live New Relic ingestion still requires a valid account key

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently.

---

## Phase 4: User Story 2 - Understand service health and dependency behavior (Priority: P2)

**Goal**: Ensure distributed request flow and dependency signals are visible in the centralized New Relic backend.

**Independent Test**: A request flowing through the Python services produces correlated traces and operational health data that identify service latency or failed dependency behavior.

### Implementation for User Story 2

- [X] T014 [P] [US2] Add distinct service naming and shared environment metadata for analytics, flag, and targeting to `services/docker-compose.yml` and `specs/001-python-observability/contracts/observability-runtime-contract.md`
- [X] T015 [US2] Configure the Docker runtime defaults in the three Python Dockerfiles and distinct per-service identities in `services/docker-compose.yml` so telemetry metadata is consistently reported to New Relic
- [X] T016 [US2] Validate that resolved Compose configuration assigns distinct service identities and enables traces, metrics, and logs for analytics, flag, and targeting

**Checkpoint**: At this point, User Stories 1 and 2 should both work independently.

---

## Phase 5: User Story 3 - Support operational readiness and continuous improvement (Priority: P3)

**Goal**: Make the observability setup operationally sustainable and easy to validate during releases and incident reviews.

**Independent Test**: An operator can use the provided runbook and Docker configuration to confirm that the microservices are exporting telemetry to New Relic and remain healthy across deployment changes.

### Implementation for User Story 3

- [X] T017 [P] [US3] Update the repository documentation and operational runbook in `README.md` and `specs/001-python-observability/quickstart.md` to capture the New Relic environment variables, Docker startup path, and validation steps
- [X] T018 [US3] Document the required health and telemetry validation flow for the Python microservices in `specs/001-python-observability/contracts/observability-runtime-contract.md` and ensure it includes the runbook for missing or degraded configuration
- [X] T019 [US3] Validate the Docker and observability configuration against the feature spec by building the images, checking Compose service metadata, and running all Python service test suites

**Checkpoint**: All user stories should now be independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final review of the runtime contract, configuration consistency, and operational quality across the Python services.

- [X] T020 [P] Review all changed files for environment-variable consistency, secret handling, and deployment compatibility across the Python services
- [X] T021 [P] Confirm the New Relic export paths and startup commands do not require direct application code instrumentation for core traces and logs
- [X] T022 Confirm the generated implementation artifacts align with the design docs in `specs/001-python-observability/plan.md` and `specs/001-python-observability/spec.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - no dependencies on other stories; covers analytics, flag, and targeting
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - may integrate with US1 but should remain independently testable
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - may integrate with US1/US2 but should remain independently testable

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel
- The Docker and environment configuration updates for the two Python services can be implemented in parallel once the base runtime contract is ready
- The documentation and validation tasks for User Story 3 can run in parallel with the final operational review

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. Stop and validate the container startup and New Relic export path
5. Deploy or demo only if the service emits telemetry without custom application instrumentation

### Incremental Delivery

1. Standardize the runtime configuration contract across the service Docker environments
2. Enable cross-service telemetry export to New Relic for the Python services
3. Add operational health and dependency visibility checks
4. Document the deployment, validation, and incident-review workflow
