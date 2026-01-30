# FSM Orchestrator - Детальный технический дизайн

**Версия:** 1.0  
**Дата:** 30 января 2026

---

## 1. Обзор компонента

FSM Orchestrator — это сердце системы планирования. Он управляет жизненным циклом задачи, переводя её через различные состояния.

### Ответственности
- Управление состоянием задачи через FSM
- Валидация переходов между состояниями
- Публикация событий состояний
- Обработка исключительных ситуаций
- Логирование всех переходов

---

## 2. Структура файлов

```
app/domain/entities/
├── fsm_state.py              # Enum состояний FSM

app/domain/services/
├── fsm_orchestrator.py       # Основная реализация FSM
├── fsm_transition_rules.py   # Правила переходов
└── fsm_context.py            # Контекст FSM для сессии

app/domain/repositories/
└── fsm_state_repository.py   # Персистентность состояний

tests/
└── test_fsm_orchestrator.py  # Комплексные тесты FSM
```

---

## 3. Реализация компонента

### 3.1 FSMState enum

```python
# app/domain/entities/fsm_state.py

from enum import Enum

class FSMState(str, Enum):
    """Состояния конечного автомата для управления жизненным циклом задачи"""
    
    IDLE = "idle"
    """Начальное состояние. Ожидание новой задачи"""
    
    CLASSIFY = "classify"
    """Классификация задачи (атомарная vs неатомарная)"""
    
    PLAN_REQUIRED = "plan_required"
    """Задача требует планирования"""
    
    ARCHITECT_PLANNING = "architect_planning"
    """Architect создает план"""
    
    EXECUTION = "execution"
    """Исполнение плана (subtasks выполняются)"""
    
    ERROR_HANDLING = "error_handling"
    """Обработка ошибки из subtask"""
    
    COMPLETED = "completed"
    """Задача успешно завершена"""
```

### 3.2 FSMTransitionRules

```python
# app/domain/services/fsm_transition_rules.py

from typing import Dict, Set
from .fsm_state import FSMState

class FSMTransitionRules:
    """Правила переходов между состояниями FSM"""
    
    # Матрица валидных переходов
    VALID_TRANSITIONS: Dict[FSMState, Set[str]] = {
        FSMState.IDLE: {"receive_message"},
        
        FSMState.CLASSIFY: {
            "is_atomic_true",      # → EXECUTION
            "is_atomic_false",     # → PLAN_REQUIRED
            "classification_error",  # → IDLE
        },
        
        FSMState.PLAN_REQUIRED: {
            "route_to_architect",  # → ARCHITECT_PLANNING
        },
        
        FSMState.ARCHITECT_PLANNING: {
            "plan_created",        # → EXECUTION
            "planning_failed",     # → ERROR_HANDLING
        },
        
        FSMState.EXECUTION: {
            "all_subtasks_done",   # → COMPLETED
            "subtask_failed",      # → ERROR_HANDLING
        },
        
        FSMState.ERROR_HANDLING: {
            "requires_replanning",  # → ARCHITECT_PLANNING
            "retry_subtask",       # → EXECUTION
            "plan_cancelled",      # → COMPLETED
        },
        
        FSMState.COMPLETED: {
            "reset",               # → IDLE
        },
    }
    
    # Отображение событий на целевые состояния
    TRANSITIONS: Dict[tuple, FSMState] = {
        (FSMState.IDLE, "receive_message"): FSMState.CLASSIFY,
        (FSMState.CLASSIFY, "is_atomic_true"): FSMState.EXECUTION,
        (FSMState.CLASSIFY, "is_atomic_false"): FSMState.PLAN_REQUIRED,
        (FSMState.CLASSIFY, "classification_error"): FSMState.IDLE,
        (FSMState.PLAN_REQUIRED, "route_to_architect"): FSMState.ARCHITECT_PLANNING,
        (FSMState.ARCHITECT_PLANNING, "plan_created"): FSMState.EXECUTION,
        (FSMState.ARCHITECT_PLANNING, "planning_failed"): FSMState.ERROR_HANDLING,
        (FSMState.EXECUTION, "all_subtasks_done"): FSMState.COMPLETED,
        (FSMState.EXECUTION, "subtask_failed"): FSMState.ERROR_HANDLING,
        (FSMState.ERROR_HANDLING, "requires_replanning"): FSMState.ARCHITECT_PLANNING,
        (FSMState.ERROR_HANDLING, "retry_subtask"): FSMState.EXECUTION,
        (FSMState.ERROR_HANDLING, "plan_cancelled"): FSMState.COMPLETED,
        (FSMState.COMPLETED, "reset"): FSMState.IDLE,
    }
    
    @staticmethod
    def is_valid_transition(
        from_state: FSMState,
        event: str
    ) -> bool:
        """Проверить, допустим ли переход"""
        return event in FSMTransitionRules.VALID_TRANSITIONS.get(from_state, set())
    
    @staticmethod
    def get_next_state(
        current_state: FSMState,
        event: str
    ) -> FSMState:
        """Получить следующее состояние по событию"""
        key = (current_state, event)
        if key not in FSMTransitionRules.TRANSITIONS:
            raise ValueError(f"Invalid transition: {current_state} + {event}")
        return FSMTransitionRules.TRANSITIONS[key]
```

### 3.3 FSMContext

```python
# app/domain/services/fsm_context.py

from typing import Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import Field
from .fsm_state import FSMState

class FSMContext:
    """Контекст состояния FSM для отдельной сессии"""
    
    def __init__(
        self,
        session_id: str,
        initial_state: FSMState = FSMState.IDLE
    ):
        self.session_id = session_id
        self.current_state = initial_state
        self.previous_state: Optional[FSMState] = None
        self.state_history: list[tuple[FSMState, str, datetime]] = []
        self.metadata: Dict[str, Any] = {}
        self.created_at = datetime.now(timezone.utc)
        self.last_transition_at = self.created_at
        self.transition_count = 0
    
    def transition(
        self,
        new_state: FSMState,
        event: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Выполнить переход и записать в историю"""
        self.previous_state = self.current_state
        self.current_state = new_state
        self.last_transition_at = datetime.now(timezone.utc)
        self.transition_count += 1
        
        self.state_history.append(
            (self.current_state, event, self.last_transition_at)
        )
        
        if metadata:
            self.metadata.update(metadata)
    
    def get_state_duration(self) -> float:
        """Получить длительность текущего состояния в секундах"""
        now = datetime.now(timezone.utc)
        return (now - self.last_transition_at).total_seconds()
    
    def reset(self) -> None:
        """Сбросить контекст в начальное состояние"""
        self.previous_state = self.current_state
        self.current_state = FSMState.IDLE
        self.last_transition_at = datetime.now(timezone.utc)
        self.transition_count += 1
        self.state_history.append(
            (self.current_state, "reset", self.last_transition_at)
        )
```

### 3.4 FSMOrchestrator

```python
# app/domain/services/fsm_orchestrator.py

import logging
from typing import Dict, Any, Optional
from .fsm_state import FSMState
from .fsm_transition_rules import FSMTransitionRules
from .fsm_context import FSMContext
from app.core.errors import FSMTransitionError

logger = logging.getLogger("agent-runtime.fsm_orchestrator")

class FSMOrchestrator:
    """Оркестратор конечного автомата для управления жизненным циклом задачи"""
    
    def __init__(self):
        """Инициализация FSM оркератора"""
        self._contexts: Dict[str, FSMContext] = {}
        logger.info("FSMOrchestrator initialized")
    
    def get_context(self, session_id: str) -> FSMContext:
        """Получить или создать контекст для сессии"""
        if session_id not in self._contexts:
            self._contexts[session_id] = FSMContext(session_id)
            logger.debug(f"Created new FSM context for session {session_id}")
        
        return self._contexts[session_id]
    
    async def transition(
        self,
        session_id: str,
        event: str,
        context: Optional[Dict[str, Any]] = None
    ) -> FSMState:
        """
        Выполнить переход по событию
        
        Args:
            session_id: Идентификатор сессии
            event: Название события
            context: Дополнительный контекст (опционально)
        
        Returns:
            Новое состояние FSM
        
        Raises:
            FSMTransitionError: Если переход невалидный
        """
        fsm_context = self.get_context(session_id)
        current_state = fsm_context.current_state
        
        # Валидировать переход
        if not FSMTransitionRules.is_valid_transition(current_state, event):
            error_msg = (
                f"Invalid FSM transition for session {session_id}: "
                f"{current_state} + {event}"
            )
            logger.error(error_msg)
            raise FSMTransitionError(error_msg)
        
        # Получить новое состояние
        new_state = FSMTransitionRules.get_next_state(current_state, event)
        
        # Выполнить переход
        fsm_context.transition(new_state, event, context)
        
        logger.info(
            f"FSM transition for session {session_id}: "
            f"{current_state.value} → {new_state.value} (event: {event})"
        )
        
        # Публиковать событие (будет реализовано с EventBus)
        # await self._publish_state_changed_event(session_id, current_state, new_state)
        
        return new_state
    
    def get_current_state(self, session_id: str) -> FSMState:
        """Получить текущее состояние для сессии"""
        context = self.get_context(session_id)
        return context.current_state
    
    def can_transition(
        self,
        session_id: str,
        event: str
    ) -> bool:
        """Проверить, возможен ли переход по событию"""
        context = self.get_context(session_id)
        return FSMTransitionRules.is_valid_transition(context.current_state, event)
    
    async def reset(self, session_id: str) -> None:
        """Сбросить FSM для сессии в начальное состояние"""
        context = self.get_context(session_id)
        
        # Выполнить reset через FSM (если текущее состояние это позволяет)
        if context.current_state != FSMState.IDLE:
            if not self.can_transition(session_id, "reset"):
                logger.warning(
                    f"Cannot reset FSM for session {session_id} from state {context.current_state}"
                )
                return
            
            context.reset()
        
        logger.info(f"FSM reset for session {session_id}")
    
    def get_history(self, session_id: str) -> list:
        """Получить историю переходов для сессии"""
        context = self.get_context(session_id)
        return [
            {
                "state": state.value,
                "event": event,
                "timestamp": timestamp.isoformat()
            }
            for state, event, timestamp in context.state_history
        ]
    
    def get_statistics(self, session_id: str) -> Dict[str, Any]:
        """Получить статистику FSM для сессии"""
        context = self.get_context(session_id)
        return {
            "session_id": session_id,
            "current_state": context.current_state.value,
            "previous_state": context.previous_state.value if context.previous_state else None,
            "transition_count": context.transition_count,
            "state_duration_seconds": context.get_state_duration(),
            "created_at": context.created_at.isoformat(),
            "last_transition_at": context.last_transition_at.isoformat(),
        }
```

---

## 4. Интеграция с OrchestratorAgent

```python
# Пример использования в OrchestratorAgent

class OrchestratorAgent(BaseAgent):
    
    def __init__(self):
        super().__init__(...)
        self.fsm_orchestrator = FSMOrchestrator()
        self.task_classifier = TaskClassifier()
    
    async def process(self, session_id: str, message: str, ...):
        try:
            # IDLE → CLASSIFY
            await self.fsm_orchestrator.transition(session_id, "receive_message")
            
            # Классификация
            classification = await self.task_classifier.classify(message)
            
            if classification.is_atomic:
                # CLASSIFY → EXECUTION
                await self.fsm_orchestrator.transition(session_id, "is_atomic_true")
                # Маршрутизировать в целевого агента
            else:
                # CLASSIFY → PLAN_REQUIRED → ARCHITECT_PLANNING
                await self.fsm_orchestrator.transition(session_id, "is_atomic_false")
                await self.fsm_orchestrator.transition(session_id, "route_to_architect")
                # Маршрутизировать в Architect
        
        except FSMTransitionError as e:
            logger.error(f"FSM error: {e}")
            yield StreamChunk(type="error", error=str(e))
```

---

## 5. Тестовые сценарии

```python
# tests/test_fsm_orchestrator.py

@pytest.mark.asyncio
async def test_valid_transition():
    """Тест валидного перехода"""
    fsm = FSMOrchestrator()
    session_id = "test-session"
    
    new_state = await fsm.transition(session_id, "receive_message")
    assert new_state == FSMState.CLASSIFY

@pytest.mark.asyncio
async def test_invalid_transition():
    """Тест невалидного перехода"""
    fsm = FSMOrchestrator()
    session_id = "test-session"
    
    with pytest.raises(FSMTransitionError):
        # Пытаемся сделать невозможный переход
        await fsm.transition(session_id, "all_subtasks_done")

@pytest.mark.asyncio
async def test_complete_workflow():
    """Тест полного workflow"""
    fsm = FSMOrchestrator()
    session_id = "test-session"
    
    # Simulate atomic task
    assert await fsm.transition(session_id, "receive_message") == FSMState.CLASSIFY
    assert await fsm.transition(session_id, "is_atomic_true") == FSMState.EXECUTION
    assert await fsm.transition(session_id, "all_subtasks_done") == FSMState.COMPLETED
    assert await fsm.transition(session_id, "reset") == FSMState.IDLE

@pytest.mark.asyncio
async def test_planning_workflow():
    """Тест workflow с планированием"""
    fsm = FSMOrchestrator()
    session_id = "test-session"
    
    # Simulate non-atomic task
    assert await fsm.transition(session_id, "receive_message") == FSMState.CLASSIFY
    assert await fsm.transition(session_id, "is_atomic_false") == FSMState.PLAN_REQUIRED
    assert await fsm.transition(session_id, "route_to_architect") == FSMState.ARCHITECT_PLANNING
    assert await fsm.transition(session_id, "plan_created") == FSMState.EXECUTION
    assert await fsm.transition(session_id, "all_subtasks_done") == FSMState.COMPLETED
```

---

## 6. Критерии готовности

- [ ] Все состояния из ТЗ реализованы
- [ ] Все валидные переходы работают
- [ ] Невалидные переходы выбрасывают исключение
- [ ] История переходов сохраняется
- [ ] Контекст сохраняется в памяти
- [ ] Unit тесты: 100% coverage
- [ ] Integration тесты с OrchestratorAgent
- [ ] Логирование всех переходов

---

**Статус:** 🟢 Готов к реализации
