# Исправление: ExecutionEngine ожидание HITL approval

## 🔴 Проблема

**ExecutionEngine продолжает выполнение следующих subtasks, не дожидаясь HITL approval для tool calls в текущей subtask.**

### Root Cause

Отсутствует механизм ожидания HITL approval между subtasks. После того, как LLM генерирует tool_call с `requires_approval=true`, ExecutionEngine сразу переходит к следующей subtask, не дожидаясь решения пользователя.

### Текущий flow

```
ExecutionEngine.execute_plan()
  └─> for subtask in all_subtasks:  # ПОСЛЕДОВАТЕЛЬНО
        └─> SubtaskExecutor.execute_subtask()
              └─> agent.process()
                    └─> stream_handler.handle()
                          └─> tool_call chunk (requires_approval=true)
                                ├─> Сохранить pending approval
                                └─> yield chunk (is_final=true)
                                      └─> ВОЗВРАТ → ExecutionEngine переходит к СЛЕДУЮЩЕЙ subtask ❌
```

## ✅ Решение

Добавить проверку pending approvals после выполнения каждой subtask и ждать их разрешения перед переходом к следующей.

### Новый flow

```
ExecutionEngine.execute_plan()
  └─> for subtask in all_subtasks:
        ├─> SubtaskExecutor.execute_subtask()
        │     └─> tool_call chunk (requires_approval=true)
        │
        ├─> ✅ Проверить pending approvals
        │
        ├─> ✅ Если есть - ЖДАТЬ разрешения
        │     └─> Polling ApprovalManager каждые 0.5s
        │           └─> Все resolved? → Продолжить
        │
        └─> Перейти к следующей subtask
```

## 📝 Изменения

### 1. ApprovalManager - добавить методы

**Файл**: `codelab-ai-service/agent-runtime/app/domain/services/approval_management.py`

```python
async def get_pending_by_session(
    self,
    session_id: str
) -> List[PendingApproval]:
    """
    Получить все pending approvals для сессии.
    
    Args:
        session_id: ID сессии
        
    Returns:
        Список pending approvals
    """
    return [
        approval for approval in self._pending_approvals.values()
        if approval.session_id == session_id and approval.status == "pending"
    ]
```

### 2. ExecutionEngine - добавить зависимость

**Файл**: `codelab-ai-service/agent-runtime/app/domain/services/execution_engine.py`

```python
def __init__(
    self,
    plan_repository: "PlanRepository",
    subtask_executor: SubtaskExecutor,
    dependency_resolver: DependencyResolver,
    approval_manager: "ApprovalManager",  # ✅ НОВОЕ
    max_parallel_tasks: int = 3
):
    self.plan_repository = plan_repository
    self.subtask_executor = subtask_executor
    self.dependency_resolver = dependency_resolver
    self.approval_manager = approval_manager  # ✅ НОВОЕ
    self.max_parallel_tasks = max_parallel_tasks
```

### 3. ExecutionEngine - добавить метод ожидания

**Файл**: `codelab-ai-service/agent-runtime/app/domain/services/execution_engine.py`

```python
async def _wait_for_approvals(
    self,
    session_id: str,
    initial_approval_ids: Set[str],
    timeout_seconds: int = 300
) -> None:
    """
    Ждать разрешения всех pending approvals.
    
    Args:
        session_id: ID сессии
        initial_approval_ids: Set ID approvals для ожидания
        timeout_seconds: Таймаут ожидания (по умолчанию 5 минут)
        
    Raises:
        ExecutionEngineError: При таймауте
    """
    import asyncio
    import time
    
    start_time = time.time()
    
    logger.info(
        f"Waiting for {len(initial_approval_ids)} approvals: "
        f"{list(initial_approval_ids)}"
    )
    
    while True:
        # Получить текущие pending approvals для сессии
        current_pending = await self.approval_manager.get_pending_by_session(session_id)
        current_pending_ids = {a.request_id for a in current_pending}
        
        # Проверить, остались ли наши approvals в pending
        still_pending = initial_approval_ids & current_pending_ids
        
        if not still_pending:
            # Все approvals разрешены
            logger.info(
                f"All {len(initial_approval_ids)} approvals resolved "
                f"after {time.time() - start_time:.1f}s"
            )
            return
        
        # Проверить таймаут
        elapsed = time.time() - start_time
        if elapsed > timeout_seconds:
            raise ExecutionEngineError(
                f"Timeout waiting for approvals after {elapsed:.1f}s. "
                f"Still pending: {list(still_pending)}"
            )
        
        # Логировать прогресс каждые 10 секунд
        if int(elapsed) % 10 == 0 and int(elapsed) > 0:
            logger.info(
                f"Still waiting for {len(still_pending)} approvals "
                f"({elapsed:.0f}s elapsed): {list(still_pending)}"
            )
        
        # Подождать перед следующей проверкой
        await asyncio.sleep(0.5)
```

### 4. ExecutionEngine - модифицировать execute_plan()

**Файл**: `codelab-ai-service/agent-runtime/app/domain/services/execution_engine.py`

**Место**: После строки 244 (после выполнения subtask)

```python
# После выполнения subtask и сбора результата

# ✅ НОВОЕ: Проверить pending approvals после выполнения subtask
pending_approvals = await self.approval_manager.get_pending_by_session(session_id)

if pending_approvals:
    pending_ids = {a.request_id for a in pending_approvals}
    logger.info(
        f"Subtask {subtask_id} has {len(pending_approvals)} pending approvals. "
        f"Waiting for user decision..."
    )
    
    # Отправить status chunk о паузе
    yield StreamChunk(
        type="status",
        content=f"⏸️ Waiting for approval of {len(pending_approvals)} tool(s)",
        metadata={
            "subtask_id": subtask_id,
            "pending_approvals": list(pending_ids),
            "status": "waiting_approval"
        }
    )
    
    # Ждать разрешения всех pending approvals
    try:
        await self._wait_for_approvals(
            session_id=session_id,
            initial_approval_ids=pending_ids,
            timeout_seconds=300
        )
        
        logger.info(f"All approvals resolved for subtask {subtask_id}, continuing...")
        
        # Отправить status chunk о продолжении
        yield StreamChunk(
            type="status",
            content="▶️ Approvals resolved, continuing execution",
            metadata={
                "subtask_id": subtask_id,
                "status": "resumed"
            }
        )
    except ExecutionEngineError as e:
        logger.error(f"Approval timeout for subtask {subtask_id}: {e}")
        errors[subtask_id] = str(e)
        
        # Отправить error chunk
        yield StreamChunk(
            type="error",
            error=f"Approval timeout: {str(e)}",
            metadata={"subtask_id": subtask_id}
        )
        # Прервать выполнение плана
        break
```

### 5. dependencies.py - передать ApprovalManager

**Файл**: `codelab-ai-service/agent-runtime/app/core/dependencies.py`

```python
def get_execution_engine(
    plan_repository: PlanRepository = Depends(get_plan_repository),
    subtask_executor: SubtaskExecutor = Depends(get_subtask_executor),
    dependency_resolver: DependencyResolver = Depends(get_dependency_resolver),
    approval_manager: ApprovalManager = Depends(get_approval_manager)  # ✅ НОВОЕ
) -> ExecutionEngine:
    """Получить ExecutionEngine с зависимостями."""
    return ExecutionEngine(
        plan_repository=plan_repository,
        subtask_executor=subtask_executor,
        dependency_resolver=dependency_resolver,
        approval_manager=approval_manager,  # ✅ НОВОЕ
        max_parallel_tasks=3
    )
```

## ✅ Преимущества

1. **Минимальные изменения**: Только ExecutionEngine и ApprovalManager
2. **Использует существующую инфраструктуру**: ApprovalManager уже управляет approvals
3. **Простой flow**: Polling - понятный и надежный механизм
4. **Timeout protection**: Защита от бесконечного ожидания (5 минут)
5. **Прозрачность**: Клиент получает status chunks о паузе/возобновлении

## 📋 Чеклист реализации

- [ ] Добавить `get_pending_by_session()` в ApprovalManager
- [ ] Добавить `approval_manager` в ExecutionEngine.__init__()
- [ ] Добавить `_wait_for_approvals()` в ExecutionEngine
- [ ] Модифицировать `execute_plan()` для проверки approvals
- [ ] Обновить `dependencies.py` для передачи ApprovalManager
- [ ] Протестировать с реальным HITL approval

## 🎯 Результат

После реализации:
- ✅ ExecutionEngine будет **ждать** HITL approval перед переходом к следующей subtask
- ✅ Клиент получит уведомления о паузе (`waiting_approval`) и возобновлении (`resumed`)
- ✅ Timeout (5 минут) защитит от бесконечного ожидания
- ✅ Архитектура останется чистой и понятной
