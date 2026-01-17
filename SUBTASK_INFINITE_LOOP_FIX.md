# Исправление: Бесконечный цикл при выполнении подзадач

## Проблема

При выполнении подзадач в рамках плана агент Coder попадал в бесконечный цикл:
1. Читал файл и видел, что задача уже выполнена
2. Вместо вызова `attempt_completion` снова вызывал `read_file`
3. Система продолжала выполнение после каждого `tool_result`
4. Цикл повторялся бесконечно (96+ вызовов одного и того же инструмента)

## Пример из логов

```
Tool call #75: read_file (lib/widgets/login_form.dart)
Tool call #76: read_file (lib/widgets/login_form.dart)
Tool call #77: read_file (lib/widgets/login_form.dart)
...
Tool call #96: read_file (lib/widgets/login_form.dart)
```

Агент читал один и тот же файл снова и снова, не вызывая `attempt_completion`.

## Причина

В [`multi_agent_orchestrator.py`](codelab-ai-service/agent-runtime/app/services/multi_agent_orchestrator.py:394-428) логика определения завершения подзадачи была неправильной:

**Старый код (строка 395):**
```python
if agent_finished or not tool_called:
    # Mark subtask as complete
```

Эта логика говорила: "завершить подзадачу, если агент отправил финальное сообщение ИЛИ не вызвал инструмент".

**Проблема:**
- Когда агент вызывал `read_file`, `tool_called=True` и `agent_finished=False`
- Условие не выполнялось, подзадача не завершалась
- Система продолжала выполнение, вызывая LLM снова
- LLM снова вызывал `read_file` вместо `attempt_completion`
- Бесконечный цикл

## Решение

Изменена логика определения завершения подзадачи - теперь проверяется, был ли вызван инструмент `attempt_completion`:

**Новый код:**
```python
attempt_completion_called = False

# Check if tool was called
if chunk.type == "tool_call":
    tool_called = True
    # Check if it's attempt_completion
    if chunk.tool_name == "attempt_completion":
        attempt_completion_called = True
        logger.info(f"Subtask {subtask.id} called attempt_completion - task complete!")
    else:
        logger.info(f"Subtask {subtask.id} called tool {chunk.tool_name}, waiting for tool_result")

# Mark as complete if attempt_completion was called OR agent finished without calling tools
if attempt_completion_called or (agent_finished and not tool_called):
    # Mark subtask as complete
```

## Изменения

### Файл: `codelab-ai-service/agent-runtime/app/services/multi_agent_orchestrator.py`

1. **Строка 324**: Добавлена переменная `attempt_completion_called = False`

2. **Строки 345-352, 377-384**: Добавлена проверка имени инструмента:
   ```python
   if chunk.tool_name == "attempt_completion":
       attempt_completion_called = True
       logger.info(f"Subtask {subtask.id} called attempt_completion - task complete!")
   ```

3. **Строка 395**: Изменено условие завершения:
   ```python
   # Было:
   if agent_finished or not tool_called:
   
   # Стало:
   if attempt_completion_called or (agent_finished and not tool_called):
   ```

## Логика работы

### До исправления
1. Агент вызывает `read_file` → `tool_called=True`, `agent_finished=False`
2. Условие `agent_finished or not tool_called` = `False or False` = `False`
3. Подзадача НЕ завершается
4. Система продолжает выполнение → агент снова вызывает `read_file`
5. Бесконечный цикл

### После исправления
1. Агент вызывает `read_file` → `tool_called=True`, `attempt_completion_called=False`
2. Условие `attempt_completion_called or (agent_finished and not tool_called)` = `False`
3. Подзадача НЕ завершается, ждем следующего вызова
4. Агент вызывает `attempt_completion` → `attempt_completion_called=True`
5. Условие = `True` → подзадача завершается ✅
6. Переход к следующей подзадаче

## Ожидаемый результат

После этого исправления:
1. ✅ Агент может вызывать любые инструменты (`read_file`, `write_file`, etc.)
2. ✅ Подзадача завершается ТОЛЬКО когда агент вызывает `attempt_completion`
3. ✅ Нет бесконечных циклов вызовов одного и того же инструмента
4. ✅ Система корректно переходит к следующей подзадаче

## Связанные исправления

Это исправление работает в связке с исправлениями промптов:
- [`AGENT_ATTEMPT_COMPLETION_FIX.md`](AGENT_ATTEMPT_COMPLETION_FIX.md) - Coder agent
- [`ALL_AGENTS_ATTEMPT_COMPLETION_FIX.md`](ALL_AGENTS_ATTEMPT_COMPLETION_FIX.md) - все агенты

Промпты инструктируют агентов вызывать `attempt_completion`, а оркестратор теперь правильно обрабатывает этот вызов.

## Тестирование

Тестируется на task_006 (создание формы с валидацией), которая создает план с 3 подзадачами.
