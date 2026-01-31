# OrchestratorAgent Integration Plan

> **Цель:** Интегрировать TaskClassifier, FSMOrchestrator и ExecutionEngine в OrchestratorAgent  
> **Время:** 6-8 часов  
> **Статус:** 🚧 In Progress

---

## 🎯 Задачи интеграции

### Phase 1: Подготовка (1-2 часа)

- [x] Изучить текущую реализацию OrchestratorAgent
- [ ] Создать backup текущей версии
- [ ] Определить точки интеграции
- [ ] Спланировать backward compatibility

### Phase 2: Интеграция TaskClassifier (1-2 часа)

- [ ] Заменить `classify_task_with_llm()` на `TaskClassifier.classify()`
- [ ] Обновить обработку результатов классификации
- [ ] Сохранить fallback механизм
- [ ] Обновить тесты

### Phase 3: Интеграция FSMOrchestrator (2-3 часа)

- [ ] Добавить FSMOrchestrator в `__init__()`
- [ ] Интегрировать FSM transitions в message flow
- [ ] Обработать все состояния FSM
- [ ] Добавить error handling для FSM

### Phase 4: Интеграция ExecutionEngine (2-3 часа)

- [ ] Добавить ExecutionEngine в `__init__()`
- [ ] Обработать состояние EXECUTION
- [ ] Интегрировать мониторинг прогресса
- [ ] Добавить cancellation support

### Phase 5: Тестирование (1-2 часа)

- [ ] Обновить существующие тесты
- [ ] Добавить новые тесты для интеграции
- [ ] Проверить backward compatibility
- [ ] E2E тестирование

---

## 🔍 Анализ текущей реализации

### Текущий OrchestratorAgent

```python
class OrchestratorAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_type=AgentType.ORCHESTRATOR,
            system_prompt=ORCHESTRATOR_PROMPT,
            allowed_tools=["read_file", "list_files", "search_in_code"]
        )
    
    async def process(self, session_id, message, context, ...):
        # 1. Классификация через LLM
        target_agent, classification_info = await self.classify_task_with_llm(message)
        
        # 2. Отправка switch_agent chunk
        yield StreamChunk(
            type="switch_agent",
            content=f"Routing to {target_agent.value} agent",
            metadata={
                "target_agent": target_agent.value,
                "reason": classification_info.get("reasoning", ...),
                ...
            }
        )
```

### Целевая реализация

```python
class OrchestratorAgent(BaseAgent):
    def __init__(
        self,
        task_classifier: TaskClassifier,
        fsm_orchestrator: FSMOrchestrator,
        execution_engine: ExecutionEngine,
        plan_repository: PlanRepository
    ):
        super().__init__(...)
        self.task_classifier = task_classifier
        self.fsm = fsm_orchestrator
        self.execution_engine = execution_engine
        self.plan_repository = plan_repository
    
    async def process(self, session_id, message, context, ...):
        # 1. Классификация через TaskClassifier
        classification = await self.task_classifier.classify(message)
        
        # 2. FSM transition
        new_state = await self.fsm.transition(
            session_id=session_id,
            event=classification
        )
        
        # 3. Обработка состояния
        if new_state == FSMState.PLAN_REQUIRED:
            # Требуется план - переключить на Architect
            yield self._create_switch_chunk(AgentType.ARCHITECT, ...)
            
        elif new_state == FSMState.EXECUTION:
            # Выполнить план
            plan_id = context.get("plan_id")
            result = await self.execution_engine.execute_plan(
                plan_id=plan_id,
                session_id=session_id,
                ...
            )
            yield self._create_result_chunk(result)
            
        elif new_state == FSMState.CLASSIFY:
            # Атомарная задача - переключить на целевого агента
            target_agent = classification.agent
            yield self._create_switch_chunk(target_agent, ...)
```

---

## 🔄 Изменения в message flow

### Текущий flow

```
User Message
    ↓
OrchestratorAgent.process()
    ↓
classify_task_with_llm()
    ↓
switch_agent chunk
    ↓
Target Agent
```

### Новый flow

```
User Message
    ↓
OrchestratorAgent.process()
    ↓
TaskClassifier.classify()
    ↓
FSMOrchestrator.transition()
    ↓
┌─────────────────────────────────┐
│ FSM State Decision              │
├─────────────────────────────────┤
│ CLASSIFY → switch to agent      │
│ PLAN_REQUIRED → switch to plan  │
│ EXECUTION → execute_plan()      │
│ ERROR_HANDLING → handle error   │
│ COMPLETED → return result       │
└─────────────────────────────────┘
    ↓
Target Agent / ExecutionEngine
```

---

## 📝 Детальный план изменений

### 1. Обновить `__init__()`

```python
# Было
def __init__(self):
    super().__init__(...)

# Стало
def __init__(
    self,
    task_classifier: Optional[TaskClassifier] = None,
    fsm_orchestrator: Optional[FSMOrchestrator] = None,
    execution_engine: Optional[ExecutionEngine] = None,
    plan_repository: Optional[PlanRepository] = None
):
    super().__init__(...)
    
    # Dependency Injection с fallback на создание
    self.task_classifier = task_classifier or self._create_task_classifier()
    self.fsm = fsm_orchestrator or self._create_fsm_orchestrator()
    self.execution_engine = execution_engine or self._create_execution_engine()
    self.plan_repository = plan_repository or self._create_plan_repository()
```

### 2. Обновить `process()`

```python
async def process(self, session_id, message, context, ...):
    # 1. Классификация
    classification = await self.task_classifier.classify(
        task_description=message,
        context=context
    )
    
    # 2. FSM transition
    try:
        new_state = await self.fsm.transition(
            session_id=session_id,
            event={
                "type": "task_classified",
                "classification": classification
            }
        )
    except FSMTransitionError as e:
        logger.error(f"FSM transition error: {e}")
        yield self._create_error_chunk(str(e))
        return
    
    # 3. Обработка состояния
    async for chunk in self._handle_state(
        state=new_state,
        session_id=session_id,
        message=message,
        context=context,
        classification=classification,
        ...
    ):
        yield chunk
```

### 3. Добавить `_handle_state()`

```python
async def _handle_state(
    self,
    state: FSMState,
    session_id: str,
    message: str,
    context: Dict[str, Any],
    classification: TaskClassification,
    ...
) -> AsyncGenerator[StreamChunk, None]:
    """Обработать текущее состояние FSM"""
    
    if state == FSMState.CLASSIFY:
        # Атомарная задача - переключить на целевого агента
        target_agent = self._map_agent_type(classification.agent)
        yield self._create_switch_chunk(
            target_agent=target_agent,
            reason=classification.reasoning,
            confidence=classification.confidence
        )
    
    elif state == FSMState.PLAN_REQUIRED:
        # Требуется план - переключить на Architect
        yield self._create_switch_chunk(
            target_agent=AgentType.ARCHITECT,
            reason="Complex task requires planning",
            confidence="high"
        )
    
    elif state == FSMState.EXECUTION:
        # Выполнить план
        plan_id = context.get("plan_id")
        if not plan_id:
            yield self._create_error_chunk("No plan_id in context")
            return
        
        try:
            result = await self.execution_engine.execute_plan(
                plan_id=plan_id,
                session_id=session_id,
                session_service=session_service,
                stream_handler=stream_handler
            )
            
            yield self._create_execution_result_chunk(result)
            
        except ExecutionEngineError as e:
            logger.error(f"Execution error: {e}")
            yield self._create_error_chunk(str(e))
    
    elif state == FSMState.ERROR_HANDLING:
        # Обработка ошибки
        error_info = context.get("error")
        yield self._create_error_chunk(error_info)
    
    elif state == FSMState.COMPLETED:
        # Завершение
        yield StreamChunk(
            type="done",
            content="Task completed",
            is_final=True
        )
```

### 4. Добавить helper методы

```python
def _map_agent_type(self, agent_str: str) -> AgentType:
    """Маппинг строки агента в AgentType"""
    mapping = {
        "code": AgentType.CODER,
        "coder": AgentType.CODER,
        "plan": AgentType.ARCHITECT,
        "architect": AgentType.ARCHITECT,
        "debug": AgentType.DEBUG,
        "explain": AgentType.ASK,
        "ask": AgentType.ASK
    }
    return mapping.get(agent_str.lower(), AgentType.CODER)

def _create_switch_chunk(
    self,
    target_agent: AgentType,
    reason: str,
    confidence: str
) -> StreamChunk:
    """Создать switch_agent chunk"""
    return StreamChunk(
        type="switch_agent",
        content=f"Routing to {target_agent.value} agent",
        metadata={
            "target_agent": target_agent.value,
            "reason": reason,
            "confidence": confidence,
            "classification_method": "task_classifier"
        },
        is_final=True
    )

def _create_execution_result_chunk(
    self,
    result: ExecutionResult
) -> StreamChunk:
    """Создать chunk с результатом выполнения"""
    return StreamChunk(
        type="assistant_message",
        content=f"Plan execution {result.status}",
        metadata={
            "plan_id": result.plan_id,
            "status": result.status,
            "completed": result.completed_subtasks,
            "failed": result.failed_subtasks,
            "total": result.total_subtasks,
            "duration": result.duration_seconds
        },
        is_final=True
    )

def _create_error_chunk(self, error: str) -> StreamChunk:
    """Создать error chunk"""
    return StreamChunk(
        type="error",
        error=error,
        is_final=True
    )
```

---

## 🧪 Тестирование

### Новые тесты

```python
# test_orchestrator_integration.py

async def test_orchestrator_atomic_task():
    """Тест обработки атомарной задачи"""
    orchestrator = OrchestratorAgent(...)
    
    chunks = []
    async for chunk in orchestrator.process(
        session_id="test",
        message="Create a button component",
        ...
    ):
        chunks.append(chunk)
    
    # Должен переключить на Coder
    assert chunks[-1].type == "switch_agent"
    assert chunks[-1].metadata["target_agent"] == "coder"

async def test_orchestrator_complex_task():
    """Тест обработки сложной задачи"""
    orchestrator = OrchestratorAgent(...)
    
    chunks = []
    async for chunk in orchestrator.process(
        session_id="test",
        message="Build authentication system",
        ...
    ):
        chunks.append(chunk)
    
    # Должен переключить на Architect
    assert chunks[-1].type == "switch_agent"
    assert chunks[-1].metadata["target_agent"] == "architect"

async def test_orchestrator_plan_execution():
    """Тест выполнения плана"""
    orchestrator = OrchestratorAgent(...)
    
    # Создать план
    plan = create_test_plan()
    await plan_repository.save(plan)
    
    # Выполнить через orchestrator
    chunks = []
    async for chunk in orchestrator.process(
        session_id="test",
        message="execute_plan",
        context={"plan_id": plan.id},
        ...
    ):
        chunks.append(chunk)
    
    # Проверить результат
    assert any(c.type == "assistant_message" for c in chunks)
```

---

## ⚠️ Риски и митигация

### Риск 1: Breaking changes

**Проблема:** Изменения могут сломать существующий функционал

**Митигация:**
- Сохранить backward compatibility
- Добавить feature flags
- Постепенная миграция

### Риск 2: Performance degradation

**Проблема:** Дополнительные слои могут замедлить работу

**Митигация:**
- Benchmarking до и после
- Оптимизация критических путей
- Кэширование где возможно

### Риск 3: Сложность тестирования

**Проблема:** Интеграционные тесты сложнее unit тестов

**Митигация:**
- Использовать mocks для зависимостей
- Создать test fixtures
- Изолировать тестовые сценарии

---

## 🔄 Backward Compatibility

### Стратегия

1. **Feature Flag:** Включать новую систему через конфиг
2. **Fallback:** Сохранить старую логику как fallback
3. **Gradual Migration:** Постепенно переводить на новую систему

### Пример

```python
class OrchestratorAgent:
    def __init__(self, use_planning_system: bool = False):
        self.use_planning_system = use_planning_system
        
        if use_planning_system:
            self.task_classifier = TaskClassifier()
            self.fsm = FSMOrchestrator()
            self.execution_engine = ExecutionEngine()
    
    async def process(self, ...):
        if self.use_planning_system:
            # Новая логика
            return await self._process_with_planning_system(...)
        else:
            # Старая логика (fallback)
            return await self._process_legacy(...)
```

---

## 📋 Checklist

### Код
- [ ] Обновить `OrchestratorAgent.__init__()`
- [ ] Обновить `OrchestratorAgent.process()`
- [ ] Добавить `_handle_state()`
- [ ] Добавить helper методы
- [ ] Добавить error handling
- [ ] Добавить logging

### Тесты
- [ ] Обновить существующие тесты
- [ ] Добавить тесты для TaskClassifier integration
- [ ] Добавить тесты для FSM integration
- [ ] Добавить тесты для ExecutionEngine integration
- [ ] Добавить E2E тесты

### Документация
- [ ] Обновить OrchestratorAgent docs
- [ ] Добавить migration guide
- [ ] Обновить API documentation
- [ ] Добавить примеры использования

---

## 🎯 Критерии успеха

- [ ] Все существующие тесты проходят
- [ ] Новые тесты проходят (>90%)
- [ ] Backward compatibility сохранена
- [ ] Performance не ухудшилась
- [ ] Документация обновлена

---

**Версия:** 1.0.0  
**Дата:** 2026-01-31  
**Автор:** CodeLab Team
