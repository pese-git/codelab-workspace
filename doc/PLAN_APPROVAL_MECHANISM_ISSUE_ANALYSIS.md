# Анализ проблемы: Plan Approval не запрашивается на стороне клиента IDE

**Дата:** 2026-02-01  
**Статус:** Проблема идентифицирована  
**Приоритет:** Высокий

---

## 🔍 Описание проблемы

При создании плана в FSM (состояние `PLAN_REVIEW`), на стороне клиента IDE не отображается запрос на одобрение плана (approve plan). Это блокирует переход к выполнению плана и нарушает workflow FSM.

**Важно:** Эта проблема **не связана** с UNIQUE constraint в базе данных и требует отдельного исследования механизма approval в FSM.

---

## 📊 Текущая архитектура Plan Approval

### 1. Backend: Создание approval request

**Файл:** [`codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py`](codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py:547-593)

```python
# Step 3: Request user approval for plan
logger.info(f"Plan {plan_id} requesting user approval")

# Create approval request if ApprovalManager available
if self.approval_manager:
    approval_request_id = f"plan-approval-{plan_id}"
    
    # Add to pending approvals
    await self.approval_manager.add_pending(
        request_id=approval_request_id,
        request_type="plan",
        subject=plan_summary['goal'][:100],
        session_id=session_id,
        details={
            "plan_id": plan_id,
            "goal": plan_summary['goal'],
            "subtasks_count": plan_summary['subtasks_count'],
            "total_estimated_time": plan_summary['total_estimated_time'],
            "subtasks": plan_summary['subtasks']
        },
        reason="Complex plan requires user approval before execution"
    )
    
    # Yield approval required chunk
    yield StreamChunk(
        type="plan_approval_required",
        content="Plan requires your approval before execution",
        metadata={
            "approval_request_id": approval_request_id,
            "plan_id": plan_id,
            "fsm_state": FSMState.PLAN_REVIEW.value
        }
    )
```

✅ **Статус:** Работает корректно. Approval request создается и сохраняется в БД.

---

### 2. Agent Runtime: StreamChunk schema

**Файл:** [`codelab-ai-service/agent-runtime/app/api/v1/schemas/common.py`](codelab-ai-service/agent-runtime/app/api/v1/schemas/common.py:28-60)

```python
class StreamChunk(BaseModel):
    """SSE event chunk for streaming responses"""
    
    type: Literal[
        "assistant_message",
        "tool_call",
        "error",
        "done",
        "switch_agent",
        "agent_switched",
        "status",
        "plan_created",
        "plan_approval_required",  # ✅ Поддерживается
        "plan_rejected",
        "plan_modification_requested",
        "execution_completed"
    ]
    content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None  # ⚠️ Данные в metadata
```

✅ **Статус:** Тип `plan_approval_required` поддерживается.

---

### 3. Agent Runtime: SSE Streaming

**Файл:** [`codelab-ai-service/agent-runtime/app/api/v1/routers/messages_router.py`](codelab-ai-service/agent-runtime/app/api/v1/routers/messages_router.py:85-93)

```python
async def generate():
    try:
        async for chunk in message_orchestration_service.process_message(
            session_id=session_id,
            message=content,
            agent_type=agent_type
        ):
            # Преобразовать в SSE формат
            yield f"data: {chunk.model_dump_json()}\n\n"
```

✅ **Статус:** Chunk корректно преобразуется в SSE формат.

**Пример SSE события:**
```
data: {"type":"plan_approval_required","content":"Plan requires your approval before execution","metadata":{"approval_request_id":"plan-approval-xyz","plan_id":"xyz","fsm_state":"plan_review"}}
```

---

### 4. Gateway: WebSocket модель

**Файл:** [`codelab-ai-service/gateway/app/models/websocket.py`](codelab-ai-service/gateway/app/models/websocket.py:130-153)

```python
class WSPlanApprovalRequired(BaseModel):
    """WebSocket message for plan approval request from Agent to IDE"""
    
    type: Literal["plan_approval_required"]
    content: str
    approval_request_id: str  # ⚠️ На верхнем уровне
    plan_id: str              # ⚠️ На верхнем уровне
    plan_summary: Dict[str, Any]  # ⚠️ На верхнем уровне
```

✅ **Статус:** Модель определена корректно.

**Ожидаемый формат для клиента:**
```json
{
  "type": "plan_approval_required",
  "content": "Plan requires your approval before execution",
  "approval_request_id": "plan-approval-xyz",
  "plan_id": "xyz",
  "plan_summary": {
    "goal": "Create Flutter login form",
    "subtasks_count": 4,
    "total_estimated_time": "20 min"
  }
}
```

---

### 5. Gateway: WebSocket endpoint

**Файл:** [`codelab-ai-service/gateway/app/api/v1/endpoints.py`](codelab-ai-service/gateway/app/api/v1/endpoints.py:565-577)

```python
# Парсим JSON данные только для event: message
if current_event_type == "message":
    try:
        data = json.loads(data_str)
        msg_type = data.get('type')
        
        # Фильтруем null значения
        filtered_data = {k: v for k, v in data.items() if v is not None}
        
        # Пересылаем событие в IDE через WebSocket
        await websocket.send_json(filtered_data)
```

❌ **ПРОБЛЕМА НАЙДЕНА:** Gateway просто пересылает JSON как есть, **без преобразования** в формат `WSPlanApprovalRequired`.

---

## 🐛 Корневая причина проблемы

### Несоответствие форматов данных

**Backend отправляет:**
```json
{
  "type": "plan_approval_required",
  "content": "Plan requires your approval before execution",
  "metadata": {
    "approval_request_id": "plan-approval-xyz",
    "plan_id": "xyz",
    "fsm_state": "plan_review"
  }
}
```

**Клиент ожидает:**
```json
{
  "type": "plan_approval_required",
  "content": "Plan requires your approval before execution",
  "approval_request_id": "plan-approval-xyz",
  "plan_id": "xyz",
  "plan_summary": {
    "goal": "...",
    "subtasks_count": 4,
    "total_estimated_time": "20 min"
  }
}
```

### Проблемы:

1. ❌ **Данные в metadata:** `approval_request_id` и `plan_id` находятся внутри `metadata`, а не на верхнем уровне
2. ❌ **Отсутствует plan_summary:** Клиент ожидает `plan_summary` на верхнем уровне, но его нет
3. ❌ **Gateway не трансформирует:** Gateway не преобразует формат chunk в формат WebSocket модели

---

## 🔧 Решения

### Вариант 1: Исправить формат chunk в orchestrator_agent (Рекомендуется)

**Преимущества:**
- Минимальные изменения
- Соответствие ожидаемому формату клиента
- Не требует изменений в gateway

**Изменения в [`orchestrator_agent.py`](codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py:576-584):**

```python
# Yield approval required chunk
yield StreamChunk(
    type="plan_approval_required",
    content="Plan requires your approval before execution",
    metadata={
        "approval_request_id": approval_request_id,
        "plan_id": plan_id,
        "plan_summary": plan_summary,  # ✅ Добавить полный plan_summary
        "fsm_state": FSMState.PLAN_REVIEW.value
    }
)
```

**Затем добавить в [`StreamChunk`](codelab-ai-service/agent-runtime/app/api/v1/schemas/common.py:28-60):**

```python
class StreamChunk(BaseModel):
    # ... existing fields ...
    
    # For plan_approval_required type
    approval_request_id: Optional[str] = Field(default=None)
    plan_id: Optional[str] = Field(default=None)
    plan_summary: Optional[Dict[str, Any]] = Field(default=None)
```

---

### Вариант 2: Добавить трансформацию в Gateway

**Преимущества:**
- Централизованная обработка форматов
- Разделение ответственности (backend - бизнес-логика, gateway - протокол)

**Недостатки:**
- Больше изменений
- Дублирование логики преобразования

**Изменения в [`endpoints.py`](codelab-ai-service/gateway/app/api/v1/endpoints.py:565-577):**

```python
if current_event_type == "message":
    try:
        data = json.loads(data_str)
        msg_type = data.get('type')
        
        # ✅ Специальная обработка для plan_approval_required
        if msg_type == "plan_approval_required":
            metadata = data.get('metadata', {})
            transformed_data = {
                "type": "plan_approval_required",
                "content": data.get('content', ''),
                "approval_request_id": metadata.get('approval_request_id'),
                "plan_id": metadata.get('plan_id'),
                "plan_summary": metadata.get('plan_summary', {})
            }
            await websocket.send_json(transformed_data)
        else:
            # Обычная обработка для других типов
            filtered_data = {k: v for k, v in data.items() if v is not None}
            await websocket.send_json(filtered_data)
```

---

### Вариант 3: Использовать metadata как есть (Не рекомендуется)

Оставить backend как есть и изменить клиент IDE для чтения данных из `metadata`.

**Преимущества:**
- Не требует изменений на backend
- Быстрое решение

**Недостатки:**
- Нарушает контракт WebSocket API
- Требует изменений на клиенте
- **Несогласованность с другими типами сообщений:** Все остальные типы WebSocket сообщений (`tool_call`, `hitl_decision`, etc.) имеют данные на верхнем уровне, а не в `metadata`. Если `plan_approval_required` будет использовать `metadata`, это создаст непоследовательный API.

**Пример несогласованности:**

```dart
// tool_call - данные на верхнем уровне ✅
{
  "type": "tool_call",
  "call_id": "call-123",
  "tool_name": "read_file",
  "arguments": {...}
}

// plan_approval_required - данные в metadata ❌
{
  "type": "plan_approval_required",
  "content": "...",
  "metadata": {
    "approval_request_id": "...",
    "plan_id": "..."
  }
}
```

Это усложняет обработку на клиенте и нарушает принцип единообразия API.

#### Изменения на клиенте для Варианта 3

**Файл:** `lib/services/websocket_service.dart` (codelab-ai-assistant)

```dart
void _handleWebSocketMessage(Map<String, dynamic> message) {
  final type = message['type'];
  
  switch (type) {
    case 'plan_approval_required':
      // ⚠️ Читаем данные из metadata вместо верхнего уровня
      final metadata = message['metadata'] as Map<String, dynamic>?;
      
      if (metadata == null) {
        logger.error('plan_approval_required: metadata is null');
        return;
      }
      
      final approvalRequestId = metadata['approval_request_id'] as String?;
      final planId = metadata['plan_id'] as String?;
      
      // ⚠️ plan_summary отсутствует в metadata, нужно получить отдельно
      // Вариант 1: Запросить через REST API
      final planSummary = await _fetchPlanSummary(planId);
      
      // Вариант 2: Использовать данные из предыдущего chunk 'plan_created'
      // (если он был отправлен ранее)
      
      if (approvalRequestId == null || planId == null) {
        logger.error('plan_approval_required: missing required fields');
        return;
      }
      
      _showPlanApprovalDialog(
        approvalRequestId: approvalRequestId,
        planId: planId,
        planSummary: planSummary,
      );
      break;
      
    case 'plan_created':
      // Сохранить plan_summary для последующего использования
      final metadata = message['metadata'] as Map<String, dynamic>?;
      if (metadata != null && metadata['plan_summary'] != null) {
        _cachedPlanSummaries[metadata['plan_id']] = metadata['plan_summary'];
      }
      break;
  }
}

// Дополнительный метод для получения plan summary
Future<Map<String, dynamic>> _fetchPlanSummary(String? planId) async {
  if (planId == null) return {};
  
  // Проверить кэш
  if (_cachedPlanSummaries.containsKey(planId)) {
    return _cachedPlanSummaries[planId]!;
  }
  
  // Запросить через REST API (если доступен endpoint)
  try {
    final response = await http.get(
      Uri.parse('$baseUrl/plans/$planId/summary'),
    );
    if (response.statusCode == 200) {
      return json.decode(response.body);
    }
  } catch (e) {
    logger.error('Failed to fetch plan summary: $e');
  }
  
  return {};
}
```

**Проблемы с Вариантом 3:**

1. ❌ **Дополнительная сложность:** Клиент должен кэшировать или запрашивать `plan_summary` отдельно
2. ❌ **Дополнительный REST endpoint:** Нужен новый endpoint `/plans/{id}/summary` (если его нет)
3. ❌ **Race condition:** Chunk `plan_created` может прийти после `plan_approval_required`
4. ❌ **Непоследовательный API:** Разные типы сообщений обрабатываются по-разному
5. ❌ **Технический долг:** В будущем придется рефакторить

**Вывод:** Вариант 3 создает больше проблем, чем решает. Рекомендуется использовать Вариант 1 или 2.

---

## 📋 Рекомендуемый план действий

### Шаг 1: Исправить формат chunk (Вариант 1)

1. ✅ Добавить поля в `StreamChunk`:
   - `approval_request_id`
   - `plan_id`
   - `plan_summary`

2. ✅ Обновить создание chunk в `orchestrator_agent.py`:
   - Переместить данные из `metadata` на верхний уровень
   - Добавить полный `plan_summary`

3. ✅ Обновить документацию WebSocket API

### Шаг 2: Тестирование

1. ✅ Unit тесты для `StreamChunk` с новыми полями
2. ✅ Integration тест для plan approval flow
3. ✅ E2E тест с реальным клиентом IDE

### Шаг 3: Проверка совместимости

1. ✅ Убедиться, что изменения не ломают существующие типы chunks
2. ✅ Проверить обратную совместимость с клиентами

---

## 📝 Связанные файлы

### Backend (Agent Runtime)
- [`app/agents/orchestrator_agent.py`](codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py) - Создание approval request
- [`app/api/v1/schemas/common.py`](codelab-ai-service/agent-runtime/app/api/v1/schemas/common.py) - StreamChunk schema
- [`app/api/v1/routers/messages_router.py`](codelab-ai-service/agent-runtime/app/api/v1/routers/messages_router.py) - SSE streaming endpoint
- [`app/domain/services/plan_approval_handler.py`](codelab-ai-service/agent-runtime/app/domain/services/plan_approval_handler.py) - Обработка решений

### Gateway
- [`app/models/websocket.py`](codelab-ai-service/gateway/app/models/websocket.py) - WebSocket модели
- [`app/api/v1/endpoints.py`](codelab-ai-service/gateway/app/api/v1/endpoints.py) - WebSocket endpoint

### FSM
- [`app/domain/entities/fsm_state.py`](codelab-ai-service/agent-runtime/app/domain/entities/fsm_state.py) - FSM states и events
- [`app/domain/services/fsm_orchestrator.py`](codelab-ai-service/agent-runtime/app/domain/services/fsm_orchestrator.py) - FSM transitions

---

## 🎯 Ожидаемый результат

После исправления:

1. ✅ Backend создает chunk с данными на верхнем уровне
2. ✅ Gateway пересылает chunk без изменений
3. ✅ Клиент IDE получает корректный формат и отображает диалог approval
4. ✅ Пользователь может approve/reject/modify план
5. ✅ FSM корректно переходит из `PLAN_REVIEW` в `PLAN_EXECUTION` или `ARCHITECT_PLANNING`

---

## 📚 Дополнительная информация

### Текущий FSM workflow для планов

```
IDLE → CLASSIFY → PLAN_REQUIRED → ARCHITECT_PLANNING
  ↓
PLAN_REVIEW (⚠️ Здесь должен быть approval)
  ↓
PLAN_EXECUTION → COMPLETED
```

### События FSM
- `PLAN_CREATED` - План создан, переход в PLAN_REVIEW
- `PLAN_APPROVED` - План одобрен, переход в PLAN_EXECUTION
- `PLAN_REJECTED` - План отклонен, переход в IDLE
- `PLAN_MODIFICATION_REQUESTED` - Запрошена модификация, переход в ARCHITECT_PLANNING

---

## ✅ Заключение

**Проблема идентифицирована:** Несоответствие формата данных между backend (данные в `metadata`) и клиентом (данные на верхнем уровне).

**Рекомендуемое решение:** Вариант 1 - исправить формат chunk в `orchestrator_agent.py` и добавить поля в `StreamChunk`.

**Приоритет:** Высокий - блокирует работу Planning System.

**Следующий шаг:** Реализовать исправления согласно Варианту 1.
