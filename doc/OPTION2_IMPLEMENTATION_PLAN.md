# Option 2 Implementation Plan: OrchestratorAgent Coordination

## Обзор

**Цель:** Реализовать централизованную координацию выполнения планов через OrchestratorAgent  
**Время:** 8-11 часов  
**Сложность:** ⭐⭐⭐⭐ (Высокая)  
**Преимущества:** Лучшая поддержка replanning, централизованное управление

---

## Архитектура Option 2

```
User Request
    ↓
OrchestratorAgent (classify as complex)
    ↓
    ├─→ FSM: CLASSIFY → PLAN_REQUIRED
    ↓
ArchitectAgent.create_plan()
    ↓
    └─→ Returns plan_id
    ↓
OrchestratorAgent
    ├─→ FSM: PLAN_REQUIRED → PLAN_REVIEW
    ├─→ Show plan to user
    ├─→ Request approval
    ↓
User approves
    ↓
OrchestratorAgent
    ├─→ FSM: PLAN_REVIEW → PLAN_EXECUTION
    ↓
ExecutionCoordinator.execute_plan()
    ↓
ExecutionEngine
    ├─→ SubtaskExecutor
    │   ├─→ CoderAgent
    │   ├─→ DebugAgent
    │   └─→ AskAgent
    └─→ Collect results
    ↓
OrchestratorAgent
    ├─→ FSM: PLAN_EXECUTION → COMPLETED
    └─→ Present results to user
```

---

## Phase 1: FSM States Extension (1-2 часа)

### 1.1. Добавить новые FSM states

**Файл:** `codelab-ai-service/agent-runtime/app/domain/services/fsm_orchestrator.py`

```python
class FSMState(str, Enum):
    """FSM states для Orchestrator"""
    IDLE = "idle"
    CLASSIFY = "classify"
    EXECUTION = "execution"
    PLAN_REQUIRED = "plan_required"      # NEW
    PLAN_REVIEW = "plan_review"          # NEW
    PLAN_EXECUTION = "plan_execution"    # NEW
    COMPLETED = "completed"
    ERROR = "error"
```

### 1.2. Обновить FSM transitions

```python
# В FSMOrchestrator.__init__()
self._transitions = {
    FSMState.IDLE: [FSMState.CLASSIFY],
    FSMState.CLASSIFY: [
        FSMState.EXECUTION,
        FSMState.PLAN_REQUIRED,  # NEW: для complex tasks
        FSMState.ERROR
    ],
    FSMState.PLAN_REQUIRED: [
        FSMState.PLAN_REVIEW,    # NEW: после создания плана
        FSMState.ERROR
    ],
    FSMState.PLAN_REVIEW: [
        FSMState.PLAN_EXECUTION, # NEW: после approval
        FSMState.PLAN_REQUIRED,  # NEW: если нужны изменения
        FSMState.IDLE,           # NEW: если отменено
        FSMState.ERROR
    ],
    FSMState.PLAN_EXECUTION: [
        FSMState.COMPLETED,      # NEW: успешное выполнение
        FSMState.ERROR           # NEW: ошибка выполнения
    ],
    FSMState.EXECUTION: [FSMState.COMPLETED, FSMState.ERROR],
    FSMState.COMPLETED: [FSMState.IDLE],
    FSMState.ERROR: [FSMState.IDLE]
}
```

### 1.3. Добавить validation rules

```python
def _validate_transition(
    self,
    from_state: FSMState,
    to_state: FSMState
) -> None:
    """Validate FSM transition"""
    
    # Existing validation...
    
    # NEW: Plan-specific validations
    if to_state == FSMState.PLAN_EXECUTION:
        if from_state != FSMState.PLAN_REVIEW:
            raise ValueError(
                f"Can only execute plan from PLAN_REVIEW state, "
                f"current: {from_state.value}"
            )
```

**Тесты:**
- Test new states transitions
- Test validation rules
- Test invalid transitions

---

## Phase 2: ArchitectAgent Updates (1.5-2 часа)

### 2.1. Добавить create_plan method

**Файл:** `codelab-ai-service/agent-runtime/app/agents/architect_agent.py`

```python
class ArchitectAgent(BaseAgent):
    """Architect agent - только планирование"""
    
    def __init__(
        self,
        plan_repository: Optional["PlanRepository"] = None
    ):
        super().__init__(
            agent_type=AgentType.ARCHITECT,
            system_prompt=ARCHITECT_PROMPT,
            allowed_tools=[
                "read_file",
                "write_file",  # Only .md files
                "list_files",
                "search_in_code",
                "attempt_completion",
                "ask_followup_question"
                # NO create_plan or execute_plan tools!
            ],
            file_restrictions=[r".*\.md$"]
        )
        self.plan_repository = plan_repository
    
    async def create_plan(
        self,
        session_id: str,
        task: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Create execution plan for complex task.
        
        Args:
            session_id: Session ID
            task: Task description
            context: Additional context
            
        Returns:
            plan_id: ID of created plan
            
        Raises:
            ValueError: If plan creation fails
        """
        logger.info(f"Architect creating plan for task: {task[:100]}")
        
        # 1. Analyze task with LLM
        analysis = await self._analyze_task_with_llm(
            session_id=session_id,
            task=task,
            context=context
        )
        
        # 2. Create Plan entity
        plan = Plan(
            session_id=session_id,
            goal=task,
            metadata={
                "created_by": "architect",
                "analysis": analysis
            }
        )
        
        # 3. Add subtasks from analysis
        for subtask_data in analysis["subtasks"]:
            subtask = Subtask(
                description=subtask_data["description"],
                agent=AgentType(subtask_data["agent"]),
                dependencies=subtask_data.get("dependencies", []),
                estimated_time=subtask_data.get("estimated_time", "5 min")
            )
            plan.add_subtask(subtask)
        
        # 4. Approve plan automatically
        plan.approve()
        
        # 5. Save to repository
        await self.plan_repository.save(plan)
        
        logger.info(
            f"Plan {plan.id} created with {len(plan.subtasks)} subtasks"
        )
        
        return plan.id
    
    async def _analyze_task_with_llm(
        self,
        session_id: str,
        task: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze task and create subtasks using LLM.
        
        Returns:
            {
                "subtasks": [
                    {
                        "description": str,
                        "agent": "coder|debug|ask",
                        "dependencies": [int],
                        "estimated_time": str
                    }
                ]
            }
        """
        # Construct prompt for LLM
        prompt = f"""Analyze this task and break it down into subtasks:

Task: {task}

Context: {json.dumps(context, indent=2)}

Create a JSON response with subtasks. Each subtask must:
1. Be concrete and actionable
2. Be assigned to coder, debug, or ask agent (NOT architect)
3. Specify dependencies by index (0-based)
4. Include estimated time

Example response:
{{
  "subtasks": [
    {{
      "description": "Create login_form.dart file",
      "agent": "coder",
      "dependencies": [],
      "estimated_time": "5 min"
    }},
    {{
      "description": "Add validation logic",
      "agent": "coder",
      "dependencies": [0],
      "estimated_time": "3 min"
    }}
  ]
}}

Respond with JSON only:"""
        
        # Call LLM (simplified, actual implementation uses stream_handler)
        response = await self._call_llm_for_analysis(prompt)
        
        # Parse and validate response
        analysis = json.loads(response)
        self._validate_analysis(analysis)
        
        return analysis
    
    def _validate_analysis(self, analysis: Dict[str, Any]) -> None:
        """Validate LLM analysis"""
        if "subtasks" not in analysis:
            raise ValueError("Analysis missing 'subtasks' field")
        
        if not analysis["subtasks"]:
            raise ValueError("Analysis has no subtasks")
        
        for i, subtask in enumerate(analysis["subtasks"]):
            # Validate required fields
            if "description" not in subtask:
                raise ValueError(f"Subtask {i} missing 'description'")
            if "agent" not in subtask:
                raise ValueError(f"Subtask {i} missing 'agent'")
            
            # Validate agent (NOT architect)
            if subtask["agent"] == "architect":
                raise ValueError(
                    f"Subtask {i} assigned to architect. "
                    "Architect cannot execute subtasks."
                )
            
            # Validate agent type
            valid_agents = ["coder", "debug", "ask"]
            if subtask["agent"] not in valid_agents:
                raise ValueError(
                    f"Subtask {i} has invalid agent: {subtask['agent']}. "
                    f"Must be one of: {valid_agents}"
                )
```

**Тесты:**
- Test create_plan with valid task
- Test LLM analysis parsing
- Test validation (no architect in subtasks)
- Test plan repository integration

---

## Phase 3: ExecutionCoordinator (2-3 часа)

### 3.1. Создать ExecutionCoordinator

**Файл:** `codelab-ai-service/agent-runtime/app/application/coordinators/execution_coordinator.py`

```python
"""
ExecutionCoordinator - координатор выполнения планов.

Отвечает за:
- Координацию ExecutionEngine
- Мониторинг прогресса
- Обработку ошибок
- Replanning support
"""

import logging
from typing import Dict, Any, Optional, TYPE_CHECKING

from app.domain.services.execution_engine import (
    ExecutionEngine,
    ExecutionResult,
    ExecutionEngineError
)

if TYPE_CHECKING:
    from app.domain.repositories.plan_repository import PlanRepository
    from app.domain.services.session_management import SessionManagementService
    from app.domain.interfaces.stream_handler import IStreamHandler

logger = logging.getLogger("agent-runtime.application.execution_coordinator")


class ExecutionCoordinator:
    """
    Application-level coordinator для выполнения планов.
    
    Координирует взаимодействие между:
    - OrchestratorAgent
    - ExecutionEngine
    - PlanRepository
    
    Responsibilities:
    - Start/pause/resume execution
    - Monitor progress
    - Handle failures
    - Support replanning
    """
    
    def __init__(
        self,
        execution_engine: ExecutionEngine,
        plan_repository: "PlanRepository"
    ):
        """
        Initialize ExecutionCoordinator.
        
        Args:
            execution_engine: Engine для выполнения планов
            plan_repository: Repository для работы с планами
        """
        self.execution_engine = execution_engine
        self.plan_repository = plan_repository
        
        logger.info("ExecutionCoordinator initialized")
    
    async def execute_plan(
        self,
        plan_id: str,
        session_id: str,
        session_service: "SessionManagementService",
        stream_handler: "IStreamHandler"
    ) -> ExecutionResult:
        """
        Execute plan with coordination.
        
        Args:
            plan_id: ID плана
            session_id: ID сессии
            session_service: Сервис управления сессиями
            stream_handler: Handler для стриминга
            
        Returns:
            ExecutionResult с результатами выполнения
            
        Raises:
            ExecutionEngineError: При ошибке выполнения
        """
        logger.info(f"ExecutionCoordinator starting execution of plan {plan_id}")
        
        try:
            # Execute through ExecutionEngine
            result = await self.execution_engine.execute_plan(
                plan_id=plan_id,
                session_id=session_id,
                session_service=session_service,
                stream_handler=stream_handler
            )
            
            logger.info(
                f"Plan {plan_id} execution completed: "
                f"{result.completed_subtasks}/{result.total_subtasks} successful"
            )
            
            return result
            
        except ExecutionEngineError as e:
            logger.error(f"Execution failed for plan {plan_id}: {e}")
            raise
    
    async def get_execution_status(
        self,
        plan_id: str
    ) -> Dict[str, Any]:
        """
        Get current execution status.
        
        Args:
            plan_id: ID плана
            
        Returns:
            Status information
        """
        return await self.execution_engine.get_execution_status(plan_id)
    
    async def cancel_execution(
        self,
        plan_id: str,
        reason: str
    ) -> Dict[str, Any]:
        """
        Cancel plan execution.
        
        Args:
            plan_id: ID плана
            reason: Причина отмены
            
        Returns:
            Cancellation information
        """
        logger.info(f"Cancelling execution of plan {plan_id}: {reason}")
        return await self.execution_engine.cancel_execution(plan_id, reason)
```

**Тесты:**
- Test execute_plan success
- Test execute_plan failure
- Test get_execution_status
- Test cancel_execution

---

## Phase 4: OrchestratorAgent Integration (3-4 часа)

### 4.1. Обновить OrchestratorAgent

**Файл:** `codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py`

```python
class OrchestratorAgent(BaseAgent):
    """Orchestrator agent with plan coordination"""
    
    def __init__(
        self,
        task_classifier: Optional[TaskClassifier] = None,
        fsm_orchestrator: Optional[FSMOrchestrator] = None,
        architect_agent: Optional[ArchitectAgent] = None,  # NEW
        execution_coordinator: Optional[ExecutionCoordinator] = None  # NEW
    ):
        super().__init__(
            agent_type=AgentType.ORCHESTRATOR,
            system_prompt=ORCHESTRATOR_PROMPT
        )
        
        # Existing dependencies
        self.task_classifier = task_classifier or TaskClassifier()
        self.fsm = fsm_orchestrator or FSMOrchestrator()
        
        # NEW: Plan coordination dependencies
        self.architect = architect_agent
        self.execution_coordinator = execution_coordinator
        
        logger.info("OrchestratorAgent initialized with plan coordination")
    
    async def process(
        self,
        session_id: str,
        message: str,
        context: Dict[str, Any],
        session: Session,
        session_service: SessionManagementService,
        stream_handler: "IStreamHandler"
    ) -> AsyncGenerator[StreamChunk, None]:
        """Process message with plan coordination"""
        
        # 1. Transition to CLASSIFY
        await self.fsm.transition(FSMState.CLASSIFY)
        
        # 2. Classify task
        classification = await self._classify_with_planning_system(
            message=message,
            context=context
        )
        
        # 3. Route based on classification
        if classification.task_type == TaskType.ATOMIC:
            # Direct execution
            await self.fsm.transition(FSMState.EXECUTION)
            async for chunk in self._execute_atomic_task(...):
                yield chunk
        
        elif classification.task_type == TaskType.COMPLEX:
            # Plan coordination flow
            async for chunk in self._coordinate_plan_execution(
                session_id=session_id,
                message=message,
                context=context,
                session=session,
                session_service=session_service,
                stream_handler=stream_handler
            ):
                yield chunk
    
    async def _coordinate_plan_execution(
        self,
        session_id: str,
        message: str,
        context: Dict[str, Any],
        session: Session,
        session_service: SessionManagementService,
        stream_handler: "IStreamHandler"
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Coordinate plan creation and execution.
        
        Flow:
        1. CLASSIFY → PLAN_REQUIRED
        2. Request Architect to create plan
        3. PLAN_REQUIRED → PLAN_REVIEW
        4. Show plan to user, request approval
        5. PLAN_REVIEW → PLAN_EXECUTION
        6. Execute plan through ExecutionCoordinator
        7. PLAN_EXECUTION → COMPLETED
        8. Present results
        """
        try:
            # 1. Transition to PLAN_REQUIRED
            await self.fsm.transition(FSMState.PLAN_REQUIRED)
            
            yield StreamChunk(
                type="status",
                content="Creating execution plan...",
                metadata={"fsm_state": FSMState.PLAN_REQUIRED.value}
            )
            
            # 2. Request Architect to create plan
            plan_id = await self.architect.create_plan(
                session_id=session_id,
                task=message,
                context=context
            )
            
            # 3. Transition to PLAN_REVIEW
            await self.fsm.transition(FSMState.PLAN_REVIEW)
            
            # 4. Show plan to user
            plan = await self._get_plan(plan_id)
            yield StreamChunk(
                type="plan_created",
                content=self._format_plan_for_user(plan),
                metadata={
                    "plan_id": plan_id,
                    "fsm_state": FSMState.PLAN_REVIEW.value,
                    "requires_approval": True
                }
            )
            
            # 5. Wait for approval (handled by UI/API layer)
            # For now, assume approval is given
            # TODO: Implement approval mechanism
            
            # 6. Transition to PLAN_EXECUTION
            await self.fsm.transition(FSMState.PLAN_EXECUTION)
            
            yield StreamChunk(
                type="status",
                content="Executing plan...",
                metadata={"fsm_state": FSMState.PLAN_EXECUTION.value}
            )
            
            # 7. Execute plan
            result = await self.execution_coordinator.execute_plan(
                plan_id=plan_id,
                session_id=session_id,
                session_service=session_service,
                stream_handler=stream_handler
            )
            
            # 8. Transition to COMPLETED
            await self.fsm.transition(FSMState.COMPLETED)
            
            # 9. Present results
            yield StreamChunk(
                type="execution_completed",
                content=self._format_execution_result(result),
                metadata={
                    "plan_id": plan_id,
                    "fsm_state": FSMState.COMPLETED.value,
                    "result": result.to_dict()
                },
                is_final=True
            )
            
        except Exception as e:
            logger.error(f"Plan coordination error: {e}", exc_info=True)
            await self.fsm.transition(FSMState.ERROR)
            
            yield StreamChunk(
                type="error",
                error=str(e),
                metadata={"fsm_state": FSMState.ERROR.value},
                is_final=True
            )
```

**Тесты:**
- Test plan coordination flow
- Test FSM transitions
- Test error handling
- Test approval mechanism

---

## Phase 5: Testing (2-3 часа)

### 5.1. Unit Tests

**Файлы:**
- `tests/test_execution_coordinator.py`
- `tests/test_architect_agent_planning.py`
- `tests/test_orchestrator_coordination.py`
- `tests/test_fsm_plan_states.py`

### 5.2. Integration Tests

**Файл:** `tests/integration/test_option2_flow.py`

```python
async def test_complete_plan_coordination_flow():
    """Test complete Option 2 flow"""
    
    # 1. User sends complex task
    # 2. Orchestrator classifies as COMPLEX
    # 3. Architect creates plan
    # 4. User approves plan
    # 5. ExecutionCoordinator executes
    # 6. Results returned
    
    # Assert FSM transitions
    # Assert plan created
    # Assert subtasks executed
    # Assert results correct
```

---

## Оценка времени

| Phase | Задача | Время |
|-------|--------|-------|
| 1 | FSM States Extension | 1-2 ч |
| 2 | ArchitectAgent Updates | 1.5-2 ч |
| 3 | ExecutionCoordinator | 2-3 ч |
| 4 | OrchestratorAgent Integration | 3-4 ч |
| 5 | Testing | 2-3 ч |
| **Total** | | **9.5-14 ч** |

---

## Риски и митигация

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| Сложная координация | Высокая | Тщательное тестирование каждого шага |
| FSM transition errors | Средняя | Строгая валидация transitions |
| Approval mechanism | Средняя | Начать с простой реализации |
| Integration complexity | Высокая | Incremental integration, много tests |

---

## Следующие шаги

1. ✅ Создать implementation plan (этот документ)
2. ⏳ Начать с Phase 1: FSM States
3. ⏳ Продолжить с Phase 2-5
4. ⏳ Запустить все тесты
5. ⏳ Обновить документацию

**Начинаем реализацию Option 2!**
