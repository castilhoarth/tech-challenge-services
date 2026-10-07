# Data Model: Observability Configuration and Telemetry

## Overview

This feature introduces a minimal observability model for the analytics, flag, and targeting Python microservices without embedding custom instrumentation logic into each application. The data model centers on service identity, runtime configuration, and emitted telemetry streams that are exported to New Relic.

## Entities

### ServiceInstance

Represents a deployed instance of a Python microservice.

Fields:
- `service_name`: human-readable identity used in telemetry and dashboards
- `environment`: deployment environment, such as `dev`, `staging`, or `prod`
- `version`: application or image version
- `container_id`: runtime host/container identifier
- `observability_enabled`: boolean flag indicating the service is exporting telemetry

Relationships:
- emits zero or more `TelemetryEvent` records
- belongs to one or more `ServiceGroup` or runtime environment views

### TelemetryConfig

Represents the runtime configuration needed to send telemetry to the central backend.

Fields:
- `new_relic_license_key`: secret used to authenticate to New Relic
- `otlp_endpoint`: export endpoint used by the OpenTelemetry collector or gateway
- `otlp_headers`: any auth metadata required for the exporter
- `service_name`: logical identity for the running service
- `sampling_ratio`: chosen trace sampling profile
- `log_level`: runtime logging granularity for the process

Validation rules:
- `service_name` is required
- `otlp_endpoint` is required when export is enabled
- `new_relic_license_key` must be supplied through a managed secret source, never as a hardcoded value
- `observability_enabled` must be false if the service cannot export telemetry

### TelemetryEvent

Represents a unit of emitted observability data.

Fields:
- `event_type`: one of `trace`, `metric`, or `log`
- `timestamp`: when the event was generated
- `service_name`: originating service
- `correlation_id`: request or transaction identifier shared across services
- `status`: success, failure, timeout, or degraded state
- `attributes`: structured metadata for root cause analysis and dashboarding

Relationships:
- created by a `ServiceInstance`
- associated with one `RequestFlow`

### RequestFlow

Represents the end-to-end flow of a user request or system transaction across services.

Fields:
- `trace_id`: unique request identifier across service boundaries
- `entry_service`: first service touched by the request
- `path`: route or logical workflow name
- `duration_ms`: observed total response time
- `error_count`: number of failed operations in the flow

Validation rules:
- `trace_id` is required for distributed tracing
- `path` must be present for a meaningful request flow view
- `status` must be reported consistently for downstream health analysis

## State transitions

### ServiceInstance

- `not_configured` → `enabled` when telemetry environment variables are present
- `enabled` → `degraded` when exporter configuration is incomplete or the backend is unreachable
- `degraded` → `enabled` once configuration is restored

### TelemetryEvent

- `queued` → `exported` when successfully sent to New Relic
- `queued` → `dropped` if validation or export rules fail

## Notes

- This model intentionally focuses on platform/runtime behavior, not business objects or application-specific domain entities.
- The design supports centralized observability without increasing application complexity or requiring per-service custom instrumentation.
