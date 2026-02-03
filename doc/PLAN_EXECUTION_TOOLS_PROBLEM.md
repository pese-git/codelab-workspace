# Проблема: План выполняется, но проект не создается

## Симптомы

1. ✅ План создается успешно
2. ✅ План одобряется пользователем
3. ✅ FSM transitions работают: `plan_review` → `plan_execution` → `completed`
4. ✅ Все 7 подзадач завершаются со статусом `completed`
5. ❌ **НО**: Проект физически не создается - нет файлов, нет директорий

## Анализ логов

### Что происходит

Из логов `docker compose logs agent-runtime --tail=200`:

```
2026-02-03 12:57:06,991 - agent-runtime.application.execution_coordinator - INFO - 
Plan 6d7852ec-da0f-4f1f-9b36-51473d0abb80 execution completed: 
status=completed, completed=7/7, failed=0, duration=35.13s
```

Все подзадачи выполнились успешно, но:

```
2026-02-03 12:56:47,896 - agent-runtime.domain.tool_filter_service - WARNING - 
Requested unknown tools: ['attempt_completion', 'ask_followup_question']. 
Available tools: ['calculator', 'create_directory', 'echo', 'execute_command', 
'list_files', 'read_file', 'search_in_code', 'switch_mode', 'write_file']
```

### Корневая причина

**Агенты запрашивают несуществующие инструменты, что приводит к неправильной фильтрации.**

#### 1. Агенты определяют `allowed_tools` с несуществующими инструментами

**Файл:** [`coder_agent.py`](../codelab-ai-service/agent-runtime/app/agents/coder_agent.py:38-47)

```python
allowed_tools=[
    "read_file",
    "write_file",
    "list_files",
    "search_in_code",
    "create_directory",
    "execute_command",
    "attempt_completion",      # ← НЕ ЗАРЕГИСТРИРОВАН!
    "ask_followup_question"    # ← НЕ ЗАРЕГИСТРИРОВАН!
]
```

То же самое в:
- [`debug_agent.py`](../codelab-ai-service/agent-runtime/app/agents/debug_agent.py:42-47)
- [`ask_agent.py`](../codelab-ai-service/agent-runtime/app/agents/ask_agent.py:43-47)
- [`architect_agent.py`](../codelab-ai-service/agent-runtime/app/agents/architect_agent.py:51-56)

#### 2. Tool Registry не содержит эти инструменты

**Файл:** [`tool_registry.py`](../codelab-ai-service/agent-runtime/app/domain/services/tool_registry.py:83-333)

Зарегистрированные инструменты:
- ✅ `echo`
- ✅ `calculator`
- ✅ `switch_mode`
- ✅ `read_file`
- ✅ `write_file`
- ✅ `list_files`
- ✅ `create_directory`
- ✅ `execute_command`
- ✅ `search_in_code`

Отсутствуют:
- ❌ `attempt_completion`
- ❌ `ask_followup_question`

#### 3. Tool Filter Service выдает WARNING

**Файл:** [`tool_filter_service.py`](../codelab-ai-service/agent-runtime/app/domain/services/tool_filter_service.py)

```python
# Проверка на неизвестные инструменты
unknown_tools = [t for t in allowed_tools if t not in available_tool_names]
if unknown_tools:
    logger.warning(
        f"Requested unknown tools: {unknown_tools}. "
        f"Available tools: {available_tool_names}"
    )
```

#### 4. Результат: LLM не получает правильные инструменты

Когда `tool_filter_service` видит неизвестные инструменты в `allowed_tools`, он:
1. Логирует WARNING
2. Фильтрует инструменты
3. **Возможно, возвращает пустой или неполный список инструментов**

В результате LLM:
- ❌ Не может вызвать `write_file`
- ❌ Не может вызвать `create_directory`
- ❌ Не может вызвать `execute_command`
- ✅ Может только отвечать текстом

### Доказательство

Из логов видно, что все подзадачи возвращают только **текстовые ответы** (assistant messages), а не tool calls:

```
2026-02-03 12:56:47,879 - agent-runtime.application.stream_llm_response_handler - INFO - 
Sending assistant message: 185 chars

2026-02-03 12:56:50,674 - agent-runtime.application.stream_llm_response_handler - INFO - 
Sending assistant message: 177 chars

2026-02-03 12:57:04,841 - agent-runtime.application.stream_llm_response_handler - INFO - 
Sending assistant message: 2926 chars

2026-02-03 12:57:06,973 - agent-runtime.application.stream_llm_response_handler - INFO - 
Sending assistant message: 209 chars
```

**Нет ни одного tool call!** Все ответы - это `assistant_message`, а не `tool_call`.

## Решение

### Вариант 1: Удалить несуществующие инструменты из агентов (РЕКОМЕНДУЕТСЯ)

Удалить `attempt_completion` и `ask_followup_question` из `allowed_tools` во всех агентах:

**Файлы для изменения:**
- [`coder_agent.py`](../codelab-ai-service/agent-runtime/app/agents/coder_agent.py:38-47)
- [`debug_agent.py`](../codelab-ai-service/agent-runtime/app/agents/debug_agent.py:42-47)
- [`ask_agent.py`](../codelab-ai-service/agent-runtime/app/agents/ask_agent.py:43-47)
- [`architect_agent.py`](../codelab-ai-service/agent-runtime/app/agents/architect_agent.py:51-56)

**Изменение:**
```python
# БЫЛО:
allowed_tools=[
    "read_file",
    "write_file",
    "list_files",
    "search_in_code",
    "create_directory",
    "execute_command",
    "attempt_completion",      # ← УДАЛИТЬ
    "ask_followup_question"    # ← УДАЛИТЬ
]

# СТАЛО:
allowed_tools=[
    "read_file",
    "write_file",
    "list_files",
    "search_in_code",
    "create_directory",
    "execute_command"
]
```

### Вариант 2: Добавить инструменты в Tool Registry

Если `attempt_completion` и `ask_followup_question` действительно нужны, добавить их в [`tool_registry.py`](../codelab-ai-service/agent-runtime/app/domain/services/tool_registry.py).

**НО**: Эти инструменты, скорее всего, не нужны для выполнения подзадач в плане. Они используются для интерактивного взаимодействия с пользователем, что не имеет смысла в контексте автоматического выполнения плана.

## Проверка Tool Filter Service

Нужно также проверить логику фильтрации в [`tool_filter_service.py`](../codelab-ai-service/agent-runtime/app/domain/services/tool_filter_service.py), чтобы убедиться, что при наличии неизвестных инструментов в `allowed_tools` не фильтруются **все** инструменты.

## Следующие шаги

1. ✅ Исправлен `stream_handler` - теперь передается корректно
2. ⏳ **ТЕКУЩАЯ ПРОБЛЕМА**: Удалить `attempt_completion` и `ask_followup_question` из `allowed_tools` всех агентов
3. ⏳ Проверить логику `tool_filter_service.filter_tools()`
4. ⏳ Перезапустить и протестировать выполнение плана

## Связанные файлы

- [`coder_agent.py`](../codelab-ai-service/agent-runtime/app/agents/coder_agent.py)
- [`debug_agent.py`](../codelab-ai-service/agent-runtime/app/agents/debug_agent.py)
- [`ask_agent.py`](../codelab-ai-service/agent-runtime/app/agents/ask_agent.py)
- [`architect_agent.py`](../codelab-ai-service/agent-runtime/app/agents/architect_agent.py)
- [`tool_registry.py`](../codelab-ai-service/agent-runtime/app/domain/services/tool_registry.py)
- [`tool_filter_service.py`](../codelab-ai-service/agent-runtime/app/domain/services/tool_filter_service.py)
