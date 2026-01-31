# Migration Path: Option 2 → Option 3

## Вопрос: Насколько сложно мигрировать с Option 2 на Option 3?

**Краткий ответ:** Средняя сложность (⭐⭐⭐), но хорошо структурированная миграция.

**Время:** 8-12 часов работы  
**Риски:** 🟡 Средние (требует тщательного тестирования)  
**Обратная совместимость:** Возможна (через adapter pattern)

---

## Анализ миграции

### Что общего между Option 2 и Option 3

#### ✅ Компоненты, которые остаются без изменений:

1. **Domain Layer**
   - ✅ `Plan` и `Subtask` entities
   - ✅ `ExecutionEngine`
   - ✅ `SubtaskExecutor`
   - ✅ `DependencyResolver`
   - ✅ `PlanRepository`
   - ✅ Все агенты (Architect, Coder, Debug, Ask)

2. **Business Logic**
   - ✅ Валидация планов
   - ✅ Dependency resolution
   - ✅ Subtask execution
   - ✅ Error handling

3. **Data Models**
   - ✅ Plan structure
   - ✅ Subtask structure
   - ✅ Execution results

**Вывод:** ~70% кода остаётся без изменений!

---

### Что нужно изменить

#### 🔄 Компоненты для рефакторинга:

1. **OrchestratorAgent** → **Event Publishers**
   - Заменить прямые вызовы на публикацию событий
   - Добавить event handlers
   - Сохранить FSM logic (можно переиспользовать)

2. **Coordination Logic** → **Event Handlers**
   - Извлечь coordination в отдельные handlers
   - Каждый handler подписывается на свои события
   - Сохранить бизнес-логику

3. **Communication** → **Event Bus**
   - Добавить Event Bus infrastructure
   - Заменить method calls на events
   - Добавить event routing

---

## Пошаговая миграция

### Phase 1: Подготовка (2-3 часа)

#### 1.1. Добавить Event Bus Infrastructure

```python
# app/infrastructure/events/event_bus.py
from typing import Dict, List, Callable, Any
import asyncio

class EventBus:
    """Simple in-memory event bus"""
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
    
    def subscribe(self, event_type: str, handler: Callable):
        """Subscribe to event type"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
    
    async def publish(self, event: Event):
        """Publish event to all subscribers"""
        handlers = self._subscribers.get(event.type, [])
        await asyncio.gather(*[h(event) for h in handlers])
```

**Сложность:** ⭐ (Простая)  
**Время:** 1 час

#### 1.2. Определить Event Types

```python
# app/domain/events/planning_events.py
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Event:
    """Base event"""
    type: str
    timestamp: datetime
    correlation_id: str

@dataclass
class PlanCreatedEvent(Event):
    plan_id: str
    goal: str
    subtasks_count: int

@dataclass
class PlanApprovedEvent(Event):
    plan_id: str
    approved_by: str

@dataclass
class ExecutionStartedEvent(Event):
    plan_id: str
    
@dataclass
class SubtaskStartedEvent(Event):
    plan_id: str
    subtask_id: str
    agent: str

@dataclass
class SubtaskCompletedEvent(Event):
    plan_id: str
    subtask_id: str
    result: Any

@dataclass
class SubtaskFailedEvent(Event):
    plan_id: str
    subtask_id: str
    error: str

@dataclass
class ExecutionCompletedEvent(Event):
    plan_id: str
    results: Dict[str, Any]
```

**Сложность:** ⭐ (Простая)  
**Время:** 1 час

---

### Phase 2: Создать Event Handlers (3-4 часа)

#### 2.1. Извлечь Orchestrator Logic в Handlers

**До (Option 2):**
```python
class OrchestratorAgent:
    async def handle_plan_creation(self, task: str):
        # Direct call
        plan_id = await self.architect.create_plan(task)
        await self.show_plan_to_user(plan_id)
        approval = await self.request_approval()
        if approval:
            await self.execution_engine.execute_plan(plan_id)
```

**После (Option 3):**
```python
class PlanCreationHandler:
    """Handler for plan creation events"""
    
    def __init__(self, event_bus: EventBus, architect: ArchitectAgent):
        self.event_bus = event_bus
        self.architect = architect
        
        # Subscribe to events
        event_bus.subscribe("TaskReceived", self.handle_task)
    
    async def handle_task(self, event: TaskReceivedEvent):
        """Handle task received event"""
        # Create plan
        plan_id = await self.architect.create_plan(event.task)
        
        # Publish plan created event
        await self.event_bus.publish(
            PlanCreatedEvent(
                type="PlanCreated",
                timestamp=datetime.now(),
                correlation_id=event.correlation_id,
                plan_id=plan_id,
                goal=event.task,
                subtasks_count=len(plan.subtasks)
            )
        )

class PlanApprovalHandler:
    """Handler for plan approval"""
    
    def __init__(self, event_bus: EventBus, ui_service: UIService):
        self.event_bus = event_bus
        self.ui_service = ui_service
        
        event_bus.subscribe("PlanCreated", self.handle_plan_created)
    
    async def handle_plan_created(self, event: PlanCreatedEvent):
        """Show plan to user and request approval"""
        # Show plan
        await self.ui_service.show_plan(event.plan_id)
        
        # Request approval
        approval = await self.ui_service.request_approval()
        
        if approval:
            await self.event_bus.publish(
                PlanApprovedEvent(
                    type="PlanApproved",
                    timestamp=datetime.now(),
                    correlation_id=event.correlation_id,
                    plan_id=event.plan_id,
                    approved_by="user"
                )
            )

class ExecutionHandler:
    """Handler for plan execution"""
    
    def __init__(
        self,
        event_bus: EventBus,
        execution_engine: ExecutionEngine
    ):
        self.event_bus = event_bus
        self.execution_engine = execution_engine
        
        event_bus.subscribe("PlanApproved", self.handle_plan_approved)
    
    async def handle_plan_approved(self, event: PlanApprovedEvent):
        """Execute approved plan"""
        # Start execution
        await self.event_bus.publish(
            ExecutionStartedEvent(
                type="ExecutionStarted",
                timestamp=datetime.now(),
                correlation_id=event.correlation_id,
                plan_id=event.plan_id
            )
        )
        
        # Execute
        result = await self.execution_engine.execute_plan(event.plan_id)
        
        # Publish completion
        await self.event_bus.publish(
            ExecutionCompletedEvent(
                type="ExecutionCompleted",
                timestamp=datetime.now(),
                correlation_id=event.correlation_id,
                plan_id=event.plan_id,
                results=result.to_dict()
            )
        )
```

**Сложность:** ⭐⭐⭐ (Средняя)  
**Время:** 3-4 часа

---

### Phase 3: Обновить ExecutionEngine (2-3 часа)

#### 3.1. Добавить Event Publishing в ExecutionEngine

**До (Option 2):**
```python
class ExecutionEngine:
    async def execute_plan(self, plan_id: str):
        # Execute subtasks
        for subtask_id in execution_order:
            result = await self._execute_subtask(subtask_id)
        return results
```

**После (Option 3):**
```python
class ExecutionEngine:
    def __init__(
        self,
        plan_repository: PlanRepository,
        subtask_executor: SubtaskExecutor,
        event_bus: EventBus  # NEW
    ):
        self.plan_repository = plan_repository
        self.subtask_executor = subtask_executor
        self.event_bus = event_bus  # NEW
    
    async def execute_plan(self, plan_id: str):
        # Publish execution started
        await self.event_bus.publish(
            ExecutionStartedEvent(
                type="ExecutionStarted",
                plan_id=plan_id,
                timestamp=datetime.now()
            )
        )
        
        # Execute subtasks
        for subtask_id in execution_order:
            # Publish subtask started
            await self.event_bus.publish(
                SubtaskStartedEvent(
                    type="SubtaskStarted",
                    plan_id=plan_id,
                    subtask_id=subtask_id,
                    timestamp=datetime.now()
                )
            )
            
            try:
                result = await self._execute_subtask(subtask_id)
                
                # Publish subtask completed
                await self.event_bus.publish(
                    SubtaskCompletedEvent(
                        type="SubtaskCompleted",
                        plan_id=plan_id,
                        subtask_id=subtask_id,
                        result=result,
                        timestamp=datetime.now()
                    )
                )
            except Exception as e:
                # Publish subtask failed
                await self.event_bus.publish(
                    SubtaskFailedEvent(
                        type="SubtaskFailed",
                        plan_id=plan_id,
                        subtask_id=subtask_id,
                        error=str(e),
                        timestamp=datetime.now()
                    )
                )
        
        # Publish execution completed
        await self.event_bus.publish(
            ExecutionCompletedEvent(
                type="ExecutionCompleted",
                plan_id=plan_id,
                results=results,
                timestamp=datetime.now()
            )
        )
        
        return results
```

**Сложность:** ⭐⭐ (Низкая-средняя)  
**Время:** 2-3 часа

---

### Phase 4: Adapter Pattern для обратной совместимости (1-2 часа)

#### 4.1. Создать Adapter для Option 2 API

```python
class OrchestratorAdapter:
    """
    Adapter для сохранения Option 2 API поверх Option 3.
    Позволяет постепенную миграцию.
    """
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._pending_results = {}
        
        # Subscribe to completion events
        event_bus.subscribe(
            "ExecutionCompleted",
            self._handle_completion
        )
    
    async def execute_plan(self, plan_id: str) -> ExecutionResult:
        """
        Option 2 style API that works with Option 3 events.
        """
        # Create future for result
        future = asyncio.Future()
        self._pending_results[plan_id] = future
        
        # Publish plan approved event
        await self.event_bus.publish(
            PlanApprovedEvent(
                type="PlanApproved",
                plan_id=plan_id,
                timestamp=datetime.now()
            )
        )
        
        # Wait for completion
        result = await future
        return result
    
    async def _handle_completion(self, event: ExecutionCompletedEvent):
        """Handle execution completed event"""
        if event.plan_id in self._pending_results:
            future = self._pending_results.pop(event.plan_id)
            future.set_result(event.results)
```

**Преимущества:**
- ✅ Старый код продолжает работать
- ✅ Можно мигрировать постепенно
- ✅ Тестировать по частям

**Сложность:** ⭐⭐ (Низкая-средняя)  
**Время:** 1-2 часа

---

## Сравнение сложности миграций

| Миграция | Сложность | Время | Риски | Обратная совместимость |
|----------|-----------|-------|-------|------------------------|
| **Option 1 → Option 2** | ⭐⭐⭐⭐ | 6-8 ч | 🟡 Средние | 🔴 Сложно |
| **Option 2 → Option 3** | ⭐⭐⭐ | 8-12 ч | 🟡 Средние | 🟢 Да (через adapter) |
| **Option 1 → Option 3** | ⭐⭐⭐⭐⭐ | 15-20 ч | 🔴 Высокие | 🔴 Нет |

---

## Преимущества миграции Option 2 → Option 3

### ✅ Что упрощает миграцию:

1. **Уже есть координация**
   - Option 2 уже имеет coordination logic
   - Просто извлекаем в event handlers
   - Бизнес-логика остаётся той же

2. **FSM можно переиспользовать**
   - FSM states → Event types
   - FSM transitions → Event publishing
   - Валидация остаётся

3. **Domain layer не меняется**
   - ExecutionEngine остаётся
   - Только добавляем event publishing
   - Entities не трогаем

4. **Постепенная миграция**
   - Можно использовать Adapter
   - Мигрировать по одному handler
   - Тестировать инкрементально

5. **Хорошая структура**
   - Option 2 уже разделён на компоненты
   - Легко извлечь в handlers
   - Понятные boundaries

---

## Недостатки и риски

### ❌ Что усложняет миграцию:

1. **Асинхронность**
   - Нужно правильно обработать async events
   - Возможны race conditions
   - Требует тщательного тестирования

2. **Debugging**
   - Сложнее отследить flow
   - Нужны инструменты для event tracing
   - Больше moving parts

3. **Testing**
   - Нужно тестировать event flows
   - Mock event bus
   - Integration tests сложнее

4. **Infrastructure**
   - Нужен Event Bus
   - Возможно Event Store
   - Monitoring и observability

---

## Пошаговый план миграции

### Рекомендуемый подход: Incremental Migration

#### Week 1: Infrastructure (2-3 часа)
- ✅ Добавить Event Bus
- ✅ Определить Event Types
- ✅ Создать базовые handlers
- ✅ Добавить Adapter для обратной совместимости

#### Week 2: Migrate Planning (3-4 часа)
- ✅ Извлечь plan creation в handler
- ✅ Извлечь plan approval в handler
- ✅ Тестировать через Adapter
- ✅ Старый код продолжает работать

#### Week 3: Migrate Execution (2-3 часа)
- ✅ Добавить event publishing в ExecutionEngine
- ✅ Создать execution handler
- ✅ Тестировать полный flow
- ✅ Проверить обратную совместимость

#### Week 4: Cleanup (1-2 часа)
- ✅ Удалить старый coordination code
- ✅ Удалить Adapter (если не нужен)
- ✅ Обновить документацию
- ✅ Final testing

**Итого:** 8-12 часов работы, распределённых на 4 недели

---

## Сравнение с другими миграциями

### Option 1 → Option 2 (сложнее)

**Почему сложнее:**
- ❌ Нужно добавить Orchestrator coordination
- ❌ Architect теряет control
- ❌ Больше изменений в существующем коде
- ❌ Сложнее сохранить обратную совместимость

### Option 1 → Option 3 (намного сложнее)

**Почему намного сложнее:**
- ❌ Нужно добавить и coordination, и events
- ❌ Два больших изменения сразу
- ❌ Нет промежуточного состояния
- ❌ Высокие риски

### Option 2 → Option 3 (оптимально)

**Почему оптимально:**
- ✅ Coordination уже есть
- ✅ Просто меняем communication mechanism
- ✅ Можно делать постепенно
- ✅ Adapter сохраняет совместимость

---

## Финальная рекомендация

### Если планируете Option 3 в будущем: **Начните с Option 2**

**Обоснование:**

1. **Естественный путь эволюции:**
   ```
   Option 1 (simple) → Option 2 (coordination) → Option 3 (events)
   ```

2. **Каждый шаг добавляет ценность:**
   - Option 1: Базовая функциональность
   - Option 2: Централизованное управление + replanning
   - Option 3: Максимальная гибкость + масштабируемость

3. **Миграция Option 2 → Option 3 проще:**
   - Средняя сложность (⭐⭐⭐)
   - 8-12 часов работы
   - Можно делать постепенно
   - Обратная совместимость через Adapter

4. **Получаете опыт:**
   - Понимаете требования к replanning
   - Видите bottlenecks
   - Знаете, какие события нужны
   - Готовы к Option 3

---

## Итоговая таблица решений

| Если в будущем нужен... | Начать с | Причина |
|-------------------------|----------|---------|
| **Только базовая функциональность** | Option 1 | Простота |
| **Replanning** | Option 2 | Централизация |
| **Event-driven в будущем** | Option 2 | Легче мигрировать |
| **Event-driven сейчас** | Option 3 | Сразу нужно |
| **Микросервисы в будущем** | Option 2 | Подготовка |

---

## Вывод

**Миграция Option 2 → Option 3: Средняя сложность, но хорошо структурирована**

**Ключевые факты:**
- ⭐⭐⭐ Сложность (средняя)
- 🕐 8-12 часов работы
- 🟡 Средние риски
- ✅ Обратная совместимость возможна
- ✅ Постепенная миграция
- ✅ 70% кода остаётся без изменений

**Если планируете Option 3 в будущем → начните с Option 2!**

Это даст вам:
1. Быстрый старт с Option 2
2. Опыт работы с coordination
3. Понимание требований
4. Простую миграцию к Option 3 когда нужно
