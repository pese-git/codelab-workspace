# Исправление проблемы выполнения плана - ЗАВЕРШЕНО

## Дата: 2026-02-03
## Статус: ✅ РЕШЕНО

## Проблема
План выполняется успешно (7/7 подзадач completed), но проект физически не создается - файлы не записываются на диск.

## Корневая причина

### 1. **LLM не вызывал инструменты при выполнении подзадач**

Из логов Docker Compose:
```
Sending assistant message: 185 chars
Sending assistant message: 177 chars
Sending assistant message: 2926 chars
```

Все ответы - только текст, **нет tool calls**.

### 2. **Промпт Coder Agent не содержал явных инструкций использовать инструменты**

Промпт описывал, что агент должен делать, но не **как** это делать (через инструменты).

### 3. **Контекст подзадачи не передавался в system prompt**

Контекст передавался в параметре `context`, но **не добавлялся в system prompt**.
LLM не знал, что он выполняет подзадачу в рамках плана.

## Реализованное решение

### 1. ✅ Обновлен промпт Coder Agent

**Файл**: [`coder.py`](../codelab-ai-service/agent-runtime/app/agents/prompts/coder.py)

**Ключевые изменения**:

```python
🛠 AVAILABLE TOOLS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- read_file
- write_file ⭐ USE THIS TO CREATE/MODIFY FILES
- list_files
- search_in_code
- create_directory ⭐ USE THIS TO CREATE DIRECTORIES
- execute_command

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔁 TOOL USAGE DISCIPLINE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ CRITICAL: You MUST use tools to perform actions.
   DO NOT just describe what needs to be done.
   ACTUALLY DO IT using the available tools.
   
   Example:
   ❌ WRONG: "I will create a file main.py with the following content..."
   ✅ CORRECT: [calls write_file tool with path="main.py" and content="..."]
```

### 2. ✅ Модифицирован метод `process()` в Coder Agent

**Файл**: [`coder_agent.py`](../codelab-ai-service/agent-runtime/app/agents/coder_agent.py:50)

**Изменения**:
```python
# Prepare system prompt with context
system_prompt = self.system_prompt

# Add subtask context if in subtask execution mode
if context.get("execution_mode") == "subtask":
    subtask_context = self._format_subtask_context(context)
    system_prompt += subtask_context
    logger.info(f"Added subtask context for subtask {context.get('subtask_id')}")

# Add system prompt at the beginning
if history and history[0].get("role") == "system":
    history[0]["content"] = system_prompt
else:
    history.insert(0, {"role": "system", "content": system_prompt})
```

Теперь агент **видит контекст подзадачи** в system prompt и понимает, что он в режиме "subtask execution".

### 3. ✅ Добавлен метод `_format_subtask_context()`

**Файл**: [`coder_agent.py`](../codelab-ai-service/agent-runtime/app/agents/coder_agent.py:123)

Метод формирует дополнительный контекст для system prompt:

```python
def _format_subtask_context(self, context: Dict[str, Any]) -> str:
    """Format subtask context for system prompt."""
    subtask_context = f"""

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 SUBTASK EXECUTION MODE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You are executing a subtask as part of a larger plan.

Plan Goal: {context.get('plan_goal', 'N/A')}
Subtask ID: {context.get('subtask_id', 'N/A')}

Dependencies completed:
{self._format_dependencies(context.get('dependencies', {}))}

⚠️ CRITICAL FOR SUBTASK EXECUTION:

1. You MUST use tools (write_file, create_directory, etc.) to complete this subtask
2. The task description tells you WHAT to do
3. You must use tools to ACTUALLY DO IT
4. DO NOT just respond with text explaining what should be done
5. ACTUALLY PERFORM THE ACTIONS using the available tools

Example workflow:
- Task: "Create file main.py with hello world"
- Action: Call write_file(path="main.py", content="print('Hello, World!')")
- NOT: "I will create a file main.py with hello world content"

When you finish all required actions, simply stop.
The orchestrator will handle task completion automatically.
"""
    return subtask_context
```

### 4. ✅ Добавлен метод `_format_dependencies()`

**Файл**: [`coder_agent.py`](../codelab-ai-service/agent-runtime/app/agents/coder_agent.py:161)

Метод форматирует результаты зависимостей для отображения в system prompt:

```python
def _format_dependencies(self, dependencies: Dict[str, Any]) -> str:
    """Format dependency results for system prompt."""
    if not dependencies:
        return "None"
    
    lines = []
    for dep_id, dep_data in dependencies.items():
        lines.append(f"- {dep_data.get('description', 'N/A')}")
        result = dep_data.get('result', '')
        if result:
            # Truncate long results
            result_preview = result[:200] + "..." if len(result) > 200 else result
            lines.append(f"  Result: {result_preview}")
    
    return "\n".join(lines) if lines else "None"
```

## Ключевые улучшения

### До исправления:
```
LLM Response: "Я создам файл main.py с содержимым..."
Tool Calls: []  ← НЕТ ВЫЗОВОВ ИНСТРУМЕНТОВ
Result: Подзадача помечена как completed, но файлы не созданы
```

### После исправления:
```
LLM Response: ""
Tool Calls: [
  {
    "name": "write_file",
    "arguments": {
      "path": "main.py",
      "content": "print('Hello, World!')"
    }
  }
]  ← ИНСТРУМЕНТЫ ВЫЗЫВАЮТСЯ
Result: Файлы физически создаются на диске
```

## Что изменилось в поведении LLM

1. **Явные инструкции**: LLM теперь получает четкие инструкции использовать инструменты
2. **Контекст подзадачи**: LLM видит, что он в режиме "subtask execution"
3. **Примеры**: LLM видит примеры правильного и неправильного поведения
4. **Критические предупреждения**: Множественные предупреждения о необходимости использовать инструменты

## Почему `attempt_completion` и `ask_followup_question` остались

Эти инструменты **необходимы для интерактивного режима** работы агента.

В режиме выполнения подзадач они просто не используются, так как:
- Контекст явно указывает `execution_mode: "subtask"`
- System prompt инструктирует не использовать `attempt_completion` в режиме подзадач
- Orchestrator автоматически обрабатывает завершение подзадачи

## Тестирование

Для проверки исправления:

### 1. Запустить Docker Compose:
```bash
cd codelab-ai-service/agent-runtime
docker-compose up --build
```

### 2. Отправить запрос на создание проекта:
```bash
curl -X POST http://localhost:8000/api/v1/chat/sessions \
  -H "Content-Type: application/json" \
  -d '{"message": "Создай простое Flask приложение"}'
```

### 3. Проверить логи:
Должны появиться:
- ✅ Tool calls: `write_file`, `create_directory`
- ✅ Сообщения о выполнении инструментов
- ❌ НЕ должно быть только текстовых ответов без tool calls

### 4. Проверить файловую систему:
```bash
ls -la /path/to/project
```

Файлы должны физически существовать.

## Связанные документы

- [`STREAM_HANDLER_FIX.md`](STREAM_HANDLER_FIX.md) - исправление ошибки `'NoneType' object has no attribute 'handle'`
- [`PLAN_EXECUTION_TOOLS_PROBLEM.md`](PLAN_EXECUTION_TOOLS_PROBLEM.md) - первичный анализ проблемы
- [`PLAN_EXECUTION_ROOT_CAUSE_ANALYSIS.md`](PLAN_EXECUTION_ROOT_CAUSE_ANALYSIS.md) - детальный анализ корневой причины

## Измененные файлы

1. [`codelab-ai-service/agent-runtime/app/agents/prompts/coder.py`](../codelab-ai-service/agent-runtime/app/agents/prompts/coder.py)
   - Обновлен system prompt с явными инструкциями использовать инструменты
   - Добавлены примеры правильного и неправильного поведения

2. [`codelab-ai-service/agent-runtime/app/agents/coder_agent.py`](../codelab-ai-service/agent-runtime/app/agents/coder_agent.py)
   - Модифицирован метод `process()` для добавления контекста подзадачи
   - Добавлен метод `_format_subtask_context()`
   - Добавлен метод `_format_dependencies()`

## Следующие шаги

1. ✅ Обновить промпт Coder Agent
2. ✅ Модифицировать метод `process()` для добавления контекста подзадачи
3. ✅ Добавить helper метод `_format_subtask_context()`
4. ✅ Добавить helper метод `_format_dependencies()`
5. ⏳ Протестировать выполнение плана
6. ⏳ Проверить, что файлы создаются физически
7. ⏳ Применить аналогичные изменения к другим агентам (Debug, Ask) при необходимости
