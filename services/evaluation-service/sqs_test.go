package main

import (
	"context"
	"testing"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/propagation"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	"go.opentelemetry.io/otel/trace"
)

func TestSQSMessageAttributesCarryW3CTraceContext(t *testing.T) {
	previousPropagator := otel.GetTextMapPropagator()
	otel.SetTextMapPropagator(propagation.TraceContext{})
	defer otel.SetTextMapPropagator(previousPropagator)

	provider := sdktrace.NewTracerProvider()
	defer func() {
		if err := provider.Shutdown(context.Background()); err != nil {
			t.Errorf("shutting down tracer provider: %v", err)
		}
	}()

	ctx, parentSpan := provider.Tracer("evaluation-service").Start(context.Background(), "request")
	defer parentSpan.End()
	attributes := sqsTraceMessageAttributes(ctx)

	carrier := propagation.MapCarrier{}
	for key, value := range attributes {
		if value.DataType == nil || *value.DataType != "String" {
			t.Fatalf("attribute %q has DataType %v, want String", key, value.DataType)
		}
		if value.StringValue == nil {
			t.Fatalf("attribute %q has no string value", key)
		}
		carrier[key] = *value.StringValue
	}

	extracted := otel.GetTextMapPropagator().Extract(context.Background(), carrier)
	got := trace.SpanContextFromContext(extracted)
	want := parentSpan.SpanContext()
	if got.TraceID() != want.TraceID() || got.SpanID() != want.SpanID() {
		t.Fatalf("extracted span context = %s/%s, want %s/%s",
			got.TraceID(), got.SpanID(), want.TraceID(), want.SpanID())
	}
}

func TestSQSMessageAttributesOmitContextWithoutActiveSpan(t *testing.T) {
	previousPropagator := otel.GetTextMapPropagator()
	otel.SetTextMapPropagator(propagation.TraceContext{})
	defer otel.SetTextMapPropagator(previousPropagator)

	attributes := sqsTraceMessageAttributes(context.Background())
	if len(attributes) != 0 {
		t.Fatalf("got %d trace attributes without an active span, want 0", len(attributes))
	}
}
