# Сравнение Вариант 1 vs Вариант 2 для Resumable Execution

## 🎯 Оба варианта решают проблему

**Execution должен останавливаться после tool_call и возобновляться через tool_result.**

---

## Вариант 1: Tool_result продолжает execution

### Описание

После обработки tool_result проверять активный plan и продолжать execution.

### Архитектура

```
tool_result_handler.handle()
  ├─> add_message(role="tool")
  ├─> agent.process()  # Продолжить текущую subtask
  │     └─> Может быть еще tool_calls
  │
  └─> ✅ Проверить активный plan
        └─> Если есть IN_PROGRESS plan
              └─> execution_coordinator.execute_plan()
                    └─> Выполнить следующую subtask
```

### Код

```python
# tool_result_handler.py
async def handle(session_id, call_id, result):
    # 1. Добавить tool message
    await session_service.add_message(role="tool", ...)
    
    # 2. Продолжить обработку текущей subtask
    async for chunk in agent.process(...):
        yield chunk
    
    # 3. ✅ Проверить активный plan
    active_plan = await plan_repository.find_in_progress_by_session(session_id)
    
    if active_plan:
        logger.info(f"Resuming plan execution {active_plan.id}")
        
        # 4. Продолжить execution (следующая subtask)
        async for chunk in execution_coordinator.execute_plan(
            plan_id=active_plan.id,
            session_id=session_id
        ):
            yield chunk
```

### ✅ Плюсы

1. **Минимальные изменения**: Только tool_result_handler
2. **Автоматическое продолжение**: Не нужно вызывать отдельный endpoint
3. **Прозрачно для клиента**: IDE не знает о resumable execution
4. **Простая логика**: Линейный flow

### ❌ Минусы

1. **Рекурсивный вызов**: execute_plan может вызвать tool_call → tool_result → execute_plan → ...
2. **Глубокий call stack**: При многих subtasks может быть проблема
3. **Сложнее отлаживать**: Execution "прыгает" между tool_result_handler и execution_engine
4. **Coupling**: tool_result_handler знает о plan execution

---

## Вариант 2: ExecutionEngine выполняет по одной subtask

### Описание

ExecutionEngine выполняет только ОДНУ subtask за вызов, затем останавливается.

### Архитектура

```
execution_engine.execute_plan()
  ├─> Получить следующую pending subtask
  ├─> Если нет → execution_completed
  │
  └─> Выполнить ОДНУ subtask
        └─> tool_call → HTTP завершается
              └─> tool_result → agent.process()
                    └─> ✅ Вызвать execute_plan() снова
                          └─> Следующая subtask
```

### Код

```python
# execution_engine.py
async def execute_plan(...):
    state_manager = self._get_state_manager(plan_id)
    
    # Получить следующую pending subtask
    next_subtask = plan.get_next_pending_subtask()
    
    if not next_subtask:
        # Все subtasks выполнены
        plan.complete()
        state_manager.transition_to(ExecutionState.COMPLETED)
        self._cleanup_state_manager(plan_id)
        
        yield StreamChunk(
            type="execution_completed",
            content="Plan execution completed",
            metadata={"plan_id": plan_id}
        )
        return
    
    # Выполнить ОДНУ subtask
    logger.info(f"Executing subtask: {next_subtask.description[:50]}...")
    
    async for chunk in execute_subtask(next_subtask):
        yield chunk
        
        # Если tool_call - execution автоматически остановится
    
    # Subtask завершена - НЕ продолжать к следующей
    # Tool_result вызовет execute_plan() снова

# tool_result_handler.py
async def handle(session_id, call_id, result):
    # 1. Добавить tool message
    await session_service.add_message(role="tool", ...)
    
    # 2. Продолжить обработку
    async for chunk in agent.process(...):
        yield chunk
    
    # 3. ✅ Проверить активный plan
    active_plan = await plan_repository.find_in_progress_by_session(session_id)
    
    if active_plan:
        # 4. Продолжить execution (следующая subtask)
        async for chunk in execution_coordinator.execute_plan(
            plan_id=active_plan.id,
            session_id=session_id
        ):
            yield chunk
```

### ✅ Плюсы

1. **Явный control flow**: Одна subtask за раз
2. **Плоский call stack**: Нет глубокой рекурсии
3. **Легче отлаживать**: Четкие границы между subtasks
4. **Resumable**: Можно остановить и продолжить в любой момент
5. **State Machine friendly**: Четкие transitions между subtasks

### ❌ Минусы

1. **Больше изменений**: ExecutionEngine + tool_result_handler
2. **Изменение логики**: ExecutionEngine работает по-другому
3. **Нужен метод**: `plan.get_next_pending_subtask()`

---

## 📊 Детальное сравнение

| Критерий | Вариант 1 | Вариант 2 | Победитель |
|----------|-----------|-----------|------------|
| Простота реализации | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | Вариант 1 |
| Читаемость кода | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Вариант 2 |
| Отладка | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Вариант 2 |
| Call stack | ⭐⭐ | ⭐⭐⭐⭐⭐ | Вариант 2 |
| Coupling | ⭐⭐⭐ | ⭐⭐⭐⭐ | Вариант 2 |
| Resumability | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Вариант 2 |
| State Machine integration | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Вариант 2 |

**Итого**: Вариант 1 = 20/35, Вариант 2 = 31/35

---

## 🎯 Рекомендация

### **Вариант 2** - правильное архитектурное решение

### Почему?

1. **Явный control flow**: Одна subtask = один вызов execute_plan
2. **Плоский call stack**: Нет рекурсии
3. **Легче отлаживать**: Четкие границы
4. **State Machine friendly**: Transitions между subtasks
5. **Resumable**: Можно остановить/продолжить в любой момент

### Когда Вариант 1 лучше?

- Если нужно **быстро** исправить (1 час)
- Если не хотите менять ExecutionEngine
- Если рекурсия не проблема (мало subtasks)

### Но для production:

**Вариант 2** - более чистая и поддерживаемая архитектура.

---

## 📝 План реализации Варианта 2

### 1. Добавить метод в Plan entity

```python
# plan.py
def get_next_pending_subtask(self) -> Optional[Subtask]:
    """
    Получить следующую pending subtask для выполнения.
    
    Returns:
        Следующая subtask со статусом PENDING или None
    """
    for subtask in self.subtasks:
        if subtask.status == SubtaskStatus.PENDING:
            # Проверить, что все зависимости выполнены
            deps_completed = all(
                self.get_subtask_by_id(dep_id).status == SubtaskStatus.DONE
                for dep_id in subtask.dependencies
            )
            if deps_completed:
                return subtask
    return None
```

### 2. Модифицировать ExecutionEngine.execute_plan()

```python
# execution_engine.py
async def execute_plan(...):
    state_manager = self._get_state_manager(plan_id)
    
    # Получить план
    plan = await self.plan_repository.find_by_id(plan_id)
    
    # Получить следующую pending subtask
    next_subtask = plan.get_next_pending_subtask()
    
    if not next_subtask:
        # Все subtasks выполнены
        plan.complete()
        state_manager.transition_to(ExecutionState.COMPLETED)
        self._cleanup_state_manager(plan_id)
        
        yield StreamChunk(type="execution_completed", ...)
        return
    
    # Выполнить ОДНУ subtask
    logger.info(f"Executing subtask: {next_subtask.description[:50]}...")
    
    try:
        async for chunk in self.subtask_executor.execute_subtask(
            plan_id=plan.id,
            subtask_id=next_subtask.id,
            session_id=session_id,
            session_service=session_service,
            stream_handler=stream_handler
        ):
            yield chunk
        
        # Subtask завершена
        # ✅ НЕ продолжать к следующей
        # Tool_result вызовет execute_plan() снова
        
    except SubtaskExecutionError as e:
        logger.error(f"Subtask {next_subtask.id} failed: {e}")
        plan.fail(str(e))
        state_manager.transition_to(ExecutionState.FAILED)
        await self.plan_repository.save(plan)
        self._cleanup_state_manager(plan_id)
        
        yield StreamChunk(type="error", error=str(e))
```

### 3. Модифицировать tool_result_handler

```python
# tool_result_handler.py
async def handle(session_id, call_id, result):
    # 1-2. Добавить tool message и продолжить agent.process()
    ...
    
    # 3. Проверить активный plan
    active_plan = await self._get_active_plan(session_id)
    
    if active_plan:
        logger.info(f"Resuming plan execution {active_plan.id}")
        
        # 4. Продолжить execution (следующая subtask)
        async for chunk in self._execution_coordinator.execute_plan(
            plan_id=active_plan.id,
            session_id=session_id,
            session_service=self._session_service,
            stream_handler=self._stream_handler
        ):
            yield chunk

async def _get_active_plan(self, session_id):
    """Получить активный plan для сессии"""
    # Найти plan со статусом IN_PROGRESS для этой сессии
    # Через plan_repository
```

---

## ✅ Итог

**Вариант 2** - правильное решение для production:
- Чистая архитектура
- Легко отлаживать
- Resumable execution
- State Machine friendly

**Вариант 1** - быстрое решение для MVP:
- Минимальные изменения
- Работает, но не идеально
- Можно рефакторить позже в Вариант 2
