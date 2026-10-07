!/bin/bash

########################################
# CONFIGURAÇÃO
########################################

BASE_URL_AUTH=${BASE_URL_AUTH:-http://localhost:8001}
BASE_URL_FLAG=${BASE_URL_FLAG:-http://localhost:8002}
BASE_URL_TARGETING=${BASE_URL_TARGETING:-http://localhost:8003}
BASE_URL_EVALUATION=${BASE_URL_EVALUATION:-http://localhost:8004}
BASE_URL_ANALYTICS=${BASE_URL_ANALYTICS:-http://localhost:8005}

MASTER_KEY=${MASTER_KEY:-admin-secreto-123}

FLAG_NAME="enable-new-dashboard-$(date +%s)"

USER_NAME1="user-$(date +%s)"
sleep 2
USER_NAME2="user-$(date +%s)"

echo ""
echo "========================================"
echo "AMBIENTE DE TESTE"
echo "========================================"
echo "AUTH      : $BASE_URL_AUTH"
echo "FLAG      : $BASE_URL_FLAG"
echo "TARGETING : $BASE_URL_TARGETING"
echo "EVALUATION : $BASE_URL_EVALUATION"
echo "ANALYTICS : $BASE_URL_ANALYTICS"
echo ""

########################################
# HEALTH CHECK
########################################

echo "========================================"
echo "1. Health Check"
echo "========================================"

curl "$BASE_URL_AUTH/health"
echo
echo

curl "$BASE_URL_FLAG/health"
echo
echo

curl "$BASE_URL_TARGETING/health"
echo
echo

curl "$BASE_URL_EVALUATION/health"
echo
echo

curl "$BASE_URL_ANALYTICS/health"
echo
echo

########################################
# CRIAR API KEY
########################################

echo ""
echo "========================================"
echo "2. Criando API Key"
echo "========================================"

HTTP_CODE=$(curl -s -o response.json -w "%{http_code}" \
-X POST "$BASE_URL_AUTH/admin/keys" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer admin-secreto-123" \
-d '{"name":"teste-automacao"}')

if [ "$HTTP_CODE" != "201" ]; then
    echo "ERRO ao criar API Key (HTTP $HTTP_CODE)"
    cat response.json
    exit 1
fi

API_KEY=$(grep -o '"key":"[^"]*' response.json | cut -d'"' -f4)

echo "API KEY:"
echo "$API_KEY"
echo ""
echo ""

########################################
# CRIAR FLAG
########################################

echo "========================================"
echo "3. Criando Flag"
echo "========================================"

HTTP_CODE=$(curl -s -o response.json -w "%{http_code}" \
-X POST "$BASE_URL_FLAG/flags" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $API_KEY" \
-d "{
    \"name\":\"$FLAG_NAME\",
    \"description\":\"Teste automatizado\",
    \"is_enabled\":true
}")

if [ "$HTTP_CODE" != "201" ]; then
    echo "ERRO ao criar Flag (HTTP $HTTP_CODE)"
    cat response.json
    exit 1
fi

cat response.json

echo ""
echo ""


echo "========================================"
echo "4. Listando Flags"
echo "========================================"

HTTP_CODE=$(curl -s -o response.json -w "%{http_code}" \
-H "Authorization: Bearer $API_KEY" \
"$BASE_URL_FLAG/flags")

if [ "$HTTP_CODE" != "200" ]; then
    echo "ERRO ao listar flags (HTTP $HTTP_CODE)"
    cat response.json
    exit 1
fi

echo "Flags encontradas:"
grep -o '"name":"[^"]*"' response.json | cut -d'"' -f4

echo ""
echo ""

echo "========================================"
echo "5. Consultando Flag"
echo "========================================"

HTTP_CODE=$(curl -s -o response.json -w "%{http_code}" \
"$BASE_URL_FLAG/flags/$FLAG_NAME" \
-H "Authorization: Bearer $API_KEY")

if [ "$HTTP_CODE" != "200" ]; then
    echo "ERRO ao consultar flag (HTTP $HTTP_CODE)"
    cat response.json
    exit 1
fi

cat response.json

echo ""
echo ""

echo "========================================"
echo "6. Atualizando Flag"
echo "========================================"

HTTP_CODE=$(curl -s -o response.json -w "%{http_code}" \
-X PUT "$BASE_URL_FLAG/flags/$FLAG_NAME" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $API_KEY" \
-d '{
  "is_enabled": false
}')

if [ "$HTTP_CODE" != "200" ]; then
    echo "ERRO ao atualizar flag (HTTP $HTTP_CODE)"
    cat response.json
    exit 1
fi

cat response.json

echo ""
echo ""

echo "========================================"
echo "7. Criando Regra de Targeting"
echo "========================================"

HTTP_CODE=$(curl -s -o response.json -w "%{http_code}" \
-X POST "$BASE_URL_TARGETING/rules" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $API_KEY" \
-d "{
  \"flag_name\":\"$FLAG_NAME\",
  \"is_enabled\":true,
  \"rules\":{
      \"type\":\"PERCENTAGE\",
      \"value\":50
  }
}")

if [ "$HTTP_CODE" != "201" ]; then
    echo "ERRO ao criar regra (HTTP $HTTP_CODE)"
    cat response.json
    exit 1
fi

cat response.json

echo ""
echo ""

echo "========================================"
echo "8. Consultando Regra"
echo "========================================"

HTTP_CODE=$(curl -s -o response.json -w "%{http_code}" \
"$BASE_URL_TARGETING/rules/$FLAG_NAME" \
-H "Authorization: Bearer $API_KEY")

if [ "$HTTP_CODE" != "200" ]; then
    echo "ERRO ao consultar regra (HTTP $HTTP_CODE)"
    cat response.json
    exit 1
fi

cat response.json

echo ""
echo ""

echo "========================================"
echo "9. Atualizando Regra"
echo "========================================"

HTTP_CODE=$(curl -s -o response.json -w "%{http_code}" \
-X PUT "$BASE_URL_TARGETING/rules/$FLAG_NAME" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $API_KEY" \
-d '{
  "rules":{
      "type":"PERCENTAGE",
      "value":75
  }
}')

if [ "$HTTP_CODE" != "200" ]; then
    echo "ERRO ao atualizar regra (HTTP $HTTP_CODE)"
    cat response.json
    exit 1
fi

cat response.json

echo ""
echo ""

echo "========================================"
echo "10. Testando a fila SQS e o processamento"
echo "========================================"

echo "user 1 - $USER_NAME1"

for i in 1 2
do
  echo "=== Request $i ==="

  HTTP_CODE=$(curl -s -o response.json -w "%{http_code}" \
    "$BASE_URL_EVALUATION/evaluate?user_id=$USER_NAME1&flag_name=$FLAG_NAME" \
    )

  if [ "$HTTP_CODE" != "200" ]; then
      echo "ERRO na tentativa $i (HTTP $HTTP_CODE)"
      cat response.json
      exit 1
  fi

  cat response.json
  echo -e "\n"
done

echo ""
echo ""

echo "user 2 - $USER_NAME2"

for i in 1 2
do
  echo "=== Request $i ==="

  HTTP_CODE=$(curl -s -o response.json -w "%{http_code}" \
    "$BASE_URL_EVALUATION/evaluate?user_id=$USER_NAME2&flag_name=enable-new-dashboard-1780855960" \
    )

  if [ "$HTTP_CODE" != "200" ]; then
      echo "ERRO na tentativa $i (HTTP $HTTP_CODE)"
      cat response.json
      exit 1
  fi

  cat response.json
  echo -e "\n"
done

echo ""
echo ""

echo "========================================"
echo "11. Deletando Flag"
echo "========================================"

echo "FLAG_NAME=$FLAG_NAME"

HTTP_CODE=$(curl -s -o response.json -w "%{http_code}" \
-X DELETE \
"$BASE_URL_FLAG/flags/$FLAG_NAME" \
-H "Authorization: Bearer $API_KEY")

if [ "$HTTP_CODE" != "204" ]; then
    echo "ERRO ao deletar flag (HTTP $HTTP_CODE)"
    cat response.json
    exit 1
fi

echo "Flag removida com sucesso."

echo ""
echo ""
echo "TESTE FINALIZADO COM SUCESSO"