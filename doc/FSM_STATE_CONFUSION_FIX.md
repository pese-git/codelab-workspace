# FSM State Confusion Fix: EXECUTION vs PLAN_EXECUTION

## 🐛 Проблема

При тестировании Plan Approval обнаружена ошибка FSM: попытка недопустимого перехода `execution -> plan_approved`.

### Симптомы
```
FSM transition error: Invalid transition from execution to plan_approved
```

## 🔍 Корневая причина

FSM имеет **два разных состояния** для выполнения задач:

1. **`EXECUTION`** - для **атомарных задач** (без плана)
   - Переходы: `EXECUTION → COMPLETED` или `EXECUTION → ERROR_HANDLING`
   - Используется когда `is_atomic=True`

2. **`PLAN_EXECUTION`** - для **выполнения одобренного плана**
   - Переходы: `PLAN_EXECUTION → COMPLETED` или `PLAN_EXECUTION → ERROR_HANDLING`
   - Используется после `PLAN_REVIEW → PLAN_APPROVED → PLAN_EXECUTION`

### Проблема
Где-то в коде происходит **путаница между этими состояниями**, и система пытается:
- Перейти из `EXECUTION` (атомарная задача) в `PLAN_APPROVED` (событие для плана)
- Это недопустимо согласно FSM правилам

## 📊 FSM States и Transitions

### Правильные переходы для планов:
```
IDLE → CLASSIFY → PLAN_REQUIRED → ARCHITECT_PLANNING → PLAN_REVIEW
                                                            ↓
                                                      PLAN_APPROVED (event)
                                                            ↓
                                                      PLAN_EXECUTION → COMPLETED
```

### Правильные переходы для атомарных задач:
```
IDLE → CLASSIFY → EXECUTION → COMPLETED
```

### ❌ Недопустимый переход (текущая ошибка):
```
EXECUTION → PLAN_APPROVED  ❌ INVALID!
```

## 🔧 Возможные места проблемы

### 1. OrchestratorAgent.process() - строка 189
```python
if current_state in [FSMState.COMPLETED, FSMState.ERROR_HANDLING, 
                     FSMState.EXECUTION, FSMState.PLAN_REVIEW, FSMState.PLAN_EXECUTION]:
```

**Проблема**: При получении нового сообщения в состоянии `EXECUTION` или `PLAN_EXECUTION`, система сбрасывает FSM. Но если это не новое сообщение, а продолжение выполнения, может произойти путаница.

### 2. PlanApprovalHandler - строка 173
```python
# FSM: PLAN_REVIEW → PLAN_EXECUTION
await self._fsm_orchestrator.transition(
    session_id=session_id,
    event=FSMEvent.PLAN_APPROVED,
    metadata={"approved_by": "user", "plan_id": plan_id}
)
```

**Потенциальная проблема**: Если текущее состояние не `PLAN_REVIEW`, а `EXECUTION`, то переход будет недопустимым.

### 3. Проверка текущего состояния перед approval
В [`plan_approval_handler.py`](codelab-ai-service/agent-runtime/app/domain/services/plan_approval_handler.py:173) **НЕТ проверки** текущего состояния FSM перед попыткой перехода!

## ✅ Решение

### Вариант 1: Добавить проверку состояния в PlanApprovalHandler

```python
async def handle(
    self,
    session_id: str,
    approval_request_id: str,
    decision: str,
    feedback: Optional[str] = None
) -> AsyncGenerator[StreamChunk, None]:
    # ... existing code ...
    
    if decision_enum == PlanApprovalDecision.APPROVE:
        # ДОБАВИТЬ: Проверить текущее состояние FSM
        current_state = await self._fsm_orchestrator.get_current_state(session_id)
        
        if current_state != FSMState.PLAN_REVIEW:
            error_msg = (
                f"Cannot approve plan: invalid FSM state. "
                f"Expected PLAN_REVIEW, got {current_state.value}"
            )
            logger.error(error_msg)
            yield StreamChunk(
                type="error",
                error=error_msg,
                is_final=True
            )
            return
        
        # ... rest of approval logic ...
```

### Вариант 2: Сделать FSM transition более устойчивым

Добавить в [`FSMOrchestrator.transition()`](codelab-ai-service/agent-runtime/app/domain/services/fsm_orchestrator.py) проверку валидности перехода:

```python
async def transition(
    self,
    session_id: str,
    event: FSMEvent,
    metadata: Optional[Dict[str, Any]] = None
) -> FSMState:
    current_state = await self.get_current_state(session_id)
    
    # Проверить валидность перехода
    if not FSMTransitionRules.is_valid_transition(current_state, event):
        raise ValueError(
            f"Invalid transition from {current_state.value} "
            f"with event {event.value}"
        )
    
    # ... rest of transition logic ...
```

## 🎯 Рекомендуемое решение

**Комбинация обоих вариантов:**

1. **Добавить проверку состояния в PlanApprovalHandler** (Вариант 1)
   - Предотвращает попытку approval в неправильном состоянии
   - Дает понятное сообщение об ошибке пользователю

2. **Улучшить валидацию в FSMOrchestrator** (Вариант 2)
   - Защита на уровне FSM от всех недопустимых переходов
   - Помогает отловить другие потенциальные проблемы

## 📝 Детальный план исправления

### Шаг 1: Добавить проверку в PlanApprovalHandler

**Файл**: `codelab-ai-service/agent-runtime/app/domain/services/plan_approval_handler.py`

**Место**: Перед строкой 172 (перед FSM transition)

**Код**:
```python
# Проверить текущее состояние FSM перед approval
current_state = await self._fsm_orchestrator.get_current_state(session_id)

if current_state != FSMState.PLAN_REVIEW:
    error_msg = (
        f"Cannot approve plan: invalid FSM state. "
        f"Expected PLAN_REVIEW, got {current_state.value}. "
        f"Plan approval is only allowed from PLAN_REVIEW state."
    )
    logger.error(error_msg)
    yield StreamChunk(
        type="error",
        error=error_msg,
        metadata={
            "expected_state": FSMState.PLAN_REVIEW.value,
            "actual_state": current_state.value,
            "plan_id": plan_id
        },
        is_final=True
    )
    return
```

### Шаг 2: Добавить аналогичные проверки для reject и modify

**Для reject** (перед строкой 228):
```python
current_state = await self._fsm_orchestrator.get_current_state(session_id)
if current_state != FSMState.PLAN_REVIEW:
    error_msg = f"Cannot reject plan: invalid FSM state {current_state.value}"
    logger.error(error_msg)
    yield StreamChunk(type="error", error=error_msg, is_final=True)
    return
```

**Для modify** (перед строкой 257):
```python
current_state = await self._fsm_orchestrator.get_current_state(session_id)
if current_state != FSMState.PLAN_REVIEW:
    error_msg = f"Cannot modify plan: invalid FSM state {current_state.value}"
    logger.error(error_msg)
    yield StreamChunk(type="error", error=error_msg, is_final=True)
    return
```

### Шаг 3: Улучшить логирование в FSMOrchestrator

**Файл**: `codelab-ai-service/agent-runtime/app/domain/services/fsm_orchestrator.py`

**Добавить в метод `transition()`**:
```python
# Log transition attempt
logger.debug(
    f"FSM transition attempt: {current_state.value} --[{event.value}]--> ?"
)

# Validate transition
if not FSMTransitionRules.is_valid_transition(current_state, event):
    error_msg = (
        f"Invalid FSM transition: {current_state.value} --[{event.value}]--> X. "
        f"Allowed events from {current_state.value}: "
        f"{[e.value for e in FSMTransitionRules.get_allowed_events(current_state)]}"
    )
    logger.error(error_msg)
    raise ValueError(error_msg)

next_state = FSMTransitionRules.get_next_state(current_state, event)
logger.info(
    f"FSM transition: {current_state.value} --[{event.value}]--> {next_state.value}"
)
```

## 🧪 Тестирование

### Тест 1: Попытка approval в неправильном состоянии
```python
async def test_approval_in_wrong_state():
    # Setup: session в состоянии EXECUTION (не PLAN_REVIEW)
    await fsm.transition(session_id, FSMEvent.IS_ATOMIC_TRUE)
    
    # Попытка approval должна вернуть ошибку
    chunks = []
    async for chunk in handler.handle(
        session_id=session_id,
        approval_request_id="test",
        decision="approve"
    ):
        chunks.append(chunk)
    
    # Проверить, что вернулась ошибка
    assert chunks[-1].type == "error"
    assert "invalid FSM state" in chunks[-1].error
```

### Тест 2: Правильный approval из PLAN_REVIEW
```python
async def test_approval_from_plan_review():
    # Setup: session в состоянии PLAN_REVIEW
    await fsm.transition(session_id, FSMEvent.RECEIVE_MESSAGE)
    await fsm.transition(session_id, FSMEvent.IS_ATOMIC_FALSE)
    await fsm.transition(session_id, FSMEvent.ROUTE_TO_ARCHITECT)
    await fsm.transition(session_id, FSMEvent.PLAN_CREATED)
    
    # Approval должен пройти успешно
    chunks = []
    async for chunk in handler.handle(
        session_id=session_id,
        approval_request_id="test",
        decision="approve"
    ):
        chunks.append(chunk)
    
    # Проверить успешный переход
    state = await fsm.get_current_state(session_id)
    assert state == FSMState.PLAN_EXECUTION
```

## 📚 Дополнительная информация

### FSM State Diagram
```
┌─────┐  RECEIVE_MESSAGE  ┌──────────┐
│IDLE │─────────────────→│ CLASSIFY │
└─────┘                   └──────────┘
                               │
                ┌──────────────┴──────────────┐
                │                             │
         IS_ATOMIC_TRUE              IS_ATOMIC_FALSE
                │                             │
                ↓                             ↓
         ┌───────────┐              ┌──────────────┐
         │ EXECUTION │              │PLAN_REQUIRED │
         └───────────┘              └──────────────┘
                │                             │
         ALL_SUBTASKS_DONE          ROUTE_TO_ARCHITECT
                │                             │
                ↓                             ↓
         ┌───────────┐              ┌──────────────────┐
         │ COMPLETED │              │ARCHITECT_PLANNING│
         └───────────┘              └──────────────────┘
                                             │
                                      PLAN_CREATED
                                             │
                                             ↓
                                    ┌─────────────┐
                                    │ PLAN_REVIEW │
                                    └─────────────┘
                                             │
                                      PLAN_APPROVED
                                             │
                                             ↓
                                    ┌────────────────┐
                                    │ PLAN_EXECUTION │
                                    └────────────────┘
                                             │
                                 PLAN_EXECUTION_COMPLETED
                                             │
                                             ↓
                                    ┌───────────┐
                                    │ COMPLETED │
                                    └───────────┘
```

### Ключевые правила FSM

1. **EXECUTION** и **PLAN_EXECUTION** - это **разные состояния**
2. **PLAN_APPROVED** - это **событие**, не состояние
3. Переход `PLAN_APPROVED` возможен **только из PLAN_REVIEW**
4. Из `EXECUTION` можно перейти только в `COMPLETED` или `ERROR_HANDLING`

## ✅ Результат

После применения исправлений:
- ✅ Plan approval работает только из состояния `PLAN_REVIEW`
- ✅ Попытки approval в неправильном состоянии возвращают понятную ошибку
- ✅ FSM transitions валидируются на уровне FSMOrchestrator
- ✅ Улучшено логирование для диагностики проблем
