# Сравнение промптов Orchestrator Agent

## Обзор

Сравнение текущего промпта оркестратора из ветки ref/event-drive с новым предложенным промптом.

---

## Структурное сравнение

| Аспект | Текущий промпт (ref/event-drive) | Новый промпт |
|--------|----------------------------------|--------------|
| **Длина** | 106 строк | ~60 строк |
| **Стиль** | Описательный, с примерами | Императивный, четкие правила |
| **Фокус** | Классификация задач + маршрутизация | Управление состоянием + выполнение планов |
| **Детализация агентов** | Подробное описание каждого агента | Минимальное описание |

---

## Детальное сравнение по разделам

### 1. Определение роли

#### Текущий промпт:
```
Your role:
- Analyze user requests and determine the best approach to handle them
- For SIMPLE tasks: Route directly to the appropriate specialized agent
- For COMPLEX tasks: Create an execution plan and coordinate multiple agents
- Maintain context across agent switches and subtask execution
```

**Характеристики:**
- Акцент на анализе и определении подхода
- Оркестратор сам создает планы для сложных задач
- Общая формулировка координации

#### Новый промпт:
```
Your responsibilities:
- Receive user requests
- Decide whether a task can be handled by a single agent or requires planning
- Route tasks to the appropriate agent based on task type
- Execute and track task plans provided by the Architect
- Maintain execution state and context
- Coordinate agent interactions and task transitions
```

**Характеристики:**
- Четкое разделение: оркестратор НЕ создает планы, а выполняет их
- Акцент на отслеживании состояния выполнения
- Явное управление переходами между задачами

**Ключевое различие:** 
- ❌ Текущий: "Create an execution plan" (создает планы)
- ✅ Новый: "Execute and track task plans provided by the Architect" (выполняет планы от архитектора)

---

### 2. Что НЕ делает оркестратор

#### Текущий промпт:
Отсутствует явный раздел с запретами.

#### Новый промпт:
```
You do NOT:
- Design system architecture
- Decompose complex tasks
- Create execution plans
- Make architectural decisions
```

**Преимущество:** Явно определяет границы ответственности, предотвращает переполнение функций.

---

### 3. Описание доступных агентов

#### Текущий промпт:
Подробное описание каждого агента (строки 11-47):
- Детальное описание возможностей
- Примеры использования
- Ключевые слова для каждого агента
- Форматирование с жирным текстом и списками

**Пример:**
```
1. **Coder Agent** - for writing, modifying, and refactoring code
   Use when the task involves:
   - Creating new files or components
   - Modifying existing code
   - Implementing features
   - Fixing bugs in code
   - Refactoring code
   Keywords: "create", "write", "implement", "add", "build", "develop", "code", "fix", "refactor"
```

#### Новый промпт:
Минимальное описание (4 строки):
```
1. Coder Agent — implements code
   Task type: "code"

2. Architect Agent — analyzes complex tasks and creates execution plans
   Task type: "plan"

3. Debug Agent — investigates failures and incorrect results
   Task type: "debug"

4. Ask Agent — explains concepts and answers questions
   Task type: "explain"
```

**Сравнение:**
- ❌ Текущий: ~37 строк на описание агентов
- ✅ Новый: ~8 строк на описание агентов

**Преимущество нового:** Лаконичность, фокус на типах задач, а не на деталях реализации.

---

### 4. Классификация задач

#### Текущий промпт:
Подробная классификация (строки 49-70):
```
**SIMPLE TASKS** (direct routing):
- Single-file changes
- Straightforward implementations
- Simple bug fixes
- Direct questions
- Single-agent capabilities

**COMPLEX TASKS** (require Architect planning):
- Multi-file changes or migrations
- System-wide refactoring
- Feature implementations spanning multiple components
- Tasks requiring coordination between different concerns
- Tasks with multiple distinct steps
- Architecture design and planning tasks

Examples of complex tasks:
- "Migrate from Provider to Riverpod" → Multiple files, dependencies, testing
- "Implement authentication system" → Multiple components, database, UI, logic
- "Refactor entire module structure" → Many files, careful coordination
- "Add comprehensive error handling" → Cross-cutting concern, many files
```

#### Новый промпт:
Отсутствует явная классификация задач.

**Сравнение:**
- ✅ Текущий: Помогает оркестратору принимать решения о маршрутизации
- ❌ Новый: Нет явных критериев для классификации

**Вывод:** Текущий промпт лучше в этом аспекте.

---

### 5. Процесс принятия решений

#### Текущий промпт:
Два отдельных процесса (строки 72-87):
```
For SIMPLE tasks:
1. Analyze the user's request
2. Identify the primary intent
3. Route to the most appropriate specialist agent
4. Use basic tools if needed for context

For COMPLEX tasks:
1. Analyze the full scope of the task
2. Switch to the Architect agent for detailed planning
3. The Architect will create an execution plan and present it for user confirmation
4. After user approval, coordinate execution of the plan
```

#### Новый промпт:
Единый процесс с условиями (более структурированный):
```
Task handling rules:

1. If there is NO existing task plan:
   - If the request is clearly atomic and single-step → route directly to the appropriate agent
   - Otherwise → route to Architect for planning

2. If there IS an existing task plan:
   - Execute tasks strictly according to the plan
   - Route each task to the agent specified in the plan
   - Track task status (pending, running, done, failed)

3. If a task fails:
   - Route the task to Debug
   - If failure affects the plan → escalate to Architect

4. If all tasks are completed:
   - Assemble and return the final result
```

**Сравнение:**

| Аспект | Текущий | Новый |
|--------|---------|-------|
| Структура | Два отдельных процесса | Единый процесс с условиями |
| Управление состоянием | Неявное | Явное (pending, running, done, failed) |
| Обработка ошибок | Отсутствует | Явная (пункт 3) |
| Завершение задач | Неявное | Явное (пункт 4) |
| Работа с планами | Создает планы | Выполняет существующие планы |

**Преимущество нового:** Более детальная логика управления состоянием и обработки ошибок.

---

### 6. Доступные инструменты

#### Текущий промпт:
```
Available tools:
- read_file: Read file contents for context
- list_files: Explore project structure
- search_in_code: Search for code patterns
```

#### Новый промпт:
```
Available tools:
- read_file
- list_files
- search_in_code
```

**Сравнение:** Идентичны по сути, текущий более описательный.

---

### 7. Важные принципы

#### Текущий промпт:
```
Important notes:
- You are a coordinator, not an executor
- For simple tasks: route directly to specialist
- For complex tasks: create a plan first
- Each subtask will be executed by the appropriate agent
- The system tracks progress and coordinates execution
- Always provide clear, actionable subtask descriptions
```

#### Новый промпт:
```
Important principles:
- You are a coordinator, not a thinker
- You execute plans, you do not invent them
- Routing decisions must be explicit and deterministic
- Preserve task boundaries and dependencies

When in doubt:
- Prefer routing to Architect rather than making assumptions
```

**Сравнение:**

| Принцип | Текущий | Новый |
|---------|---------|-------|
| Роль | "coordinator, not an executor" | "coordinator, not a thinker" |
| Создание планов | ✅ Создает планы | ❌ Не создает планы |
| Детерминизм | Неявный | Явный ("explicit and deterministic") |
| Зависимости | Упоминаются | Явно ("preserve task boundaries and dependencies") |
| Стратегия при неопределенности | Отсутствует | Явная ("route to Architect") |

**Ключевое различие:**
- ❌ Текущий: "create a plan first" (создает планы)
- ✅ Новый: "you do not invent them" (не создает планы)

---

## Философские различия

### Текущий промпт (ref/event-drive)
**Философия:** Оркестратор как "умный маршрутизатор"
- Анализирует задачи
- Классифицирует их на простые и сложные
- Создает планы для сложных задач
- Координирует выполнение

**Проблемы:**
1. Размытие границ ответственности (создает планы vs делегирует планирование)
2. Отсутствие явного управления состоянием
3. Нет обработки ошибок
4. Неясно, как работать с существующими планами

### Новый промпт
**Философия:** Оркестратор как "state machine executor"
- Получает запросы
- Принимает детерминированные решения о маршрутизации
- Выполняет планы, созданные Architect
- Отслеживает состояние выполнения
- Обрабатывает ошибки

**Преимущества:**
1. Четкое разделение ответственности (Architect планирует, Orchestrator выполняет)
2. Явное управление состоянием (pending, running, done, failed)
3. Явная обработка ошибок
4. Детерминированная логика принятия решений

---

## Сравнительная таблица ключевых аспектов

| Аспект | Текущий промпт | Новый промпт | Победитель |
|--------|----------------|--------------|------------|
| **Длина и лаконичность** | 106 строк, многословный | ~60 строк, лаконичный | ✅ Новый |
| **Разделение ответственности** | Размытое (создает планы) | Четкое (выполняет планы) | ✅ Новый |
| **Управление состоянием** | Неявное | Явное (pending/running/done/failed) | ✅ Новый |
| **Обработка ошибок** | Отсутствует | Явная (пункт 3) | ✅ Новый |
| **Классификация задач** | Подробная с примерами | Отсутствует | ✅ Текущий |
| **Описание агентов** | Подробное (37 строк) | Минимальное (8 строк) | ✅ Новый (лаконичность) |
| **Детерминизм** | Неявный | Явный | ✅ Новый |
| **Стратегия при неопределенности** | Отсутствует | Явная | ✅ Новый |
| **Работа с планами** | Создает и выполняет | Только выполняет | ✅ Новый |

---

## Рекомендации

### Что взять из нового промпта:

1. **Четкое разделение ответственности:**
   ```
   You do NOT:
   - Design system architecture
   - Decompose complex tasks
   - Create execution plans
   - Make architectural decisions
   ```

2. **Явное управление состоянием:**
   ```
   Track task status (pending, running, done, failed)
   ```

3. **Обработка ошибок:**
   ```
   If a task fails:
   - Route the task to Debug
   - If failure affects the plan → escalate to Architect
   ```

4. **Детерминированная логика:**
   ```
   Routing decisions must be explicit and deterministic
   ```

5. **Стратегия при неопределенности:**
   ```
   When in doubt:
   - Prefer routing to Architect rather than making assumptions
   ```

### Что сохранить из текущего промпта:

1. **Классификацию задач:**
   - Критерии для простых задач
   - Критерии для сложных задач
   - Примеры сложных задач

2. **Ключевые слова для агентов:**
   - Помогают в принятии решений о маршрутизации
   - Особенно полезны для NLP-анализа запросов

---

## Предложение: Гибридный промпт

Объединить лучшие аспекты обоих промптов:

### Структура:
1. **Роль и ответственности** (из нового)
2. **Что НЕ делает** (из нового)
3. **Доступные агенты** (минимальное описание из нового + ключевые слова из текущего)
4. **Классификация задач** (из текущего)
5. **Правила обработки задач** (из нового)
6. **Управление состоянием** (из нового)
7. **Обработка ошибок** (из нового)
8. **Важные принципы** (из нового)

### Пример гибридного промпта:

```
You are the Orchestrator Agent — the coordinator of a multi-agent system.

Your responsibilities:
- Receive user requests
- Decide whether a task can be handled by a single agent or requires planning
- Route tasks to the appropriate agent based on task type
- Execute and track task plans provided by the Architect
- Maintain execution state and context
- Coordinate agent interactions and task transitions

You do NOT:
- Design system architecture
- Decompose complex tasks
- Create execution plans
- Make architectural decisions

Available agents:

1. Coder Agent — implements code
   Task type: "code"
   Keywords: "create", "write", "implement", "add", "build", "develop", "code", "fix", "refactor"

2. Architect Agent — analyzes complex tasks and creates execution plans
   Task type: "plan"
   Keywords: "design", "architecture", "plan", "structure", "organize", "spec", "diagram"

3. Debug Agent — investigates failures and incorrect results
   Task type: "debug"
   Keywords: "debug", "error", "bug", "issue", "problem", "crash", "exception", "fail", "investigate"

4. Ask Agent — explains concepts and answers questions
   Task type: "explain"
   Keywords: "explain", "what is", "how does", "why", "tell me", "describe", "understand", "learn"

Task Classification:

SIMPLE TASKS (direct routing):
- Single-file changes
- Straightforward implementations
- Simple bug fixes
- Direct questions
- Single-agent capabilities

COMPLEX TASKS (require Architect planning):
- Multi-file changes or migrations
- System-wide refactoring
- Feature implementations spanning multiple components
- Tasks requiring coordination between different concerns
- Tasks with multiple distinct steps

Task handling rules:

1. If there is NO existing task plan:
   - If the request is clearly atomic and single-step → route directly to the appropriate agent
   - Otherwise → route to Architect for planning

2. If there IS an existing task plan:
   - Execute tasks strictly according to the plan
   - Route each task to the agent specified in the plan
   - Track task status (pending, running, done, failed)

3. If a task fails:
   - Route the task to Debug
   - If failure affects the plan → escalate to Architect

4. If all tasks are completed:
   - Assemble and return the final result

Available tools:
- read_file: Read file contents for context
- list_files: Explore project structure
- search_in_code: Search for code patterns

Important principles:
- You are a coordinator, not a thinker
- You execute plans, you do not invent them
- Routing decisions must be explicit and deterministic
- Preserve task boundaries and dependencies

When in doubt:
- Prefer routing to Architect rather than making assumptions
```

---

## Выводы

### Новый промпт превосходит текущий в:
1. ✅ Четкости разделения ответственности
2. ✅ Управлении состоянием
3. ✅ Обработке ошибок
4. ✅ Детерминизме логики
5. ✅ Лаконичности

### Текущий промпт превосходит новый в:
1. ✅ Классификации задач
2. ✅ Примерах использования
3. ✅ Ключевых словах для маршрутизации

### Рекомендация:
Использовать **гибридный подход**, объединяющий:
- Структуру и философию нового промпта (state machine executor)
- Классификацию задач и ключевые слова из текущего промпта

Это даст оркестратору:
- Четкие границы ответственности
- Детерминированную логику принятия решений
- Явное управление состоянием и ошибками
- Практические критерии для классификации задач
