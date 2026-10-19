package main

import (
	"context"
	"errors"
	"io"
	"log"
	"log/slog"
	"os"
	"strings"

	"go.opentelemetry.io/contrib/bridges/otelslog"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/exporters/otlp/otlplog/otlploghttp"
	"go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetrichttp"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
	"go.opentelemetry.io/otel/propagation"
	sdklog "go.opentelemetry.io/otel/sdk/log"
	"go.opentelemetry.io/otel/sdk/metric"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
)

func initTelemetry(ctx context.Context) (func(context.Context) error, error) {
	traceExporter, err := otlptracehttp.New(ctx)
	if err != nil {
		return nil, err
	}
	metricExporter, err := otlpmetrichttp.New(ctx)
	if err != nil {
		_ = traceExporter.Shutdown(ctx)
		return nil, err
	}
	logExporter, err := otlploghttp.New(ctx)
	if err != nil {
		_ = metricExporter.Shutdown(ctx)
		_ = traceExporter.Shutdown(ctx)
		return nil, err
	}

	res, err := resource.New(ctx, resource.WithAttributes(
		attribute.String("service.name", "evaluation-service"),
		attribute.String("deployment.environment", deploymentEnvironment()),
	))
	if err != nil {
		_ = logExporter.Shutdown(ctx)
		_ = metricExporter.Shutdown(ctx)
		_ = traceExporter.Shutdown(ctx)
		return nil, err
	}

	tracerProvider := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(traceExporter),
		sdktrace.WithResource(res),
	)
	meterProvider := metric.NewMeterProvider(
		metric.WithReader(metric.NewPeriodicReader(metricExporter)),
		metric.WithResource(res),
	)
	loggerProvider := sdklog.NewLoggerProvider(
		sdklog.WithProcessor(sdklog.NewBatchProcessor(logExporter)),
		sdklog.WithResource(res),
	)

	otel.SetTracerProvider(tracerProvider)
	otel.SetMeterProvider(meterProvider)
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{},
		propagation.Baggage{},
	))

	logger := slog.New(otelslog.NewHandler(
		"evaluation-service",
		otelslog.WithLoggerProvider(loggerProvider),
	))
	log.SetOutput(io.MultiWriter(os.Stderr, telemetryLogWriter{logger: logger}))

	return func(ctx context.Context) error {
		return errors.Join(
			loggerProvider.Shutdown(ctx),
			meterProvider.Shutdown(ctx),
			tracerProvider.Shutdown(ctx),
		)
	}, nil
}

func deploymentEnvironment() string {
	if environment := os.Getenv("DEPLOYMENT_ENVIRONMENT"); environment != "" {
		return environment
	}
	return "development"
}

type telemetryLogWriter struct {
	logger *slog.Logger
}

func (writer telemetryLogWriter) Write(message []byte) (int, error) {
	if text := strings.TrimSpace(string(message)); text != "" {
		writer.logger.Info(text)
	}
	return len(message), nil
}
