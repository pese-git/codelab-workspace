# Исправление выполнения плана Architect агентом с использованием HITL-подхода

## Проблема

Architect агент создает план выполнения задачи, но:
1. **Нет механизма подтверждения плана** - отсутствует явный approve/reject как для инструментов
2. **План не выполняется автоматически** - после создания плана нет передачи подзадач специализированным агентам
3. **Используется текстовый анализ** - вместо структурированного сообщения типа `plan_decision`

## Решение: Применить HITL-подход для планов

Используем тот же механизм, что и для approve/reject инструментов:
- Создать модели для решений по плану (аналог `HITLUserDecision`)
- Добавить обработку `plan_decision` в API (аналог `hitl_decision`)
- Сохранять планы в pending состоянии
- Обрабатывать approve/reject/edit для планов

## Архитектура решения

### 1. Модели данных

#### Файл: `app/models/plan_models.py` (новый)

```python
"""
Plan approval models - similar to HITL models but for execution plans.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class PlanDecision(str, Enum):
    """User decision for execution plan"""
    APPROVE = "approve"
    EDIT = "edit"
    REJECT = "reject"


class PlanUserDecision(BaseModel):
    """User decision on execution plan (message from IDE)"""
    type: Literal["plan_decision"] = Field(default="plan_decision")
    plan_id: str = Field(description="Plan identifier")
    decision: PlanDecision = Field(description="User decision")
    modified_subtasks: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Modified subtasks if decision is EDIT"
    )
    feedback: Optional[str] = Field(
        default=None,
        description="User feedback/reason for decision"
    )
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "type": "plan_decision",
                    "plan_id": "plan_abc123",
                    "decision": "approve"
                },
                {
                    "type": "plan_decision",
                    "plan_id": "plan_abc123",
                    "decision": "edit",
                    "modified_subtasks": [
                        {
                            "id": "subtask_1",
                            "description": "Modified description",
                            "agent": "coder"
                        }
                    ]
                },
                {
                    "type": "plan_decision",
                    "plan_id": "plan_abc123",
                    "decision": "reject",
                    "feedback": "This approach is not suitable"
                }
            ]
        }


class PlanAuditLog(BaseModel):
    """Audit log entry for plan decision"""
    session_id: str = Field(description="Session identifier")
    plan_id: str = Field(description="Plan identifier")
    original_task: str = Field(description="Original user task")
    decision: PlanDecision = Field(description="User decision")
    modified_subtasks: Optional[List[Dict[str, Any]]] = Field(default=None)
    feedback: Optional[str] = Field(default=None)
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_123",
                "plan_id": "plan_abc123",
                "original_task": "Create TODO app",
                "decision": "approve",
                "timestamp": "2024-01-01T12:00:00"
            }
        }
```

### 2. Обновить схемы

#### Файл: `app/models/schemas.py`

Добавить в `StreamChunk.type`:

```python
type: Literal[
    "assistant_message", 
    "tool_call", 
    "error", 
    "done", 
    "switch_agent", 
    "agent_switched", 
    "plan_notification",
    "plan_approved",      # ← Новый тип
    "plan_rejected"       # ← Новый тип
] = Field(description="Type of the stream chunk")
```

Добавить поле `requires_approval` в `ExecutionPlan`:

```python
class ExecutionPlan(BaseModel):
    """Execution plan for complex tasks"""
    
    plan_id: str = Field(description="Unique identifier for the plan")
    session_id: str = Field(description="Session this plan belongs to")
    original_task: str = Field(description="Original user task that triggered planning")
    subtasks: List[Subtask] = Field(description="List of subtasks to execute")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    current_subtask_index: int = Field(default=0, description="Index of currently executing subtask")
    is_complete: bool = Field(default=False, description="Whether all subtasks are complete")
    requires_approval: bool = Field(default=True, description="Whether plan requires user approval")  # ← Новое поле
    is_approved: bool = Field(default=False, description="Whether plan was approved by user")  # ← Новое поле
```

### 3. Менеджер планов

#### Файл: `app/services/plan_manager.py` (новый)

```python
"""
Plan Manager for managing execution plans and user decisions.

Similar to HITL Manager but for execution plans.
"""
import logging
from typing import Dict, List, Optional

from app.models.plan_models import PlanAuditLog, PlanDecision
from app.models.schemas import ExecutionPlan

logger = logging.getLogger("agent-runtime.plan_manager")

# Key for storing plan audit logs in AgentContext.metadata
PLAN_AUDIT_KEY = "plan_audit_logs"


def _get_agent_context_manager():
    """Lazy import to avoid circular dependency"""
    from app.services.agent_context_async import agent_context_manager
    return agent_context_manager


class PlanManager:
    """
    Manager for execution plans and user decisions.
    
    Stores plans in SessionManager and audit logs in AgentContext.
    """
    
    async def log_decision(
        self,
        session_id: str,
        plan_id: str,
        original_task: str,
        decision: PlanDecision,
        modified_subtasks: Optional[List[Dict]] = None,
        feedback: Optional[str] = None
    ) -> PlanAuditLog:
        """
        Log a user decision to audit log.
        
        Args:
            session_id: Session identifier
            plan_id: Plan identifier
            original_task: Original user task
            decision: User decision
            modified_subtasks: Modified subtasks (for EDIT)
            feedback: User feedback (for REJECT)
            
        Returns:
            Created PlanAuditLog
        """
        # Get or create context (async)
        context = await _get_agent_context_manager().get_or_create(session_id)
        
        # Initialize audit logs list if not exists
        if PLAN_AUDIT_KEY not in context.metadata:
            context.metadata[PLAN_AUDIT_KEY] = []
        
        # Create audit log entry
        audit_log = PlanAuditLog(
            session_id=session_id,
            plan_id=plan_id,
            original_task=original_task,
            decision=decision,
            modified_subtasks=modified_subtasks,
            feedback=feedback
        )
        
        # Store in context metadata
        context.metadata[PLAN_AUDIT_KEY].append(audit_log.model_dump())
        
        logger.info(
            f"Logged plan decision: session={session_id}, plan_id={plan_id}, "
            f"decision={decision.value}"
        )
        
        return audit_log
    
    def get_audit_logs(self, session_id: str) -> List[PlanAuditLog]:
        """
        Get all audit logs for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of PlanAuditLog objects
        """
        context = _get_agent_context_manager().get(session_id)
        if not context:
            return []
        
        audit_logs_data = context.metadata.get(PLAN_AUDIT_KEY, [])
        return [PlanAuditLog(**data) for data in audit_logs_data]


# Singleton instance
plan_manager = PlanManager()
```

### 4. Обновить Architect Agent

#### Файл: `app/agents/architect_agent.py`

Изменить строки 146-184:

```python
# Set pending confirmation state
session_mgr.set_pending_plan_confirmation(session_id)

# Mark plan as requiring approval
plan.requires_approval = True
plan.is_approved = False

# Emit detailed plan notification to user
plan_summary = f"**План выполнения задачи:** {len(subtasks)} подзадач\n\n"
for i, st in enumerate(subtasks, 1):
    plan_summary += f"{i}. **{st.description}**\n"
    plan_summary += f"   - Агент: {st.agent}\n"
    if st.estimated_time:
        plan_summary += f"   - Время: {st.estimated_time}\n"
    if st.dependencies:
        deps = [d for d in st.dependencies if d]
        if deps:
            plan_summary += f"   - Зависимости: {', '.join(deps)}\n"
    plan_summary += "\n"

plan_summary += (
    "**Требуется подтверждение:**\n"
    "- Отправьте `plan_decision` с `approve` для выполнения\n"
    "- Отправьте `plan_decision` с `reject` для отмены\n"
    "- Отправьте `plan_decision` с `edit` для изменения"
)

yield StreamChunk(
    type="plan_notification",
    content=plan_summary,
    metadata={
        "plan_id": plan.plan_id,
        "subtask_count": len(subtasks),
        "subtasks": [
            {
                "id": st.id,
                "description": st.description,
                "agent": st.agent,
                "estimated_time": st.estimated_time,
                "dependencies": st.dependencies
            }
            for st in subtasks
        ],
        "requires_approval": True  # ← Явно указываем
    },
    is_final=True  # ← Изменено с False на True
)
return
```

### 5. Обновить API endpoint

#### Файл: `app/api/v1/endpoints.py`

Добавить обработку `plan_decision` после строки 78:

```python
if message_type == "plan_decision":
    # Plan user decision (approve/edit/reject)
    plan_id = request.message.get("plan_id")
    decision_str = request.message.get("decision")
    modified_subtasks = request.message.get("modified_subtasks")
    feedback = request.message.get("feedback")
    
    logger.info(
        f"Received plan decision: plan_id={plan_id}, "
        f"decision={decision_str}, session={request.session_id}"
    )
    
    # Validate decision
    try:
        from app.models.plan_models import PlanDecision
        decision = PlanDecision(decision_str)
    except ValueError:
        error_msg = f"Invalid plan decision: {decision_str}"
        logger.error(error_msg)
        yield {
            "event": "error",
            "data": json.dumps({
                "type": "error",
                "error": error_msg,
                "is_final": True
            })
        }
        return
    
    # Get plan from session manager
    plan = async_session_mgr.get_plan(request.session_id)
    if not plan or plan.plan_id != plan_id:
        error_msg = f"No plan found with id={plan_id}"
        logger.error(error_msg)
        yield {
            "event": "error",
            "data": json.dumps({
                "type": "error",
                "error": error_msg,
                "is_final": True
            })
        }
        return
    
    # Log decision to audit
    from app.services.plan_manager import plan_manager
    await plan_manager.log_decision(
        session_id=request.session_id,
        plan_id=plan_id,
        original_task=plan.original_task,
        decision=decision,
        modified_subtasks=modified_subtasks,
        feedback=feedback
    )
    
    # Clear pending confirmation
    async_session_mgr.clear_pending_plan_confirmation(request.session_id)
    
    # Process decision
    if decision == PlanDecision.APPROVE:
        logger.info(f"Plan APPROVED: executing {len(plan.subtasks)} subtasks")
        
        # Mark plan as approved
        plan.is_approved = True
        
        # Notify about approval
        yield {
            "event": "message",
            "data": json.dumps({
                "type": "plan_approved",
                "content": f"План подтвержден. Начинаю выполнение {len(plan.subtasks)} подзадач...",
                "metadata": {
                    "plan_id": plan_id,
                    "subtask_count": len(plan.subtasks)
                },
                "is_final": False
            })
        }
        
        # Execute plan
        async for chunk in multi_agent_orchestrator.process_message(
            session_id=request.session_id,
            message=""  # Empty message to trigger plan execution
        ):
            chunk_dict = chunk.model_dump(exclude_none=True)
            chunk_json = json.dumps(chunk_dict)
            
            yield {
                "event": "message",
                "data": chunk_json
            }
            
            if chunk.is_final:
                break
        
    elif decision == PlanDecision.EDIT:
        logger.info(f"Plan EDITED: updating subtasks")
        
        if modified_subtasks:
            # Update plan with modified subtasks
            from app.models.schemas import Subtask, SubtaskStatus
            plan.subtasks = [
                Subtask(
                    id=st.get("id", f"subtask_{i+1}"),
                    description=st["description"],
                    agent=st["agent"],
                    estimated_time=st.get("estimated_time"),
                    status=SubtaskStatus.PENDING,
                    dependencies=st.get("dependencies", [])
                )
                for i, st in enumerate(modified_subtasks)
            ]
            plan.is_approved = True
            
            # Notify about edit
            yield {
                "event": "message",
                "data": json.dumps({
                    "type": "plan_approved",
                    "content": f"План обновлен. Начинаю выполнение {len(plan.subtasks)} подзадач...",
                    "metadata": {
                        "plan_id": plan_id,
                        "subtask_count": len(plan.subtasks),
                        "was_edited": True
                    },
                    "is_final": False
                })
            }
            
            # Execute modified plan
            async for chunk in multi_agent_orchestrator.process_message(
                session_id=request.session_id,
                message=""
            ):
                chunk_dict = chunk.model_dump(exclude_none=True)
                chunk_json = json.dumps(chunk_dict)
                
                yield {
                    "event": "message",
                    "data": chunk_json
                }
                
                if chunk.is_final:
                    break
        else:
            error_msg = "EDIT decision requires modified_subtasks"
            logger.error(error_msg)
            yield {
                "event": "error",
                "data": json.dumps({
                    "type": "error",
                    "error": error_msg,
                    "is_final": True
                })
            }
        
    elif decision == PlanDecision.REJECT:
        logger.info(f"Plan REJECTED: {feedback}")
        
        # Clear plan
        async_session_mgr.clear_plan(request.session_id)
        
        # Notify about rejection
        yield {
            "event": "message",
            "data": json.dumps({
                "type": "plan_rejected",
                "content": f"План отменен. {feedback or 'Чем могу помочь?'}",
                "metadata": {
                    "plan_id": plan_id,
                    "feedback": feedback
                },
                "is_final": True
            })
        }
    
    return

elif message_type == "hitl_decision":
    # ... существующий код для HITL ...
```

### 6. Обновить MultiAgentOrchestrator

#### Файл: `app/services/multi_agent_orchestrator.py`

Удалить строки 72-97 (старая логика подтверждения):

```python
# УДАЛИТЬ ЭТО:
# Check if there's a plan waiting for user confirmation
if async_session_mgr.has_pending_plan_confirmation(session_id):
    logger.info(f"Session {session_id} has plan waiting for confirmation")
    confirmation_result = self._handle_plan_confirmation(session_id, message, async_session_mgr, context)
    if confirmation_result["action"] == "execute":
        ...
```

Заменить на:

```python
# Check if there's an active execution plan that is approved
if async_session_mgr.has_plan(session_id):
    plan = async_session_mgr.get_plan(session_id)
    
    # If plan requires approval but not yet approved, wait for plan_decision
    if plan.requires_approval and not plan.is_approved:
        logger.info(f"Session {session_id} has plan waiting for approval")
        # Don't process message, wait for plan_decision
        yield StreamChunk(
            type="assistant_message",
            content="Ожидаю подтверждения плана...",
            is_final=True
        )
        return
    
    # Plan is approved, execute it
    if plan.is_approved and not plan.is_complete:
        logger.info(f"Session {session_id} has approved plan, continuing execution")
        async for chunk in self._execute_plan(session_id, async_session_mgr, context):
            yield chunk
        return
```

Удалить метод `_handle_plan_confirmation` (строки 398-432) - больше не нужен.

## Преимущества нового подхода

### 1. Единообразие с HITL
- Используется тот же паттерн approve/edit/reject
- Структурированные сообщения вместо текстового анализа
- Audit logging для всех решений

### 2. Надежность
- Явное состояние `requires_approval` и `is_approved`
- Нет зависимости от распознавания текста
- Четкий протокол взаимодействия

### 3. Расширяемость
- Легко добавить новые типы решений
- Можно добавить таймауты
- Поддержка редактирования плана

### 4. Персистентность
- Audit logs сохраняются в AgentContext
- Планы сохраняются в SessionManager
- Восстановление после перезапуска

## Протокол взаимодействия

### 1. Создание плана

```
User → Agent Runtime: POST /agent/message/stream
{
  "session_id": "session_123",
  "message": {
    "type": "user_message",
    "content": "Создай TODO приложение"
  }
}

Agent Runtime → User: SSE stream
{
  "type": "switch_agent",
  "metadata": {"target_agent": "architect"}
}

{
  "type": "plan_notification",
  "content": "План выполнения задачи: 5 подзадач...",
  "metadata": {
    "plan_id": "plan_abc123",
    "subtask_count": 5,
    "subtasks": [...],
    "requires_approval": true
  },
  "is_final": true
}
```

### 2. Подтверждение плана

```
User → Agent Runtime: POST /agent/message/stream
{
  "session_id": "session_123",
  "message": {
    "type": "plan_decision",
    "plan_id": "plan_abc123",
    "decision": "approve"
  }
}

Agent Runtime → User: SSE stream
{
  "type": "plan_approved",
  "content": "План подтвержден. Начинаю выполнение 5 подзадач...",
  "is_final": false
}

{
  "type": "assistant_message",
  "content": "Subtask 1/5: Создание структуры проекта",
  "metadata": {"subtask_id": "subtask_1", "subtask_status": "in_progress"},
  "is_final": false
}

... выполнение подзадач ...

{
  "type": "assistant_message",
  "content": "Plan Execution Complete\n- Total: 5\n- Completed: 5\n- Failed: 0",
  "is_final": true
}
```

### 3. Редактирование плана

```
User → Agent Runtime: POST /agent/message/stream
{
  "session_id": "session_123",
  "message": {
    "type": "plan_decision",
    "plan_id": "plan_abc123",
    "decision": "edit",
    "modified_subtasks": [
      {
        "id": "subtask_1",
        "description": "Измененное описание",
        "agent": "coder",
        "estimated_time": "3 min"
      },
      ...
    ]
  }
}
```

### 4. Отклонение плана

```
User → Agent Runtime: POST /agent/message/stream
{
  "session_id": "session_123",
  "message": {
    "type": "plan_decision",
    "plan_id": "plan_abc123",
    "decision": "reject",
    "feedback": "Этот подход не подходит"
  }
}

Agent Runtime → User: SSE stream
{
  "type": "plan_rejected",
  "content": "План отменен. Этот подход не подходит",
  "metadata": {
    "plan_id": "plan_abc123",
    "feedback": "Этот подход не подходит"
  },
  "is_final": true
}
```

## Изменения в IDE (Flutter)

### 1. Обработка `plan_notification`

```dart
// В StreamChunk handler
if (chunk.type == 'plan_notification') {
  final planId = chunk.metadata?['plan_id'];
  final subtasks = chunk.metadata?['subtasks'];
  final requiresApproval = chunk.metadata?['requires_approval'] ?? false;
  
  if (requiresApproval) {
    // Показать UI для подтверждения плана
    _showPlanApprovalDialog(
      planId: planId,
      subtasks: subtasks,
      onApprove: () => _sendPlanDecision(planId, 'approve'),
      onReject: (feedback) => _sendPlanDecision(planId, 'reject', feedback: feedback),
      onEdit: (modifiedSubtasks) => _sendPlanDecision(planId, 'edit', modifiedSubtasks: modifiedSubtasks),
    );
  }
}
```

### 2. Отправка решения

```dart
Future<void> _sendPlanDecision(
  String planId,
  String decision, {
  String? feedback,
  List<Map<String, dynamic>>? modifiedSubtasks,
}) async {
  final message = {
    'type': 'plan_decision',
    'plan_id': planId,
    'decision': decision,
    if (feedback != null) 'feedback': feedback,
    if (modifiedSubtasks != null) 'modified_subtasks': modifiedSubtasks,
  };
  
  await _agentService.sendMessage(sessionId, message);
}
```

### 3. UI компонент для подтверждения

```dart
class PlanApprovalDialog extends StatelessWidget {
  final String planId;
  final List<dynamic> subtasks;
  final VoidCallback onApprove;
  final Function(String feedback) onReject;
  final Function(List<Map<String, dynamic>>) onEdit;
  
  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text('План выполнения задачи'),
      content: Column(
        children: [
          Text('${subtasks.length} подзадач:'),
          ...subtasks.map((st) => ListTile(
            title: Text(st['description']),
            subtitle: Text('Агент: ${st['agent']}'),
          )),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () {
            Navigator.pop(context);
            _showRejectDialog(context, onReject);
          },
          child: Text('Отклонить'),
        ),
        TextButton(
          onPressed: () {
            Navigator.pop(context);
            _showEditDialog(context, subtasks, onEdit);
          },
          child: Text('Редактировать'),
        ),
        ElevatedButton(
          onPressed: () {
            Navigator.pop(context);
            onApprove();
          },
          child: Text('Подтвердить'),
        ),
      ],
    );
  }
}
```

## Тестирование

### Тест 1: Создание и подтверждение плана

```bash
# 1. Создать план
curl -X POST http://localhost:8001/api/v1/agent/message/stream \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test_123",
    "message": {
      "type": "user_message",
      "content": "Создай простое TODO приложение"
    }
  }'

# Ожидаемый результат:
# - plan_notification с requires_approval=true

# 2. Подтвердить план
curl -X POST http://localhost:8001/api/v1/agent/message/stream \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test_123",
    "message": {
      "type": "plan_decision",
      "plan_id": "plan_abc123",
      "decision": "approve"
    }
  }'

# Ожидаемый результат:
# - plan_approved
# - Последовательное выполнение подзадач
# - Финальное сообщение о завершении
```

### Тест 2: Отклонение плана

```bash
curl -X POST http://localhost:8001/api/v1/agent/message/stream \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test_123",
    "message": {
      "type": "plan_decision",
      "plan_id": "plan_abc123",
      "decision": "reject",
      "feedback": "Этот подход слишком сложный"
    }
  }'

# Ожидаемый результат:
# - plan_rejected
# - План удален из session_manager
```

### Тест 3: Редактирование плана

```bash
curl -X POST http://localhost:8001/api/v1/agent/message/stream \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test_123",
    "message": {
      "type": "plan_decision",
      "plan_id": "plan_abc123",
      "decision": "edit",
      "modified_subtasks": [
        {
          "id": "subtask_1",
          "description": "Измененное описание первой подзадачи",
          "agent": "coder",
          "estimated_time": "3 min"
        }
      ]
    }
  }'

# Ожидаемый результат:
# - plan_approved с was_edited=true
# - Выполнение измененного плана
```

## Миграция существующего кода

### Шаг 1: Создать новые файлы

```bash
touch codelab-ai-service/agent-runtime/app/models/plan_models.py
touch codelab-ai-service/agent-runtime/app/services/plan_manager.py
```

### Шаг 2: Обновить существующие файлы

1. [`app/models/schemas.py`](codelab-ai-service/agent-runtime/app/models/schemas.py) - добавить поля в `ExecutionPlan` и типы в `StreamChunk`
2. [`app/agents/architect_agent.py`](codelab-ai-service/agent-runtime/app/agents/architect_agent.py) - изменить `is_final` и добавить поля плана
3. [`app/api/v1/endpoints.py`](codelab-ai-service/agent-runtime/app/api/v1/endpoints.py) - добавить обработку `plan_decision`
4. [`app/services/multi_agent_orchestrator.py`](codelab-ai-service/agent-runtime/app/services/multi_agent_orchestrator.py) - заменить логику подтверждения

### Шаг 3: Тестирование

```bash
# Запустить сервис
cd codelab-ai-service/agent-runtime
python -m app.main

# Запустить тесты
pytest tests/test_plan_approval.py -v
```

## Заключение

Новый подход использует проверенный механизм HITL для подтверждения планов:

✅ **Единообразие** - тот же паттерн, что и для инструментов
✅ **Надежность** - структурированные сообщения вместо текста
✅ **Расширяемость** - легко добавить новые функции
✅ **Персистентность** - audit logging и восстановление
✅ **UX** - четкий UI для approve/reject/edit

После внесения изменений:
1. Architect создает план → отправляет `plan_notification`
2. IDE показывает диалог подтверждения
3. Пользователь выбирает approve/reject/edit
4. IDE отправляет `plan_decision`
5. Agent Runtime выполняет план или отменяет его
6. Результаты возвращаются пользователю

Все компоненты работают согласованно, используя единый протокол взаимодействия.