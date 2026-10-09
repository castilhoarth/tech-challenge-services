# Runbook do OpenTelemetry e New Relic

Este runbook inicia localmente o conjunto de microsserviços com a versão
fixada do OpenTelemetry Collector e envia para o New Relic os sinais de
telemetria suportados. Os comandos devem ser executados a partir da raiz do
repositório.

## Pré-requisitos

- Docker Engine ou Docker Desktop com Docker Compose.
- `curl`, `jq` e `openssl` disponíveis no terminal.
- Uma conta New Relic, uma chave de ingestão (license key), o ID numérico da
  conta e uma chave de usuário/API com permissão para consultar NerdGraph.
- Configurações das aplicações em `services/.env`. Não adicione a chave do
  New Relic a esse arquivo.
- Uma flag existente nos dados da aplicação para usar na requisição de
  avaliação.
- Credenciais AWS válidas e `AWS_SQS_URL` apontando para uma fila acessível
  para verificar também a relação assíncrona com `analytics-service`.

## 1. Confira a configuração local

Antes de iniciar, confirme no seu editor que `services/.env` contém a
configuração local necessária e que `SERVICE_API_KEY` corresponde a uma chave
ativa criada pelo
`auth-service`. `evaluation-service` envia essa chave a `flag-service` e
`targeting-service`, que a validam com `auth-service`. Se o arquivo já contém
uma chave ativa, mantenha-a e pule para a próxima seção.

Se não tiver essa chave, inicie o stack e siga a etapa 4 para criá-la.

## 2. Configure o runtime do New Relic

No zsh, leia a chave de ingestão sem exibi-la e exporte-a somente na sessão
atual do terminal. Somente o Collector está configurado para receber essa
chave. O endpoint abaixo é dos EUA; para uma conta na União Europeia, use
`https://otlp.eu01.nr-data.net`.

```sh
printf 'New Relic ingest license key: '
read -s NEW_RELIC_LICENSE_KEY
printf '\n'
export NEW_RELIC_LICENSE_KEY
export NEW_RELIC_OTLP_ENDPOINT='https://otlp.nr-data.net'
export DEPLOYMENT_ENVIRONMENT='development'
```

Não adicione a chave de ingestão ao `services/.env`, ao Compose, às
configurações das aplicações ou aos argumentos de build do Docker.

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

## 3. Inicie o conjunto de serviços

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

## 4. Gere tráfego e verifique os traces distribuídos

Se `SERVICE_API_KEY` ainda não corresponder a uma chave ativa do
`auth-service`, crie uma agora. No zsh, leia a master key sem exibi-la:

```sh
printf 'Auth master key: '
read -s MASTER_KEY
printf '\n'

curl -fsS -X POST http://localhost:8001/admin/keys \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${MASTER_KEY}" \
  -d '{"name":"local-evaluation"}' | jq -r '.key'

unset MASTER_KEY
```

Copie a chave retornada para `SERVICE_API_KEY` em `services/.env`, usando seu
editor local. Trate-a como segredo e não a compartilhe. Recrie os três serviços
para que leiam a nova chave:

```sh
docker compose --env-file services/.env -f deploy/local/docker-compose.yml \
  up -d --force-recreate evaluation-service flag-service targeting-service
```

O script envia uma requisição de avaliação com um novo ID W3C e consulta o
NerdGraph até encontrar o trace. Informe o ID numérico da conta New Relic;
quando solicitado, digite uma chave de usuário/API do New Relic com permissão
de consulta, sem exibi-la. Essa chave é diferente da chave de ingestão usada
pelo Collector.

```sh
NEW_RELIC_ACCOUNT_ID='seu-account-id' \
FLAG_NAME='sua-flag-existente' \
MIN_SERVICE_COUNT=5 \
scripts/observability/test-distributed-traces.sh
```

Por padrão, o script testa `enable-new-dashboard`; escolha uma flag que exista
no ambiente. `MIN_SERVICE_COUNT=5` faz o teste passar apenas quando o mesmo
trace contiver `evaluation-service`, `flag-service`, `targeting-service`,
`auth-service` e `analytics-service`. O script requer `curl`, `jq` e `openssl`.
Ele pede a chave de usuário/API em um prompt oculto; alternativamente, defina
`NEW_RELIC_USER_API_KEY` no ambiente. Não a coloque em `services/.env`.

A execução de 2026-10-09 foi confirmada no New Relic com os cinco serviços em
um único trace. Isso valida o caminho síncrono e a propagação SQS para aquela
execução; cada nova tentativa gera uma nova verificação independente.

Se o script retornar HTTP 502, confirme que `SERVICE_API_KEY` em
`services/.env` corresponde a uma chave ativa do `auth-service`, atualize-a
conforme a etapa 4 e recrie os três serviços. Se o trace mostrar os serviços
síncronos, mas não `analytics-service`, confirme que as credenciais AWS não
expiraram e que `AWS_SQS_URL` aponta para uma fila acessível.

O script aguarda até 120 segundos por padrão; use `TRACE_WAIT_SECONDS` para
ajustar esse limite e `TRACE_POLL_INTERVAL_SECONDS` para alterar a frequência
das consultas. Para outra região, configure `NEW_RELIC_OTLP_ENDPOINT` para o
Collector e `NEW_RELIC_GRAPHQL_URL` para o NerdGraph regional.

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
telemetria. A propagação de contexto pelo SQS está configurada, coberta por
testes unitários focados e foi verificada no New Relic em 2026-10-09: uma
execução mostrou os cinco serviços no mesmo trace. Isso confirma aquela
execução, não garante que analytics apareça em todos os traces futuros. A
entrega e o consumo do evento dependem de credenciais AWS válidas e de
`AWS_SQS_URL` apontar para uma fila funcional. Considere cada nova execução
validada somente após observar os serviços relacionados no New Relic.

## Pare o conjunto de serviços

Pare os serviços sem excluir os dados persistentes:

```sh
docker compose --env-file services/.env -f deploy/local/docker-compose.yml down
```

Não use `docker compose down -v`: isso removeria os volumes persistentes dos
bancos de dados e do DynamoDB.

Ao terminar, remova a chave do shell atual:

```sh
unset NEW_RELIC_LICENSE_KEY NEW_RELIC_OTLP_ENDPOINT DEPLOYMENT_ENVIRONMENT
```
