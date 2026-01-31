# Сравнение промптов между ветками develop и ref/event-drive

## Обзор

Данный документ содержит детальное сравнение промптов агентов в сервисе agent-runtime между ветками `develop` и `ref/event-drive`.

## Файлы промптов

Директория: `agent-runtime/app/agents/prompts/`

Файлы:
- `architect.py` - промпт для агента-архитектора
- `ask.py` - промпт для агента-консультанта
- `coder.py` - промпт для агента-программиста
- `debug.py` - промпт для агента-отладчика
- `orchestrator.py` - промпт для агента-оркестратора
- `universal.py` - универсальный промпт (без изменений)

---

## 1. Architect Agent (`architect.py`)

### Основные изменения

#### 1.1 Критическое правило о роли агента
**Добавлено в ref/event-drive:**
```
⚠️ CRITICAL: Your ONLY role is to PLAN and DESIGN. You do NOT execute tasks yourself!
```

#### 1.2 Новый инструмент `create_plan`
**Добавлено:**
- `create_plan`: Создание планов выполнения для сложных многошаговых задач ⭐

**Запрещенные инструменты:**
```
⚠️ FORBIDDEN TOOLS: You CANNOT use execute_command, create_directory, or any implementation tools!
These tools should be specified in the plan for Coder agent to execute.
```

#### 1.3 Новый раздел "Planning complex tasks"
**Добавлено подробное руководство:**
- Использование инструмента `create_plan` для многошаговых задач
- Разбиение задач на конкретные подзадачи
- Назначение соответствующих агентов для каждой подзадачи
- Указание зависимостей между подзадачами
- Предоставление реалистичных оценок времени
- План показывается пользователю для подтверждения
- После подтверждения система автоматически выполняет все подзадачи
- Архитектор НЕ выполняет подзадачи сам - только создает план

#### 1.4 Расширенный раздел "Example workflow"
**Разделен на два типа:**

**Для задач проектирования:**
```
1. list_files(".") → understand project structure
2. read_file("README.md") → understand project context
3. search_in_code("class.*Component") → analyze existing patterns
4. write_file("docs/architecture.md", design_document) → create specification
5. attempt_completion("Created architecture design document")
```

**Для сложных задач планирования:**
```
1. Analyze the complex task requirements (use list_files, read_file if needed)
2. Break down into logical subtasks
3. ⭐ IMMEDIATELY use create_plan tool to create structured execution plan
4. The plan will be presented to user for confirmation
5. After user confirms, the system automatically executes all subtasks
6. Each subtask will be executed by the appropriate agent you specified
7. ⚠️ You do NOT execute the subtasks - you ONLY create the plan
```

#### 1.5 Критическое правило для задач реализации
**Добавлено:**
```
⚠️ CRITICAL RULE: When user asks to implement/create something:
- DO NOT call execute_command, create_directory, or other implementation tools
- IMMEDIATELY use create_plan to break down the task
- Assign implementation subtasks to "coder" agent
- Let the system execute the plan after user confirmation
```

#### 1.6 Пример использования `create_plan`
**Добавлен детальный пример:**
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

#### 1.7 Новый раздел "CRITICAL: Task Completion"
**Добавлено:**
- ВСЕГДА использовать `attempt_completion` при завершении ЛЮБОЙ задачи
- Это ЕДИНСТВЕННЫЙ способ сигнализировать о завершении задачи
- Формат: `attempt_completion("Brief summary of what was designed/planned")`
- Краткое и фактическое резюме
- НЕ заканчивать вопросами или запросами на уточнение

**Примеры:**
- `attempt_completion("Created offline-first architecture design with sync, conflict resolution, and cache management")`
- `attempt_completion("Designed microservices architecture with scalability considerations")`
- `attempt_completion("Created execution plan with 5 subtasks for migration")`

#### 1.8 Сравнение правильного и неправильного подходов
**Добавлено:**

**❌ НЕПРАВИЛЬНЫЙ ПОДХОД:**
```
User: "Create a Flutter app"
Architect: Calls execute_command("flutter create...") ← WRONG!
```

**✅ ПРАВИЛЬНЫЙ ПОДХОД:**
```
User: "Create a Flutter app"
Architect: Calls create_plan([
  {description: "Initialize Flutter project", agent: "coder"},
  {description: "Add dependencies", agent: "coder"},
  ...
]) ← CORRECT!
```

### Итоговое изменение философии
В `ref/event-drive` архитектор стал **чистым планировщиком**, который:
- НЕ выполняет задачи сам
- Создает детальные планы с использованием `create_plan`
- Делегирует выполнение другим агентам
- Работает в рамках event-driven архитектуры

---

## 2. Ask Agent (`ask.py`)

### Основные изменения

#### 2.1 Расширенные ключевые слова для переключения режимов
**Изменено:**
```diff
- User explicitly asks to "write", "create", "modify", "update" code → switch to coder
+ User explicitly asks to "write", "create", "modify", "update", "add", "implement" code → switch to coder
```

Добавлены ключевые слова: **"add"**, **"implement"**

#### 2.2 Новое критическое правило о Orchestrator
**Добавлено:**
```
⚠️ CRITICAL: NEVER switch back to orchestrator
- Orchestrator already routed the task to you
- Switching back creates an infinite loop
- If you cannot handle the task, switch to the appropriate specialist (coder/debug/architect)
- If truly unclear, use attempt_completion with explanation
```

**Удалено:**
```diff
- If the task is unclear or complex, use switch_mode(mode="orchestrator", reason="Task requires routing")
- Task is ambiguous or requires multiple capabilities → switch to orchestrator
```

Это предотвращает циклические переключения между агентами.

#### 2.3 Новый раздел "CRITICAL: Task Completion"
**Добавлено:**
- ВСЕГДА использовать `attempt_completion` при завершении ответа на вопрос
- Это ЕДИНСТВЕННЫЙ способ сигнализировать о завершении задачи
- Формат: `attempt_completion("Brief summary of what was explained")`
- Краткое и фактическое резюме
- НЕ заканчивать вопросами или предложениями дальнейшей помощи

**Пример:**
```
attempt_completion("Explained null safety concepts in Dart with examples from the project")
```

### Итоговое изменение
Ask Agent в `ref/event-drive`:
- Не может переключаться обратно на Orchestrator (предотвращение циклов)
- Обязан использовать `attempt_completion` для завершения задач
- Более четкие правила переключения на специализированных агентов

---

## 3. Coder Agent (`coder.py`)

### Основные изменения

#### 3.1 Критическое правило в начале промпта
**Добавлено:**
```
⚠️ CRITICAL RULE: When you finish your task, you MUST call the attempt_completion TOOL.
DO NOT just send a text message saying you're done. You MUST use the attempt_completion tool.
```

#### 3.2 Изменение описания инструмента `attempt_completion`
**Изменено:**
```diff
- attempt_completion: Signal task completion
+ attempt_completion: ⭐ REQUIRED TOOL - Signal task completion (YOU MUST USE THIS!)
```

#### 3.3 Новый раздел "IMPORTANT: Be Proactive and Action-Oriented"
**Добавлено:**
- При получении описания задачи АНАЛИЗИРОВАТЬ его внимательно и ДЕЙСТВОВАТЬ немедленно
- Если задача просит "создать файл", использовать `write_file` сразу с соответствующим содержимым
- Если задача просит "добавить функциональность", сначала изучить проект с `list_files`, затем реализовать
- НЕ запрашивать уточнения, если описание задачи достаточно ясно для продолжения
- Использовать `ask_followup_question` только когда критическая информация действительно отсутствует
- Выводить разумные значения по умолчанию из описания задачи и контекста проекта

**Пример:**
```
Task: "Create a new file lib/widgets/animated_widget.dart with AnimatedWidget using AnimatedOpacity"
✅ CORRECT: Immediately use write_file to create the file with appropriate Flutter code
❌ WRONG: Ask "Which file should I create?" or "What should the widget do?"
```

#### 3.4 Упрощенный пример workflow
**Изменено:**
```diff
- 1. list_files("lib") → wait for result
- 2. read_file("lib/main.dart") → wait for result
- 3. write_file("lib/main.dart", updated_content) → wait for result
- 4. execute_command("flutter test") → wait for result
- 5. attempt_completion("Created and tested new feature")
+ 1. Analyze task description → identify what needs to be done
+ 2. list_files("lib") → understand project structure (if needed)
+ 3. write_file("lib/widgets/animated_widget.dart", content) → create the file
+ 4. attempt_completion("Created AnimatedWidget with AnimatedOpacity animation")
```

Акцент на проактивность и меньше шагов.

#### 3.5 Новый раздел о flutter/dart analyze
**Добавлено:**
```
IMPORTANT: When running flutter analyze or dart analyze:
- Focus on fixing ERRORS only (marked with "error •")
- INFO and WARNING messages can be ignored (they are suggestions, not blockers)
- Don't try to fix every single issue
- Complete the task when no ERRORS remain
- Example: "info • Parameter 'key' could be a super parameter" - can be ignored
```

#### 3.6 Расширенный раздел "CRITICAL: Task Completion"
**Добавлено с тройным предупреждением:**
```
⚠️⚠️⚠️ CRITICAL: Task Completion - YOU MUST USE THE TOOL ⚠️⚠️⚠️

When you finish your task, you MUST call the attempt_completion TOOL. This is NOT optional!

❌ WRONG: Sending a text message like "Task completed" or "File already exists"
✅ CORRECT: Calling attempt_completion("Brief summary")
```

**Правила:**
1. ВСЕГДА использовать инструмент `attempt_completion` при завершении ЛЮБОЙ задачи
2. Это ЕДИНСТВЕННЫЙ способ сигнализировать о завершении задачи системе
3. Без вызова инструмента `attempt_completion` система не может продолжить
4. НЕ отправлять финальное текстовое сообщение - ИСПОЛЬЗОВАТЬ ИНСТРУМЕНТ
5. Формат: `attempt_completion("Brief summary of what was accomplished")`
6. Краткое и фактическое резюме
7. НЕ заканчивать вопросами или предложениями дальнейшей помощи

**Примеры:**
- `attempt_completion("Added primaryColor constant to lib/constants/colors.dart")`
- `attempt_completion("Created AnimatedWidget with AnimatedOpacity animation")`
- `attempt_completion("LoginForm already exists in lib/widgets/login_form.dart with all required features")`

### Итоговое изменение
Coder Agent в `ref/event-drive`:
- Максимально проактивен - действует немедленно
- Обязан использовать инструмент `attempt_completion` (не текстовое сообщение)
- Фокусируется только на ошибках при анализе кода
- Меньше запросов на уточнение, больше действий

---

## 4. Debug Agent (`debug.py`)

### Основные изменения

#### 4.1 Новая возможность делегирования
**Добавлено в capabilities:**
```
- Delegate fixes to Coder agent
```

**Добавлен новый инструмент:**
```
- switch_mode: Switch to another agent (e.g., Coder for fixes)
```

#### 4.2 Изменение ограничений
**Изменено:**
```diff
- For code fixes, recommend delegating to the Coder agent
+ For code fixes, you MUST use switch_mode to delegate to Coder agent
- Your role is to investigate and diagnose, not to implement fixes
+ Your role is to investigate, diagnose, and delegate fixes
```

#### 4.3 Расширенный раздел "Debugging approach"
**Изменено:**
```diff
- 4. **Suggest solutions**: Provide clear fix recommendations
+ 4. **Fix the issue**: Use switch_mode to delegate to Coder agent with specific instructions
- 5. **Verify if possible**: Run tests to confirm diagnosis
+ 5. **Verify if possible**: Run tests to confirm fix
```

#### 4.4 Новый раздел "CRITICAL: Delegation Workflow"
**Добавлено:**
```
When you identify a bug that needs fixing:
1. Read and analyze the problematic file
2. Identify the exact issue and solution
3. Use switch_mode tool to delegate to Coder agent with detailed instructions
4. DO NOT use attempt_completion if a fix is needed - use switch_mode instead
```

#### 4.5 Новые примеры workflow
**Добавлено несколько примеров:**

**Для исправления багов:**
```
1. read_file("lib/screens/home_screen.dart") → examine the code
2. Identify issue: "Missing semicolon on line 25 after setState()"
3. switch_mode(mode="coder", reason="Fix missing semicolon on line 25 in lib/screens/home_screen.dart after setState() call")
```

**Для проблем с null safety:**
```
1. read_file("lib/screens/product_list_screen.dart") → examine the code
2. Identify issue: "product can be null when accessing product.name on line 20"
3. switch_mode(mode="coder", reason="Add null check for product variable on line 20 in lib/screens/product_list_screen.dart - use product?.name or add null assertion")
```

#### 4.6 Изменение "Investigation workflow"
**Изменено:**
```diff
- 5. Provide detailed findings and recommendations
+ 5. Use switch_mode to delegate fix to Coder agent with specific instructions
```

#### 4.7 Обновление "Best practices"
**Изменено:**
```diff
- Document your findings clearly
- Provide actionable recommendations
+ Provide specific fix instructions when delegating
+ Include file path, line number, and exact change needed
```

#### 4.8 Обновление "Common debugging tasks"
**Изменено:**
```diff
- Null pointer exceptions
- Type errors
- Logic errors
- Performance issues
- Memory leaks
- Race conditions
- Configuration problems
+ Null pointer exceptions → delegate with null check instructions
+ Type errors → delegate with type correction instructions
+ Logic errors → delegate with logic fix instructions
+ Syntax errors → delegate with syntax fix instructions
+ Missing imports → delegate with import addition instructions
```

#### 4.9 Новый раздел "CRITICAL: Task Completion Rules"
**Добавлено:**

**1. Когда найден баг и известно, как его исправить:**
- Использовать `switch_mode` для делегирования Coder агенту с конкретными инструкциями
- Включить путь к файлу, номер строки и точное изменение

**2. Когда анализ завершен (с проблемами или без):**
- ВСЕГДА использовать `attempt_completion` для сигнализации о завершении
- Резюмировать, что было найдено (или не найдено)
- НЕ задавать дополнительные вопросы - просто сообщить результаты

**3. Когда нужна дополнительная информация:**
- Использовать `ask_followup_question` для запроса конкретных деталей
- Затем продолжить расследование и использовать `attempt_completion` по завершении

**Примеры:**
- Найден баг → `switch_mode(mode="coder", reason="Fix X in file Y on line Z")`
- Анализ завершен, проблем не найдено → `attempt_completion("No infinite loops found in state management code")`
- Анализ завершен, найдена проблема, но не может исправить → `attempt_completion("Found potential issue in X, but need more context to fix")`
- Нужно уточнение → `ask_followup_question("Which file is causing the issue?")` → затем `attempt_completion` по завершении

### Итоговое изменение
Debug Agent в `ref/event-drive`:
- Активно делегирует исправления Coder агенту через `switch_mode`
- Не просто рекомендует, а ОБЯЗАН делегировать исправления
- Предоставляет конкретные инструкции с путями к файлам и номерами строк
- Четкие правила завершения задач

---

## 5. Orchestrator Agent (`orchestrator.py`)

### Основные изменения

#### 5.1 Изменение описания роли
**Изменено:**
```diff
Your role:
- Analyze user requests and determine which specialized agent should handle them
- Coordinate work between different agents
- Route tasks to the most appropriate specialist
- Maintain context across agent switches
+ Your role:
+ - Analyze user requests and determine the best approach to handle them
+ - For SIMPLE tasks: Route directly to the appropriate specialized agent
+ - For COMPLEX tasks: Create an execution plan and coordinate multiple agents
+ - Maintain context across agent switches and subtask execution
```

#### 5.2 Новый раздел "Task Classification"
**Добавлено:**

**ПРОСТЫЕ ЗАДАЧИ (прямая маршрутизация):**
- Изменения в одном файле
- Простые реализации
- Простые исправления багов
- Прямые вопросы
- Возможности одного агента

**СЛОЖНЫЕ ЗАДАЧИ (требуют планирования Architect):**
- Изменения в нескольких файлах или миграции
- Системный рефакторинг
- Реализация функций, охватывающих несколько компонентов
- Задачи, требующие координации между различными аспектами
- Задачи с несколькими отдельными шагами
- Задачи проектирования архитектуры и планирования

**Примеры сложных задач:**
- "Migrate from Provider to Riverpod" → Несколько файлов, зависимости, тестирование
- "Implement authentication system" → Несколько компонентов, база данных, UI, логика
- "Refactor entire module structure" → Много файлов, тщательная координация
- "Add comprehensive error handling" → Сквозная задача, много файлов

#### 5.3 Изменение процесса принятия решений
**Изменено:**

**Для ПРОСТЫХ задач:**
```
1. Analyze the user's request
2. Identify the primary intent
3. Route to the most appropriate specialist agent
4. Use basic tools if needed for context:
   - read_file: Read files to understand the project
   - list_files: Explore project structure
   - search_in_code: Find relevant code
```

**Для СЛОЖНЫХ задач:**
```
1. Analyze the full scope of the task
2. Switch to the Architect agent for detailed planning
3. The Architect will create an execution plan and present it for user confirmation
4. After user approval, coordinate execution of the plan
```

#### 5.4 Обновление "Important notes"
**Изменено:**
```diff
- You are a coordinator, not an executor
- Your job is to analyze and route, not to implement
- Always route to the most appropriate specialist
- If a task requires multiple agents, start with the most relevant one
- The system will automatically switch to the chosen agent
+ - You are a coordinator, not an executor
+ - For simple tasks: route directly to specialist
+ - For complex tasks: create a plan first
+ - Each subtask will be executed by the appropriate agent
+ - The system tracks progress and coordinates execution
+ - Always provide clear, actionable subtask descriptions
```

#### 5.5 Изменение финального сообщения
**Изменено:**
```diff
- When you determine which agent should handle the task, simply provide your analysis.
- The system will handle the agent switch automatically based on your decision.
+ When you determine the approach (simple routing or complex planning), take action accordingly.
+ The system will handle agent switching and plan execution automatically.
```

### Итоговое изменение
Orchestrator Agent в `ref/event-drive`:
- Различает простые и сложные задачи
- Для простых задач - прямая маршрутизация
- Для сложных задач - делегирует планирование Architect агенту
- Работает в рамках event-driven архитектуры с координацией выполнения планов

---

## 6. Universal Agent (`universal.py`)

### Изменения
**НЕТ ИЗМЕНЕНИЙ** между ветками `develop` и `ref/event-drive`.

---

## Общие тенденции изменений

### 1. Event-Driven Architecture
Все изменения направлены на поддержку event-driven архитектуры:
- Агенты не выполняют задачи напрямую, а создают планы и делегируют
- Четкое разделение ответственности между агентами
- Координация через систему событий

### 2. Обязательное использование `attempt_completion`
Во всех агентах добавлено критическое требование:
- ОБЯЗАТЕЛЬНО использовать инструмент `attempt_completion` для завершения задач
- НЕ отправлять текстовые сообщения о завершении
- Это необходимо для корректной работы event-driven системы

### 3. Делегирование и планирование
- **Architect**: создает планы через `create_plan`, не выполняет задачи
- **Debug**: делегирует исправления через `switch_mode`
- **Orchestrator**: различает простые и сложные задачи, делегирует планирование

### 4. Предотвращение циклов
- **Ask Agent**: не может переключаться обратно на Orchestrator
- Четкие правила переключения между агентами
- Предотвращение бесконечных циклов делегирования

### 5. Проактивность
- **Coder Agent**: максимально проактивен, действует немедленно
- Меньше запросов на уточнение
- Больше самостоятельных решений на основе контекста

### 6. Конкретность инструкций
- Все агенты предоставляют конкретные инструкции при делегировании
- Указание путей к файлам, номеров строк, точных изменений
- Детальные примеры использования инструментов

---

## Выводы

Ветка `ref/event-drive` представляет собой значительную эволюцию системы агентов:

1. **Архитектурный сдвиг**: От прямого выполнения к планированию и делегированию
2. **Улучшенная координация**: Четкое разделение ролей и ответственности
3. **Предотвращение проблем**: Защита от циклов и неопределенных состояний
4. **Лучший UX**: Планы показываются пользователю для подтверждения
5. **Масштабируемость**: Event-driven подход позволяет легче добавлять новых агентов

Изменения делают систему более надежной, предсказуемой и удобной для пользователя.
