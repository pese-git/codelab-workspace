# ExecutionEngine Integration Design

## Цель
Интегрировать ExecutionEngine в Architect Agent для автоматического выполнения созданных планов.

## Архитектурное решение

### Option 1: Architect Agent Integration (ВЫБРАНО)

**Обоснование:**
- Architect создаёт план → получает approval → выполняет через ExecutionEngine
- Чистая архитектура, минимальный coupling
- Architect остаётся ответственным за весь lifecycle плана
- ExecutionEngine используется как сервис, а не как часть orchestration

### Компоненты интеграции

#### 1. Planning Tools (Domain Layer)

Два новых tool для работы с планами:

**`create_plan`** - создание плана
- Input: goal, subtasks (list of {description, agent, dependencies, estimated_time})
- Output: plan_id, status="draft"
- Сохраняет план в PlanRepository
- Возвращает plan для review

**`execute_plan`** - выполнение утверждённого плана
- Input: plan_id
- Output: execution_result
- Требует approval от пользователя
- Использует ExecutionEngine для координации выполнения
- Возвращает результаты всех subtasks

#### 2. Tool Registry Updates

Добавить спецификации в `tool_registry.py`:

```python
_create_tool_spec(
    name="create_plan",
    description="Create an execution plan for complex tasks...",
    parameters={...}
)

_create_tool_spec(
    name="execute_plan", 
    description="Execute an approved plan...",
    parameters={...}
)
```

#### 3. Tool Handlers (Application Layer)

Создать `app/application/handlers/planning_tool_handler.py`:

```python
class PlanningToolHandler:
    """Handler для planning tools"""
    
    def __init__(
        self,
        plan_repository: PlanRepository,
        execution_engine: ExecutionEngine
    ):
        ...
    
    async def handle_create_plan(...) -> Dict[str, Any]:
        """Создать план и сохранить в репозитории"""
        
    async def handle_execute_plan(...) -> Dict[str, Any]:
        """Выполнить план через ExecutionEngine"""
```

#### 4. Architect Agent Updates

Обновить `ArchitectAgent`:

```python
class ArchitectAgent(BaseAgent):
    def __init__(
        self,
        plan_repository: Optional[PlanRepository] = None,
        execution_engine: Optional[ExecutionEngine] = None
    ):
        self.plan_repository = plan_repository
        self.execution_engine = execution_engine
        
        # Add planning tools
        allowed_tools=[
            ...,
            "create_plan",
            "execute_plan"  # Requires approval
        ]
```

#### 5. Tool Execution Flow

**Create Plan Flow:**
```
Architect Agent
  → LLM calls create_plan tool
  → StreamHandler detects tool_call
  → PlanningToolHandler.handle_create_plan()
  → Create Plan entity
  → Save to PlanRepository
  → Return plan_id + summary
  → Architect presents plan to user
```

**Execute Plan Flow:**
```
User approves plan
  → Architect Agent
  → LLM calls execute_plan tool
  → StreamHandler detects tool_call (requires_approval=True)
  → User approves execution
  → PlanningToolHandler.handle_execute_plan()
  → ExecutionEngine.execute_plan()
    → Parallel execution of subtasks
    → SubtaskExecutor routes to agents
    → Collect results
  → Return execution_result
  → Architect presents results
```

## Детали реализации

### 1. PlanningToolHandler

```python
class PlanningToolHandler:
    """
    Application handler для planning tools.
    
    Координирует создание и выполнение планов.
    """
    
    async def handle_create_plan(
        self,
        session_id: str,
        goal: str,
        subtasks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Создать план.
        
        Returns:
            {
                "plan_id": str,
                "status": "draft",
                "goal": str,
                "subtasks_count": int,
                "message": str
            }
        """
        # 1. Создать Plan entity
        plan = Plan(
            session_id=session_id,
            goal=goal
        )
        
        # 2. Добавить subtasks
        for st_data in subtasks:
            subtask = Subtask(
                description=st_data["description"],
                agent=AgentType(st_data["agent"]),
                dependencies=st_data.get("dependencies", []),
                estimated_time=st_data.get("estimated_time")
            )
            plan.add_subtask(subtask)
        
        # 3. Approve plan (автоматически после создания)
        plan.approve()
        
        # 4. Сохранить в репозитории
        await self.plan_repository.save(plan)
        
        return {
            "plan_id": plan.id,
            "status": plan.status.value,
            "goal": plan.goal,
            "subtasks_count": len(plan.subtasks),
            "message": f"Plan created with {len(plan.subtasks)} subtasks. Ready for execution."
        }
    
    async def handle_execute_plan(
        self,
        plan_id: str,
        session_id: str,
        session_service: SessionManagementService,
        stream_handler: IStreamHandler
    ) -> Dict[str, Any]:
        """
        Выполнить план.
        
        Returns:
            ExecutionResult.to_dict()
        """
        # Выполнить через ExecutionEngine
        result = await self.execution_engine.execute_plan(
            plan_id=plan_id,
            session_id=session_id,
            session_service=session_service,
            stream_handler=stream_handler
        )
        
        return result.to_dict()
```

### 2. Tool Specifications

```python
# В tool_registry.py

_create_tool_spec(
    name="create_plan",
    description=(
        "Create an execution plan for a complex task. "
        "Breaks down the task into subtasks with dependencies. "
        "Each subtask is assigned to a specific agent (coder, debug, ask). "
        "Returns a plan_id that can be executed with execute_plan."
    ),
    parameters={
        "type": "object",
        "properties": {
            "goal": {
                "type": "string",
                "description": "High-level goal of the plan"
            },
            "subtasks": {
                "type": "array",
                "description": "List of subtasks to execute",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "Clear description of what to do"
                        },
                        "agent": {
                            "type": "string",
                            "enum": ["coder", "debug", "ask"],
                            "description": "Agent to execute this subtask"
                        },
                        "dependencies": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Indices of subtasks this depends on (0-based)",
                            "default": []
                        },
                        "estimated_time": {
                            "type": "string",
                            "description": "Estimated time (e.g., '5 min', '1 hour')",
                            "default": "5 min"
                        }
                    },
                    "required": ["description", "agent"]
                }
            }
        },
        "required": ["goal", "subtasks"]
    }
),

_create_tool_spec(
    name="execute_plan",
    description=(
        "Execute an approved execution plan. "
        "Requires user approval before execution. "
        "Coordinates parallel execution of subtasks with dependency management. "
        "Returns execution results for all subtasks."
    ),
    parameters={
        "type": "object",
        "properties": {
            "plan_id": {
                "type": "string",
                "description": "ID of the plan to execute (from create_plan)"
            }
        },
        "required": ["plan_id"]
    }
)
```

### 3. StreamHandler Integration

Обновить `StreamLLMResponseHandler` для обработки planning tools:

```python
# В _handle_tool_call()

# Проверить, является ли tool planning tool
if tool_call.tool_name in ["create_plan", "execute_plan"]:
    # Получить planning_tool_handler из dependencies
    result = await self._planning_tool_handler.handle_tool(
        tool_name=tool_call.tool_name,
        arguments=tool_call.arguments,
        session_id=session_id,
        session_service=session_service,
        stream_handler=self
    )
    
    # Вернуть результат как tool_result
    return StreamChunk(
        type="tool_result",
        call_id=tool_call.id,
        tool_name=tool_call.tool_name,
        result=result,
        is_final=True
    )
```

### 4. Approval Integration

`execute_plan` требует approval:

```python
# В LLMResponseProcessor

def _requires_approval(self, tool_call: ToolCall) -> tuple[bool, Optional[str]]:
    """Check if tool requires approval"""
    
    # execute_plan всегда требует approval
    if tool_call.tool_name == "execute_plan":
        return True, "Plan execution requires user confirmation"
    
    # ... existing logic
```

## Workflow Example

### Пример 1: Создание и выполнение плана

**User:** "Create a Flutter login form with validation"

**Architect Agent:**
1. Анализирует задачу
2. Вызывает `create_plan`:
```json
{
  "goal": "Create Flutter login form with validation",
  "subtasks": [
    {
      "description": "Create login_form.dart with email and password fields",
      "agent": "coder",
      "estimated_time": "5 min"
    },
    {
      "description": "Add form validation logic",
      "agent": "coder",
      "dependencies": [0],
      "estimated_time": "3 min"
    },
    {
      "description": "Create unit tests for validation",
      "agent": "coder",
      "dependencies": [1],
      "estimated_time": "5 min"
    }
  ]
}
```

3. Получает `plan_id="plan-123"`
4. Представляет план пользователю
5. Вызывает `execute_plan(plan_id="plan-123")`
6. Пользователь одобряет
7. ExecutionEngine выполняет subtasks:
   - Subtask 0 → Coder Agent
   - Subtask 1 → Coder Agent (после 0)
   - Subtask 2 → Coder Agent (после 1)
8. Собирает результаты
9. Представляет итоговый результат

## Преимущества решения

1. **Clean Architecture**
   - Architect остаётся в роли планировщика
   - ExecutionEngine - чистый сервис координации
   - Минимальный coupling между компонентами

2. **User Control**
   - План создаётся и показывается пользователю
   - Выполнение требует explicit approval
   - Пользователь видит прогресс

3. **Testability**
   - Каждый компонент тестируется независимо
   - Mock dependencies для unit tests
   - Integration tests для полного flow

4. **Extensibility**
   - Легко добавить новые planning tools
   - Можно расширить ExecutionEngine
   - Поддержка различных стратегий выполнения

## Альтернативы (не выбраны)

### Option 2: OrchestratorAgent Coordination
- Сложнее: Orchestrator должен координировать Architect + ExecutionEngine
- Больше coupling между компонентами
- Менее понятный flow для пользователя

### Option 3: Event-Driven Architecture
- Требует больше изменений в существующей архитектуре
- Сложнее debugging и tracing
- Overkill для текущих требований

## Риски и митигация

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Циклические зависимости в плане | Средняя | Высокое | DependencyResolver валидирует граф |
| Subtask execution failure | Высокая | Среднее | Retry logic, error handling |
| Long-running execution timeout | Средняя | Среднее | Timeout configuration, cancellation |
| Plan approval UX confusion | Низкая | Среднее | Clear messaging, documentation |

## Метрики успеха

1. **Функциональные:**
   - ✅ Architect может создавать планы
   - ✅ ExecutionEngine выполняет планы с зависимостями
   - ✅ Все subtasks выполняются корректными агентами
   - ✅ Результаты агрегируются правильно

2. **Качественные:**
   - ✅ 100% test coverage для новых компонентов
   - ✅ No regressions в существующих тестах
   - ✅ Clean architecture principles соблюдены

3. **UX:**
   - ✅ Пользователь видит план перед выполнением
   - ✅ Прогресс выполнения отображается
   - ✅ Ошибки обрабатываются gracefully

## Следующие шаги

1. ✅ Создать дизайн документ (этот файл)
2. ⏳ Добавить tool specifications в ToolRegistry
3. ⏳ Реализовать PlanningToolHandler
4. ⏳ Обновить StreamLLMResponseHandler
5. ⏳ Обновить ArchitectAgent
6. ⏳ Создать unit tests
7. ⏳ Создать integration tests
8. ⏳ Обновить документацию
9. ⏳ Code review и merge
