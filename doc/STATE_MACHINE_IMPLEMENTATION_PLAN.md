# State Machine Implementation Plan для ExecutionEngine

## 🎯 Цель

Реализовать State Machine для управления жизненным циклом ExecutionEngine с поддержкой ожидания HITL approval.

## 📊 Архитектура State Machine

### States (Состояния)

```python
class ExecutionState(str, Enum):
    """Состояния выполнения плана"""
    RUNNING = "running"              # Выполняется subtask
    WAITING_APPROVAL = "waiting_approval"  # Ждет HITL approval
    RESUMED = "resumed"              # Approval получен, продолжаем
    COMPLETED = "completed"          # План завершен успешно
    FAILED = "failed"                # План завершен с ошибкой
    CANCELLED = "cancelled"          # План отменен пользователем
```

### Transitions (Переходы)

```
RUNNING → WAITING_APPROVAL  (когда есть pending approvals)
WAITING_APPROVAL → RESUMED  (когда все approvals resolved)
WAITING_APPROVAL → CANCELLED (когда timeout или user cancel)
RESUMED → RUNNING           (продолжить выполнение)
RUNNING → COMPLETED         (все subtasks выполнены)
RUNNING → FAILED            (subtask failed)
RUNNING → CANCELLED         (user cancel)
```

### State Diagram

```
    ┌─────────┐
    │ RUNNING │◄──────────┐
    └────┬────┘           │
         │                │
         │ pending        │ all resolved
         │ approvals      │
         ▼                │
  ┌──────────────────┐   │
  │ WAITING_APPROVAL │───┘
  └────┬─────────────┘
       │
       │ timeout/cancel
       ▼
  ┌───────────┐
  │ CANCELLED │
  └───────────┘
```

## 📝 Файлы для изменения

### 1. Создать новый файл: `execution_state.py`

**Путь**: `codelab-ai-service/agent-runtime/app/domain/entities/execution_state.py`

**Содержимое**:
```python
"""
Execution State Management для ExecutionEngine.

Управляет состояниями выполнения плана и transitions между ними.
"""

from enum import Enum
from typing import Optional, Set
from datetime import datetime, timezone
import logging

logger = logging.getLogger("agent-runtime.domain.execution_state")


class ExecutionState(str, Enum):
    """Состояния выполнения плана"""
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    RESUMED = "resumed"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionStateManager:
    """
    Менеджер состояний выполнения плана.
    
    Отвечает за:
    - Управление текущим состоянием
    - Валидацию transitions
    - Хранение истории transitions
    - Thread-safe операции
    """
    
    # Разрешенные transitions
    ALLOWED_TRANSITIONS = {
        ExecutionState.RUNNING: {
            ExecutionState.WAITING_APPROVAL,
            ExecutionState.COMPLETED,
            ExecutionState.FAILED,
            ExecutionState.CANCELLED
        },
        ExecutionState.WAITING_APPROVAL: {
            ExecutionState.RESUMED,
            ExecutionState.CANCELLED
        },
        ExecutionState.RESUMED: {
            ExecutionState.RUNNING
        },
        ExecutionState.COMPLETED: set(),  # Terminal state
        ExecutionState.FAILED: set(),     # Terminal state
        ExecutionState.CANCELLED: set()   # Terminal state
    }
    
    def __init__(self, plan_id: str, initial_state: ExecutionState = ExecutionState.RUNNING):
        """
        Инициализация state manager.
        
        Args:
            plan_id: ID плана
            initial_state: Начальное состояние
        """
        self.plan_id = plan_id
        self._current_state = initial_state
        self._transition_history = []
        self._state_metadata = {}
        
        # Записать начальное состояние
        self._record_transition(None, initial_state, "Initial state")
        
        logger.info(f"ExecutionStateManager initialized for plan {plan_id} in state {initial_state.value}")
    
    @property
    def current_state(self) -> ExecutionState:
        """Получить текущее состояние"""
        return self._current_state
    
    def can_transition_to(self, new_state: ExecutionState) -> bool:
        """
        Проверить, возможен ли переход в новое состояние.
        
        Args:
            new_state: Целевое состояние
            
        Returns:
            True если переход разрешен
        """
        allowed = self.ALLOWED_TRANSITIONS.get(self._current_state, set())
        return new_state in allowed
    
    def transition_to(
        self,
        new_state: ExecutionState,
        reason: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> None:
        """
        Выполнить переход в новое состояние.
        
        Args:
            new_state: Целевое состояние
            reason: Причина перехода
            metadata: Дополнительные данные
            
        Raises:
            ValueError: Если переход не разрешен
        """
        if not self.can_transition_to(new_state):
            raise ValueError(
                f"Invalid transition from {self._current_state.value} "
                f"to {new_state.value} for plan {self.plan_id}"
            )
        
        old_state = self._current_state
        self._current_state = new_state
        
        # Сохранить metadata
        if metadata:
            self._state_metadata[new_state.value] = metadata
        
        # Записать в историю
        self._record_transition(old_state, new_state, reason)
        
        logger.info(
            f"Plan {self.plan_id} transitioned from {old_state.value} "
            f"to {new_state.value}: {reason or 'No reason'}"
        )
    
    def is_terminal(self) -> bool:
        """Проверить, находится ли в терминальном состоянии"""
        return self._current_state in {
            ExecutionState.COMPLETED,
            ExecutionState.FAILED,
            ExecutionState.CANCELLED
        }
    
    def is_waiting_approval(self) -> bool:
        """Проверить, ждет ли approval"""
        return self._current_state == ExecutionState.WAITING_APPROVAL
    
    def get_transition_history(self) -> list:
        """Получить историю transitions"""
        return self._transition_history.copy()
    
    def get_state_metadata(self, state: ExecutionState) -> Optional[dict]:
        """Получить metadata для состояния"""
        return self._state_metadata.get(state.value)
    
    def _record_transition(
        self,
        from_state: Optional[ExecutionState],
        to_state: ExecutionState,
        reason: Optional[str]
    ) -> None:
        """Записать transition в историю"""
        self._transition_history.append({
            "from_state": from_state.value if from_state else None,
            "to_state": to_state.value,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    def to_dict(self) -> dict:
        """Преобразовать в словарь для сериализации"""
        return {
            "plan_id": self.plan_id,
            "current_state": self._current_state.value,
            "is_terminal": self.is_terminal(),
            "transition_history": self._transition_history,
            "state_metadata": self._state_metadata
        }
```

### 2. Модифицировать: `execution_engine.py`

**Изменения**:

1. Добавить import:
```python
from app.domain.entities.execution_state import ExecutionState, ExecutionStateManager
from app.domain.services.approval_management import ApprovalManager
```

2. Добавить в `__init__`:
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
    
    # State managers для активных executions
    self._state_managers: Dict[str, ExecutionStateManager] = {}
```

3. Добавить методы управления состоянием:
```python
def _get_state_manager(self, plan_id: str) -> ExecutionStateManager:
    """Получить или создать state manager для плана"""
    if plan_id not in self._state_managers:
        self._state_managers[plan_id] = ExecutionStateManager(plan_id)
    return self._state_managers[plan_id]

def _cleanup_state_manager(self, plan_id: str) -> None:
    """Удалить state manager после завершения"""
    if plan_id in self._state_managers:
        del self._state_managers[plan_id]
```

4. Добавить метод ожидания approval:
```python
async def _wait_for_approval_resolution(
    self,
    plan_id: str,
    session_id: str,
    pending_approval_ids: Set[str],
    timeout_seconds: int = 300
) -> None:
    """
    Ждать разрешения approvals с использованием state machine.
    
    Args:
        plan_id: ID плана
        session_id: ID сессии
        pending_approval_ids: Set ID approvals для ожидания
        timeout_seconds: Таймаут ожидания
        
    Raises:
        ExecutionEngineError: При таймауте или ошибке
    """
    import asyncio
    import time
    
    state_manager = self._get_state_manager(plan_id)
    
    # Переход в состояние WAITING_APPROVAL
    state_manager.transition_to(
        ExecutionState.WAITING_APPROVAL,
        reason=f"Waiting for {len(pending_approval_ids)} approvals",
        metadata={"approval_ids": list(pending_approval_ids)}
    )
    
    start_time = time.time()
    
    logger.info(
        f"Plan {plan_id} entered WAITING_APPROVAL state for "
        f"{len(pending_approval_ids)} approvals"
    )
    
    while state_manager.is_waiting_approval():
        # Получить текущие pending approvals
        current_pending = await self.approval_manager.get_pending_by_session(session_id)
        current_pending_ids = {a.request_id for a in current_pending}
        
        # Проверить, остались ли наши approvals в pending
        still_pending = pending_approval_ids & current_pending_ids
        
        if not still_pending:
            # Все approvals разрешены - переход в RESUMED
            elapsed = time.time() - start_time
            state_manager.transition_to(
                ExecutionState.RESUMED,
                reason=f"All approvals resolved after {elapsed:.1f}s"
            )
            logger.info(
                f"Plan {plan_id} transitioned to RESUMED after {elapsed:.1f}s"
            )
            return
        
        # Проверить таймаут
        elapsed = time.time() - start_time
        if elapsed > timeout_seconds:
            # Timeout - переход в CANCELLED
            state_manager.transition_to(
                ExecutionState.CANCELLED,
                reason=f"Approval timeout after {elapsed:.1f}s",
                metadata={"still_pending": list(still_pending)}
            )
            raise ExecutionEngineError(
                f"Timeout waiting for approvals after {elapsed:.1f}s. "
                f"Still pending: {list(still_pending)}"
            )
        
        # Логировать прогресс
        if int(elapsed) % 10 == 0 and int(elapsed) > 0:
            logger.info(
                f"Plan {plan_id} still waiting for {len(still_pending)} approvals "
                f"({elapsed:.0f}s elapsed)"
            )
        
        # Подождать перед следующей проверкой
        await asyncio.sleep(0.5)
```

5. Модифицировать `execute_plan()` - добавить после выполнения subtask:
```python
# После выполнения subtask (строка ~244)

# ✅ Проверить pending approvals
pending_approvals = await self.approval_manager.get_pending_by_session(session_id)

if pending_approvals:
    pending_ids = {a.request_id for a in pending_approvals}
    
    logger.info(
        f"Subtask {subtask_id} has {len(pending_approvals)} pending approvals"
    )
    
    # Отправить status chunk о паузе
    yield StreamChunk(
        type="status",
        content=f"⏸️ Waiting for approval of {len(pending_approvals)} tool(s)",
        metadata={
            "subtask_id": subtask_id,
            "pending_approvals": list(pending_ids),
            "status": "waiting_approval",
            "state": state_manager.current_state.value
        }
    )
    
    # Ждать разрешения approvals
    try:
        await self._wait_for_approval_resolution(
            plan_id=plan.id,
            session_id=session_id,
            pending_approval_ids=pending_ids,
            timeout_seconds=300
        )
        
        # Переход обратно в RUNNING
        state_manager.transition_to(
            ExecutionState.RUNNING,
            reason="Resuming execution after approval"
        )
        
        # Отправить status chunk о продолжении
        yield StreamChunk(
            type="status",
            content="▶️ Approvals resolved, continuing execution",
            metadata={
                "subtask_id": subtask_id,
                "status": "resumed",
                "state": state_manager.current_state.value
            }
        )
        
    except ExecutionEngineError as e:
        logger.error(f"Approval error for plan {plan.id}: {e}")
        errors[subtask_id] = str(e)
        
        # Отправить error chunk
        yield StreamChunk(
            type="error",
            error=f"Approval error: {str(e)}",
            metadata={
                "subtask_id": subtask_id,
                "state": state_manager.current_state.value
            }
        )
        # Прервать выполнение
        break
```

6. В конце `execute_plan()` - обновить финальные transitions:
```python
# После проверки результатов (строка ~256)

state_manager = self._get_state_manager(plan_id)

if failed_count == 0:
    plan.complete()
    state_manager.transition_to(
        ExecutionState.COMPLETED,
        reason="All subtasks completed successfully"
    )
    final_status = "completed"
else:
    plan.fail(f"Failed {failed_count} of {total_count} subtasks")
    state_manager.transition_to(
        ExecutionState.FAILED,
        reason=f"Failed {failed_count}/{total_count} subtasks"
    )
    final_status = "failed"

# Cleanup state manager
self._cleanup_state_manager(plan_id)
```

### 3. Модифицировать: `approval_management.py`

Добавить метод:
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

### 4. Модифицировать: `dependencies.py`

Обновить `get_execution_engine`:
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

## 📋 Чеклист реализации

- [ ] Создать `execution_state.py` с ExecutionState и ExecutionStateManager
- [ ] Добавить `approval_manager` в ExecutionEngine.__init__()
- [ ] Добавить `_state_managers` dict в ExecutionEngine
- [ ] Добавить `_get_state_manager()` и `_cleanup_state_manager()`
- [ ] Добавить `_wait_for_approval_resolution()` с state transitions
- [ ] Модифицировать `execute_plan()` для проверки approvals
- [ ] Добавить state transitions в начале и конце execution
- [ ] Добавить `get_pending_by_session()` в ApprovalManager
- [ ] Обновить `dependencies.py`
- [ ] Протестировать все transitions

## ✅ Преимущества State Machine

1. **Явное управление состоянием**: Всегда знаем, в каком состоянии execution
2. **Audit trail**: История transitions для debugging
3. **Валидация**: Невозможны недопустимые transitions
4. **Мониторинг**: Легко отслеживать состояние executions
5. **Расширяемость**: Легко добавить новые состояния

## 🎯 Результат

После реализации:
- ✅ ExecutionEngine управляется через State Machine
- ✅ Явные состояния для каждого этапа execution
- ✅ Валидация всех transitions
- ✅ История transitions для debugging
- ✅ Ожидание HITL approval через состояние WAITING_APPROVAL
