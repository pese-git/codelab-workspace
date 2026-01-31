# ExecutionEngine Integration: Архитектурные диаграммы

## Option 1: Architect Agent Integration

### Sequence Diagram - Create and Execute Plan

```mermaid
sequenceDiagram
    participant User
    participant Orchestrator as OrchestratorAgent
    participant Architect as ArchitectAgent
    participant LLM
    participant PlanHandler as PlanningToolHandler
    participant PlanRepo as PlanRepository
    participant ExecEngine as ExecutionEngine
    participant SubtaskExec as SubtaskExecutor
    participant Coder as CoderAgent
    participant Debug as DebugAgent

    User->>Orchestrator: "Create Flutter login form"
    Orchestrator->>Orchestrator: classify_task()
    Note over Orchestrator: TaskType.COMPLEX
    
    Orchestrator->>Architect: process(message)
    Architect->>LLM: Analyze task
    LLM->>Architect: Need to create plan
    
    Architect->>LLM: Call create_plan tool
    Note over LLM: {goal, subtasks[]}
    
    LLM-->>Architect: tool_call: create_plan
    Architect->>PlanHandler: handle_create_plan()
    PlanHandler->>PlanRepo: save(plan)
    PlanRepo-->>PlanHandler: plan_id
    PlanHandler-->>Architect: {plan_id, status: "approved"}
    
    Architect->>User: Present plan for review
    User->>Architect: Approve plan
    
    Architect->>LLM: Call execute_plan tool
    Note over LLM: {plan_id}
    
    LLM-->>Architect: tool_call: execute_plan
    Note over Architect: Requires approval
    Architect->>User: Request execution approval
    User->>Architect: Approve execution
    
    Architect->>PlanHandler: handle_execute_plan()
    PlanHandler->>ExecEngine: execute_plan(plan_id)
    
    ExecEngine->>ExecEngine: get_execution_order()
    Note over ExecEngine: Resolve dependencies
    
    loop For each batch
        ExecEngine->>SubtaskExec: execute_subtask()
        SubtaskExec->>Coder: process(subtask)
        Coder-->>SubtaskExec: result
        SubtaskExec-->>ExecEngine: subtask_result
    end
    
    ExecEngine-->>PlanHandler: ExecutionResult
    PlanHandler-->>Architect: execution_result
    Architect->>User: Present results
```

### Component Diagram

```mermaid
graph TB
    subgraph "API Layer"
        User[User/IDE]
    end
    
    subgraph "Application Layer"
        Orchestrator[OrchestratorAgent]
        StreamHandler[StreamLLMResponseHandler]
        PlanHandler[PlanningToolHandler]
    end
    
    subgraph "Domain Layer - Agents"
        Architect[ArchitectAgent]
        Coder[CoderAgent]
        Debug[DebugAgent]
        Ask[AskAgent]
    end
    
    subgraph "Domain Layer - Services"
        ExecEngine[ExecutionEngine]
        SubtaskExec[SubtaskExecutor]
        DepResolver[DependencyResolver]
    end
    
    subgraph "Domain Layer - Repositories"
        PlanRepo[PlanRepository]
    end
    
    subgraph "Infrastructure Layer"
        LLM[LLM Client]
        DB[(Database)]
    end
    
    User -->|request| Orchestrator
    Orchestrator -->|delegate| Architect
    Architect -->|use| StreamHandler
    StreamHandler -->|call| LLM
    StreamHandler -->|route tool| PlanHandler
    
    PlanHandler -->|save/load| PlanRepo
    PlanHandler -->|execute| ExecEngine
    
    ExecEngine -->|use| SubtaskExec
    ExecEngine -->|use| DepResolver
    ExecEngine -->|update| PlanRepo
    
    SubtaskExec -->|route to| Coder
    SubtaskExec -->|route to| Debug
    SubtaskExec -->|route to| Ask
    
    PlanRepo -->|persist| DB
    
    style Architect fill:#90EE90
    style PlanHandler fill:#FFD700
    style ExecEngine fill:#87CEEB
```

### State Machine Diagram

```mermaid
stateDiagram-v2
    [*] --> Idle
    
    Idle --> Classify: User request
    Classify --> ArchitectMode: Complex task
    
    ArchitectMode --> PlanCreation: Analyze task
    PlanCreation --> PlanReview: create_plan tool
    
    PlanReview --> PlanExecution: User approves
    PlanReview --> PlanCreation: User requests changes
    PlanReview --> Idle: User cancels
    
    PlanExecution --> ExecutingSubtasks: execute_plan tool + approval
    
    ExecutingSubtasks --> SubtaskRunning: Start subtask
    SubtaskRunning --> SubtaskCompleted: Success
    SubtaskRunning --> SubtaskFailed: Error
    
    SubtaskCompleted --> ExecutingSubtasks: More subtasks
    SubtaskCompleted --> PlanCompleted: All done
    
    SubtaskFailed --> ExecutionFailed: Critical error
    SubtaskFailed --> ExecutingSubtasks: Continue with others
    
    PlanCompleted --> ResultsPresentation
    ExecutionFailed --> ResultsPresentation
    
    ResultsPresentation --> Idle
```

---

## Option 2: OrchestratorAgent Coordination

### Sequence Diagram

```mermaid
sequenceDiagram
    participant User
    participant Orchestrator as OrchestratorAgent
    participant FSM as FSMOrchestrator
    participant Architect as ArchitectAgent
    participant ExecEngine as ExecutionEngine
    participant SubtaskExec as SubtaskExecutor
    participant Coder as CoderAgent

    User->>Orchestrator: "Create Flutter login form"
    Orchestrator->>FSM: transition(CLASSIFY)
    Orchestrator->>Orchestrator: classify_task()
    Note over Orchestrator: TaskType.COMPLEX
    
    Orchestrator->>FSM: transition(PLAN_REQUIRED)
    Orchestrator->>Architect: create_plan(task)
    Architect->>Architect: Analyze and decompose
    Architect-->>Orchestrator: plan_id
    
    Orchestrator->>FSM: transition(PLAN_REVIEW)
    Orchestrator->>User: Present plan
    User->>Orchestrator: Approve plan
    
    Orchestrator->>FSM: transition(PLAN_EXECUTION)
    Orchestrator->>ExecEngine: execute_plan(plan_id)
    
    ExecEngine->>ExecEngine: get_execution_order()
    
    loop For each subtask
        ExecEngine->>SubtaskExec: execute_subtask()
        SubtaskExec->>Coder: process(subtask)
        Coder-->>SubtaskExec: result
        SubtaskExec-->>ExecEngine: subtask_result
        ExecEngine->>Orchestrator: Progress update
    end
    
    ExecEngine-->>Orchestrator: ExecutionResult
    Orchestrator->>FSM: transition(COMPLETED)
    Orchestrator->>User: Present results
```

### Component Diagram

```mermaid
graph TB
    subgraph "API Layer"
        User[User/IDE]
    end
    
    subgraph "Application Layer - Orchestration"
        Orchestrator[OrchestratorAgent<br/>COORDINATOR]
        FSM[FSMOrchestrator]
        TaskClassifier[TaskClassifier]
    end
    
    subgraph "Application Layer - Execution"
        ExecCoordinator[ExecutionCoordinator]
    end
    
    subgraph "Domain Layer - Agents"
        Architect[ArchitectAgent<br/>PLANNER ONLY]
        Coder[CoderAgent]
        Debug[DebugAgent]
        Ask[AskAgent]
    end
    
    subgraph "Domain Layer - Services"
        ExecEngine[ExecutionEngine]
        SubtaskExec[SubtaskExecutor]
    end
    
    subgraph "Domain Layer - Repositories"
        PlanRepo[PlanRepository]
    end
    
    User -->|request| Orchestrator
    Orchestrator -->|use| FSM
    Orchestrator -->|use| TaskClassifier
    Orchestrator -->|delegate planning| Architect
    Orchestrator -->|coordinate execution| ExecCoordinator
    
    ExecCoordinator -->|use| ExecEngine
    ExecEngine -->|use| SubtaskExec
    ExecEngine -->|update| PlanRepo
    
    Architect -->|create| PlanRepo
    
    SubtaskExec -->|route to| Coder
    SubtaskExec -->|route to| Debug
    SubtaskExec -->|route to| Ask
    
    style Orchestrator fill:#FF6B6B
    style ExecCoordinator fill:#FFD700
    style Architect fill:#90EE90
    style ExecEngine fill:#87CEEB
```

### State Machine Diagram

```mermaid
stateDiagram-v2
    [*] --> IDLE
    
    IDLE --> CLASSIFY: User request
    CLASSIFY --> PLAN_REQUIRED: Complex task
    CLASSIFY --> EXECUTION: Atomic task
    
    PLAN_REQUIRED --> PLANNING: Delegate to Architect
    PLANNING --> PLAN_REVIEW: Plan created
    
    PLAN_REVIEW --> PLAN_APPROVED: User approves
    PLAN_REVIEW --> PLANNING: User requests changes
    PLAN_REVIEW --> IDLE: User cancels
    
    PLAN_APPROVED --> PLAN_EXECUTION: Start execution
    
    PLAN_EXECUTION --> EXECUTING_BATCH: Process batch
    EXECUTING_BATCH --> SUBTASK_RUNNING: Execute subtask
    
    SUBTASK_RUNNING --> SUBTASK_DONE: Success
    SUBTASK_RUNNING --> SUBTASK_FAILED: Error
    
    SUBTASK_DONE --> EXECUTING_BATCH: More in batch
    SUBTASK_DONE --> PLAN_EXECUTION: Next batch
    SUBTASK_DONE --> PLAN_COMPLETED: All done
    
    SUBTASK_FAILED --> EXECUTION_FAILED: Critical
    SUBTASK_FAILED --> EXECUTING_BATCH: Continue
    
    PLAN_COMPLETED --> RESULTS_READY
    EXECUTION_FAILED --> RESULTS_READY
    
    RESULTS_READY --> IDLE: Present results
    
    EXECUTION --> IDLE: Direct execution
```

---

## Option 3: Event-Driven Architecture

### Sequence Diagram

```mermaid
sequenceDiagram
    participant User
    participant Orchestrator as OrchestratorAgent
    participant EventBus as Event Bus
    participant Architect as ArchitectAgent
    participant ExecEngine as ExecutionEngine
    participant SubtaskExec as SubtaskExecutor
    participant Coder as CoderAgent

    User->>Orchestrator: "Create Flutter login form"
    Orchestrator->>EventBus: Publish: TaskReceived
    
    EventBus->>Architect: Subscribe: TaskReceived
    Architect->>Architect: Analyze task
    Architect->>EventBus: Publish: PlanCreated(plan_id)
    
    EventBus->>Orchestrator: Subscribe: PlanCreated
    Orchestrator->>User: Present plan
    User->>Orchestrator: Approve
    Orchestrator->>EventBus: Publish: PlanApproved(plan_id)
    
    EventBus->>ExecEngine: Subscribe: PlanApproved
    ExecEngine->>ExecEngine: Load plan
    ExecEngine->>EventBus: Publish: ExecutionStarted(plan_id)
    
    loop For each subtask
        ExecEngine->>EventBus: Publish: SubtaskStarted(subtask_id)
        EventBus->>SubtaskExec: Subscribe: SubtaskStarted
        SubtaskExec->>Coder: Execute
        Coder-->>SubtaskExec: Result
        SubtaskExec->>EventBus: Publish: SubtaskCompleted(subtask_id, result)
        EventBus->>ExecEngine: Subscribe: SubtaskCompleted
        EventBus->>Orchestrator: Subscribe: SubtaskCompleted
        Orchestrator->>User: Progress update
    end
    
    ExecEngine->>EventBus: Publish: ExecutionCompleted(plan_id, results)
    EventBus->>Orchestrator: Subscribe: ExecutionCompleted
    Orchestrator->>User: Present results
```

### Component Diagram

```mermaid
graph TB
    subgraph "API Layer"
        User[User/IDE]
    end
    
    subgraph "Event Infrastructure"
        EventBus[Event Bus<br/>Publisher/Subscriber]
        EventStore[(Event Store)]
    end
    
    subgraph "Application Layer - Event Handlers"
        OrchestratorHandler[OrchestratorEventHandler]
        ArchitectHandler[ArchitectEventHandler]
        ExecutionHandler[ExecutionEventHandler]
    end
    
    subgraph "Domain Layer - Agents"
        Orchestrator[OrchestratorAgent]
        Architect[ArchitectAgent]
        Coder[CoderAgent]
        Debug[DebugAgent]
    end
    
    subgraph "Domain Layer - Services"
        ExecEngine[ExecutionEngine]
        SubtaskExec[SubtaskExecutor]
    end
    
    subgraph "Domain Layer - Repositories"
        PlanRepo[PlanRepository]
    end
    
    User -->|request| Orchestrator
    Orchestrator -->|publish| EventBus
    
    EventBus -->|subscribe| OrchestratorHandler
    EventBus -->|subscribe| ArchitectHandler
    EventBus -->|subscribe| ExecutionHandler
    
    EventBus -->|persist| EventStore
    
    OrchestratorHandler -->|trigger| Orchestrator
    ArchitectHandler -->|trigger| Architect
    ExecutionHandler -->|trigger| ExecEngine
    
    Architect -->|publish via| EventBus
    ExecEngine -->|publish via| EventBus
    
    ExecEngine -->|use| SubtaskExec
    SubtaskExec -->|route to| Coder
    SubtaskExec -->|route to| Debug
    
    Architect -->|save| PlanRepo
    ExecEngine -->|load| PlanRepo
    
    style EventBus fill:#FF6B6B
    style EventStore fill:#FFD700
    style OrchestratorHandler fill:#90EE90
    style ArchitectHandler fill:#87CEEB
    style ExecutionHandler fill:#DDA0DD
```

### Event Flow Diagram

```mermaid
graph LR
    subgraph "Planning Phase"
        E1[TaskReceived] -->|Architect| E2[PlanCreated]
        E2 -->|Orchestrator| E3[PlanApproved]
    end
    
    subgraph "Execution Phase"
        E3 -->|ExecutionEngine| E4[ExecutionStarted]
        E4 --> E5[SubtaskStarted]
        E5 -->|SubtaskExecutor| E6[SubtaskCompleted]
        E6 -->|More subtasks| E5
        E6 -->|All done| E7[ExecutionCompleted]
    end
    
    subgraph "Error Handling"
        E5 -.->|Error| E8[SubtaskFailed]
        E8 -.->|Retry| E5
        E8 -.->|Critical| E9[ExecutionFailed]
    end
    
    subgraph "Progress Updates"
        E5 -->|Notify| E10[ProgressUpdate]
        E6 -->|Notify| E10
        E10 -->|UI| E11[UserNotification]
    end
    
    style E1 fill:#90EE90
    style E3 fill:#FFD700
    style E4 fill:#87CEEB
    style E7 fill:#98FB98
    style E8 fill:#FFB6C1
    style E9 fill:#FF6B6B
```

### State Machine with Events

```mermaid
stateDiagram-v2
    [*] --> Idle
    
    Idle --> Planning: Event: TaskReceived
    Planning --> PlanReview: Event: PlanCreated
    
    PlanReview --> Executing: Event: PlanApproved
    PlanReview --> Planning: Event: PlanRejected
    
    Executing --> SubtaskRunning: Event: SubtaskStarted
    SubtaskRunning --> SubtaskDone: Event: SubtaskCompleted
    SubtaskRunning --> SubtaskError: Event: SubtaskFailed
    
    SubtaskDone --> SubtaskRunning: Event: SubtaskStarted<br/>(next subtask)
    SubtaskDone --> Completed: Event: ExecutionCompleted
    
    SubtaskError --> SubtaskRunning: Event: SubtaskRetry
    SubtaskError --> Failed: Event: ExecutionFailed
    
    Completed --> Idle: Event: ResultsPresented
    Failed --> Idle: Event: ErrorHandled
    
    note right of Planning
        Subscribers:
        - ArchitectAgent
        - Orchestrator (monitor)
    end note
    
    note right of Executing
        Subscribers:
        - ExecutionEngine
        - Orchestrator (progress)
        - UI (updates)
    end note
```

---

## Сравнение диаграмм

### Complexity Comparison

| Aspect | Option 1 | Option 2 | Option 3 |
|--------|----------|----------|----------|
| **Sequence steps** | 15-20 | 20-25 | 25-35 |
| **Components** | 8 | 12 | 15+ |
| **State transitions** | 10 | 15 | 20+ |
| **Integration points** | 3 | 6 | 10+ |
| **Event types** | 0 | 0 | 10+ |

### Visual Complexity

```mermaid
graph LR
    subgraph "Complexity Scale"
        O1[Option 1<br/>⭐⭐<br/>Simple]
        O2[Option 2<br/>⭐⭐⭐⭐<br/>Complex]
        O3[Option 3<br/>⭐⭐⭐⭐⭐<br/>Very Complex]
    end
    
    O1 -->|Add coordination| O2
    O2 -->|Add events| O3
    
    style O1 fill:#90EE90
    style O2 fill:#FFD700
    style O3 fill:#FF6B6B
```

---

## Выводы из диаграмм

### Option 1: Простота и ясность
- **Линейный flow**: User → Orchestrator → Architect → ExecutionEngine
- **Минимум компонентов**: 8 основных компонентов
- **Понятные связи**: Прямые вызовы методов
- **Легко отследить**: Простой call stack

### Option 2: Координация и контроль
- **Централизованное управление**: Orchestrator контролирует всё
- **Больше состояний**: 15 FSM states
- **Сложнее debugging**: Нужно отслеживать FSM transitions
- **Больше coupling**: Orchestrator знает о всех компонентах

### Option 3: Гибкость и масштабируемость
- **Асинхронность**: Компоненты не ждут друг друга
- **Развязка**: Компоненты общаются только через события
- **Сложный flow**: Трудно отследить последовательность
- **Много moving parts**: 15+ компонентов, 10+ типов событий

---

## Рекомендация: Option 1

**Диаграммы подтверждают выбор Option 1:**

1. **Простота архитектуры** - минимум компонентов и связей
2. **Понятный flow** - легко читать sequence diagram
3. **Низкая сложность** - простая state machine
4. **Быстрая реализация** - меньше кода для написания

**Option 1 обеспечивает оптимальный баланс между функциональностью и сложностью.**
