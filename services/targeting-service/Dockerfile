# ==========================
# Build Stage
# ==========================
FROM python:3.11-slim AS builder

WORKDIR /app

# Instala as dependências necessárias para build
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Instala as dependências em um diretório separado
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ==========================
# Runtime Stage
# ==========================
FROM python:3.11-slim

ENV OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318 \
    OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf \
    OTEL_TRACES_EXPORTER=otlp \
    OTEL_METRICS_EXPORTER=otlp \
    OTEL_LOGS_EXPORTER=otlp \
    OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED=true

WORKDIR /app

# Copia as dependências já instaladas
COPY --from=builder /install /usr/local

# Copia o código da aplicação
COPY app.py .
COPY db ./db

EXPOSE 8003

CMD ["opentelemetry-instrument", "gunicorn", "--bind", "0.0.0.0:8003", "app:app"]