# Исправление проблемы множественных вызовов инструментов

## Проблема

AI агент (agent-runtime) неправильно вызывал инструменты, пытаясь выполнить несколько операций одновременно, не дожидаясь завершения предыдущих.

### Симптомы

При выполнении команды `flutter create -t app .` агент:
1. Вызывал `execute_command` для создания проекта
2. **Немедленно** пытался вызвать `read_file` для чтения созданных файлов
3. Файлы еще не существовали, так как команда не завершилась

Это приводило к ошибкам "файл не найден" и некорректной работе агента.

## Причина

В системном промпте [`SYSTEM_PROMPT`](../codelab-ai-service/agent-runtime/app/core/agent/prompts.py) отсутствовали критически важные инструкции о том, что агент должен:

1. **Использовать только один инструмент за раз**
2. **Ждать результата выполнения инструмента перед следующим вызовом**
3. **Работать итеративно, шаг за шагом**

## Решение

### 1. Обновление системного промпта

Добавлены критические правила использования инструментов в [`prompts.py`](../codelab-ai-service/agent-runtime/app/core/agent/prompts.py:133-143):

```python
CRITICAL: Tool Usage Rules:
- You MUST use exactly ONE tool at a time. Never call multiple tools in the same response.
- After each tool use, you MUST wait for the user's response with the tool execution result.
- Work iteratively: use tool → wait for result → analyze result → use next tool if needed.
- DO NOT assume or predict tool results. Always wait for actual execution results.
- Example: When running "flutter create", you must:
  1. Call execute_command with "flutter create" command
  2. Wait for the command completion result from the user
  3. Only after receiving confirmation that files were created, then call read_file or list_files
- NEVER try to read files that don't exist yet (e.g., before "flutter create" completes).
- Each tool call is a separate step that requires user confirmation before proceeding.
```

### 2. Добавление валидации в коде

Добавлена валидация в [`llm_stream_service.py`](../codelab-ai-service/agent-runtime/app/services/llm_stream_service.py:112-122), которая:

- Проверяет количество вызванных инструментов
- Логирует предупреждение, если LLM попытался вызвать несколько инструментов
- Выполняет только первый инструмент
- Информирует о нарушении правила "один инструмент за раз"

```python
# КРИТИЧЕСКАЯ ВАЛИДАЦИЯ: Агент должен вызывать только ОДИН инструмент за раз
if len(tool_calls) > 1:
    logger.warning(
        f"[Agent][VALIDATION] LLM attempted to call {len(tool_calls)} tools simultaneously! "
        f"This violates the one-tool-at-a-time rule. Tools: {[tc.tool_name for tc in tool_calls]}"
    )
    logger.warning(
        "[Agent][VALIDATION] Only the first tool call will be executed. "
        "The agent should wait for tool result before calling next tool."
    )
```

## Правильная последовательность работы

### Пример: Создание Flutter проекта

**Правильно:**
```
1. Агент: execute_command("flutter create -t app .")
2. Система: Выполняет команду, возвращает результат
3. Агент: Анализирует результат
4. Агент: list_files(".") - проверяет созданные файлы
5. Система: Возвращает список файлов
6. Агент: read_file("pubspec.yaml") - читает конфигурацию
7. Система: Возвращает содержимое файла
8. Агент: attempt_completion("Проект создан успешно")
```

**Неправильно (старое поведение):**
```
1. Агент: execute_command("flutter create -t app .") + read_file("pubspec.yaml") + list_files(".")
   ❌ Попытка вызвать 3 инструмента одновременно
   ❌ Файлы еще не созданы
   ❌ Ошибки "файл не найден"
```

## Преимущества исправления

1. **Надежность**: Агент всегда дожидается завершения операций
2. **Предсказуемость**: Четкая последовательность действий
3. **Отладка**: Логирование предупреждений помогает выявить проблемы
4. **Соответствие архитектуре**: Правильное использование итеративного подхода

## Тестирование

Для проверки исправления:

1. Запросите создание Flutter проекта
2. Проверьте логи - не должно быть предупреждений о множественных tool calls
3. Убедитесь, что агент выполняет операции последовательно
4. Проверьте, что файлы читаются только после завершения `flutter create`

## Связанные файлы

- [`prompts.py`](../codelab-ai-service/agent-runtime/app/core/agent/prompts.py) - Системный промпт с правилами
- [`llm_stream_service.py`](../codelab-ai-service/agent-runtime/app/services/llm_stream_service.py) - Валидация tool calls
- [`tool_parser.py`](../codelab-ai-service/agent-runtime/app/services/tool_parser.py) - Парсинг tool calls
- [`orchestrator.py`](../codelab-ai-service/agent-runtime/app/services/orchestrator.py) - Оркестрация выполнения

## Дата исправления

2025-12-29
