# Research: Python Observability with New Relic

## Decision

Use OpenTelemetry Python auto-instrumentation as the standard no-code observability layer for the Python microservices, and route all telemetry to New Relic through the OTLP export path or New Relic-compatible OTEL configuration. Standardize the runtime configuration through environment variables and Docker container settings so each Python service can emit traces, logs, and metrics without bespoke application instrumentation.

## Rationale

- The repository contains three Python services (`analytics-service-main`, `flag-service-main`, and `targeting-service-main`) built as containerized apps, which makes a shared runtime configuration approach the most reliable and low-maintenance option.
- The feature requirement explicitly favors no-code observability, which aligns with OpenTelemetry auto-instrumentation for Flask, HTTP clients, and standard logging hooks rather than manual span creation in application code.
- New Relic is the approved backend, so configuration must be centralized and environment-driven rather than embedded in code.
- The Dockerfiles already centralize runtime behavior, making them the correct place to add dependencies, environment variables, and startup commands needed for telemetry collection.

## Alternatives considered

1. Manual instrumentation in application code
   - Pros: maximum control over trace details.
   - Cons: violates the no-code requirement and increases engineering effort across each service.

2. Vendor-specific New Relic Python agent only
   - Pros: strong New Relic native support.
   - Cons: less aligned with the OpenTelemetry requirement and less portable across future backends.

3. Local-only logging without remote backend
   - Pros: minimal setup.
   - Cons: does not meet the requirement for central observability and operational cross-service analysis.

## Implementation direction

- Install OpenTelemetry Python packages in all three Python service images, using a shared base pattern for all affected container builds.
- Configure service identity and export settings with environment variables such as:
  - `NEW_RELIC_LICENSE_KEY`
  - `OTEL_SERVICE_NAME`
  - `OTEL_EXPORTER_OTLP_ENDPOINT`
  - `OTEL_EXPORTER_OTLP_HEADERS`
- Use New Relic's native OTLP ingestion with the license key in the exact `api-key` header, `http/protobuf` protocol, and the regional endpoint selected for the New Relic account.
- Use a startup command that launches the service with auto-instrumentation enabled, for example via the `opentelemetry-instrument` wrapper or equivalent environment-based setup.
- Extend Dockerfiles to include the required environment defaults and copy any startup script if needed.
- Keep deployment configuration external to code so secrets remain in environment management and not committed to source control.

## Confirmed configuration choices

- Python 3.11 is the runtime in all three in-scope Dockerfiles.
- New Relic native OTLP ingestion is used; the default is the US endpoint, with the endpoint overridable for EU or other supported regions.
- OTLP/HTTP with protobuf is used for internet export, with traces, metrics, and logs enabled.
- The license key is required at Compose runtime and is interpolated into the OTLP authorization header. It is not stored in source or image build arguments.
- Analytics, flag, and targeting share exporter settings but have distinct service identities.
