# План Approval - Руководство по реализации

**Дата:** 2026-02-01  
**Статус:** ✅ Реализовано  
**Версия:** 1.0

---

## 📋 Обзор

План Approval механизм позволяет пользователю просматривать и одобрять планы выполнения сложных задач перед их выполнением. Это критически важная функция для обеспечения контроля пользователя над действиями AI агента.

---

## 🏗️ Архитектура

### Компоненты системы

```
┌─────────────────┐
│   IDE Client    │
│  (Flutter/Dart) │
└────────┬────────┘
         │ WebSocket
         ↓
┌─────────────────┐
│    Gateway      │
│  (FastAPI WS)   │
└────────┬────────┘
         │ HTTP SSE
         ↓
┌─────────────────┐
│ Agent Runtime   │
│ - Orchestrator  │
│ - Architect     │
│ - FSM           │
│ - Approval Mgr  │
└─────────────────┘
```

### Поток данных

```
1. User → IDE: "Создай Flutter login form"
2. IDE → Gateway → Agent Runtime: user_message
3. Orchestrator → TaskClassifier: classify (is_atomic=false)
4. Orchestrator → Architect: create_plan()
5. Architect → Orchestrator: plan_id
6. Orchestrator → ApprovalManager: add_pending()
7. Orchestrator → Gateway → IDE: plan_approval_required
8. IDE: Show approval dialog
9. User → IDE: approve/reject/modify
10. IDE → Gateway → Agent Runtime: plan_decision
11. PlanApprovalHandler: handle decision
12. ExecutionCoordinator: execute_plan() (if approved)
```

---

## 📦 Реализованные компоненты

### 1. Backend: StreamChunk Schema

**Файл:** [`codelab-ai-service/agent-runtime/app/api/v1/schemas/common.py`](../codelab-ai-service/agent-runtime/app/api/v1/schemas/common.py:28-60)

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
    
    # ✅ Поля для plan_approval_required на верхнем уровне
    approval_request_id: Optional[str] = Field(default=None)
    plan_id: Optional[str] = Field(default=None)
    plan_summary: Optional[Dict[str, Any]] = Field(default=None)
    
    metadata: Optional[Dict[str, Any]] = None
```

**Ключевые особенности:**
- ✅ Поля `approval_request_id`, `plan_id`, `plan_summary` на верхнем уровне
- ✅ Соответствует WebSocket модели клиента
- ✅ Единообразный формат с другими типами chunks

---

### 2. Backend: Orchestrator Agent

**Файл:** [`codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py`](../codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py:547-594)

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
    
    # ✅ Yield approval required chunk с данными на верхнем уровне
    yield StreamChunk(
        type="plan_approval_required",
        content="Plan requires your approval before execution",
        approval_request_id=approval_request_id,
        plan_id=plan_id,
        plan_summary=plan_summary,
        metadata={
            "fsm_state": FSMState.PLAN_REVIEW.value
        }
    )
    
    # Execution will continue when user sends approval decision
    logger.info(
        f"Waiting for user approval for plan {plan_id}. "
        f"Execution paused in PLAN_REVIEW state."
    )
    return
```

**Ключевые особенности:**
- ✅ Создает approval request в ApprovalManager
- ✅ Отправляет chunk с полными данными на верхнем уровне
- ✅ Приостанавливает выполнение до получения решения
- ✅ FSM переходит в состояние PLAN_REVIEW

---

### 3. Backend: Messages Router

**Файл:** [`codelab-ai-service/agent-runtime/app/api/v1/routers/messages_router.py`](../codelab-ai-service/agent-runtime/app/api/v1/routers/messages_router.py:257-301)

```python
elif message_type == "plan_decision":
    # Обработка Plan Approval решения пользователя
    approval_request_id = message_data.get("approval_request_id")
    decision = message_data.get("decision")
    feedback = message_data.get("feedback")
    
    if not approval_request_id or not decision:
        raise HTTPException(
            status_code=400,
            detail="approval_request_id and decision are required"
        )
    
    logger.info(
        f"Processing Plan Approval decision for session {session_id}: "
        f"approval_request_id={approval_request_id}, decision={decision}"
    )
    
    async def plan_decision_generate():
        try:
            # Обрабатываем через MessageOrchestrationService
            async for chunk in message_orchestration_service.process_plan_decision(
                session_id=session_id,
                approval_request_id=approval_request_id,
                decision=decision,
                feedback=feedback
            ):
                yield f"data: {chunk.model_dump_json()}\n\n"
        except Exception as e:
            logger.error(f"Error processing Plan Approval decision: {e}")
            error_chunk = StreamChunk(
                type="error",
                error=str(e),
                is_final=True
            )
            yield f"data: {error_chunk.model_dump_json()}\n\n"
    
    return StreamingResponse(
        plan_decision_generate(),
        media_type="text/event-stream"
    )
```

**Ключевые особенности:**
- ✅ Обрабатывает `plan_decision` message type
- ✅ Валидирует обязательные поля
- ✅ Делегирует обработку в MessageOrchestrationService
- ✅ Возвращает SSE stream с результатами

---

### 4. Backend: Plan Approval Handler

**Файл:** [`codelab-ai-service/agent-runtime/app/domain/services/plan_approval_handler.py`](../codelab-ai-service/agent-runtime/app/domain/services/plan_approval_handler.py:72-266)

```python
async def handle(
    self,
    session_id: str,
    approval_request_id: str,
    decision: str,
    feedback: Optional[str] = None
) -> AsyncGenerator[StreamChunk, None]:
    """
    Обработать Plan Approval решение пользователя.
    
    Обрабатывает решение:
    - approve: Выполнить план через ExecutionCoordinator
    - reject: Отклонить план, вернуться к IDLE
    - modify: Запросить модификацию плана
    """
    
    # Валидация решения
    decision_enum = PlanApprovalDecision(decision)
    
    # Получить pending approval
    pending_approval = await self._approval_manager.get_pending(approval_request_id)
    plan_id = pending_approval.details.get("plan_id")
    
    # Обработать решение
    if decision_enum == PlanApprovalDecision.APPROVE:
        # Approve и execute
        await self._approval_manager.approve(approval_request_id)
        await self._fsm_orchestrator.transition(
            session_id=session_id,
            event=FSMEvent.PLAN_APPROVED,
            metadata={"approved_by": "user", "plan_id": plan_id}
        )
        
        execution_result = await self._execution_coordinator.execute_plan(
            plan_id=plan_id,
            session_id=session_id,
            session_service=self._session_service,
            stream_handler=None
        )
        
        yield StreamChunk(
            type="execution_completed",
            content=self._format_execution_result(execution_result),
            metadata={"plan_id": plan_id, "fsm_state": "completed"},
            is_final=True
        )
        
    elif decision_enum == PlanApprovalDecision.REJECT:
        # Reject и return to IDLE
        await self._approval_manager.reject(approval_request_id, reason=feedback)
        await self._fsm_orchestrator.transition(
            session_id=session_id,
            event=FSMEvent.PLAN_REJECTED,
            metadata={"rejected_by": "user", "reason": feedback}
        )
        
        yield StreamChunk(
            type="plan_rejected",
            content="Plan rejected. You can send a new message to start over.",
            metadata={"plan_id": plan_id, "fsm_state": "idle"},
            is_final=True
        )
        
    elif decision_enum == PlanApprovalDecision.MODIFY:
        # Request modification
        await self._approval_manager.reject(
            approval_request_id,
            reason=f"Modification requested: {feedback}"
        )
        await self._fsm_orchestrator.transition(
            session_id=session_id,
            event=FSMEvent.PLAN_MODIFICATION_REQUESTED,
            metadata={"requested_by": "user", "feedback": feedback}
        )
        
        yield StreamChunk(
            type="plan_modification_requested",
            content="Plan modification requested. Please send a new message.",
            metadata={"plan_id": plan_id, "fsm_state": "architect_planning"},
            is_final=True
        )
```

**Ключевые особенности:**
- ✅ Обрабатывает три типа решений: approve, reject, modify
- ✅ Управляет FSM transitions
- ✅ Выполняет план при approve
- ✅ Возвращает к IDLE при reject
- ✅ Запрашивает replanning при modify

---

### 5. Gateway: WebSocket Models

**Файл:** [`codelab-ai-service/gateway/app/models/websocket.py`](../codelab-ai-service/gateway/app/models/websocket.py:130-184)

```python
class WSPlanApprovalRequired(BaseModel):
    """WebSocket message for plan approval request from Agent to IDE"""
    
    type: Literal["plan_approval_required"]
    content: str
    approval_request_id: str
    plan_id: str
    plan_summary: Dict[str, Any]
    
    class Config:
        json_schema_extra = {
            "example": {
                "type": "plan_approval_required",
                "content": "Plan requires your approval before execution",
                "approval_request_id": "plan-approval-abc123",
                "plan_id": "plan-xyz789",
                "plan_summary": {
                    "goal": "Create Flutter login form",
                    "subtasks_count": 4,
                    "total_estimated_time": "20 min"
                }
            }
        }


class WSPlanDecision(BaseModel):
    """WebSocket message for plan approval decision from IDE to Agent"""
    
    type: Literal["plan_decision"]
    approval_request_id: str
    decision: Literal["approve", "reject", "modify"]
    feedback: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "type": "plan_decision",
                    "approval_request_id": "plan-approval-abc123",
                    "decision": "approve"
                },
                {
                    "type": "plan_decision",
                    "approval_request_id": "plan-approval-abc123",
                    "decision": "reject",
                    "feedback": "Plan is too complex"
                },
                {
                    "type": "plan_decision",
                    "approval_request_id": "plan-approval-abc123",
                    "decision": "modify",
                    "feedback": "Please add error handling"
                }
            ]
        }
```

**Ключевые особенности:**
- ✅ Определены модели для обоих направлений
- ✅ Поля на верхнем уровне (не в metadata)
- ✅ Примеры использования в документации
- ✅ Валидация через Pydantic

---

### 6. Gateway: WebSocket Endpoint

**Файл:** [`codelab-ai-service/gateway/app/api/v1/endpoints.py`](../codelab-ai-service/gateway/app/api/v1/endpoints.py:565-577)

```python
# Парсим JSON данные только для event: message
if current_event_type == "message":
    try:
        data = json.loads(data_str)
        msg_type = data.get('type')
        
        # Фильтруем null значения
        filtered_data = {k: v for k, v in data.items() if v is not None}
        
        logger.debug(f"[{session_id}] Sending to IDE: {json.dumps(filtered_data, indent=2)}")
        
        # ✅ Пересылаем событие в IDE через WebSocket
        await websocket.send_json(filtered_data)
        
    except json.JSONDecodeError as e:
        logger.warning(f"[{session_id}] Failed to parse SSE data: {e}")
```

**Ключевые особенности:**
- ✅ Пересылает JSON как есть (без трансформации)
- ✅ Фильтрует null значения
- ✅ Логирует отправляемые данные
- ✅ Обрабатывает ошибки парсинга

---

## 🔄 FSM State Transitions

### План Approval Flow

```
IDLE
  ↓ RECEIVE_MESSAGE
CLASSIFY
  ↓ IS_ATOMIC_FALSE
PLAN_REQUIRED
  ↓ ROUTE_TO_ARCHITECT
ARCHITECT_PLANNING
  ↓ PLAN_CREATED
PLAN_REVIEW ← ⚠️ Здесь отправляется plan_approval_required
  ↓
  ├─ PLAN_APPROVED → PLAN_EXECUTION → COMPLETED
  ├─ PLAN_REJECTED → IDLE
  └─ PLAN_MODIFICATION_REQUESTED → ARCHITECT_PLANNING
```

### События FSM

| Событие | Описание | Переход |
|---------|----------|---------|
| `PLAN_CREATED` | План создан Architect | ARCHITECT_PLANNING → PLAN_REVIEW |
| `PLAN_APPROVED` | Пользователь одобрил план | PLAN_REVIEW → PLAN_EXECUTION |
| `PLAN_REJECTED` | Пользователь отклонил план | PLAN_REVIEW → IDLE |
| `PLAN_MODIFICATION_REQUESTED` | Запрошена модификация | PLAN_REVIEW → ARCHITECT_PLANNING |
| `PLAN_EXECUTION_COMPLETED` | Выполнение завершено | PLAN_EXECUTION → COMPLETED |
| `PLAN_EXECUTION_FAILED` | Выполнение провалилось | PLAN_EXECUTION → ERROR_HANDLING |

---

## 📝 Формат сообщений

### 1. plan_approval_required (Agent → IDE)

**SSE формат от Agent Runtime:**
```json
{
  "type": "plan_approval_required",
  "content": "Plan requires your approval before execution",
  "approval_request_id": "plan-approval-abc123",
  "plan_id": "plan-xyz789",
  "plan_summary": {
    "goal": "Create Flutter login form with validation",
    "subtasks_count": 4,
    "total_estimated_time": "20 min",
    "subtasks": [
      {
        "id": "subtask-1",
        "description": "Create login form widget",
        "agent": "coder",
        "estimated_time": "5 min"
      },
      {
        "id": "subtask-2",
        "description": "Add form validation",
        "agent": "coder",
        "estimated_time": "5 min"
      },
      {
        "id": "subtask-3",
        "description": "Implement authentication logic",
        "agent": "coder",
        "estimated_time": "7 min"
      },
      {
        "id": "subtask-4",
        "description": "Write unit tests",
        "agent": "coder",
        "estimated_time": "3 min"
      }
    ]
  },
  "metadata": {
    "fsm_state": "plan_review"
  }
}
```

**WebSocket формат для IDE (то же самое):**
```json
{
  "type": "plan_approval_required",
  "content": "Plan requires your approval before execution",
  "approval_request_id": "plan-approval-abc123",
  "plan_id": "plan-xyz789",
  "plan_summary": { ... }
}
```

---

### 2. plan_decision (IDE → Agent)

**WebSocket формат от IDE:**
```json
{
  "type": "plan_decision",
  "approval_request_id": "plan-approval-abc123",
  "decision": "approve"
}
```

**С feedback (для reject/modify):**
```json
{
  "type": "plan_decision",
  "approval_request_id": "plan-approval-abc123",
  "decision": "reject",
  "feedback": "Plan is too complex, please simplify"
}
```

**HTTP формат для Agent Runtime (то же самое):**
```json
{
  "session_id": "session-123",
  "message": {
    "type": "plan_decision",
    "approval_request_id": "plan-approval-abc123",
    "decision": "approve"
  }
}
```

---

### 3. Ответные сообщения

**При approve:**
```json
{
  "type": "execution_completed",
  "content": "✅ **Plan Execution Completed**\n\n**Results:**\n- Completed: 4/4\n- Failed: 0\n- Duration: 45.2s",
  "metadata": {
    "plan_id": "plan-xyz789",
    "fsm_state": "completed",
    "execution_result": {
      "status": "completed",
      "completed_subtasks": 4,
      "failed_subtasks": 0,
      "total_subtasks": 4,
      "duration_seconds": 45.2
    }
  },
  "is_final": true
}
```

**При reject:**
```json
{
  "type": "plan_rejected",
  "content": "Plan rejected. You can send a new message to start over.",
  "metadata": {
    "plan_id": "plan-xyz789",
    "fsm_state": "idle"
  },
  "is_final": true
}
```

**При modify:**
```json
{
  "type": "plan_modification_requested",
  "content": "Plan modification requested. Replanning logic not yet implemented. Please send a new message to create a new plan.",
  "metadata": {
    "plan_id": "plan-xyz789",
    "fsm_state": "architect_planning",
    "feedback": "Please add error handling"
  },
  "is_final": true
}
```

---

## 🧪 Тестирование

### Unit тесты

**Тест StreamChunk с plan_approval_required:**
```python
def test_stream_chunk_plan_approval():
    chunk = StreamChunk(
        type="plan_approval_required",
        content="Plan requires approval",
        approval_request_id="plan-approval-123",
        plan_id="plan-456",
        plan_summary={
            "goal": "Test goal",
            "subtasks_count": 3,
            "total_estimated_time": "15 min"
        }
    )
    
    assert chunk.type == "plan_approval_required"
    assert chunk.approval_request_id == "plan-approval-123"
    assert chunk.plan_id == "plan-456"
    assert chunk.plan_summary["subtasks_count"] == 3
```

### Integration тесты

**Тест полного flow:**
```python
async def test_plan_approval_flow():
    # 1. Send user message
    response = await client.post(
        "/agent/message/stream",
        json={
            "session_id": "test-session",
            "message": {
                "type": "user_message",
                "content": "Create Flutter login form"
            }
        }
    )
    
    # 2. Expect plan_approval_required
    chunks = []
    async for line in response.aiter_lines():
        if line.startswith("data: "):
            chunk = json.loads(line[6:])
            chunks.append(chunk)
    
    approval_chunk = next(
        c for c in chunks 
        if c["type"] == "plan_approval_required"
    )
    
    assert approval_chunk["approval_request_id"]
    assert approval_chunk["plan_id"]
    assert approval_chunk["plan_summary"]
    
    # 3. Send approval decision
    response = await client.post(
        "/agent/message/stream",
        json={
            "session_id": "test-session",
            "message": {
                "type": "plan_decision",
                "approval_request_id": approval_chunk["approval_request_id"],
                "decision": "approve"
            }
        }
    )
    
    # 4. Expect execution_completed
    chunks = []
    async for line in response.aiter_lines():
        if line.startswith("data: "):
            chunk = json.loads(line[6:])
            chunks.append(chunk)
    
    completed_chunk = next(
        c for c in chunks 
        if c["type"] == "execution_completed"
    )
    
    assert completed_chunk["metadata"]["fsm_state"] == "completed"
```

---

## 🐛 Troubleshooting

### Проблема: plan_approval_required не приходит на клиент

**Возможные причины:**

1. ❌ **ApprovalManager не настроен**
   - Проверить: `orchestrator_agent.approval_manager is not None`
   - Решение: Настроить ApprovalManager в dependencies

2. ❌ **FSM не в состоянии PLAN_REVIEW**
   - Проверить: Логи FSM transitions
   - Решение: Убедиться, что PLAN_CREATED event отправлен

3. ❌ **Gateway не пересылает сообщение**
   - Проверить: Логи Gateway `[session_id] Sending to IDE`
   - Решение: Проверить WebSocket соединение

4. ❌ **Клиент не обрабатывает тип сообщения**
   - Проверить: Handler для `plan_approval_required` в клиенте
   - Решение: Добавить обработчик в WebSocket service

### Проблема: plan_decision не обрабатывается

**Возможные причины:**

1. ❌ **Неверный approval_request_id**
   - Проверить: ID совпадает с отправленным в plan_approval_required
   - Решение: Сохранить ID на клиенте при получении approval request

2. ❌ **Pending approval не найден**
   - Проверить: Логи `No pending approval found`
   - Решение: Убедиться, что approval не был удален/expired

3. ❌ **Неверный формат decision**
   - Проверить: decision in ["approve", "reject", "modify"]
   - Решение: Использовать правильные значения

---

## 📚 Дополнительные ресурсы

### Связанные файлы

**Backend (Agent Runtime):**
- [`app/agents/orchestrator_agent.py`](../codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py) - Создание approval request
- [`app/api/v1/schemas/common.py`](../codelab-ai-service/agent-runtime/app/api/v1/schemas/common.py) - StreamChunk schema
- [`app/api/v1/routers/messages_router.py`](../codelab-ai-service/agent-runtime/app/api/v1/routers/messages_router.py) - Messages endpoint
- [`app/domain/services/plan_approval_handler.py`](../codelab-ai-service/agent-runtime/app/domain/services/plan_approval_handler.py) - Обработка решений
- [`app/domain/services/message_orchestration.py`](../codelab-ai-service/agent-runtime/app/domain/services/message_orchestration.py) - Orchestration service

**Gateway:**
- [`app/models/websocket.py`](../codelab-ai-service/gateway/app/models/websocket.py) - WebSocket модели
- [`app/api/v1/endpoints.py`](../codelab-ai-service/gateway/app/api/v1/endpoints.py) - WebSocket endpoint

**FSM:**
- [`app/domain/entities/fsm_state.py`](../codelab-ai-service/agent-runtime/app/domain/entities/fsm_state.py) - FSM states и events
- [`app/domain/services/fsm_orchestrator.py`](../codelab-ai-service/agent-runtime/app/domain/services/fsm_orchestrator.py) - FSM transitions

**Документация:**
- [`doc/PLAN_APPROVAL_MECHANISM_ISSUE_ANALYSIS.md`](PLAN_APPROVAL_MECHANISM_ISSUE_ANALYSIS.md) - Анализ проблемы
- [`doc/PLANNING_SYSTEM_README.md`](PLANNING_SYSTEM_README.md) - Planning System overview

---

## ✅ Чеклист реализации на клиенте (IDE)

### 1. WebSocket Service

- [ ] Добавить handler для `plan_approval_required` message type
- [ ] Сохранить `approval_request_id` и `plan_summary` при получении
- [ ] Отобразить диалог одобрения плана пользователю
- [ ] Отправить `plan_decision` с выбором пользователя

### 2. UI Components

- [ ] Создать `PlanApprovalDialog` widget
- [ ] Отобразить `plan_summary` (goal, subtasks, estimated time)
- [ ] Добавить кнопки: Approve, Reject, Modify
- [ ] Добавить поле для feedback (для reject/modify)

### 3. State Management

- [ ] Добавить состояние `waitingForPlanApproval` в session state
- [ ] Сохранить pending approval request
- [ ] Обработать ответные сообщения (execution_completed, plan_rejected, etc.)

### 4. Error Handling

- [ ] Обработать timeout для approval (если пользователь не отвечает)
- [ ] Обработать ошибки при отправке decision
- [ ] Показать сообщение об ошибке пользователю

---

## 🎯 Заключение

План Approval механизм **полностью реализован** на стороне backend:

✅ **StreamChunk** - поля на верхнем уровне  
✅ **OrchestratorAgent** - создание approval request  
✅ **Messages Router** - обработка plan_decision  
✅ **PlanApprovalHandler** - обработка решений  
✅ **Gateway** - пересылка сообщений  
✅ **FSM** - state transitions  

**Следующий шаг:** Реализация на стороне клиента (IDE) согласно чеклисту выше.

---

**Автор:** AI Assistant  
**Дата последнего обновления:** 2026-02-01
