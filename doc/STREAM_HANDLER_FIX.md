# Stream Handler Fix для Plan Execution

## Проблема

При выполнении плана после одобрения возникала ошибка:

```
'NoneType' object has no attribute 'handle'
```

Это происходило потому, что `stream_handler` передавался как `None` в `execute_plan()`.

## Причина

В [`plan_approval_handler.py`](../codelab-ai-service/agent-runtime/app/domain/services/plan_approval_handler.py) на строке 187 был следующий код:

```python
execution_result = await self._execution_coordinator.execute_plan(
    plan_id=plan_id,
    session_id=session_id,
    session_service=self._session_service,
    stream_handler=None  # TODO: Pass stream_handler for progress updates
)
```

`PlanApprovalHandler` не получал `stream_handler` как зависимость и передавал `None` в `execute_plan()`, что приводило к ошибке при попытке вызвать `stream_handler.handle()` в `SubtaskExecutor`.

## Решение

### 1. Обновлен `PlanApprovalHandler`

**Файл:** `codelab-ai-service/agent-runtime/app/domain/services/plan_approval_handler.py`

#### Изменения:

1. **Добавлен import для `IStreamHandler`:**
   ```python
   if TYPE_CHECKING:
       # ...
       from ..interfaces.stream_handler import IStreamHandler
   ```

2. **Добавлен параметр `stream_handler` в `__init__()`:**
   ```python
   def __init__(
       self,
       approval_manager: "ApprovalManager",
       session_service: "SessionManagementService",
       fsm_orchestrator: "FSMOrchestrator",
       execution_coordinator: "ExecutionCoordinator",
       plan_repository: "PlanRepository",
       stream_handler: "IStreamHandler"  # ← Новый параметр
   ):
       # ...
       self._stream_handler = stream_handler
   ```

3. **Передача `stream_handler` в `execute_plan()`:**
   ```python
   execution_result = await self._execution_coordinator.execute_plan(
       plan_id=plan_id,
       session_id=session_id,
       session_service=self._session_service,
       stream_handler=self._stream_handler  # ← Используем self._stream_handler
   )
   ```

### 2. Обновлен `dependencies.py`

**Файл:** `codelab-ai-service/agent-runtime/app/core/dependencies.py`

#### Изменения в `get_plan_approval_handler()`:

```python
async def get_plan_approval_handler(
    approval_manager = Depends(get_approval_manager),
    session_service: SessionManagementService = Depends(get_session_management_service),
    execution_coordinator = Depends(get_execution_coordinator),
    fsm_orchestrator = Depends(get_fsm_orchestrator),
    plan_repository = Depends(get_plan_repository)
):
    from ..domain.services import PlanApprovalHandler
    from ..domain.interfaces.stream_handler import IStreamHandler
    from .dependencies_llm import (
        get_llm_client,
        get_llm_event_publisher,
        get_tool_registry,
        get_tool_filter_service,
        get_llm_response_processor
    )
    from ..application.handlers.stream_llm_response_handler import StreamLLMResponseHandler
    
    # Создать stream handler для выполнения подзадач
    stream_handler: IStreamHandler = StreamLLMResponseHandler(
        llm_client=get_llm_client(),
        tool_filter=get_tool_filter_service(get_tool_registry()),
        response_processor=get_llm_response_processor(),
        event_publisher=get_llm_event_publisher(),
        session_service=session_service,
        approval_manager=approval_manager
    )
    
    return PlanApprovalHandler(
        approval_manager=approval_manager,
        session_service=session_service,
        fsm_orchestrator=fsm_orchestrator,
        execution_coordinator=execution_coordinator,
        plan_repository=plan_repository,
        stream_handler=stream_handler  # ← Передаем stream_handler
    )
```

## Результат

Теперь при выполнении плана:

1. ✅ `PlanApprovalHandler` получает `stream_handler` при инициализации
2. ✅ `stream_handler` передается в `execute_plan()`
3. ✅ `ExecutionEngine` → `SubtaskExecutor` → `agent.process()` получают валидный `stream_handler`
4. ✅ Подзадачи могут выполняться через агентов с LLM вызовами

## Поток выполнения

```
User approves plan
    ↓
PlanApprovalHandler.handle()
    ↓
ExecutionCoordinator.execute_plan(stream_handler=self._stream_handler)
    ↓
ExecutionEngine.execute_plan(stream_handler)
    ↓
SubtaskExecutor.execute_subtask(stream_handler)
    ↓
agent.process(stream_handler)
    ↓
stream_handler.handle() ← Теперь работает!
```

## Тестирование

После этого исправления нужно протестировать:

1. ✅ План создается успешно
2. ✅ План одобряется пользователем
3. ✅ FSM transitions: plan_review → plan_execution → completed
4. ✅ Подзадачи выполняются без ошибок `'NoneType' object has no attribute 'handle'`
5. ⏳ Результаты выполнения подзадач корректно сохраняются
6. ⏳ План завершается со статусом COMPLETED

## Связанные файлы

- [`plan_approval_handler.py`](../codelab-ai-service/agent-runtime/app/domain/services/plan_approval_handler.py)
- [`dependencies.py`](../codelab-ai-service/agent-runtime/app/core/dependencies.py)
- [`execution_engine.py`](../codelab-ai-service/agent-runtime/app/domain/services/execution_engine.py)
- [`subtask_executor.py`](../codelab-ai-service/agent-runtime/app/domain/services/subtask_executor.py)
- [`stream_handler.py`](../codelab-ai-service/agent-runtime/app/domain/interfaces/stream_handler.py)
- [`stream_llm_response_handler.py`](../codelab-ai-service/agent-runtime/app/application/handlers/stream_llm_response_handler.py)
