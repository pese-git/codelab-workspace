# Правильное решение: Resumable Execution

## 🎯 Ключевая идея

**Execution должен завершать HTTP request после tool_call, точно так же как plan approval!**

## ✅ Правильный flow

### Plan Approval (уже работает так)
```
1. User message → create plan
2. Send plan_approval_required chunk
3. ✅ HTTP ЗАВЕРШАЕТСЯ
4. User sends plan_decision (новый request)
5. Execution starts
```

### Tool Approval (должен работать так же!)
```
1. Execution starts
2. Subtask #1 executes
3. LLM generates tool_call (requires_approval)
4. Send tool_call chunk
5. ✅ HTTP ДОЛЖЕН ЗАВЕРШИТЬСЯ (но сейчас не завершается!)
6. User sends hitl_decision (новый request)
7. User sends tool_result (новый request)
8. ✅ Execution ПРОДОЛЖАЕТСЯ с того же места
```

## 🔧 Решение: Убрать блокирующее ожидание

### Что нужно изменить:

1. **Убрать `_wait_for_approval_resolution()`** из execute_plan
2. **Execution должен ОСТАНАВЛИВАТЬСЯ** после tool_call
3. **HTTP request должен ЗАВЕРШАТЬСЯ**
4. **Tool_result handler должен ПРОДОЛЖАТЬ execution**

### Изменения в коде:

#### 1. ExecutionEngine - убрать ожидание approval

```python
# execution_engine.py - УБРАТЬ этот блок:

# ❌ УДАЛИТЬ:
pending_approvals = await self.approval_manager.get_pending_by_session(session_id)

if pending_approvals:
    # ... весь блок ожидания
    await self._wait_for_approval_resolution(...)
```

**Почему?**
- Execution уже ОСТАНАВЛИВАЕТСЯ после tool_call
- SubtaskExecutor.execute_subtask() возвращает chunks и завершается
- HTTP request завершается
- Approval придет через tool_result

#### 2. Execution уже resumable!

**Текущий код уже поддерживает resume:**

```python
# tool_result_handler.py
async def handle(call_id, result):
    # Добавить tool message
    await session_service.add_message(role="tool", ...)
    
    # ✅ Продолжить обработку
    async for chunk in agent.process(...):
        yield chunk
```

**Это уже работает!** Agent продолжает с того места, где остановился.

## 🎯 Вывод

**НАМ НЕ НУЖНО ЖДАТЬ APPROVAL В EXECUTION!**

Текущая архитектура **УЖЕ ПРАВИЛЬНАЯ**:
1. ✅ Execution выполняет subtask
2. ✅ Tool_call отправляется
3. ✅ Execution завершается (HTTP закрывается)
4. ✅ Tool_result продолжает execution

**Проблема была в том, что мы ДОБАВИЛИ блокирующее ожидание, которое НЕ НУЖНО!**

## 📝 Что делать?

### ОТКАТИТЬ изменения в ExecutionEngine:

1. **Убрать** проверку pending approvals после subtask
2. **Убрать** `_wait_for_approval_resolution()`
3. **Оставить** State Machine (для мониторинга, но без блокировки)

### Правильное использование State Machine:

```python
# execution_engine.py
async def execute_plan(...):
    state_manager = self._get_state_manager(plan_id)
    
    for subtask in subtasks:
        # Выполнить subtask
        async for chunk in execute_subtask(...):
            yield chunk
            
            # ✅ Если tool_call с approval - просто отметить в state
            if chunk.type == "tool_call" and chunk.requires_approval:
                state_manager.transition_to(
                    ExecutionState.WAITING_APPROVAL,
                    reason=f"Waiting for tool approval: {chunk.tool_name}"
                )
                # ✅ НЕ ЖДАТЬ - просто вернуть chunk и завершить
                return
        
        # Subtask завершена
        results[subtask_id] = ...
    
    # Все subtasks завершены
    state_manager.transition_to(ExecutionState.COMPLETED)
```

## ✅ Итог

**Исходная архитектура была правильной!**

Мы пытались решить проблему, которой не существует:
- ❌ "ExecutionEngine не ждет approval" - это ПРАВИЛЬНО!
- ✅ Execution должен ОСТАНАВЛИВАТЬСЯ, а не ЖДАТЬ
- ✅ Tool_result продолжает execution

**Нужно откатить блокирующее ожидание и оставить только State Machine для мониторинга.**
