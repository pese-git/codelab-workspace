# Решение: Автоматическое одобрение инструментов во время выполнения плана

## Проблема

После подтверждения плана пользователь ожидает автоматического выполнения всех подзадач, но система запрашивает подтверждение HITL для каждого инструмента (write_file, execute_command и т.д.).

**Результат:** План не выполняется автоматически, требуется подтверждение на каждом шаге.

## Решение

Добавить флаг `auto_approve_tools` в ExecutionPlan и проверять его при вызове инструментов.

### Шаг 1: Добавить флаг в ExecutionPlan

**Файл:** `codelab-ai-service/agent-runtime/app/models/schemas.py`

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
    requires_approval: bool = Field(default=True, description="Whether plan requires user approval")
    is_approved: bool = Field(default=False, description="Whether plan was approved by user")
    auto_approve_tools: bool = Field(default=True, description="Auto-approve tools during plan execution")  # ← НОВОЕ
```

### Шаг 2: Установить флаг при подтверждении плана

**Файл:** `codelab-ai-service/agent-runtime/app/api/v1/endpoints.py`

Строка 141:

```python
if decision == PlanDecision.APPROVE:
    logger.info(f"Plan APPROVED: executing {len(plan.subtasks)} subtasks")
    
    # Mark plan as approved
    plan.is_approved = True
    plan.auto_approve_tools = True  # ← ДОБАВИТЬ: Автоматически одобрять инструменты
    
    # Update plan in session manager to persist the change
    async_session_mgr.set_plan(request.session_id, plan)
```

Строка 176 (для EDIT):

```python
plan.is_approved = True
plan.auto_approve_tools = True  # ← ДОБАВИТЬ
```

### Шаг 3: Проверять флаг при вызове инструментов

**Файл:** `codelab-ai-service/agent-runtime/app/services/llm_stream_service.py`

Найти место, где проверяется HITL (примерно строка 150-200), и добавить проверку:

```python
# Проверить, нужно ли HITL подтверждение
requires_hitl = hitl_policy_service.requires_approval(tool_name)

# Проверить, выполняется ли план с auto_approve
plan = session_mgr.get_plan(session_id)
if plan and plan.auto_approve_tools and plan.is_approved:
    # План подтвержден и включено автоматическое одобрение
    logger.info(
        f"Auto-approving tool {tool_name} during plan execution "
        f"(plan_id={plan.plan_id})"
    )
    requires_hitl = False  # Отключить HITL для этого инструмента

if requires_hitl:
    # Обычный HITL flow
    # ...
else:
    # Выполнить инструмент напрямую
    # ...
```

### Шаг 4: Сбросить флаг после завершения плана

**Файл:** `codelab-ai-service/agent-runtime/app/services/multi_agent_orchestrator.py`

Строка 381 (в конце `_execute_plan`):

```python
# Clear the plan
session_mgr.clear_plan(session_id)

# Reset to orchestrator
context.switch_agent(AgentType.ORCHESTRATOR, "Plan execution complete")
```

Флаг автоматически сбросится при удалении плана.

## Альтернативное решение (более простое)

Если не хочется изменять модель ExecutionPlan, можно использовать временный флаг в session_mgr:

### Вариант 2: Использовать временный флаг в SessionManager

**Файл:** `codelab-ai-service/agent-runtime/app/services/session_manager_async.py`

Добавить методы:

```python
def set_auto_approve_mode(self, session_id: str, enabled: bool) -> None:
    """
    Enable/disable auto-approve mode for a session.
    
    When enabled, all tool calls will be auto-approved without HITL.
    
    Args:
        session_id: Session identifier
        enabled: Whether to enable auto-approve mode
    """
    if not hasattr(self, '_auto_approve_sessions'):
        self._auto_approve_sessions = set()
    
    if enabled:
        self._auto_approve_sessions.add(session_id)
        logger.info(f"Enabled auto-approve mode for session {session_id}")
    else:
        self._auto_approve_sessions.discard(session_id)
        logger.info(f"Disabled auto-approve mode for session {session_id}")

def is_auto_approve_enabled(self, session_id: str) -> bool:
    """
    Check if auto-approve mode is enabled for a session.
    
    Args:
        session_id: Session identifier
        
    Returns:
        True if auto-approve is enabled, False otherwise
    """
    if not hasattr(self, '_auto_approve_sessions'):
        self._auto_approve_sessions = set()
    
    return session_id in self._auto_approve_sessions
```

**Файл:** `codelab-ai-service/agent-runtime/app/services/multi_agent_orchestrator.py`

В начале `_execute_plan` (строка 236):

```python
async def _execute_plan(
    self,
    session_id: str,
    session_mgr: "AsyncSessionManager",
    context: Any
) -> AsyncGenerator[StreamChunk, None]:
    """Execute an execution plan subtask by subtask."""
    
    # Enable auto-approve mode for plan execution
    session_mgr.set_auto_approve_mode(session_id, True)
    
    try:
        plan = session_mgr.get_plan(session_id)
        # ... остальной код ...
        
    finally:
        # Disable auto-approve mode after plan execution
        session_mgr.set_auto_approve_mode(session_id, False)
```

**Файл:** `codelab-ai-service/agent-runtime/app/services/llm_stream_service.py`

В месте проверки HITL:

```python
# Проверить, нужно ли HITL подтверждение
requires_hitl = hitl_policy_service.requires_approval(tool_name)

# Проверить, включен ли режим автоматического одобрения
if session_mgr.is_auto_approve_enabled(session_id):
    logger.info(
        f"Auto-approving tool {tool_name} (auto-approve mode enabled for session)"
    )
    requires_hitl = False

if requires_hitl:
    # Обычный HITL flow
    # ...
```

## Рекомендация

**Используйте Вариант 2** (временный флаг в SessionManager), потому что:

✅ Не требует изменения модели ExecutionPlan
✅ Проще реализовать
✅ Автоматически сбрасывается после выполнения плана
✅ Не требует миграции данных
✅ Легко тестировать

## Поток выполнения после исправления

```
User: Подтверждает план (plan_decision: approve)
  ↓
API: plan.is_approved = True
  ↓
MultiAgentOrchestrator: _execute_plan()
  ↓
SessionManager: set_auto_approve_mode(session_id, True)
  ↓
Subtask 1: "Создать структуру"
  ↓
Coder: Вызывает write_file(...)
  ↓
LLM Stream Service: Проверяет is_auto_approve_enabled() → True
  ↓
LLM Stream Service: Пропускает HITL, выполняет инструмент напрямую
  ↓
Subtask 2: "Создать модели"
  ↓
Coder: Вызывает write_file(...)
  ↓
LLM Stream Service: Автоматически одобряет и выполняет
  ↓
... все подзадачи выполняются автоматически ...
  ↓
MultiAgentOrchestrator: План завершен
  ↓
SessionManager: set_auto_approve_mode(session_id, False)
  ↓
Result: "Plan Execution Complete" с Completed: 8
```

## Безопасность

### Вопрос: Не опасно ли автоматически одобрять все инструменты?

**Ответ:** Нет, потому что:

1. **Пользователь уже подтвердил план** - он видел все подзадачи и согласился с ними
2. **Автоматическое одобрение работает только во время выполнения плана** - после завершения плана режим отключается
3. **План создан Architect агентом** - который специализируется на планировании и понимает, какие операции безопасны
4. **Пользователь может отклонить план** - если он не согласен с какими-то операциями

### Дополнительная безопасность (опционально)

Можно добавить список "опасных" инструментов, которые всегда требуют подтверждения:

```python
ALWAYS_REQUIRE_APPROVAL = [
    "execute_command",  # Выполнение команд всегда требует подтверждения
    "delete_file",      # Удаление файлов всегда требует подтверждения
]

# В llm_stream_service.py
if tool_name in ALWAYS_REQUIRE_APPROVAL:
    requires_hitl = True  # Всегда требовать подтверждения
elif session_mgr.is_auto_approve_enabled(session_id):
    requires_hitl = False  # Автоматически одобрить
```

Но для начала можно использовать простой вариант без дополнительных проверок.
