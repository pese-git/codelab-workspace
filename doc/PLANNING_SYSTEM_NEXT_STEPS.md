# 🚀 Planning System - Next Steps

## ✅ Текущий статус

### Завершено
- ✅ **ExecutionEngine Tests Fixed** - 100% pass rate (18/18 tests)
- ✅ **Planning System Tests** - 100% pass rate (104/104 tests)
- ✅ **Performance Improvements** - устранены избыточные DB queries
- ✅ **Documentation** - comprehensive guides и reports

### Готовность компонентов
**6/8 компонентов готовы (75%)**

1. ✅ TaskClassifier (28 tests, 100%)
2. ✅ PlanRepository (100%)
3. ✅ FSMOrchestrator (37 tests, 100%)
4. ✅ DependencyResolver (100%)
5. ✅ SubtaskExecutor (21 tests, 100%)
6. ✅ ExecutionEngine (18 tests, 100%)
7. 📋 OrchestratorAgent Integration (план готов)
8. ⏳ API Endpoints (pending)

## 🎯 Следующие шаги для MVP

### Phase 1: OrchestratorAgent Integration (6-8 часов)

#### 1.1 Подготовка (1 час)
- [ ] Создать feature branch `feature/orchestrator-integration`
- [ ] Создать backup текущей версии OrchestratorAgent
- [ ] Настроить feature flag для постепенной миграции
- [ ] Подготовить test fixtures

#### 1.2 Интеграция TaskClassifier (1-2 часа)
```python
# Заменить classify_task_with_llm() на TaskClassifier
class OrchestratorAgent:
    def __init__(self, task_classifier: Optional[TaskClassifier] = None):
        self.task_classifier = task_classifier or TaskClassifier(...)
    
    async def process(self, ...):
        # Вместо LLM classification
        classification = await self.task_classifier.classify(
            task_description=message,
            context=context
        )
```

**Задачи:**
- [ ] Добавить TaskClassifier в `__init__()`
- [ ] Заменить `classify_task_with_llm()` на `TaskClassifier.classify()`
- [ ] Обновить обработку результатов классификации
- [ ] Сохранить fallback на LLM при ошибках
- [ ] Обновить тесты

#### 1.3 Интеграция FSMOrchestrator (2-3 часа)
```python
async def process(self, ...):
    # 1. Классификация
    classification = await self.task_classifier.classify(message)
    
    # 2. FSM transition
    new_state = await self.fsm.transition(
        session_id=session_id,
        event={"type": "task_classified", "classification": classification}
    )
    
    # 3. Обработка состояния
    async for chunk in self._handle_state(new_state, ...):
        yield chunk
```

**Задачи:**
- [ ] Добавить FSMOrchestrator в `__init__()`
- [ ] Интегрировать FSM transitions в message flow
- [ ] Добавить `_handle_state()` для обработки состояний
- [ ] Обработать все состояния FSM (CLASSIFY, PLAN_REQUIRED, EXECUTION, etc.)
- [ ] Добавить error handling для FSM transitions
- [ ] Обновить тесты

#### 1.4 Интеграция ExecutionEngine (2-3 часа)
```python
async def _handle_state(self, state, ...):
    if state == FSMState.EXECUTION:
        plan_id = context.get("plan_id")
        result = await self.execution_engine.execute_plan(
            plan_id=plan_id,
            session_id=session_id,
            session_service=session_service,
            stream_handler=stream_handler
        )
        yield self._create_execution_result_chunk(result)
```

**Задачи:**
- [ ] Добавить ExecutionEngine в `__init__()`
- [ ] Обработать состояние EXECUTION
- [ ] Интегрировать мониторинг прогресса выполнения
- [ ] Добавить cancellation support
- [ ] Добавить streaming результатов выполнения
- [ ] Обновить тесты

### Phase 2: API Endpoints (4-6 часов)

#### 2.1 Plan Management Endpoints (2-3 часа)
```python
# POST /api/v1/plans
async def create_plan(request: CreatePlanRequest):
    """Создать новый план"""
    
# GET /api/v1/plans/{plan_id}
async def get_plan(plan_id: str):
    """Получить план по ID"""
    
# PUT /api/v1/plans/{plan_id}
async def update_plan(plan_id: str, request: UpdatePlanRequest):
    """Обновить план"""
    
# DELETE /api/v1/plans/{plan_id}
async def delete_plan(plan_id: str):
    """Удалить план"""
```

**Задачи:**
- [ ] Создать Pydantic schemas для requests/responses
- [ ] Реализовать CRUD endpoints для планов
- [ ] Добавить валидацию входных данных
- [ ] Добавить error handling
- [ ] Добавить тесты для endpoints

#### 2.2 Plan Execution Endpoints (2-3 часа)
```python
# POST /api/v1/plans/{plan_id}/execute
async def execute_plan(plan_id: str):
    """Запустить выполнение плана"""
    
# GET /api/v1/plans/{plan_id}/status
async def get_execution_status(plan_id: str):
    """Получить статус выполнения"""
    
# POST /api/v1/plans/{plan_id}/cancel
async def cancel_execution(plan_id: str):
    """Отменить выполнение плана"""
```

**Задачи:**
- [ ] Реализовать execution endpoints
- [ ] Добавить WebSocket support для real-time updates
- [ ] Интегрировать с ExecutionEngine
- [ ] Добавить progress tracking
- [ ] Добавить тесты для endpoints

### Phase 3: End-to-End Testing (2-3 часа)

#### 3.1 Integration Tests
- [ ] Тест полного flow: классификация → планирование → выполнение
- [ ] Тест атомарной задачи через OrchestratorAgent
- [ ] Тест сложной задачи с планированием
- [ ] Тест выполнения плана с зависимостями
- [ ] Тест error handling и recovery

#### 3.2 Performance Testing
- [ ] Benchmark классификации задач
- [ ] Benchmark выполнения планов
- [ ] Тест параллельного выполнения подзадач
- [ ] Тест нагрузки на систему

#### 3.3 Manual Testing
- [ ] Тест через IDE интерфейс
- [ ] Тест через API endpoints
- [ ] Тест различных сценариев использования

### Phase 4: Documentation (1-2 часа)

#### 4.1 Developer Documentation
- [ ] Обновить OrchestratorAgent documentation
- [ ] Добавить migration guide
- [ ] Обновить API documentation
- [ ] Добавить примеры использования

#### 4.2 User Documentation
- [ ] Создать user guide для Planning System
- [ ] Добавить примеры типичных задач
- [ ] Создать troubleshooting guide

## 📊 Оценка времени

| Phase | Задача | Время | Приоритет |
|-------|--------|-------|-----------|
| 1.1 | Подготовка | 1 ч | High |
| 1.2 | TaskClassifier Integration | 1-2 ч | High |
| 1.3 | FSMOrchestrator Integration | 2-3 ч | High |
| 1.4 | ExecutionEngine Integration | 2-3 ч | High |
| 2.1 | Plan Management Endpoints | 2-3 ч | Medium |
| 2.2 | Plan Execution Endpoints | 2-3 ч | Medium |
| 3 | End-to-End Testing | 2-3 ч | High |
| 4 | Documentation | 1-2 ч | Medium |

**Total:** 13-19 часов

## 🎯 MVP Scope

### Must Have (для MVP)
- ✅ TaskClassifier
- ✅ FSMOrchestrator
- ✅ ExecutionEngine
- ✅ SubtaskExecutor
- ✅ DependencyResolver
- 📋 OrchestratorAgent Integration
- 📋 Basic API Endpoints (create, execute, status)
- 📋 Basic E2E Tests

### Nice to Have (post-MVP)
- ⏳ Advanced API Endpoints (update, delete, list)
- ⏳ WebSocket real-time updates
- ⏳ Plan templates
- ⏳ Plan versioning
- ⏳ Advanced monitoring и analytics

## 🔄 Рекомендуемый порядок выполнения

### Неделя 1: OrchestratorAgent Integration
**День 1-2:** TaskClassifier + FSMOrchestrator integration  
**День 3-4:** ExecutionEngine integration  
**День 5:** Testing и bug fixes

### Неделя 2: API Endpoints + Testing
**День 1-2:** Plan Management Endpoints  
**День 3:** Plan Execution Endpoints  
**День 4:** End-to-End Testing  
**День 5:** Documentation + Release

## 📋 Готовые ресурсы

### Документация
- ✅ [`ORCHESTRATOR_INTEGRATION_PLAN.md`](ORCHESTRATOR_INTEGRATION_PLAN.md) - детальный план интеграции
- ✅ [`EXECUTION_ENGINE_GUIDE.md`](../codelab-ai-service/agent-runtime/doc/EXECUTION_ENGINE_GUIDE.md) - руководство по ExecutionEngine
- ✅ [`PLANNING_SYSTEM_QUICKSTART.md`](../codelab-ai-service/agent-runtime/doc/PLANNING_SYSTEM_QUICKSTART.md) - quick start guide
- ✅ [`PLANNING_SYSTEM_TESTS_FIXED.md`](PLANNING_SYSTEM_TESTS_FIXED.md) - отчёт об исправлениях

### Код
- ✅ TaskClassifier - полностью реализован и протестирован
- ✅ FSMOrchestrator - полностью реализован и протестирован
- ✅ ExecutionEngine - полностью реализован и протестирован
- ✅ SubtaskExecutor - полностью реализован и протестирован
- ✅ DependencyResolver - полностью реализован и протестирован

### Тесты
- ✅ 104 unit tests (100% pass rate)
- ✅ Test fixtures готовы
- ✅ Mock infrastructure готова

## 🚀 Quick Start для интеграции

### 1. Создать feature branch
```bash
cd codelab-ai-service/agent-runtime
git checkout -b feature/orchestrator-integration
```

### 2. Обновить OrchestratorAgent
```python
# app/agents/orchestrator_agent.py
from app.domain.services.task_classifier import TaskClassifier
from app.domain.services.fsm_orchestrator import FSMOrchestrator
from app.domain.services.execution_engine import ExecutionEngine

class OrchestratorAgent(BaseAgent):
    def __init__(
        self,
        task_classifier: Optional[TaskClassifier] = None,
        fsm_orchestrator: Optional[FSMOrchestrator] = None,
        execution_engine: Optional[ExecutionEngine] = None
    ):
        super().__init__(...)
        self.task_classifier = task_classifier or self._create_task_classifier()
        self.fsm = fsm_orchestrator or FSMOrchestrator()
        self.execution_engine = execution_engine or self._create_execution_engine()
```

### 3. Запустить тесты
```bash
uv run pytest tests/test_orchestrator_agent.py -v
```

## 📞 Контакты и поддержка

**Вопросы по интеграции:**
- См. [`ORCHESTRATOR_INTEGRATION_PLAN.md`](ORCHESTRATOR_INTEGRATION_PLAN.md)
- См. [`EXECUTION_ENGINE_GUIDE.md`](../codelab-ai-service/agent-runtime/doc/EXECUTION_ENGINE_GUIDE.md)

**Проблемы с тестами:**
- См. [`PLANNING_SYSTEM_TESTS_FIXED.md`](PLANNING_SYSTEM_TESTS_FIXED.md)

---

**Версия:** 1.0.0  
**Дата:** 2026-01-31  
**Статус:** 🚧 Ready for Integration  
**ETA до MVP:** 2-3 недели при текущем темпе
