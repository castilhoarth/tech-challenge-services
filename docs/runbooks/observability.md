# Runbook do OpenTelemetry e New Relic

Este runbook inicia localmente o conjunto de microsserviços com a versão
fixada do OpenTelemetry Collector e envia para o New Relic os sinais de
telemetria suportados. Os comandos devem ser executados a partir da raiz do
repositório.

## Pré-requisitos

- Docker Engine ou Docker Desktop com Docker Compose.
- Uma conta New Relic e uma chave de licença.
- Configurações das aplicações em `services/.env`. Não adicione a chave do
  New Relic a esse arquivo.
- Uma flag existente nos dados da aplicação para usar na requisição de
  avaliação.

## Configure as variáveis de runtime do New Relic

Leia a chave sem exibi-la e exporte-a somente na sessão atual do terminal.
Somente o Collector está configurado para receber essa chave.

```sh
printf 'New Relic license key: '
read -r -s NEW_RELIC_LICENSE_KEY
printf '\n'
export NEW_RELIC_LICENSE_KEY
export NEW_RELIC_OTLP_ENDPOINT='https://otlp.nr-data.net'
export DEPLOYMENT_ENVIRONMENT='development'
```

O endpoint acima é o dos EUA. Para uma conta na União Europeia, use
`https://otlp.eu01.nr-data.net`. Não cole a chave em comandos do shell,
arquivos do Compose, configurações das aplicações ou argumentos de build do
Docker.

## Valide a configuração (opcional)

Valide a configuração do Collector usando uma chave fictícia. Isso não envia
telemetria ao New Relic.

```sh
docker run --rm \
  --entrypoint /otelcol-contrib \
  -v "$PWD/deploy/observability/otel-collector/config.yaml:/etc/otelcol-contrib/config.yaml:ro" \
  -e NEW_RELIC_LICENSE_KEY=validation-only \
  -e NEW_RELIC_OTLP_ENDPOINT=https://otlp.nr-data.net \
  otel/opentelemetry-collector-contrib:0.162.0 \
  validate --config=/etc/otelcol-contrib/config.yaml
```

Verifique a sintaxe da configuração combinada do Compose sem exibir os valores
resolvidos:

```sh
NEW_RELIC_LICENSE_KEY=validation-only \
NEW_RELIC_OTLP_ENDPOINT=https://otlp.nr-data.net \
DEPLOYMENT_ENVIRONMENT=validation \
docker compose --env-file services/.env -f deploy/local/docker-compose.yml config --quiet
```

## Inicie o conjunto de serviços

Compile e inicie todos os serviços:

```sh
docker compose --env-file services/.env -f deploy/local/docker-compose.yml up --build -d
```

Verifique o estado dos containers e a saúde do Collector:

```sh
docker compose --env-file services/.env -f deploy/local/docker-compose.yml ps
curl -fsS http://localhost:13133/
```

Verifique os endpoints HTTP de saúde dos serviços:

```sh
curl -fsS http://localhost:8001/health
curl -fsS http://localhost:8002/health
curl -fsS http://localhost:8003/health
curl -fsS http://localhost:8004/health
curl -fsS http://localhost:8005/health
```

## Gere tráfego representativo

Substitua `existing-flag` por uma flag que exista nos dados configurados da
aplicação:

```sh
curl -i 'http://localhost:8004/evaluate?user_id=otel-smoke&flag_name=existing-flag'
```

Repita a requisição para gerar mais tráfego. Em caso de cache miss no serviço
de avaliação, `evaluation-service` chama `flag-service` e `targeting-service`;
esses serviços validam as chaves de API por meio de `auth-service`. Se o SQS
estiver configurado e disponível, os eventos de avaliação também poderão ser
processados por `analytics-service`. O produtor Go inclui `traceparent` e
`tracestate` do W3C nos atributos da mensagem SQS; o worker Python extrai esses
valores e inicia um span consumidor no trace de origem.

Para gerar várias requisições com IDs de trace exclusivos, execute:

```sh
scripts/observability/generate-otel-traffic.sh
```

Por padrão, o script envia 10 requisições para `enable-new-dashboard`, com um
segundo de intervalo. Confirme que essa flag existe nos dados locais. Você
pode alterar o comportamento com estas variáveis de ambiente:

```sh
FLAG_NAME='your-existing-flag' \
TRAFFIC_COUNT=25 \
REQUEST_INTERVAL_SECONDS=0.5 \
scripts/observability/generate-otel-traffic.sh
```

O script imprime o ID W3C de cada trace para que você possa localizar a
requisição no New Relic. Ele não exige uma chave de API de consulta do New
Relic e, por si só, não confirma a ingestão da telemetria.

Na interface de consulta do New Relic, pesquise um dos IDs impressos:

```sql
SELECT count(*) FROM Span
WHERE trace.id = 'paste-printed-trace-id-here'
SINCE 30 minutes ago
```

Para ver quais serviços foram observados nesse trace:

```sql
SELECT uniques(service.name) FROM Span
WHERE trace.id = 'paste-printed-trace-id-here'
SINCE 30 minutes ago
```

Se o trace aparecer, o New Relic o recebeu. O serviço de avaliação mantém em
cache os dados da flag; por isso, requisições posteriores talvez não incluam
spans de flag/targeting/auth. Aguarde o TTL do cache ou use outra flag
existente para exercitar essas relações.

## Inspecione o estado de runtime

Use o estado do Compose e os logs do Collector para investigar problemas de
inicialização ou exportação. Evite exibir variáveis de ambiente ou a
configuração resolvida do Compose.

```sh
docker compose --env-file services/.env -f deploy/local/docker-compose.yml ps
docker compose --env-file services/.env -f deploy/local/docker-compose.yml logs --tail=100 otel-collector
```

## Verifique a telemetria no New Relic

Confirme se aparecem estas identidades distintas de serviço:

- `auth-service`
- `flag-service`
- `targeting-service`
- `evaluation-service`
- `analytics-service`

Inspecione traces, métricas e logs separadamente e confirme o atributo
`deployment.environment`. Com tráfego representativo de avaliação, procure as
relações síncronas observadas: evaluation com flag e targeting, e depois flag
e targeting com auth. Os spans de banco de dados e Redis só devem ser
considerados presentes se aparecerem na telemetria recebida.

Collector pronto e configuração válida não comprovam que o New Relic recebeu
telemetria. A propagação de contexto pelo SQS está configurada e coberta por
testes unitários focados, mas a relação entre evaluation e analytics ainda não
foi verificada de ponta a ponta. Para confirmá-la, o produtor precisa enviar a
mensagem, o worker precisa consumi-la e os spans relacionados precisam
aparecer no New Relic. Confirme que as credenciais AWS são válidas e que
`AWS_SQS_URL` aponta para uma fila funcional; credenciais expiradas impedem
essa verificação. Considere qualquer sinal ou relação validado somente depois
de observá-lo no New Relic.

## Pare o conjunto de serviços

Pare os serviços sem excluir os dados persistentes:

```sh
docker compose --env-file services/.env -f deploy/local/docker-compose.yml down
```

Não use `docker compose down -v`: isso removeria os volumes persistentes dos
bancos de dados e do DynamoDB.

Ao terminar, remova a chave do shell atual:

```sh
unset NEW_RELIC_LICENSE_KEY
```
