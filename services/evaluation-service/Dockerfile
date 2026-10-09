# ==========================
# Build Stage
# ==========================

FROM golang:1.21 AS builder

WORKDIR /app

COPY go.mod .
COPY go.sum .

RUN go mod download

COPY . .

RUN CGO_ENABLED=0 GOOS=linux go build -o evaluation-service .

# ==========================
# Runtime Stage
# ==========================

FROM alpine:3.20

ENV OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318 \
    OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf \
    OTEL_TRACES_EXPORTER=otlp \
    OTEL_METRICS_EXPORTER=otlp \
    OTEL_LOGS_EXPORTER=otlp

WORKDIR /app

RUN apk --no-cache add ca-certificates

COPY --from=builder /app/evaluation-service .

EXPOSE 8004

CMD ["./evaluation-service"]