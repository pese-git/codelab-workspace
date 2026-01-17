# Исправление: Подзадачи не завершались из-за преждевременного закрытия SSE stream

## Проблема

Когда агент отправлял финальное сообщение с `is_final: true`, endpoints.py немедленно закрывал SSE stream, отправляя `event: done`. Это приводило к тому, что код в `_execute_plan` после цикла `async for` не выполнялся, и подзадача не завершалась.

### Последовательность событий (ДО исправления)

1. Агент вызывает `read_file` → получает результат
2. Агент отправляет финальное сообщение с `is_final: true`
3. `_execute_plan` получает chunk с `is_final: true`
4. `_execute_plan` делает `yield chunk` → передает chunk в endpoints.py
5. endpoints.py видит `is_final: true` → отправляет `event: done` → закрывает SSE stream
6. Код после цикла `async for` в `_execute_plan` (строки 405-452) НЕ выполняется
7. Подзадача НЕ завершается
8. При следующем `tool_result` система снова вызывает LLM
9. Бесконечный цикл или таймаут

### Пример из логов

```
2026-01-17 09:27:13,417 - agent-runtime.multi_agent_orchestrator - INFO - Subtask subtask_1 received final message from LLM
2026-01-17 09:27:13,417 - sse_starlette.sse - DEBUG - chunk: event: message
data: {"type": "assistant_message", "content": "...", "is_final": true, ...}

2026-01-17 09:27:13,417 - sse_starlette.sse - DEBUG - chunk: event: done
data: {"status": "completed"}

[Больше нет логов - код после цикла не выполнился]
[Таймаут 60 секунд]
```

## Причина

Проблема в архитектуре SSE streaming:
1. endpoints.py ждет chunks от `_execute_plan`
2. Когда получает chunk с `is_final: true`, немедленно закрывает stream
3. Не ждет дополнительных chunks (например, `subtask_completed`)
4. Код после `async for` в `_execute_plan` не может отправить свои chunks, потому что stream уже закрыт

## Решение

Модифицировать `is_final` флаг перед отправкой chunk клиенту:

**В `_execute_plan` (строки 340-369, 374-403):**

```python
async for chunk in stream_response(...):
    if chunk.type == "assistant_message" and chunk.content:
        subtask_result.append(chunk.content)
        
        if chunk.is_final:
            agent_finished = True
            logger.info(f"Subtask {subtask.id} received final message from LLM")
            # Don't forward is_final=True to client yet - we need to complete subtask first
            chunk.is_final = False  # ← КЛЮЧЕВОЕ ИЗМЕНЕНИЕ
    
    # Forward chunk (with modified is_final if needed)
    yield chunk
```

Теперь:
1. Агент отправляет финальное сообщение с `is_final: true`
2. `_execute_plan` получает chunk, устанавливает `agent_finished = True`
3. `_execute_plan` изменяет `chunk.is_final = False` перед отправкой клиенту
4. endpoints.py НЕ закрывает stream, продолжает ждать
5. Цикл `async for` завершается
6. Код после цикла выполняется (строки 405-452)
7. Проверяется `agent_finished` → подзадача завершается
8. Отправляется `subtask_completed` chunk
9. Продолжается выполнение следующей подзадачи или отправляется `plan_completed` с `is_final: true`

## Изменения

### Файл: `codelab-ai-service/agent-runtime/app/services/multi_agent_orchestrator.py`

**Строка 353-354** (в цикле continuation):
```python
if chunk.is_final:
    agent_finished = True
    logger.info(f"Subtask {subtask.id} received final message from LLM")
    # Don't forward is_final=True to client yet - we need to complete subtask first
    chunk.is_final = False
```

**Строка 387-388** (в цикле new subtask):
```python
if chunk.is_final:
    agent_finished = True
    logger.info(f"Subtask {subtask.id} received final message from agent")
    # Don't forward is_final=True to client yet - we need to complete subtask first
    chunk.is_final = False
```

## Логика работы

### Сценарий 1: Агент вызывает attempt_completion (идеально)
1. Агент вызывает `attempt_completion("Summary")`
2. `attempt_completion_called = True`
3. Код после цикла: `should_complete = True` (строка 409-411)
4. Подзадача завершается
5. Отправляется `subtask_completed`

### Сценарий 2: Агент отправляет is_final без инструментов (приемлемо)
1. Агент отправляет текстовое сообщение с `is_final: true`, не вызывая инструменты
2. `agent_finished = True`, `tool_called = False`
3. Код после цикла: `should_complete = True` (строка 412-414)
4. Подзадача завершается

### Сценарий 3: Агент отправляет is_final после вызова других инструментов (fallback)
1. Агент вызывает `read_file` → получает результат
2. Агент отправляет текстовое сообщение с `is_final: true`
3. `agent_finished = True`, `tool_called = True`, `attempt_completion_called = False`
4. Код после цикла: `should_complete = True` (строка 415-424, fallback)
5. Логируется warning
6. Подзадача завершается

## Ожидаемый результат

После этого исправления:
1. ✅ Подзадачи завершаются корректно
2. ✅ Нет преждевременного закрытия SSE stream
3. ✅ Отправляется `subtask_completed` chunk
4. ✅ План выполняется последовательно
5. ✅ Нет таймаутов и зависаний

## Связанные исправления

- [`ALL_AGENTS_ATTEMPT_COMPLETION_FIX.md`](ALL_AGENTS_ATTEMPT_COMPLETION_FIX.md) - промпты агентов
- [`SUBTASK_INFINITE_LOOP_FIX.md`](SUBTASK_INFINITE_LOOP_FIX.md) - логика завершения
- [`ORCHESTRATOR_CLASSIFICATION_FIX.md`](ORCHESTRATOR_CLASSIFICATION_FIX.md) - классификация
