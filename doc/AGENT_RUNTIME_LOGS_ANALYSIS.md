# Анализ логов Agent Runtime

**Дата:** 2026-02-10  
**Контейнер:** `codelab-ai-service-agent-runtime-1`  
**Статус:** Up 31 minutes (healthy)

## 📊 Общая информация

Контейнер работает и проходит health checks, но в логах обнаружены критические ошибки во время выполнения запросов.

## 🔴 Критические ошибки

### 1. TypeError в SubtaskExecutor (КРИТИЧНО)

**Локация:** `/app/app/core/di/execution_module.py:100`

```python
TypeError: SubtaskExecutor.__init__() got an unexpected keyword argument 'agent_registry'
```

**Стек вызовов:**
```
messages_router.py:287 -> hitl_decision_generate
  -> container.get_handle_approval_use_case(uow.session)
    -> container._create_plan_approval_handler(db)
      -> execution_module.provide_subtask_executor()
        -> SubtaskExecutor(agent_registry=...)  # ❌ ОШИБКА
```

**Проблема:**
- При создании `SubtaskExecutor` передается параметр `agent_registry`, который не существует в конструкторе
- Это происходит в контексте HITL (Human-in-the-Loop) approval flow
- Ошибка блокирует функциональность одобрения планов

**Затронутый функционал:**
- ❌ Plan approval через HITL
- ❌ Генерация решений для одобрения
- ❌ Endpoint: `POST /agent/message/stream` (hitl_decision_generate)

---

### 2. AttributeError в ProcessToolResultUseCase

**Локация:** `/app/app/application/use_cases/process_tool_result_use_case.py:145`

```python
AttributeError: 'NoneType' object has no attribute 'get'
```

**Код:**
```python
f"Новый tool call: {chunk.metadata.get('tool_name')} "
                    ^^^^^^^^^^^^^^^^^^
```

**Проблема:**
- `chunk.metadata` равен `None`
- Попытка вызвать `.get()` на `None` вызывает AttributeError
- Происходит при обработке tool_call chunks

**Контекст:**
```
Session: 4fc6b049-5204-4f0a-aef3-2f223ee48fb1
Call ID: call_Zet4BKuvSvjJxzQr5DiFQOOp
Tool: execute_command (dart test)
```

**Последствия:**
- ⚠️ Ошибка логируется, но не прерывает выполнение
- Может привести к потере метаданных о tool calls
- Влияет на отладку и мониторинг

---

### 3. LLM Provider Error (OpenRouter/Azure)

**Локация:** LLM Proxy -> OpenRouter -> Azure

```json
{
  "error": {
    "message": "No tool output found for function call call_Utq12oy7uYcGPkto12yRwluw.",
    "type": "invalid_request_error",
    "code": "400"
  }
}
```

**Проблема:**
- Azure OpenAI не находит результат для tool call `call_Utq12oy7uYcGPkto12yRwluw`
- Это происходит из-за дублирования tool_call_id в истории сообщений

**Анализ истории сообщений:**

```json
[
  // Первый tool call
  {"role": "assistant", "tool_calls": [{"id": "call_Zet4BKuvSvjJxzQr5DiFQOOp", "function": {"name": "execute_command"}}]},
  {"role": "tool", "content": "...", "tool_call_id": "call_Zet4BKuvSvjJxzQr5DiFQOOp"},
  
  // Второй tool call
  {"role": "assistant", "tool_calls": [{"id": "call_Utq12oy7uYcGPkto12yRwluw", "function": {"name": "list_files"}}]},
  
  // ❌ ПРОБЛЕМА: Неправильный tool_call_id
  {"role": "tool", "content": "...", "tool_call_id": "call_Zet4BKuvSvjJxzQr5DiFQOOp"},  // Должен быть call_Utq12oy7uYcGPkto12yRwluw
  
  // Следующий запрос к LLM с этой историей
  // Azure видит tool call call_Utq12oy7uYcGPkto12yRwluw без соответствующего результата
]
```

**Корневая причина:**
- Неправильная привязка результатов инструментов к tool_call_id
- Возможно, проблема в `conversation_mapper.py` или `tool_result_handler.py`

---

## ⚠️ Предупреждения

### 1. Дублирование tool results

В логах видно, что один и тот же tool result обрабатывается дважды:

```
13:18:46,033 - Processing tool_result: call_id=call_Zet4BKuvSvjJxzQr5DiFQOOp
13:18:47,977 - Processing tool_result: call_id=call_Zet4BKuvSvjJxzQr5DiFQOOp (повторно)
```

**Возможные причины:**
- Retry логика в gateway
- Проблемы с SSE (Server-Sent Events) потоком
- Race condition в обработке результатов

---

## ✅ Что работает корректно

1. **Health checks:** Контейнер здоров
2. **Database:** Postgres подключение работает
3. **LLM Client:** Успешные запросы к llm-proxy
4. **Session management:** Сессии создаются и сохраняются
5. **Conversation persistence:** Сообщения сохраняются в БД
6. **Agent switching:** Переключение orchestrator → coder работает
7. **Tool execution:** Инструменты выполняются (execute_command, list_files)
8. **Metrics collection:** LLM метрики собираются корректно

---

## 🔍 Детальный анализ сессии

**Session ID:** `4fc6b049-5204-4f0a-aef3-2f223ee48fb1`

### Последовательность событий:

1. **User message:** "вызови dart test"
2. **Agent switch:** orchestrator → coder
3. **Tool call 1:** `execute_command("dart test")`
   - ✅ Выполнено успешно
   - Exit code: 65 (No pubspec.yaml found)
4. **Tool call 2:** `list_files(".", pattern="pubspec.yaml")`
   - ✅ Выполнено успешно
   - Result: empty list
5. **LLM Response 1:** Assistant message (646 chars)
   - ✅ Сохранено в БД
6. **LLM Response 2:** Assistant message (239 chars)
   - ✅ Сохранено в БД
   - ⚠️ Но с ошибкой от Azure о missing tool output

### Метрики сессии:

```
Total LLM requests: 4
Total tokens: 4847
Average response time: ~3.5s
```

---

## 🛠 Рекомендации по исправлению

### Приоритет 1: SubtaskExecutor TypeError

**Файл:** `codelab-ai-service/agent-runtime/app/core/di/execution_module.py`

```python
# Проверить сигнатуру SubtaskExecutor.__init__()
# Убрать или добавить параметр agent_registry в зависимости от реализации
```

**Проверить также:**
- `app/application/execution/subtask_executor.py`
- Все места создания SubtaskExecutor

### Приоритет 2: chunk.metadata AttributeError

**Файл:** `codelab-ai-service/agent-runtime/app/application/use_cases/process_tool_result_use_case.py:145`

```python
# Было:
f"Новый tool call: {chunk.metadata.get('tool_name')} "

# Должно быть:
f"Новый tool call: {chunk.metadata.get('tool_name') if chunk.metadata else 'unknown'} "
```

### Приоритет 3: Tool call ID mismatch

**Файлы для проверки:**
- `app/infrastructure/persistence/mappers/conversation_mapper.py`
- `app/domain/tool_result_handler.py`
- `app/application/handlers/stream_llm_response_handler.py`

**Проверить:**
1. Правильность привязки tool results к tool_call_id
2. Логику сохранения tool messages в БД
3. Восстановление истории из БД

---

## 📈 Статистика логов

- **Всего строк:** ~500
- **Ошибок (ERROR):** 1
- **Исключений (Exception/Traceback):** 2
- **Предупреждений (WARNING):** 0
- **Успешных HTTP запросов:** Множество (200 OK)
- **Health checks:** Регулярные, успешные

---

## 🎯 Следующие шаги

1. ✅ **Немедленно:** Исправить SubtaskExecutor TypeError
2. ✅ **Высокий приоритет:** Исправить chunk.metadata AttributeError
3. ⚠️ **Средний приоритет:** Исследовать tool_call_id mismatch
4. 📊 **Низкий приоритет:** Оптимизировать дублирование tool result processing

---

## 📝 Дополнительные наблюдения

### Положительные моменты:

1. **Resilience:** Система продолжает работать несмотря на ошибки
2. **Logging:** Отличное логирование на всех уровнях
3. **Transactions:** UnitOfWork корректно управляет транзакциями
4. **Lock management:** Session locks работают правильно
5. **Event-driven:** Event bus публикует события корректно

### Области для улучшения:

1. **Error handling:** Некоторые ошибки не обрабатываются gracefully
2. **Validation:** Нужна валидация chunk.metadata перед использованием
3. **DI configuration:** Несоответствие в dependency injection для SubtaskExecutor
4. **Tool result mapping:** Проблемы с привязкой результатов к вызовам

---

## 🔗 Связанные файлы

- [`messages_router.py:287`](../codelab-ai-service/agent-runtime/app/api/v1/routers/messages_router.py)
- [`execution_module.py:100`](../codelab-ai-service/agent-runtime/app/core/di/execution_module.py)
- [`process_tool_result_use_case.py:145`](../codelab-ai-service/agent-runtime/app/application/use_cases/process_tool_result_use_case.py)
- [`conversation_mapper.py`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/mappers/conversation_mapper.py)
- [`tool_result_handler.py`](../codelab-ai-service/agent-runtime/app/domain/tool_result_handler.py)

---

**Анализ выполнен:** 2026-02-10 16:20 (UTC+3)  
**Версия:** Docker Compose logs (последние 500 строк)
