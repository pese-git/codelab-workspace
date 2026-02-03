# КОРНЕВАЯ ПРИЧИНА ПРОБЛЕМЫ С TOOL EXECUTION НАЙДЕНА

## Дата: 2026-02-03
## Статус: 🎯 КОРНЕВАЯ ПРИЧИНА НАЙДЕНА И ПОДТВЕРЖДЕНА

## Резюме

Проблема "No tool output found for function call" возникает потому, что **`SubtaskExecutor` НЕ пересылает `tool_call` chunks от агента через SSE**.

## Корневая причина

**Файл**: [`subtask_executor.py:136-145`](codelab-ai-service/agent-runtime/app/domain/services/subtask_executor.py:136)

```python
# Выполнить подзадачу через агента
result_chunks = []
async for chunk in agent.process(
    session_id=session_id,
    message=subtask.description,
    context=context,
    session=session,
    session_service=session_service,
    stream_handler=stream_handler
):
    result_chunks.append(chunk)  # ❌ ПРОБЛЕМА: Только собирает chunks
    # Можно стримить прогресс через stream_handler  # ❌ Комментарий, но не реализовано!
```

### Что происходит:

1. ✅ Агент вызывает LLM
2. ✅ LLM возвращает `tool_call`
3. ✅ `StreamLLMResponseHandler` создает `StreamChunk` с `type="tool_call"`
4. ✅ `StreamChunk` возвращается через `yield` из `agent.process()`
5. ❌ **`SubtaskExecutor` получает chunk, но НЕ пересылает его дальше!**
6. ❌ Chunk только добавляется в `result_chunks` для локального сбора
7. ❌ SSE stream НЕ получает `tool_call` событие
8. ❌ Gateway НЕ получает `tool_call` событие
9. ❌ IDE НЕ получает `tool_call` событие
10. ❌ Инструмент НЕ выполняется
11. ❌ `tool_result` НЕ отправляется обратно
12. ❌ LLM получает ошибку "No tool output found"

## Доказательства

### 1. Логи Agent Runtime подтверждают

```
Tool call detected: execute_command (call_id=call_oCCFrSiHDjgwXkEHHxfHwngd)
Saving assistant message with tool_call: execute_command, call_id=call_oCCFrSiHDjgwXkEHHxfHwngd
```

✅ Tool call **ОБНАРУЖЕН** и **СОХРАНЕН** в Agent Runtime

### 2. Логи Gateway НЕ показывают tool_call

```
Received SSE data (event=None): type=status
Received SSE data (event=None): type=plan_created
Received SSE data (event=None): type=plan_approval_required
Received SSE data (event=None): type=execution_completed
```

❌ **НЕТ** `type=tool_call` событий!

### 3. История перед повторным вызовом LLM

```json
[
  {"role": "user", "content": "..."},
  {"role": "assistant", "tool_calls": [...]},  // ✅ Есть
  {"role": "assistant", "content": "[Error] No tool output found..."}  // ❌ Нет tool message!
]
```

❌ **НЕТ** `{"role": "tool", "tool_call_id": "...", "content": "..."}` в истории!

## Решение

### Вариант 1: Пересылать chunks через yield (РЕКОМЕНДУЕТСЯ)

Изменить `SubtaskExecutor.execute_subtask()` чтобы пересылать chunks:

```python
# Выполнить подзадачу через агента
result_chunks = []
async for chunk in agent.process(
    session_id=session_id,
    message=subtask.description,
    context=context,
    session=session,
    session_service=session_service,
    stream_handler=stream_handler
):
    result_chunks.append(chunk)
    
    # ✅ ИСПРАВЛЕНИЕ: Пересылать chunk дальше
    yield chunk  # Отправить chunk через SSE
```

Но это требует изменения сигнатуры метода на `AsyncGenerator[StreamChunk, None]`.

### Вариант 2: Обрабатывать tool_call chunks специально

```python
async for chunk in agent.process(...):
    result_chunks.append(chunk)
    
    # Если это tool_call, нужно дождаться tool_result от клиента
    if chunk.type == "tool_call":
        # Отправить chunk клиенту
        yield chunk
        
        # Дождаться tool_result (через какой-то механизм)
        # ...
```

### Вариант 3: Выполнять инструменты локально в SubtaskExecutor

```python
async for chunk in agent.process(...):
    result_chunks.append(chunk)
    
    # Если это tool_call, выполнить локально
    if chunk.type == "tool_call":
        # Выполнить инструмент
        tool_result = await execute_tool_locally(chunk.tool_name, chunk.arguments)
        
        # Отправить tool_result обратно в Agent Runtime
        await send_tool_result(session_id, chunk.call_id, tool_result)
```

## Рекомендуемое решение

**Вариант 1** - самый простой и правильный:

1. Изменить `SubtaskExecutor.execute_subtask()` на `AsyncGenerator`
2. Пересылать все chunks через `yield`
3. Это позволит tool_call событиям доходить до клиента
4. Клиент (Gateway/IDE) сможет выполнить инструменты
5. Клиент отправит tool_result обратно
6. Agent Runtime продолжит обработку

### Изменения в коде

**Файл**: `subtask_executor.py`

```python
async def execute_subtask(
    self,
    plan_id: str,
    subtask_id: str,
    session_id: str,
    session_service: "SessionManagementService",
    stream_handler: "IStreamHandler"
) -> AsyncGenerator[StreamChunk, None]:  # ✅ Изменить возвращаемый тип
    """Выполнить подзадачу в целевом агенте."""
    
    # ... (начало метода без изменений)
    
    try:
        # Получить целевого агента
        agent = self._get_agent_for_subtask(subtask)
        
        # Получить сессию
        session = await session_service.get_session(session_id)
        
        # Подготовить контекст
        context = self._prepare_agent_context(subtask, plan)
        
        # Выполнить подзадачу через агента
        result_chunks = []
        async for chunk in agent.process(
            session_id=session_id,
            message=subtask.description,
            context=context,
            session=session,
            session_service=session_service,
            stream_handler=stream_handler
        ):
            result_chunks.append(chunk)
            yield chunk  # ✅ ИСПРАВЛЕНИЕ: Пересылать chunk дальше
        
        # Собрать результат
        result = self._collect_result(result_chunks)
        
        # Завершить подзадачу
        subtask.complete(result=result["content"])
        await self.plan_repository.save(plan)
        
        # Отправить финальный chunk с результатом
        yield StreamChunk(
            type="subtask_completed",
            content=f"Subtask {subtask_id} completed",
            metadata={
                "subtask_id": subtask_id,
                "status": "completed",
                "result": result
            },
            is_final=True
        )
        
    except Exception as e:
        # ... (обработка ошибок)
        yield StreamChunk(
            type="error",
            error=str(e),
            is_final=True
        )
```

**Файл**: `execution_engine.py` (вызывающий код)

Нужно также изменить `ExecutionEngine` чтобы пересылать chunks от `SubtaskExecutor`.

## Следующие шаги

1. ✅ Изменить `SubtaskExecutor.execute_subtask()` на `AsyncGenerator`
2. ✅ Добавить `yield chunk` для пересылки chunks
3. ✅ Изменить `ExecutionEngine` для пересылки chunks
4. ✅ Протестировать выполнение плана с tool calls
5. ✅ Убедиться, что tool_call события доходят до Gateway/IDE
6. ✅ Реализовать выполнение инструментов в Gateway/IDE
7. ✅ Протестировать end-to-end flow

## Связанные документы

- [`TOOL_EXECUTION_PROBLEM.md`](TOOL_EXECUTION_PROBLEM.md) - первичный анализ
- [`TOOL_EXECUTION_ANALYSIS_COMPLETE.md`](TOOL_EXECUTION_ANALYSIS_COMPLETE.md) - полный анализ flow
- [`TOOL_EXECUTION_ROOT_CAUSE_FOUND.md`](TOOL_EXECUTION_ROOT_CAUSE_FOUND.md) - промежуточный анализ
- [`TOOL_EXECUTION_DIAGNOSTIC_LOGGING.md`](TOOL_EXECUTION_DIAGNOSTIC_LOGGING.md) - добавленное логирование
- [`PLAN_EXECUTION_FIX_COMPLETE.md`](PLAN_EXECUTION_FIX_COMPLETE.md) - исправления промпта Coder Agent

## Вывод

Проблема **НЕ** в Agent Runtime, **НЕ** в Gateway, **НЕ** в IDE.

Проблема в том, что **`SubtaskExecutor` не пересылает chunks от агента**, что приводит к тому, что `tool_call` события не доходят до клиента.

Решение простое: добавить `yield chunk` в цикле обработки chunks от агента.
