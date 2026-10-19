package main

import (
	"context"
	"encoding/json"
	"log"
	"time"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/service/sqs"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/trace"
)

// Evento que será enviado para a fila
type EvaluationEvent struct {
	UserID    string    `json:"user_id"`
	FlagName  string    `json:"flag_name"`
	Result    bool      `json:"result"`
	Timestamp time.Time `json:"timestamp"`
}

// sendEvaluationEvent envia um evento para a fila SQS
func (a *App) sendEvaluationEvent(ctx context.Context, userID, flagName string, result bool) {
	// Se a URL da fila não foi configurada, apenas loga localmente e sai.
	if a.SqsSvc == nil || a.SqsQueueURL == "" {
		log.Println("SQS desabilitado; evento de avaliação não enviado")
		return
	}

	event := EvaluationEvent{
		UserID:    userID,
		FlagName:  flagName,
		Result:    result,
		Timestamp: time.Now().UTC(),
	}

	body, err := json.Marshal(event)
	if err != nil {
		log.Printf("Erro ao serializar evento SQS: %v", err)
		return
	}

	sendContext, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()
	sendContext, span := otel.Tracer("evaluation-service").Start(
		sendContext,
		"sqs.send",
		trace.WithSpanKind(trace.SpanKindProducer),
		trace.WithAttributes(attribute.String("messaging.system", "aws_sqs")),
	)
	defer span.End()

	_, err = a.SqsSvc.SendMessage(&sqs.SendMessageInput{
		MessageBody:       aws.String(string(body)),
		QueueUrl:          aws.String(a.SqsQueueURL),
		MessageAttributes: sqsTraceMessageAttributes(sendContext),
	})

	if err != nil {
		span.SetStatus(codes.Error, "SQS send failed")
		log.Printf("Erro ao enviar mensagem para SQS: %v", err)
	} else {
		log.Println("Evento de avaliação enviado para SQS")
	}
}

func sqsTraceMessageAttributes(ctx context.Context) map[string]*sqs.MessageAttributeValue {
	carrier := propagation.MapCarrier{}
	otel.GetTextMapPropagator().Inject(ctx, carrier)
	messageAttributes := make(map[string]*sqs.MessageAttributeValue, len(carrier))
	for key, value := range carrier {
		if key != "traceparent" && key != "tracestate" {
			continue
		}
		messageAttributes[key] = &sqs.MessageAttributeValue{
			DataType:    aws.String("String"),
			StringValue: aws.String(value),
		}
	}
	return messageAttributes
}
