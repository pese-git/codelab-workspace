# План рефакторинга OrchestratorAgent

## Текущее состояние

Класс `OrchestratorAgent` (274 строки) выполняет только **маршрутизацию задач**:
- Классифицирует задачи с помощью LLM
- Определяет целевого агента
- Отправляет `switch_agent` chunk
- Поддерживает single-agent mode

## Проблемы текущей реализации

1. **Не управляет выполнением планов** - нет логики для работы с task plans
2. **Не отслеживает состояние задач** - нет tracking (pending, running, done, failed)
3. **Не обрабатывает ошибки** - нет логики для route to Debug при сбоях
4. **Не координирует переходы** - нет управления task transitions
5. **Создает планы** - в `CLASSIFICATION_PROMPT` есть "architect" для планирования, но сам не создает планы

## Требования нового промпта

Согласно новому промпту, Orchestrator должен:

### 1. Управление планами
```
- Execute and track task plans provided by the Architect
- Route each task to the agent specified in the plan
```

### 2. Отслеживание состояния
```
- Track task status (pending, running, done, failed)
- Maintain execution state and context
```

### 3. Обработка ошибок
```
If a task fails:
- Route the task to Debug
- If failure affects the plan → escalate to Architect
```

### 4. Завершение выполнения
```
If all tasks are completed:
- Assemble and return the final result
```

### 5. Правила маршрутизации
```
1. If there is NO existing task plan:
   - If atomic and single-step → route directly
   - Otherwise → route to Architect for planning

2. If there IS an existing task plan:
   - Execute tasks strictly according to the plan
```

## Необходимые изменения

### 1. Добавить структуры данных для планов

```python
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"

@dataclass
class Task:
    id: str
    description: str
    agent: AgentType
    status: TaskStatus
    dependencies: List[str]
    result: Optional[Any] = None
    error: Optional[str] = None

@dataclass
class TaskPlan:
    id: str
    tasks: List[Task]
    current_task_index: int = 0
    
    def get_next_task(self) -> Optional[Task]:
        """Get next pending task that has all dependencies completed"""
        pass
    
    def mark_task_done(self, task_id: str, result: Any):
        """Mark task as completed"""
        pass
    
    def mark_task_failed(self, task_id: str, error: str):
        """Mark task as failed"""
        pass
    
    def is_completed(self) -> bool:
        """Check if all tasks are done"""
        pass
```

### 2. Добавить хранение планов в Session

Нужно расширить `Session` entity для хранения текущего плана:

```python
# В app/domain/entities/session.py
class Session:
    # ... existing fields ...
    current_plan: Optional[TaskPlan] = None
```

### 3. Обновить метод `process()`

```python
async def process(
    self,
    session_id: str,
    message: str,
    context: Dict[str, Any],
    session: "Session",
    session_service: "SessionManagementService",
    stream_handler: "IStreamHandler"
) -> AsyncGenerator[StreamChunk, None]:
    """
    Process request with plan-aware routing.
    """
    
    # Check if there's an existing plan
    if session.current_plan:
        # Execute next task from plan
        yield from self._execute_plan_task(session, session_service, stream_handler)
    else:
        # No plan - decide routing
        if self._is_atomic_task(message):
            # Route directly to appropriate agent
            target_agent = await self.classify_task_with_llm(message)
            yield self._create_switch_chunk(target_agent, "Direct routing")
        else:
            # Route to Architect for planning
            yield self._create_switch_chunk(
                AgentType.ARCHITECT, 
                "Complex task requires planning"
            )
```

### 4. Добавить методы управления планом

```python
async def _execute_plan_task(
    self,
    session: "Session",
    session_service: "SessionManagementService",
    stream_handler: "IStreamHandler"
) -> AsyncGenerator[StreamChunk, None]:
    """Execute next task from current plan"""
    
    plan = session.current_plan
    next_task = plan.get_next_task()
    
    if not next_task:
        # All tasks completed
        yield from self._finalize_plan(session, plan)
        return
    
    # Mark task as running
    next_task.status = TaskStatus.RUNNING
    
    # Route to specified agent
    yield StreamChunk(
        type="switch_agent",
        content=f"Executing task: {next_task.description}",
        metadata={
            "target_agent": next_task.agent.value,
            "task_id": next_task.id,
            "plan_id": plan.id
        }
    )

def _is_atomic_task(self, message: str) -> bool:
    """Determine if task is atomic and single-step"""
    # Use LLM or heuristics to determine task complexity
    pass

async def _finalize_plan(
    self,
    session: "Session",
    plan: TaskPlan
) -> AsyncGenerator[StreamChunk, None]:
    """Assemble and return final result when all tasks completed"""
    
    # Collect results from all tasks
    results = [task.result for task in plan.tasks if task.status == TaskStatus.DONE]
    
    # Clear current plan
    session.current_plan = None
    
    # Send completion chunk
    yield StreamChunk(
        type="plan_completed",
        content="All tasks completed successfully",
        metadata={
            "plan_id": plan.id,
            "completed_tasks": len(results),
            "results": results
        },
        is_final=True
    )
```

### 5. Добавить обработку ошибок

```python
async def handle_task_failure(
    self,
    session: "Session",
    task_id: str,
    error: str
) -> AsyncGenerator[StreamChunk, None]:
    """Handle task failure according to rules"""
    
    plan = session.current_plan
    task = next(t for t in plan.tasks if t.id == task_id)
    
    # Mark task as failed
    plan.mark_task_failed(task_id, error)
    
    # Determine if failure affects the plan
    if self._failure_affects_plan(plan, task):
        # Escalate to Architect
        yield StreamChunk(
            type="switch_agent",
            content=f"Task failure affects plan, escalating to Architect",
            metadata={
                "target_agent": AgentType.ARCHITECT.value,
                "reason": "plan_failure",
                "failed_task": task_id,
                "error": error
            }
        )
    else:
        # Route to Debug
        yield StreamChunk(
            type="switch_agent",
            content=f"Routing failed task to Debug agent",
            metadata={
                "target_agent": AgentType.DEBUG.value,
                "reason": "task_failure",
                "failed_task": task_id,
                "error": error
            }
        )

def _failure_affects_plan(self, plan: TaskPlan, failed_task: Task) -> bool:
    """Determine if task failure affects the overall plan"""
    # Check if other tasks depend on this one
    dependent_tasks = [
        t for t in plan.tasks 
        if failed_task.id in t.dependencies
    ]
    return len(dependent_tasks) > 0
```

### 6. Обновить CLASSIFICATION_PROMPT

Упростить промпт, убрать детальные описания агентов (они теперь в основном промпте):

```python
CLASSIFICATION_PROMPT = """Classify the task type for routing.

Task types:
- code: Implementation tasks
- plan: Complex tasks requiring planning
- debug: Error investigation
- explain: Questions and explanations

Respond with JSON:
{
  "task_type": "code|plan|debug|explain",
  "is_atomic": true|false,
  "reasoning": "brief explanation"
}

User request: {user_message}"""
```

## Архитектурные вопросы

### 1. Где хранить TaskPlan?

**Варианты:**
- ✅ **В Session entity** (рекомендуется) - логично, план привязан к сессии
- ❌ В отдельном репозитории - избыточно для MVP
- ❌ В памяти Orchestrator - теряется при перезапуске

### 2. Как Architect передает план Orchestrator?

**Варианты:**

**A. Через специальный chunk type:**
```python
yield StreamChunk(
    type="plan_created",
    content="Execution plan created",
    metadata={
        "plan": {
            "id": "plan_123",
            "tasks": [
                {"id": "task_1", "agent": "coder", "description": "..."},
                {"id": "task_2", "agent": "coder", "description": "..."}
            ]
        }
    }
)
```

**B. Через session context:**
```python
# Architect сохраняет план в session
session.current_plan = TaskPlan(...)
await session_service.update_session(session)
```

**Рекомендация:** Вариант B проще и надежнее.

### 3. Как обрабатывать результаты задач?

**Варианты:**

**A. Через metadata в attempt_completion:**
```python
# Coder agent при завершении задачи
yield StreamChunk(
    type="attempt_completion",
    content="Task completed",
    metadata={
        "task_id": "task_1",
        "result": {...}
    }
)
```

**B. Через session context:**
```python
# Coder agent сохраняет результат в session
task = session.current_plan.get_task("task_1")
task.result = {...}
task.status = TaskStatus.DONE
```

**Рекомендация:** Вариант B для консистентности.

## План реализации

### Фаза 1: Базовая инфраструктура (2-3 часа)
1. ✅ Создать структуры данных (Task, TaskPlan, TaskStatus)
2. ✅ Добавить `current_plan` в Session entity
3. ✅ Обновить Session repository для сохранения планов

### Фаза 2: Обновление Orchestrator (3-4 часа)
1. ✅ Добавить метод `_is_atomic_task()`
2. ✅ Обновить `process()` с проверкой плана
3. ✅ Добавить `_execute_plan_task()`
4. ✅ Добавить `_finalize_plan()`
5. ✅ Добавить `handle_task_failure()`

### Фаза 3: Интеграция с Architect (2-3 часа)
1. ✅ Обновить Architect agent для создания планов
2. ✅ Добавить сохранение плана в session
3. ✅ Добавить обработку `plan_created` события

### Фаза 4: Обработка результатов (2-3 часа)
1. ✅ Обновить агентов для сохранения результатов в task
2. ✅ Добавить обработку `attempt_completion` с task_id
3. ✅ Добавить логику перехода к следующей задаче

### Фаза 5: Тестирование (3-4 часа)
1. ✅ Unit тесты для TaskPlan
2. ✅ Unit тесты для Orchestrator
3. ✅ Integration тесты для полного flow
4. ✅ E2E тесты с реальными агентами

**Общее время:** 12-17 часов

## Альтернативный подход: Минимальная реализация

Если полная реализация слишком сложна, можно начать с минимальной версии:

### MVP функциональность:
1. ✅ Orchestrator проверяет, есть ли план в session
2. ✅ Если плана нет - маршрутизирует как сейчас
3. ✅ Если план есть - выполняет задачи последовательно
4. ❌ Пока без обработки зависимостей
5. ❌ Пока без сложной обработки ошибок

### Код MVP:

```python
async def process(self, ...):
    # Check for existing plan
    if hasattr(session, 'current_plan') and session.current_plan:
        # Execute next task from plan
        plan = session.current_plan
        
        # Find next pending task
        next_task = next(
            (t for t in plan.tasks if t.status == TaskStatus.PENDING),
            None
        )
        
        if next_task:
            # Mark as running and route
            next_task.status = TaskStatus.RUNNING
            yield StreamChunk(
                type="switch_agent",
                content=f"Executing: {next_task.description}",
                metadata={"target_agent": next_task.agent.value}
            )
        else:
            # All tasks done
            session.current_plan = None
            yield StreamChunk(
                type="plan_completed",
                content="All tasks completed"
            )
    else:
        # No plan - route as before
        target_agent, info = await self.classify_task_with_llm(message)
        yield StreamChunk(
            type="switch_agent",
            content=f"Routing to {target_agent.value}",
            metadata={"target_agent": target_agent.value}
        )
```

## Рекомендация

**Начать с MVP подхода:**
1. Минимальная реализация управления планами
2. Простая последовательная обработка задач
3. Базовая обработка ошибок
4. Постепенное добавление функциональности

**Затем итеративно добавлять:**
- Обработку зависимостей
- Сложную обработку ошибок
- Параллельное выполнение независимых задач
- Детальное отслеживание состояния

## Выводы

Текущая реализация `OrchestratorAgent` **не соответствует** новому промпту. Требуется значительный рефакторинг для добавления:
1. Управления планами выполнения
2. Отслеживания состояния задач
3. Обработки ошибок и эскалации
4. Координации переходов между задачами

Рекомендуется начать с MVP реализации и итеративно добавлять функциональность.
