# Финальное правильное решение: Execution останавливается после tool_call

## 🎯 Проблема (подтверждена)

**ExecutionEngine продолжает выполнение следующих subtasks, не дожидаясь HITL approval.**

## ❌ Неправильное решение (вызывает timeout)

Блокирующее ожидание approval внутри HTTP request:
```python
# ❌ НЕ РАБОТАЕТ
await self._wait_for_approval_resolution(...)  # Блокирует HTTP
```

## ✅ Правильное решение

**Execution должен ОСТАНАВЛИВАТЬСЯ после tool_call, а не ЖДАТЬ.**

### Ключевая идея

Execution работает как **state machine с паузами**:

```
Execution → Subtask #1 → Tool call → ⏸️ STOP (HTTP завершается)
                                      ↓
                                   User approves
                                      ↓
                                   Tool result → ▶️ RESUME
                                      ↓
Execution → Subtask #2 → ...
```

### Как это работает сейчас?

**УЖЕ РАБОТАЕТ ПРАВИЛЬНО!** Но только для **одной** subtask.

Проблема: После tool_result execution **НЕ ПРОДОЛЖАЕТСЯ** к следующей subtask.

## 🔧 Решение: Execution должен быть resumable

### Текущий flow:

```
1. Plan approved
2. PlanApprovalHandler вызывает execution_coordinator.execute_plan()
3. ExecutionEngine выполняет subtask #1
4. Tool call → HTTP завершается ✅
5. Tool result → agent.process() продолжается
6. ❌ Но ExecutionEngine УЖЕ ЗАВЕРШИЛСЯ (вышел из цикла)
7. ❌ Subtask #2 никогда не выполнится
```

### Правильный flow:

```
1. Plan approved
2. PlanApprovalHandler вызывает execution_coordinator.execute_plan()
3. ExecutionEngine выполняет subtask #1
4. Tool call → HTTP завершается ✅
5. Tool result → ✅ ПРОДОЛЖИТЬ EXECUTION (вызвать execute_plan снова)
6. ExecutionEngine выполняет subtask #2
7. ...
```

## 📝 Реализация

### Вариант 1: Tool_result продолжает execution

**Идея**: После tool_result проверять, есть ли незавершенный plan, и продолжать execution.

```python
# tool_result_handler.py
async def handle(session_id, call_id, result):
    # Добавить tool message
    await session_service.add_message(...)
    
    # Продолжить обработку
    async for chunk in agent.process(...):
        yield chunk
    
    # ✅ НОВОЕ: Проверить, есть ли активный plan execution
    active_plan = await self._get_active_plan_for_session(session_id)
    
    if active_plan and active_plan.status == PlanStatus.IN_PROGRESS:
        logger.info(f"Resuming plan execution {active_plan.id}")
        
        # Продолжить execution
        async for chunk in execution_coordinator.execute_plan(
            plan_id=active_plan.id,
            session_id=session_id
        ):
            yield chunk
```

### Вариант 2: ExecutionEngine выполняет по одной subtask

**Идея**: ExecutionEngine выполняет только ОДНУ subtask за раз.

```python
# execution_engine.py
async def execute_plan(...):
    # Получить следующую pending subtask
    next_subtask = plan.get_next_pending_subtask()
    
    if not next_subtask:
        # Все subtasks выполнены
        plan.complete()
        yield StreamChunk(type="execution_completed", ...)
        return
    
    # Выполнить ОДНУ subtask
    async for chunk in execute_subtask(next_subtask):
        yield chunk
        
        # Если tool_call - execution автоматически остановится
        # (agent.process() завершится после tool_call)
    
    # Subtask завершена
    # ✅ НЕ продолжать к следующей - пусть tool_result вызовет execute_plan снова
```

## 🎯 Рекомендация

**Вариант 1** - проще реализовать, минимальные изменения.

### Изменения:

1. **tool_result_handler.py**:
   - После agent.process() проверить активный plan
   - Если есть - продолжить execution

2. **execution_engine.py**:
   - Убрать блокирующее ожидание (уже сделано ✅)
   - Оставить State Machine для мониторинга

3. **Добавить метод**:
   ```python
   async def _get_active_plan_for_session(session_id) -> Optional[Plan]:
       """Получить активный plan для сессии"""
   ```

## ✅ Преимущества

1. ✅ Нет блокировки HTTP
2. ✅ Нет timeouts
3. ✅ Execution автоматически продолжается
4. ✅ Минимальные изменения
5. ✅ State Machine для мониторинга

## 📋 Следующие шаги

1. Реализовать `_get_active_plan_for_session()` в tool_result_handler
2. После agent.process() проверять активный plan
3. Если есть - вызывать execution_coordinator.execute_plan()
4. Протестировать полный flow
