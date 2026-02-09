#!/bin/bash
# Тест HITL workflow end-to-end

set -e

BASE_URL="http://localhost:8000"
SESSION_ID=""
CALL_ID=""

echo "🧪 Тестирование HITL Workflow"
echo "================================"

# 1. Создание сессии
echo ""
echo "1️⃣ Создание новой сессии..."
SESSION_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/sessions" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "coder",
    "context": {
      "workspace_path": "/test",
      "language": "python"
    }
  }')

SESSION_ID=$(echo "$SESSION_RESPONSE" | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4)

if [ -z "$SESSION_ID" ]; then
  echo "❌ Ошибка: не удалось создать сессию"
  echo "Response: $SESSION_RESPONSE"
  exit 1
fi

echo "✅ Сессия создана: $SESSION_ID"

# 2. Отправка сообщения с запросом на создание файла (должно вызвать HITL)
echo ""
echo "2️⃣ Отправка сообщения с tool call..."
MESSAGE_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/sessions/$SESSION_ID/messages" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Создай файл test.py с функцией hello_world",
    "role": "user"
  }')

echo "Response: $MESSAGE_RESPONSE"

# Ждем обработки
sleep 2

# 3. Получение pending approvals
echo ""
echo "3️⃣ Проверка pending approvals..."
APPROVALS_RESPONSE=$(curl -s -X GET "$BASE_URL/api/v1/sessions/$SESSION_ID/approvals/pending")

echo "Pending approvals: $APPROVALS_RESPONSE"

# Извлекаем call_id из ответа (если есть)
CALL_ID=$(echo "$APPROVALS_RESPONSE" | grep -o '"call_id":"[^"]*"' | head -1 | cut -d'"' -f4)

if [ -z "$CALL_ID" ]; then
  echo "⚠️  Нет pending approvals (возможно, агент не вызвал tool или автоматически одобрил)"
  echo ""
  echo "4️⃣ Проверка истории сообщений..."
  HISTORY=$(curl -s -X GET "$BASE_URL/api/v1/sessions/$SESSION_ID/messages")
  echo "$HISTORY" | python3 -m json.tool 2>/dev/null || echo "$HISTORY"
  exit 0
fi

echo "✅ Найден pending approval: $CALL_ID"

# 4. Одобрение tool call
echo ""
echo "4️⃣ Одобрение tool call..."
APPROVAL_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/sessions/$SESSION_ID/approvals/$CALL_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "decision": "approved"
  }')

echo "Approval response: $APPROVAL_RESPONSE"

# Ждем обработки
sleep 2

# 5. Проверка истории сообщений на дублирование
echo ""
echo "5️⃣ Проверка истории сообщений на дублирование tool results..."
HISTORY=$(curl -s -X GET "$BASE_URL/api/v1/sessions/$SESSION_ID/messages")

# Подсчет tool результатов с одинаковым call_id
TOOL_RESULT_COUNT=$(echo "$HISTORY" | grep -o "\"role\":\"tool\"" | wc -l)
echo "Количество tool результатов: $TOOL_RESULT_COUNT"

# Проверяем дублирование по call_id
DUPLICATE_CHECK=$(echo "$HISTORY" | grep -o "\"tool_call_id\":\"$CALL_ID\"" | wc -l)

echo ""
if [ "$DUPLICATE_CHECK" -gt 1 ]; then
  echo "❌ ОШИБКА: Обнаружено дублирование tool result для call_id=$CALL_ID (найдено: $DUPLICATE_CHECK)"
  echo ""
  echo "История сообщений:"
  echo "$HISTORY" | python3 -m json.tool 2>/dev/null || echo "$HISTORY"
  exit 1
else
  echo "✅ Дублирования tool result не обнаружено"
fi

# 6. Финальная проверка
echo ""
echo "6️⃣ Финальная проверка истории..."
echo "$HISTORY" | python3 -m json.tool 2>/dev/null || echo "$HISTORY"

echo ""
echo "================================"
echo "✅ HITL Workflow тест завершен успешно!"
