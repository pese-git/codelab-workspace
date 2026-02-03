# Диагностическое логирование для проблемы с выполнением инструментов

## Дата: 2026-02-03
## Статус: ✅ ЛОГИРОВАНИЕ ДОБАВЛЕНО

## Резюме

Добавлено детальное логирование в ключевых точках tool execution flow для диагностики проблемы "No tool output found for function call".

## Добавленное логирование

### 1. LLM Client - История перед вызовом LLM

**Файл**: [`llm_client.py:169-175`](codelab-ai-service/agent-runtime/app/infrastructure/llm/llm_client.py:169)

```python
# DIAGNOSTIC: Детальное логирование истории для диагностики tool execution
logger.info(
    f"Calling LLM: model={model}, messages={len(messages)}, "
    f"tools={len(tools)}"
)
logger.debug(f"Full history before LLM call:\n{json.dumps(messages, indent=2, ensure_ascii=False)}")
```

**Что логируется**:
- Полная история сообщений в JSON формате
- Количество сообщений и инструментов
- Формат каждого сообщения (role, content, tool_calls, tool_call_id)

**Зачем**:
- Проверить, что assistant message с tool_calls присутствует в истории
- Проверить, что tool message с tool_call_id присутствует в истории
- Проверить формат tool_calls (id, type, function.name, function.arguments)

### 2. Stream Handler - Формат tool_call перед сохранением

**Файл**: [`stream_llm_response_handler.py:314-320`](codelab-ai-service/agent-runtime/app/application/handlers/stream_llm_response_handler.py:314)

```python
# DIAGNOSTIC: Логирование формата tool_call перед сохранением
logger.info(
    f"Saving assistant message with tool_call: {tool_call.tool_name}, "
    f"call_id={tool_call.id}"
)
logger.debug(f"Tool call dict format:\n{json.dumps(tool_call_dict, indent=2, ensure_ascii=False)}")
```

**Что логируется**:
- Имя инструмента и call_id
- Полный формат tool_call в JSON (id, type, function.name, function.arguments)

**Зачем**:
- Проверить, что tool_call сохраняется в правильном формате
- Проверить, что arguments правильно сериализуются в JSON строку

### 3. Tool Result Handler - Добавление tool_result

**Файл**: [`tool_result_handler.py:163-167`](codelab-ai-service/agent-runtime/app/domain/services/tool_result_handler.py:163)

```python
logger.info(
    f"Результат инструмента добавлен в сессию {session_id}, "
    f"call_id={call_id}, has_error={error is not None}, "
    f"продолжаем обработку с агентом {context.current_agent.value}"
)
```

**Что логируется**:
- Session ID и call_id
- Наличие ошибки в результате
- Текущий агент, который продолжит обработку

**Зачем**:
- Проверить, что tool_result добавляется с правильным call_id
- Проверить, что агент продолжает обработку после получения результата

## Как использовать логи для диагностики

### Шаг 1: Запустить тест с tool call

```bash
# Запустить Agent Runtime с уровнем логирования DEBUG
cd codelab-ai-service/agent-runtime
export LOG_LEVEL=DEBUG
python -m uvicorn app.main:app --reload
```

### Шаг 2: Отправить запрос, который вызовет инструмент

Например, через CLI клиент:
```bash
cd codelab-ai-service/client
python cli_chat.py
# Ввести: "список файлов в текущей директории"
```

### Шаг 3: Проверить логи

#### 3.1. Первый вызов LLM (до tool_call)

Искать в логах:
```
INFO - Calling LLM: model=gpt-4, messages=1, tools=9
DEBUG - Full history before LLM call:
[
  {
    "role": "user",
    "content": "список файлов в текущей директории"
  }
]
```

✅ **Ожидается**: История содержит только user message

#### 3.2. Сохранение tool_call

Искать в логах:
```
INFO - Saving assistant message with tool_call: list_files, call_id=call_xxx
DEBUG - Tool call dict format:
{
  "id": "call_xxx",
  "type": "function",
  "function": {
    "name": "list_files",
    "arguments": "{\"path\": \".\", \"recursive\": false}"
  }
}
```

✅ **Проверить**:
- `id` присутствует и не пустой
- `type` = "function"
- `function.arguments` - это JSON строка, а не объект

#### 3.3. Добавление tool_result

Искать в логах:
```
INFO - Результат инструмента добавлен в сессию session-xxx, call_id=call_xxx, has_error=False, продолжаем обработку с агентом coder
```

✅ **Проверить**:
- `call_id` совпадает с `id` из tool_call
- `has_error=False` (если инструмент выполнился успешно)

#### 3.4. Второй вызов LLM (после tool_result)

Искать в логах:
```
INFO - Calling LLM: model=gpt-4, messages=3, tools=9
DEBUG - Full history before LLM call:
[
  {
    "role": "user",
    "content": "список файлов в текущей директории"
  },
  {
    "role": "assistant",
    "content": "",
    "tool_calls": [
      {
        "id": "call_xxx",
        "type": "function",
        "function": {
          "name": "list_files",
          "arguments": "{\"path\": \".\", \"recursive\": false}"
        }
      }
    ]
  },
  {
    "role": "tool",
    "tool_call_id": "call_xxx",
    "content": "{\"files\": [...]}"
  }
]
```

✅ **Проверить**:
- История содержит 3 сообщения: user, assistant, tool
- Assistant message имеет `tool_calls` массив
- Tool message имеет `tool_call_id` который совпадает с `tool_calls[0].id`
- `function.arguments` - это JSON строка

### Шаг 4: Найти проблему

Если ошибка "No tool output found" все еще возникает, проверить:

1. **tool_call_id не совпадает с id**
   ```
   ❌ tool_calls[0].id = "call_xxx"
   ❌ tool_call_id = "call_yyy"  # РАЗНЫЕ!
   ```

2. **function.arguments не JSON строка**
   ```
   ❌ "arguments": {"path": ".", "recursive": false}  # Объект вместо строки!
   ```

3. **tool message отсутствует в истории**
   ```
   ❌ История содержит только user и assistant, но нет tool message
   ```

4. **assistant message без tool_calls**
   ```
   ❌ {
     "role": "assistant",
     "content": ""
     # tool_calls отсутствует!
   }
   ```

## Ожидаемый результат

После добавления логирования мы сможем точно определить:

1. ✅ Правильно ли формируется история для LLM
2. ✅ Сохраняется ли assistant message с tool_calls
3. ✅ Добавляется ли tool message с правильным tool_call_id
4. ✅ Совпадают ли id между tool_call и tool_result
5. ✅ Правильно ли форматируются arguments (JSON строка vs объект)

## Следующие шаги

1. ✅ Запустить тест с добавленным логированием
2. ⏳ Проанализировать логи и найти точную причину ошибки
3. ⏳ Исправить проблему на основе найденной причины
4. ⏳ Протестировать исправление
5. ⏳ Удалить диагностическое логирование (или оставить на уровне DEBUG)

## Измененные файлы

1. [`llm_client.py`](codelab-ai-service/agent-runtime/app/infrastructure/llm/llm_client.py)
   - Добавлено логирование полной истории перед вызовом LLM

2. [`stream_llm_response_handler.py`](codelab-ai-service/agent-runtime/app/application/handlers/stream_llm_response_handler.py)
   - Добавлен импорт `json`
   - Добавлено логирование формата tool_call перед сохранением

3. [`tool_result_handler.py`](codelab-ai-service/agent-runtime/app/domain/services/tool_result_handler.py)
   - Добавлено логирование call_id при добавлении tool_result

## Связанные документы

- [`TOOL_EXECUTION_PROBLEM.md`](TOOL_EXECUTION_PROBLEM.md) - первичный анализ проблемы
- [`TOOL_EXECUTION_ANALYSIS_COMPLETE.md`](TOOL_EXECUTION_ANALYSIS_COMPLETE.md) - полный анализ flow
- [`PLAN_EXECUTION_FIX_COMPLETE.md`](PLAN_EXECUTION_FIX_COMPLETE.md) - исправления промпта Coder Agent
