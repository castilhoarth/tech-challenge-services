# flag-service (Python)

Este é o serviço de CRUD (Create, Read, Update, Delete) do projeto ToggleMaster. Ele é responsável por gerenciar as *definições* das feature flags.

**IMPORTANTE:** Este serviço é protegido e depende que o `auth-service` esteja rodando. Todas as requisições (exceto `/health`) exigem um header `Authorization: Bearer <sua-chave-api>`.

## 📦 Pré-requisitos (Local)

* [Python](https://www.python.org/) (versão 3.9 ou superior)
* [PostgreSQL](https://www.postgresql.org/download/) (rodando localmente ou em um contêiner Docker)
* O `auth-service` deve estar rodando (localmente na porta `8001`).

## 🚀 Rodando Localmente

1.  **Clone o repositório** e entre na pasta `flag-service`.

2.  **Prepare o Banco de Dados:**
    * Crie um banco de dados no seu PostgreSQL (ex: `flags_db`).
    * Execute o script `db/init.sql` para criar a tabela `flags`:
        ```bash
        psql -U seu_usuario -d flags_db -f db/init.sql
        ```

3.  **Configure as Variáveis de Ambiente:**
    Crie um arquivo chamado `.env` na raiz desta pasta (`flag-service/`) com o seguinte conteúdo:
    ```.env
    # String de conexão do seu banco de dados PostgreSQL
    DATABASE_URL="postgres://SEU_USUARIO:SUA_SENHA@localhost:5432/flags_db"
    
    # Porta que este serviço (flag-service) irá rodar
    PORT="8002"
    
    # URL do auth-service (que deve estar rodando na porta 8001)
    AUTH_SERVICE_URL="http://localhost:8001"
    ```

4.  **Instale as Dependências:**
    ```bash
    pip install -r requirements.txt
    ```

5.  **Inicie o Serviço:**
    ```bash
    gunicorn --bind 0.0.0.0:8002 app:app
    ```
    O servidor estará rodando em `http://localhost:8002`.

## 🧪 Testando os Endpoints

**Primeiro, você precisa de uma chave de API válida!**

1.  Vá até o terminal do `auth-service` (que deve estar rodando) e crie uma chave:
    ```bash
    curl -X POST http://localhost:8001/admin/keys \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer admin-secreto-123" \
    -d '{"name": "admin-para-flag-service"}'
    ```
2.  Copie a chave retornada (ex: `tm_key_...`). Vamos chamá-la de `SUA_CHAVE_API` no resto dos exemplos.

---

**Agora, teste o `flag-service`:**

**1. Verifique a Saúde (Health Check):**
```bash
curl http://localhost:8002/health
```

Saída esperada: `{"status":"ok"}`

**2. Tente Acessar um Endpoint Protegido (Sem Chave):**
```bash
curl http://localhost:8002/flags
```

Saída esperada: `{"error":"Authorization header obrigatório"}`

**3. Crie uma nova Flag (Com a Chave Correta):**
```bash
curl -X POST http://localhost:8002/flags \
-H "Content-Type: application/json" \
-H "Authorization: Bearer SUA_CHAVE_API" \
-d '{
    "name": "enable-new-dashboard",
    "description": "Ativa o novo dashboard para usuários",
    "is_enabled": true
}'
```
Saída esperada: (Um JSON com os dados da flag criada).

**4. Liste todas as Flags:**
```bash
curl http://localhost:8002/flags \
-H "Authorization: Bearer SUA_CHAVE_API"
```
Saída esperada: (Uma lista `[]` contendo a flag que você criou).

**5. Desative a Flag (PUT):**
```bash
curl -X PUT http://localhost:8002/flags/enable-new-dashboard \
-H "Content-Type: application/json" \
-H "Authorization: Bearer SUA_CHAVE_API" \
-d '{"is_enabled": false}'
```
Saída esperada: (O JSON da flag atualizada, com `"is_enabled": false`).

## Simulando erros 500

O endpoint `POST /__test__/error` usa a mesma validação de API key que os
endpoints de flags e retorna exatamente um HTTP 500 por requisição. Ele também
incrementa a métrica Prometheus `flag_service_simulated_errors_total` e registra
`simulated_http_error` nos logs. O endpoint não mantém um loop em execução.

Para executar uma simulação limitada, defina a chave de API sem exibi-la e
informe a URL e a duração desejada. O gerador envia a primeira requisição
imediatamente e as próximas a cada cinco segundos. Execute o comando a partir
da raiz do repositório `tech-challenge-services`:

```bash
read -s -p "Flag-service API key: " FLAG_SERVICE_API_KEY
printf '\n'
export FLAG_SERVICE_API_KEY
FLAG_SERVICE_SIMULATOR_URL="http://localhost:8002/__test__/error" \
ERROR_SIMULATION_DURATION_SECONDS=60 \
scripts/observability/simulate-flag-service-errors.sh
unset FLAG_SERVICE_API_KEY
```

Para executar pelo Ingress no AWS, use a URL pública do serviço com o prefixo
`/flags`, por exemplo
`https://<ingress-host>/flags/__test__/error`. O Ingress remove esse prefixo
antes de encaminhar a requisição. Use uma duração positiva em segundos; o
gerador encerra automaticamente ao fim do intervalo ou ao receber uma resposta
inesperada. HTTP 500 é o resultado esperado.

O Deployment marca os pods para scrape Prometheus em `/metrics` na porta 8002.
O agente/scraper Prometheus do cluster precisa estar configurado para descobrir
pods por essas annotations. No Grafana, use a expressão abaixo para alertar
quando houver ao menos um erro simulado no último minuto:

```promql
sum(increase(flag_service_simulated_errors_total[1m])) > 0
```

Confirme também a presença dos logs `simulated_http_error` no Loki e inspecione
os traces HTTP 500 no New Relic. O endpoint `/health` continua retornando 200
durante a simulação, portanto os probes do Kubernetes não devem reiniciar o
serviço.
