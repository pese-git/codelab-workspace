# Исправление: Улучшена классификация задач оркестратором

## Проблема

Оркестратор неправильно классифицировал простые задачи по добавлению/изменению кода, направляя их к агенту `ask` вместо `coder` или `architect`.

### Пример из логов

Задача: "В файле lib/constants/colors.dart добавить константу const Color primaryColor = Color(0xFF6200EE)"

**Неправильная классификация:**
```
orchestrator → ask (The user is asking for an analysis and classification...)
```

**Ожидаемая классификация:**
```
orchestrator → coder (Task involves adding code to a file)
```

## Причина

1. **Недостаточно четкий промпт классификации** - не было явных правил для определения типа задачи
2. **Слабые описания агентов** - не подчеркивали ключевые слова и действия
3. **Отсутствие поддержки русского языка** - fallback классификация не понимала русские ключевые слова

## Решение

### 1. Улучшен промпт классификации

Добавлены четкие правила и примеры в [`orchestrator_agent.py`](codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py:21-50):

```python
IMPORTANT CLASSIFICATION RULES:
- If the task involves CREATING, ADDING, MODIFYING, WRITING, or IMPLEMENTING code/files → use "coder"
- If the task involves DESIGNING, PLANNING architecture, or creating specifications → use "architect"  
- If the task involves DEBUGGING, FIXING errors, or investigating problems → use "debug"
- If the task is asking for EXPLANATION, DOCUMENTATION, or LEARNING → use "ask"

Examples:
- "Add constant to file" → coder
- "Create new component" → coder
- "Fix bug in code" → debug
- "Design system architecture" → architect
- "Explain how X works" → ask
```

### 2. Улучшены описания агентов

Добавлены ключевые слова и более четкие описания в [`orchestrator_agent.py`](codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py:38-71):

**До:**
```python
"coder": """**coder** - for writing, modifying, and refactoring code
   - Creating new files or components
   - Modifying existing code
   ...
```

**После:**
```python
"coder": """**coder** - for WRITING, MODIFYING, CREATING, ADDING, IMPLEMENTING code and files
   - Creating new files, components, or constants
   - Modifying existing code (add/remove/change lines)
   - Implementing features and functionality
   - Adding imports, dependencies, or configurations
   - Refactoring and code improvements
   - Running commands and tests
   Keywords: create, add, write, implement, modify, update, change, build, develop
```

### 3. Добавлена поддержка русского языка

Расширена fallback классификация с поддержкой русских ключевых слов в [`orchestrator_agent.py`](codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py:312-365):

```python
# Keyword matching for CODER (English + Russian)
coder_keywords = [
    "create", "write", "implement", "add", "build", "develop", "code", 
    "refactor", "modify", "update", "change", "file", "component", "constant",
    "создать", "создай", "добавить", "добавь", "написать", "напиши", 
    "реализовать", "реализуй", "изменить", "измени", "файл", "константу"
]
```

## Результаты тестирования

### До исправления
```
❌ Task task_005 ПРОВАЛЕНА (67.69s)
- Неправильная маршрутизация: orchestrator → ask
- Таймаут выполнения
- Success rate: 0.00%
```

### После исправления
```
✅ Task task_005 УСПЕШНО завершена (19.70s)
- Правильная маршрутизация: orchestrator → coder
- Задача выполнена корректно
- Success rate: 100.00%
```

## Изменения в файлах

### Файл: `codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py`

1. **Строки 21-50**: Обновлен `CLASSIFICATION_PROMPT_TEMPLATE` с четкими правилами и примерами
2. **Строки 38-71**: Обновлены `AGENT_DESCRIPTIONS` с ключевыми словами и улучшенными описаниями
3. **Строки 312-365**: Обновлена `_fallback_classify()` с поддержкой русского языка

## Ожидаемый эффект

После этого исправления:
1. ✅ Оркестратор правильно классифицирует задачи по добавлению/изменению кода → `coder`
2. ✅ Оркестратор правильно классифицирует задачи по планированию → `architect`
3. ✅ Оркестратор правильно классифицирует задачи по отладке → `debug`
4. ✅ Оркестратор правильно классифицирует вопросы → `ask`
5. ✅ Поддержка русского и английского языков
6. ✅ Более быстрое и точное выполнение задач

## Связанные документы

- [AGENT_ATTEMPT_COMPLETION_FIX.md](AGENT_ATTEMPT_COMPLETION_FIX.md) - исправление проблемы с attempt_completion
- [AGENT_LOGS_ANALYSIS.md](AGENT_LOGS_ANALYSIS.md) - анализ логов с подтверждением проблемы
- [TASK_024_ROOT_CAUSE_ANALYSIS.md](TASK_024_ROOT_CAUSE_ANALYSIS.md) - анализ проблемы с task_024
