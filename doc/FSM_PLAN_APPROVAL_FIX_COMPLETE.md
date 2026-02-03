# ✅ FSM Plan Approval Fix Complete

## 🐛 Проблема

При тестировании Plan Approval обнаружена ошибка FSM:
```
Invalid transition from execution to plan_approved
```

## 🔍 Корневая причина

**Двойная проблема:**

1. **Транзакционная изоляция БД** (уже исправлена в [`PLAN_TRANSACTION_ISOLATION_FIX.md`](PLAN_TRANSACTION_ISOLATION_FIX.md))
   - План создавался через `flush()`, но не был виден в других транзакциях
   - При продолжении выполнения план не находился
   - Код пытался снова сделать approval → ошибка FSM

2. **Отсутствие валидации FSM состояния** (исправлено в этом PR)
   - Не было проверки текущего состояния FSM перед plan approval
   - Попытка approval в неправильном состоянии приводила к ошибке

## 🔧 Решение

### 1. Транзакционная изоляция (уже исправлена)

**Файл**: [`plan_repository_impl.py`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/repositories/plan_repository_impl.py)

Добавлен параметр `commit: bool = False` в метод `save()`:
```python
async def save(self, plan: Plan, commit: bool = False) -> None:
    """
    Save plan to database.
    
    Args:
        plan: Plan entity to save
        commit: If True, commit transaction immediately for inter-transaction visibility
    """
    # ... save logic ...
    
    if commit:
        await self.db.commit()
        logger.debug(f"Saved and committed plan {plan.id}")
    else:
        await self.db.flush()
        logger.debug(f"Saved plan {plan.id} (not committed)")
```

**Использование**:
- [`architect_agent.py:243`](../codelab-ai-service/agent-runtime/app/agents/architect_agent.py:243) - `commit=True` при создании плана
- [`plan_approval_handler.py:167`](../codelab-ai-service/agent-runtime/app/domain/services/plan_approval_handler.py:167) - `commit=True` при обновлении статуса на APPROVED

### 2. Валидация FSM состояния (новое исправление)

**Файл**: [`plan_approval_handler.py`](../codelab-ai-service/agent-runtime/app/domain/services/plan_approval_handler.py)

Добавлена проверка состояния FSM перед каждым типом решения:

#### Для APPROVE (строка 152):
```python
# Проверить текущее состояние FSM перед approval
from ..entities.fsm_state import FSMState
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

#### Для REJECT (строка 220):
```python
# Проверить текущее состояние FSM перед rejection
from ..entities.fsm_state import FSMState
current_state = await self._fsm_orchestrator.get_current_state(session_id)

if current_state != FSMState.PLAN_REVIEW:
    error_msg = (
        f"Cannot reject plan: invalid FSM state. "
        f"Expected PLAN_REVIEW, got {current_state.value}"
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

#### Для MODIFY (строка 246):
```python
# Проверить текущее состояние FSM перед modification request
from ..entities.fsm_state import FSMState
current_state = await self._fsm_orchestrator.get_current_state(session_id)

if current_state != FSMState.PLAN_REVIEW:
    error_msg = (
        f"Cannot modify plan: invalid FSM state. "
        f"Expected PLAN_REVIEW, got {current_state.value}"
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

## 📊 FSM States и Transitions

### Правильный flow для Plan Approval:

```
IDLE → CLASSIFY → PLAN_REQUIRED → ARCHITECT_PLANNING → PLAN_REVIEW
                                                            ↓
                                                      [USER APPROVES]
                                                            ↓
                                                      PLAN_APPROVED (event)
                                                            ↓
                                                      PLAN_EXECUTION → COMPLETED
```

### Ключевые правила:

1. **`PLAN_REVIEW`** - единственное состояние, из которого можно делать plan approval
2. **`PLAN_APPROVED`** - это **событие**, не состояние
3. **`EXECUTION`** и **`PLAN_EXECUTION`** - разные состояния:
   - `EXECUTION` - для атомарных задач (без плана)
   - `PLAN_EXECUTION` - для выполнения одобренного плана
4. Из `EXECUTION` или `PLAN_EXECUTION` **нельзя** перейти через `PLAN_APPROVED`

## ✅ Результаты

### До исправления:
```
❌ План создавался через flush() → не виден в других транзакциях
❌ При продолжении выполнения план не находился
❌ Код пытался снова сделать approval
❌ FSM уже был в состоянии PLAN_EXECUTION
❌ Попытка перехода PLAN_APPROVED из неправильного состояния
❌ Ошибка: "Invalid transition from execution to plan_approved"
```

### После исправления:
```
✅ План коммитится немедленно с commit=True
✅ План виден во всех транзакциях
✅ Проверка состояния FSM перед approval
✅ Попытка approval в неправильном состоянии возвращает понятную ошибку
✅ Нет повторных попыток approval
✅ FSM transitions валидны
✅ Ошибка больше не возникает
```

## 🧪 Тестирование

### Тест 1: Правильный approval из PLAN_REVIEW
```python
async def test_plan_approval_from_plan_review():
    # Setup: создать план и перейти в PLAN_REVIEW
    plan_id = await architect.create_plan(session_id, task)
    await fsm.transition(session_id, FSMEvent.PLAN_CREATED)
    
    # Approval должен пройти успешно
    chunks = []
    async for chunk in handler.handle(
        session_id=session_id,
        approval_request_id=f"plan-approval-{plan_id}",
        decision="approve"
    ):
        chunks.append(chunk)
    
    # Проверить успешный переход
    state = await fsm.get_current_state(session_id)
    assert state == FSMState.PLAN_EXECUTION
    
    # Проверить, что план закоммичен
    plan = await plan_repo.find_by_id(plan_id)
    assert plan.status == PlanStatus.APPROVED
```

### Тест 2: Попытка approval в неправильном состоянии
```python
async def test_approval_in_wrong_state():
    # Setup: session в состоянии PLAN_EXECUTION (не PLAN_REVIEW)
    plan_id = await architect.create_plan(session_id, task)
    await fsm.transition(session_id, FSMEvent.PLAN_CREATED)
    await fsm.transition(session_id, FSMEvent.PLAN_APPROVED)
    
    # Попытка approval должна вернуть ошибку
    chunks = []
    async for chunk in handler.handle(
        session_id=session_id,
        approval_request_id=f"plan-approval-{plan_id}",
        decision="approve"
    ):
        chunks.append(chunk)
    
    # Проверить, что вернулась ошибка
    assert chunks[0].type == "error"
    assert "invalid FSM state" in chunks[0].error
    assert chunks[0].metadata["expected_state"] == "plan_review"
    assert chunks[0].metadata["actual_state"] == "plan_execution"
```

### Тест 3: План виден в других транзакциях
```python
async def test_plan_visibility_across_transactions():
    # Создать план с commit=True
    plan_id = await architect.create_plan(session_id, task)
    
    # Открыть новую транзакцию и проверить видимость
    async with new_db_session() as new_session:
        plan_repo_new = PlanRepositoryImpl(new_session)
        plan = await plan_repo_new.find_by_id(plan_id)
        
        # План должен быть виден
        assert plan is not None
        assert plan.id == plan_id
```

## 📝 Изменённые файлы

1. ✅ [`plan_repository_impl.py`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/repositories/plan_repository_impl.py) - добавлен параметр `commit`
2. ✅ [`architect_agent.py`](../codelab-ai-service/agent-runtime/app/agents/architect_agent.py) - используется `commit=True` при создании плана
3. ✅ [`plan_approval_handler.py`](../codelab-ai-service/agent-runtime/app/domain/services/plan_approval_handler.py) - добавлена валидация FSM состояния + `commit=True`

## 📚 Связанные документы

- [`PLAN_TRANSACTION_ISOLATION_FIX.md`](PLAN_TRANSACTION_ISOLATION_FIX.md) - исправление транзакционной изоляции
- [`FSM_STATE_CONFUSION_FIX.md`](FSM_STATE_CONFUSION_FIX.md) - анализ путаницы между EXECUTION и PLAN_EXECUTION
- [`FSM_TRANSITION_ERROR_ROOT_CAUSE.md`](FSM_TRANSITION_ERROR_ROOT_CAUSE.md) - детальный анализ корневой причины

## 🎯 Итог

**Проблема полностью решена:**

1. ✅ Транзакционная изоляция исправлена через `commit=True`
2. ✅ Добавлена валидация FSM состояния перед plan approval
3. ✅ Понятные сообщения об ошибках для пользователя
4. ✅ Защита от повторных попыток approval
5. ✅ FSM transitions валидны во всех сценариях

**Ошибка "Invalid transition from execution to plan_approved" больше не возникает!**
