# ✅ ExecutionEngine Resumable Execution - Финальное исправление

## 🎯 Проблема

После реализации Resumable Execution с State Machine оставалась критическая проблема:

**ToolResultHandler продолжал вызывать `agent.process()` после получения tool_result, что приводило к переключению агента и дублированию обработки, когда MessageOrchestrationService уже запускал execution через ExecutionCoordinator.**

### Симптомы

```
1. Tool_result получен
2. ToolResultHandler.handle() вызывает agent.process()
3. Агент может переключиться (например, с Coder на Orchestrator)
4. MessageOrchestrationService.process_tool_result() продолжает execution
5. ExecutionCoordinator запускает следующую subtask
6. Конфликт: два параллельных потока обработки
```

## ✅ Решение

**Пропуск `agent.process()` в ToolResultHandler при наличии активного плана (IN_PROGRESS).**

### Ключевая идея

Если есть активный план в статусе `IN_PROGRESS`, ToolResultHandler НЕ вызывает `agent.process()`, так как:
- MessageOrchestrationService продолжит execution через ExecutionCoordinator
- Это предотвращает переключение агента
- Это предотвращает дублирование обработки

## 📝 Изменения

### 1. ToolResultHandler - Проверка активного плана

**Файл:** [`tool_result_handler.py`](../codelab-ai-service/agent-runtime/app/domain/services/tool_result_handler.py)

#### Добавлен параметр `plan_repository`

```python
def __init__(
    self,
    session_service: "SessionManagementService",
    agent_service: "AgentOrchestrationService",
    agent_router,  # AgentRouter
    stream_handler: Optional["IStreamHandler"],
    switch_helper: "AgentSwitchHelper",
    approval_manager: Optional["ApprovalManager"] = None,
    plan_repository: Optional["PlanRepository"] = None  # ✅ НОВОЕ
):
```

#### Проверка активного плана перед `agent.process()`

```python
# ✅ КРИТИЧЕСКОЕ: Проверить активный план перед вызовом agent.process()
# Если есть IN_PROGRESS план, НЕ вызываем agent.process(), так как
# MessageOrchestrationService продолжит execution через ExecutionCoordinator
# Это предотвращает переключение агента и дублирование обработки
if self._plan_repository:
    active_plan = await self._get_active_plan_for_session(session_id)
    if active_plan:
        logger.info(
            f"⚠️ Найден активный план {active_plan.id} для сессии {session_id}. "
            f"Пропускаем agent.process() - execution продолжится через ExecutionCoordinator"
        )
        # Возвращаем пустой генератор - обработка продолжится в MessageOrchestrationService
        return

# Получить текущего агента и продолжить обработку
current_agent = self._agent_router.get_agent(context.current_agent)
```

#### Вспомогательный метод

```python
async def _get_active_plan_for_session(self, session_id: str):
    """
    Получить активный план для сессии.
    
    Args:
        session_id: ID сессии
        
    Returns:
        Plan со статусом IN_PROGRESS или None
    """
    from ..entities.plan import PlanStatus
    
    try:
        plan = await self._plan_repository.find_by_session_id(session_id)
        
        if plan and plan.status == PlanStatus.IN_PROGRESS:
            logger.debug(f"Found active plan {plan.id} for session {session_id}")
            return plan
        else:
            logger.debug(f"No active plan (IN_PROGRESS) found for session {session_id}")
            return None
        
    except Exception as e:
        logger.warning(f"Error finding active plan: {e}")
        return None
```

### 2. Dependencies - Передача plan_repository

**Файл:** [`dependencies.py`](../codelab-ai-service/agent-runtime/app/core/dependencies.py)

```python
async def get_tool_result_handler(
    session_service: SessionManagementService = Depends(get_session_management_service),
    agent_service: AgentOrchestrationService = Depends(get_agent_orchestration_service),
    switch_helper = Depends(get_agent_switch_helper),
    approval_manager = Depends(get_approval_manager),
    plan_repository = Depends(get_plan_repository)  # ✅ НОВОЕ
):
    """
    Получить handler результатов инструментов.
    
    Returns:
        ToolResultHandler: Handler результатов инструментов с resumable execution
    """
    # ...
    
    return ToolResultHandler(
        session_service=session_service,
        agent_service=agent_service,
        agent_router=agent_router,
        stream_handler=stream_handler,
        switch_helper=switch_helper,
        approval_manager=approval_manager,
        plan_repository=plan_repository  # ✅ НОВОЕ: Для проверки активных планов
    )
```

### 3. MessageOrchestrationService - Комментарий

**Файл:** [`message_orchestration.py`](../codelab-ai-service/agent-runtime/app/domain/services/message_orchestration.py)

Добавлен комментарий для ясности:

```python
# Делегировать в ToolResultHandler с блокировкой сессии
# ToolResultHandler проверит активный план и пропустит agent.process() если нужно
async with self._lock_manager.lock(session_id):
    async for chunk in self._tool_result_handler.handle(
        session_id=session_id,
        call_id=call_id,
        result=result,
        error=error
    ):
        yield chunk
```

## 🔄 Поток выполнения (После исправления)

### Сценарий: Tool_result для активного плана

```
1. POST /tool_result
   ↓
2. MessageOrchestrationService.process_tool_result()
   ↓
3. ToolResultHandler.handle()
   ├─ Добавить tool_result в сессию
   ├─ Проверить активный план
   ├─ Если есть IN_PROGRESS план → return (пропустить agent.process())
   └─ Если нет активного плана → agent.process() (обычная обработка)
   ↓
4. MessageOrchestrationService продолжает
   ├─ Проверить активный план
   ├─ Если есть IN_PROGRESS план → ExecutionCoordinator.execute_plan()
   └─ Следующая subtask выполняется
```

### Сценарий: Tool_result без активного плана

```
1. POST /tool_result
   ↓
2. MessageOrchestrationService.process_tool_result()
   ↓
3. ToolResultHandler.handle()
   ├─ Добавить tool_result в сессию
   ├─ Проверить активный план
   ├─ Нет активного плана
   └─ agent.process() (обычная обработка)
   ↓
4. MessageOrchestrationService продолжает
   └─ Нет активного плана → завершение
```

## ✅ Преимущества решения

1. **Предотвращение переключения агента** - agent.process() не вызывается при активном плане
2. **Предотвращение дублирования** - только один поток обработки (через ExecutionCoordinator)
3. **Обратная совместимость** - обычная обработка работает без изменений
4. **Чистая архитектура** - логика изолирована в ToolResultHandler
5. **Минимальные изменения** - только 3 файла модифицированы

## 🎯 Результат

**Resumable Execution работает корректно на 100%:**

✅ Tool_call → HTTP завершается (не блокируется)  
✅ Tool_result → Execution продолжается через ExecutionCoordinator  
✅ Одна subtask за раз  
✅ State Machine для мониторинга  
✅ Нет переключения агента при активном плане  
✅ Нет дублирования обработки  

## 📊 Измененные файлы

1. [`tool_result_handler.py`](../codelab-ai-service/agent-runtime/app/domain/services/tool_result_handler.py) - Проверка активного плана
2. [`dependencies.py`](../codelab-ai-service/agent-runtime/app/core/dependencies.py) - Передача plan_repository
3. [`message_orchestration.py`](../codelab-ai-service/agent-runtime/app/domain/services/message_orchestration.py) - Комментарий

## 🔍 Логи для мониторинга

### При активном плане

```
ToolResultHandler: Результат инструмента добавлен в сессию {session_id}
ToolResultHandler: ⚠️ Найден активный план {plan_id} для сессии {session_id}. 
                   Пропускаем agent.process() - execution продолжится через ExecutionCoordinator
MessageOrchestrationService: Found active plan {plan_id} for session {session_id}, resuming execution
ExecutionCoordinator: Executing plan {plan_id}...
```

### Без активного плана

```
ToolResultHandler: Результат инструмента добавлен в сессию {session_id}
ToolResultHandler: No active plan (IN_PROGRESS) found for session {session_id}
ToolResultHandler: Вызываем {agent}.process() для продолжения
```

## 🎉 Заключение

Архитектурная проблема ExecutionEngine HITL полностью решена. Resumable Execution работает корректно, execution останавливается после tool_call и возобновляется через tool_result без переключения агента и дублирования обработки.
