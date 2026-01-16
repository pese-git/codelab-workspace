# Архитектура распределения задач между агентами

## Текущая реализация

### Роли агентов

#### 1. **Orchestrator Agent** (Координатор)
**Ответственность:** Анализ запросов и маршрутизация к специализированным агентам

**Что делает:**
- Получает запрос пользователя
- Анализирует его с помощью LLM
- Определяет, какой специализированный агент должен обработать запрос
- Отправляет `switch_agent` для переключения на нужного агента

**Что НЕ делает:**
- Не создает планы выполнения
- Не выполняет подзадачи
- Не распределяет задачи между агентами

**Код:** [`orchestrator_agent.py:94-184`](codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py:94-184)

```python
async def process(self, session_id, message, context, session_mgr):
    # Анализирует запрос с помощью LLM
    target_agent, classification_info = await self.classify_task_with_llm(message)
    
    # Отправляет switch_agent
    yield StreamChunk(
        type="switch_agent",
        metadata={"target_agent": target_agent.value}
    )
```

#### 2. **Architect Agent** (Архитектор)
**Ответственность:** Планирование и создание технических спецификаций

**Что делает:**
- Создает план выполнения задачи (`create_plan` tool)
- Разбивает сложную задачу на подзадачи
- Определяет, какой агент должен выполнить каждую подзадачу
- Отправляет план на подтверждение пользователю

**Что НЕ делает:**
- Не выполняет подзадачи сам
- Не распределяет задачи между агентами (это делает MultiAgentOrchestrator)
- Не может редактировать код (только .md файлы)

**Код:** [`architect_agent.py:84-189`](codelab-ai-service/agent-runtime/app/agents/architect_agent.py:84-189)

```python
# Architect создает план
plan = ExecutionPlan(
    subtasks=[
        Subtask(description="...", agent="coder"),
        Subtask(description="...", agent="coder"),
        Subtask(description="...", agent="architect")
    ]
)

# Сохраняет план в session_mgr
session_mgr.set_plan(session_id, plan)

# Отправляет уведомление о плане
yield StreamChunk(type="plan_notification", metadata={...})
```

#### 3. **MultiAgentOrchestrator** (Исполнитель планов)
**Ответственность:** Выполнение планов и координация между агентами

**Что делает:**
- Получает подтвержденный план из session_mgr
- Последовательно выполняет каждую подзадачу
- Переключается на нужного агента для каждой подзадачи
- Собирает результаты выполнения

**Код:** [`multi_agent_orchestrator.py:220-384`](codelab-ai-service/agent-runtime/app/services/multi_agent_orchestrator.py:220-384)

```python
async def _execute_plan(self, session_id, session_mgr, context):
    plan = session_mgr.get_plan(session_id)
    
    while not plan.is_complete:
        # Получить следующую подзадачу
        subtask = session_mgr.get_next_subtask(session_id)
        
        # Получить нужного агента
        agent_type = AgentType(subtask.agent)
        agent = agent_router.get_agent(agent_type)
        
        # Переключить контекст на этого агента
        context.switch_agent(agent_type, f"Executing subtask: {subtask.description}")
        
        # Выполнить подзадачу
        async for chunk in agent.process(
            session_id=session_id,
            message=subtask.description,
            context=context.model_dump(),
            session_mgr=session_mgr
        ):
            yield chunk
        
        # Отметить как завершенную
        session_mgr.mark_subtask_complete(session_id, subtask.id)
```

## Поток выполнения

### Сценарий 1: Простая задача (без планирования)

```
User: "Создай файл main.dart"
  ↓
Orchestrator: Анализирует → "Это задача для Coder"
  ↓
Orchestrator: Отправляет switch_agent(target="coder")
  ↓
MultiAgentOrchestrator: Переключается на Coder
  ↓
Coder: Выполняет задачу напрямую
  ↓
Coder: Вызывает write_file(...)
  ↓
Result: Файл создан
```

### Сценарий 2: Сложная задача (с планированием)

```
User: "Создай TODO приложение на Flutter"
  ↓
Orchestrator: Анализирует → "Это сложная задача для Architect"
  ↓
Orchestrator: Отправляет switch_agent(target="architect")
  ↓
MultiAgentOrchestrator: Переключается на Architect
  ↓
Architect: Анализирует задачу
  ↓
Architect: Вызывает create_plan tool
  ↓
Architect: Создает план с 8 подзадачами:
  - Subtask 1: "Создать структуру проекта" (agent: coder)
  - Subtask 2: "Создать модели данных" (agent: coder)
  - Subtask 3: "Создать UI компоненты" (agent: coder)
  - ...
  - Subtask 8: "Создать документацию" (agent: architect)
  ↓
Architect: Сохраняет план в session_mgr
  ↓
Architect: Отправляет plan_notification (requires_approval=true)
  ↓
User: Подтверждает план (plan_decision: approve)
  ↓
API Endpoint: Устанавливает plan.is_approved = true
  ↓
API Endpoint: Вызывает multi_agent_orchestrator.process_message("")
  ↓
MultiAgentOrchestrator: Обнаруживает подтвержденный план
  ↓
MultiAgentOrchestrator: Вызывает _execute_plan()
  ↓
MultiAgentOrchestrator: Цикл по подзадачам:
  
  Subtask 1: "Создать структуру проекта" (agent: coder)
    ↓
    Переключается на Coder
    ↓
    Coder выполняет задачу
    ↓
    Отмечает как completed
  
  Subtask 2: "Создать модели данных" (agent: coder)
    ↓
    Переключается на Coder (уже активен)
    ↓
    Coder выполняет задачу
    ↓
    Отмечает как completed
  
  ...
  
  Subtask 8: "Создать документацию" (agent: architect)
    ↓
    Переключается на Architect
    ↓
    Architect выполняет задачу
    ↓
    Отмечает как completed
  ↓
MultiAgentOrchestrator: Все подзадачи завершены
  ↓
MultiAgentOrchestrator: Отправляет "Plan Execution Complete"
  ↓
Result: TODO приложение создано
```

## Ответ на вопрос

### Кто распределяет задачи между агентами?

**Ответ:** Зависит от сценария:

#### Для простых задач (без плана):
**Orchestrator Agent** - анализирует запрос и маршрутизирует к нужному агенту

#### Для сложных задач (с планом):
1. **Architect Agent** - создает план и **указывает в каждой подзадаче, какой агент должен её выполнить**
2. **MultiAgentOrchestrator** - **выполняет план**, переключаясь на нужных агентов для каждой подзадачи

### Architect НЕ выполняет подзадачи сам

Architect только:
- ✅ Создает план
- ✅ Определяет, какой агент должен выполнить каждую подзадачу
- ✅ Отправляет план на подтверждение

Architect НЕ:
- ❌ Не выполняет подзадачи
- ❌ Не вызывает других агентов напрямую
- ❌ Не координирует выполнение

### MultiAgentOrchestrator выполняет план

MultiAgentOrchestrator:
- ✅ Получает подтвержденный план
- ✅ Последовательно выполняет каждую подзадачу
- ✅ Переключается на нужного агента для каждой подзадачи
- ✅ Собирает результаты

## Диаграмма архитектуры

```
┌─────────────────────────────────────────────────────────────┐
│                         User Request                         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    Orchestrator Agent                        │
│  - Анализирует запрос с помощью LLM                         │
│  - Определяет: простая задача или сложная?                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
                ┌───────────┴───────────┐
                ↓                       ↓
    ┌───────────────────┐   ┌───────────────────┐
    │  Простая задача   │   │  Сложная задача   │
    └───────────────────┘   └───────────────────┘
                ↓                       ↓
    ┌───────────────────┐   ┌───────────────────┐
    │ switch_agent      │   │ switch_agent      │
    │ → Coder/Debug/Ask │   │ → Architect       │
    └───────────────────┘   └───────────────────┘
                ↓                       ↓
    ┌───────────────────┐   ┌───────────────────┐
    │ Агент выполняет   │   │ Architect создает │
    │ задачу напрямую   │   │ план (create_plan)│
    └───────────────────┘   └───────────────────┘
                                        ↓
                            ┌───────────────────┐
                            │ plan_notification │
                            │ (requires_approval)│
                            └───────────────────┘
                                        ↓
                            ┌───────────────────┐
                            │ User: approve     │
                            └───────────────────┘
                                        ↓
                            ┌───────────────────────────────┐
                            │ MultiAgentOrchestrator        │
                            │ _execute_plan():              │
                            │                               │
                            │ for subtask in plan.subtasks: │
                            │   agent = get_agent(subtask)  │
                            │   switch_to(agent)            │
                            │   agent.process(subtask)      │
                            │   mark_complete()             │
                            └───────────────────────────────┘
                                        ↓
                            ┌───────────────────┐
                            │ Plan Complete     │
                            └───────────────────┘
```

## Преимущества текущей архитектуры

### 1. Разделение ответственности
- **Orchestrator** - маршрутизация
- **Architect** - планирование
- **MultiAgentOrchestrator** - выполнение
- **Специализированные агенты** - конкретные задачи

### 2. Гибкость
- Architect может создавать планы любой сложности
- Можно добавлять новых специализированных агентов
- Легко изменить логику маршрутизации

### 3. Прозрачность
- Пользователь видит план перед выполнением
- Может редактировать или отклонить план
- Видит прогресс выполнения каждой подзадачи

### 4. Масштабируемость
- Каждый агент независим
- Можно выполнять подзадачи параллельно (в будущем)
- Легко добавить новые типы агентов

## Альтернативные подходы

### Вариант 1: Architect выполняет план сам
```python
# В architect_agent.py
async def process(...):
    # Создать план
    plan = create_plan(...)
    
    # Выполнить план сам
    for subtask in plan.subtasks:
        if subtask.agent == "coder":
            # Вызвать Coder
            await coder.process(subtask.description)
        elif subtask.agent == "architect":
            # Выполнить сам
            await self.execute_subtask(subtask)
```

**Проблемы:**
- ❌ Architect становится слишком сложным
- ❌ Нарушается принцип единственной ответственности
- ❌ Сложно тестировать
- ❌ Architect должен знать о всех других агентах

### Вариант 2: Orchestrator создает и выполняет планы
```python
# В orchestrator_agent.py
async def process(...):
    # Создать план
    plan = self.create_plan(message)
    
    # Выполнить план
    for subtask in plan.subtasks:
        agent = self.get_agent(subtask.agent)
        await agent.process(subtask.description)
```

**Проблемы:**
- ❌ Orchestrator становится слишком сложным
- ❌ Смешивается логика маршрутизации и планирования
- ❌ Теряется специализация Architect
- ❌ Сложно добавить подтверждение плана

## Рекомендация

**Текущая архитектура оптимальна:**

1. **Orchestrator** - маршрутизирует к Architect для сложных задач
2. **Architect** - создает план с указанием агентов для каждой подзадачи
3. **MultiAgentOrchestrator** - выполняет подтвержденный план, координируя работу агентов

Это обеспечивает:
- ✅ Четкое разделение ответственности
- ✅ Возможность подтверждения плана пользователем
- ✅ Гибкость и расширяемость
- ✅ Простоту тестирования

## Итог

**Architect Agent НЕ должен сам распределять задачи между агентами.**

Его роль - **создать план** с указанием, какой агент должен выполнить каждую подзадачу.

**MultiAgentOrchestrator** берет этот план и **выполняет его**, координируя работу специализированных агентов.

Это классический паттерн **"Планирование vs Выполнение"** (Planning vs Execution), который обеспечивает чистую архитектуру и разделение ответственности.
