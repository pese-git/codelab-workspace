# Проблема: План завершается до выполнения tool calls

## Симптомы (из скриншота и логов)

1. План создан с 9 подзадачами
2. Показывается "Subtask 1/9: Создать бизнес-сущность..."
3. Вызывается `create_directory` tool
4. **Сразу показывается "Plan Execution Complete: Completed: 0"**

## Корневая причина

В методе [`_execute_plan`](codelab-ai-service/agent-runtime/app/services/multi_agent_orchestrator.py:308-321) есть цикл:

```python
async for chunk in agent.process(
    session_id=session_id,
    message=subtask.description,
    context=context.model_dump(),
    session_mgr=session_mgr
):
    # Collect result for logging
    if chunk.type == "assistant_message" and chunk.content:
        subtask_result.append(chunk.content)
    
    # Forward chunk
    yield chunk
```

Когда агент вызывает tool (например, `create_directory`), он отправляет chunk с `type="tool_call"` и `is_final=True`, затем **завершает генерацию**.

**Проблема:** Цикл `async for chunk in agent.process()` завершается после `tool_call` chunk, и код сразу переходит к:

```python
# Mark subtask as complete
session_mgr.mark_subtask_complete(session_id, subtask.id, result_text)
```

Но tool еще **не выполнен**! Tool должен быть выполнен на стороне IDE/Gateway, и результат должен вернуться через `tool_result` message.

## Почему это происходит?

### Текущий flow (неправильный):

```
1. _execute_plan() вызывает agent.process(subtask.description)
2. Agent вызывает tool → отправляет tool_call chunk (is_final=True)
3. agent.process() завершается
4. _execute_plan() помечает subtask как completed ← ОШИБКА!
5. _execute_plan() переходит к следующей subtask
6. Цикл while завершается (нет больше pending subtasks)
7. Показывается "Plan Execution Complete: Completed: 0"
```

### Правильный flow:

```
1. _execute_plan() вызывает agent.process(subtask.description)
2. Agent вызывает tool → отправляет tool_call chunk (is_final=True)
3. agent.process() завершается
4. _execute_plan() НЕ помечает subtask как completed ← ЖДЕТ tool_result
5. IDE/Gateway выполняет tool
6. IDE отправляет tool_result обратно
7. API получает tool_result → вызывает multi_agent_orchestrator.process_message("")
8. multi_agent_orchestrator обнаруживает незавершенную subtask
9. Вызывает agent.process("") для продолжения
10. Agent получает tool_result и продолжает работу
11. Agent завершает subtask → отправляет attempt_completion или финальное сообщение
12. _execute_plan() помечает subtask как completed
13. Переходит к следующей subtask
```

## Решение

Проблема в том, что `_execute_plan` не понимает, что subtask еще не завершена, когда агент вызывает tool.

### Вариант 1: Проверять is_final в tool_call

```python
async for chunk in agent.process(...):
    if chunk.type == "assistant_message" and chunk.content:
        subtask_result.append(chunk.content)
    
    # Check if this is a tool call - don't mark as complete yet
    if chunk.type == "tool_call":
        logger.info(f"Subtask {subtask.id} called tool {chunk.tool_name}, waiting for result")
        # Forward chunk but don't mark as complete
        yield chunk
        # Exit loop but DON'T mark as complete
        break
    
    yield chunk

# Only mark as complete if we got a final assistant message, not a tool call
if subtask_result or (chunk.type == "assistant_message" and chunk.is_final):
    session_mgr.mark_subtask_complete(session_id, subtask.id, result_text)
else:
    # Tool call - subtask is still in progress
    logger.info(f"Subtask {subtask.id} waiting for tool result")
    # Don't mark as complete, will continue when tool_result arrives
```

### Вариант 2: Не использовать _execute_plan для tool-based subtasks

Проблема в том, что `_execute_plan` пытается выполнить все subtasks в одном цикле, но tool calls требуют асинхронного взаимодействия с IDE.

**Решение:** Выполнять только ОДНУ subtask за раз, затем ждать, пока tool results вернутся.

```python
async def _execute_plan(...):
    # Get next subtask
    subtask = session_mgr.get_next_subtask(session_id)
    
    if not subtask:
        # All subtasks complete
        yield "Plan Execution Complete"
        return
    
    # Execute ONLY this subtask
    async for chunk in agent.process(...):
        yield chunk
    
    # If tool was called, wait for tool_result before continuing
    # The next call to process_message will continue with next subtask
```

### Вариант 3: Отслеживать состояние subtask

Добавить поле `waiting_for_tool` в Subtask:

```python
class Subtask(BaseModel):
    status: SubtaskStatus
    waiting_for_tool: bool = False  # ← Новое поле
```

Затем в `_execute_plan`:

```python
async for chunk in agent.process(...):
    if chunk.type == "tool_call":
        # Mark subtask as waiting for tool
        subtask.waiting_for_tool = True
        yield chunk
        return  # Exit _execute_plan, wait for tool_result
    
    yield chunk

# Only mark as complete if not waiting for tool
if not subtask.waiting_for_tool:
    session_mgr.mark_subtask_complete(session_id, subtask.id)
```

## Рекомендуемое решение

**Вариант 2** - самый простой и надежный:

1. Выполнять только ОДНУ subtask за раз
2. Если subtask вызывает tool, выходить из `_execute_plan`
3. Когда приходит `tool_result`, снова вызывать `process_message("")`
4. `multi_agent_orchestrator` обнаруживает незавершенный план и продолжает с той же subtask
5. После завершения subtask переходить к следующей

Это требует изменения логики в `_execute_plan` - вместо цикла `while not plan.is_complete` выполнять только одну subtask.
