# Отчет о сравнении промптов: ветка ref/event-drive vs ветка planner

## Дата анализа
2026-01-20

## Обзор

Сравнение файлов промптов из каталога `agent-runtime/app/agents/prompts/` между текущей веткой `ref/event-drive` и веткой `planner`.

---

## 1. `__init__.py`

### Статус: ✅ ИДЕНТИЧНЫ

Оба файла полностью идентичны - экспортируют одинаковый набор промптов.

---

## 2. `orchestrator.py` - ORCHESTRATOR_PROMPT

### Статус: ⚠️ ЗНАЧИТЕЛЬНЫЕ РАЗЛИЧИЯ

### Текущая ветка (ref/event-drive)
- **Размер**: 72 строки
- **Роль**: Простой координатор и роутер задач
- **Функциональность**: Только анализ и маршрутизация к специализированным агентам

### Ветка planner
- **Размер**: ~100+ строк
- **Роль**: Расширенный координатор с планированием
- **Функциональность**: Маршрутизация + создание планов выполнения для сложных задач

### Ключевые отличия:

#### 1. **Классификация задач** (только в planner)
```
SIMPLE TASKS (direct routing):
- Single-file changes
- Straightforward implementations
- Simple bug fixes

COMPLEX TASKS (require Architect planning):
- Multi-file changes or migrations
- System-wide refactoring
- Feature implementations spanning multiple components
```

#### 2. **Процесс принятия решений**
- **ref/event-drive**: Только простая маршрутизация
- **planner**: Двухуровневая логика:
  - Простые задачи → прямая маршрутизация
  - Сложные задачи → переключение на Architect для планирования

#### 3. **Примеры сложных задач** (только в planner)
- "Migrate from Provider to Riverpod"
- "Implement authentication system"
- "Refactor entire module structure"

### Вывод:
Ветка **planner** добавляет интеллектуальную классификацию задач и механизм планирования для сложных многошаговых задач.

---

## 3. `architect.py` - ARCHITECT_PROMPT

### Статус: ⚠️ КРИТИЧЕСКИЕ РАЗЛИЧИЯ

### Текущая ветка (ref/event-drive)
- **Размер**: 57 строк
- **Роль**: Планировщик и дизайнер
- **Инструменты**: Базовые инструменты для чтения и создания документации

### Ветка planner
- **Размер**: ~180+ строк
- **Роль**: Планировщик с возможностью создания исполняемых планов
- **Инструменты**: Базовые + **create_plan** (ключевое отличие)

### Ключевые отличия:

#### 1. **Новый инструмент create_plan** (только в planner)
```python
create_plan({
  "subtasks": [
    {
      "id": "subtask_1",
      "description": "Add riverpod dependency to pubspec.yaml",
      "agent": "coder",
      "estimated_time": "2 min"
    },
    {
      "id": "subtask_2",
      "description": "Create provider definitions using Riverpod",
      "agent": "coder",
      "estimated_time": "5 min",
      "dependencies": ["subtask_1"]
    }
  ]
})
```

#### 2. **Запрет на выполнение** (усилен в planner)
- **ref/event-drive**: Может создавать только .md файлы
- **planner**: 
  - ⚠️ FORBIDDEN TOOLS: execute_command, create_directory
  - ⚠️ CRITICAL RULE: Для задач реализации НЕМЕДЛЕННО использовать create_plan
  - Множественные предупреждения о том, что Architect НЕ выполняет задачи

#### 3. **Workflow для планирования** (только в planner)
```
1. Analyze the complex task requirements
2. Break down into logical subtasks
3. ⭐ IMMEDIATELY use create_plan tool
4. The plan will be presented to user for confirmation
5. After user confirms, the system automatically executes all subtasks
6. ⚠️ You do NOT execute the subtasks - you ONLY create the plan
```

#### 4. **Примеры правильного/неправильного подхода** (только в planner)
```
⚠️ WRONG APPROACH:
User: "Create a Flutter app"
Architect: Calls execute_command("flutter create...") ← WRONG!

✅ CORRECT APPROACH:
User: "Create a Flutter app"
Architect: Calls create_plan([...]) ← CORRECT!
```

#### 5. **Обязательное использование attempt_completion** (усилено в planner)
Более детальные инструкции о том, когда и как использовать attempt_completion.

### Вывод:
Ветка **planner** превращает Architect из простого дизайнера в полноценный инструмент планирования с возможностью создания исполняемых многошаговых планов.

---

## 4. `coder.py` - CODER_PROMPT

### Статус: ⚠️ УМЕРЕННЫЕ РАЗЛИЧИЯ

### Текущая ветка (ref/event-drive)
- **Размер**: 52 строки
- **Фокус**: Базовые инструкции по написанию кода

### Ветка planner
- **Размер**: ~90+ строк
- **Фокус**: Расширенные инструкции + проактивность + строгие правила завершения

### Ключевые отличия:

#### 1. **Критическое правило о завершении** (усилено в planner)
```
⚠️⚠️⚠️ CRITICAL: Task Completion - YOU MUST USE THE TOOL ⚠️⚠️⚠️

❌ WRONG: Sending a text message like "Task completed"
✅ CORRECT: Calling attempt_completion("Brief summary")
```

#### 2. **Проактивность и ориентация на действие** (только в planner)
```
IMPORTANT: Be Proactive and Action-Oriented
- When given a task description, ANALYZE it carefully and TAKE ACTION immediately
- DO NOT ask for clarification if the task description is clear enough
- Only use ask_followup_question when critical information is truly missing
- Infer reasonable defaults from the task description
```

#### 3. **Примеры правильного поведения** (только в planner)
```
Example: Task "Create a new file lib/widgets/animated_widget.dart"
✅ CORRECT: Immediately use write_file to create the file
❌ WRONG: Ask "Which file should I create?"
```

#### 4. **Правила для flutter analyze** (только в planner)
```
IMPORTANT: When running flutter analyze:
- Focus on fixing ERRORS only (marked with "error •")
- INFO and WARNING messages can be ignored
- Don't try to fix every single issue
```

### Вывод:
Ветка **planner** делает Coder более проактивным и добавляет строгие правила о завершении задач через attempt_completion.

---

## 5. `debug.py` - DEBUG_PROMPT

### Статус: ⚠️ УМЕРЕННЫЕ РАЗЛИЧИЯ

### Текущая ветка (ref/event-drive)
- **Размер**: 67 строк
- **Инструменты**: Базовые инструменты для отладки
- **Делегирование**: Рекомендация переключиться на Coder

### Ветка planner
- **Размер**: ~100+ строк
- **Инструменты**: Базовые + **switch_mode**
- **Делегирование**: Обязательное использование switch_mode

### Ключевые отличия:

#### 1. **Инструмент switch_mode** (добавлен в planner)
```
Available tools:
- switch_mode: Switch to another agent (e.g., Coder for fixes)
```

#### 2. **Критический workflow делегирования** (только в planner)
```
CRITICAL: Delegation Workflow
When you identify a bug that needs fixing:
1. Read and analyze the problematic file
2. Identify the exact issue and solution
3. Use switch_mode tool to delegate to Coder agent with detailed instructions
4. DO NOT use attempt_completion if a fix is needed - use switch_mode instead
```

#### 3. **Конкретные примеры делегирования** (только в planner)
```
Example workflow for fixing bugs:
1. read_file("lib/screens/home_screen.dart")
2. Identify issue: "Missing semicolon on line 25"
3. switch_mode(mode="coder", reason="Fix missing semicolon on line 25...")

Example workflow for null safety issues:
1. read_file("lib/screens/product_list_screen.dart")
2. Identify issue: "product can be null when accessing product.name"
3. switch_mode(mode="coder", reason="Add null check for product variable...")
```

#### 4. **Правила завершения задач** (детализированы в planner)
```
CRITICAL: Task Completion Rules

1. When you find a bug and know how to fix it:
   - Use switch_mode to delegate to Coder agent
   
2. When you complete analysis:
   - ALWAYS use attempt_completion to signal completion
   
3. When you need more information:
   - Use ask_followup_question
```

### Вывод:
Ветка **planner** добавляет формальный механизм делегирования через switch_mode и четкие правила о том, когда использовать attempt_completion vs switch_mode.

---

## 6. `ask.py` - ASK_PROMPT

### Статус: ⚠️ УМЕРЕННЫЕ РАЗЛИЧИЯ

### Текущая ветка (ref/event-drive)
- **Размер**: 76 строк
- **Инструменты**: Базовые инструменты для чтения
- **Переключение**: Рекомендация использовать switch_mode

### Ветка planner
- **Размер**: ~110+ строк
- **Инструменты**: Базовые + **switch_mode**
- **Переключение**: Обязательное использование switch_mode с четкими правилами

### Ключевые отличия:

#### 1. **Инструмент switch_mode** (формализован в planner)
```
Available tools:
- switch_mode: Switch to another agent when you cannot handle the task
```

#### 2. **Критическое предупреждение** (только в planner)
```
⚠️ CRITICAL: NEVER switch back to orchestrator
- Orchestrator already routed the task to you
- Switching back creates an infinite loop
- If you cannot handle the task, switch to the appropriate specialist
```

#### 3. **Четкие правила переключения** (детализированы в planner)
```
When to switch modes:
- User asks to "write", "create", "modify" → switch to coder
- User asks to "run", "execute", "test" → switch to coder
- User asks to "plan", "design" → switch to architect
- User asks to "debug", "fix", "troubleshoot" → switch to debug
```

#### 4. **Правила завершения** (усилены в planner)
```
CRITICAL: Task Completion
- ALWAYS use attempt_completion when you finish answering
- This is the ONLY way to signal task completion
- Do NOT end with questions or offers for further assistance
```

### Вывод:
Ветка **planner** добавляет формальный механизм переключения и предотвращает циклические переключения обратно к orchestrator.

---

## 7. `universal.py` - UNIVERSAL_SYSTEM_PROMPT

### Статус: ✅ ФАЙЛ ОТСУТСТВУЕТ В ВЕТКЕ PLANNER

Файл [`universal.py`](codelab-ai-service/agent-runtime/app/agents/prompts/universal.py) существует только в текущей ветке `ref/event-drive`. В ветке `planner` этого файла нет.

**Назначение**: Универсальный промпт для single-agent режима (baseline для POC).

---

## Общие выводы

### Архитектурные изменения в ветке planner:

1. **Планирование сложных задач**
   - Добавлен инструмент `create_plan` для Architect
   - Orchestrator классифицирует задачи на простые и сложные
   - Сложные задачи автоматически направляются на планирование

2. **Формализация делегирования**
   - Добавлен инструмент `switch_mode` для Debug и Ask агентов
   - Четкие правила когда использовать switch_mode vs attempt_completion
   - Предотвращение циклических переключений

3. **Усиление правил завершения**
   - Множественные предупреждения об обязательном использовании attempt_completion
   - Четкие примеры правильного и неправильного поведения
   - Запрет на текстовые сообщения вместо вызова инструмента

4. **Проактивность агентов**
   - Coder должен действовать немедленно, не запрашивая лишних уточнений
   - Architect должен немедленно создавать план для задач реализации
   - Debug должен немедленно делегировать исправления через switch_mode

5. **Предотвращение ошибок**
   - Architect не может выполнять команды (только планировать)
   - Debug не может модифицировать файлы (только анализировать и делегировать)
   - Ask не может переключаться обратно на orchestrator

### Новые возможности в planner:

| Возможность | ref/event-drive | planner |
|-------------|-----------------|---------|
| Планирование многошаговых задач | ❌ | ✅ create_plan |
| Классификация задач (простые/сложные) | ❌ | ✅ |
| Формальное делегирование | ⚠️ рекомендации | ✅ switch_mode |
| Зависимости между подзадачами | ❌ | ✅ |
| Оценка времени выполнения | ❌ | ✅ |
| Предотвращение циклов | ⚠️ частично | ✅ |
| Проактивное поведение | ⚠️ базовое | ✅ усиленное |

### Рекомендации:

1. **Для продакшена**: Использовать промпты из ветки `planner` - они более зрелые и продуманные
2. **Для тестирования**: Ветка `ref/event-drive` подходит для базового функционала
3. **Миграция**: При переносе из `ref/event-drive` в `planner` необходимо:
   - Реализовать инструмент `create_plan`
   - Реализовать инструмент `switch_mode`
   - Обновить логику orchestrator для классификации задач
   - Добавить механизм выполнения планов с зависимостями

---

## Метрики изменений

| Файл | ref/event-drive | planner | Изменение |
|------|-----------------|---------|-----------|
| `__init__.py` | 16 строк | 16 строк | 0% |
| `orchestrator.py` | 72 строки | ~100 строк | +39% |
| `architect.py` | 57 строк | ~180 строк | +216% |
| `coder.py` | 52 строки | ~90 строк | +73% |
| `debug.py` | 67 строк | ~100 строк | +49% |
| `ask.py` | 76 строк | ~110 строк | +45% |
| `universal.py` | 82 строки | отсутствует | N/A |

**Общий объем промптов**: Увеличение на ~70% в ветке planner (без учета universal.py)

---

## Заключение

Ветка **planner** представляет собой значительную эволюцию системы промптов с фокусом на:
- Интеллектуальное планирование сложных задач
- Формализацию взаимодействия между агентами
- Предотвращение типичных ошибок
- Повышение автономности и проактивности агентов

Текущая ветка **ref/event-drive** содержит более простую и базовую версию промптов, подходящую для начального функционала, но не имеющую продвинутых возможностей планирования и координации.
