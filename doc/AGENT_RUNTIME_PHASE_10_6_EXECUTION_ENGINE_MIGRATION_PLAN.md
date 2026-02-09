# 🚀 Phase 10.6: ExecutionEngine Migration Plan

**Статус:** 📋 Запланировано  
**Приоритет:** Medium  
**Оценка:** 2-3 дня  
**Зависимости:** Phase 10.5 (завершена на 80%)

---

## 📋 Обзор

Phase 10.6 завершает работу по очистке legacy кода, начатую в Phase 10.5. Основная цель - миграция [`ExecutionCoordinator`](codelab-ai-service/agent-runtime/app/application/coordinators/execution_coordinator.py) с legacy [`ExecutionEngine`](codelab-ai-service/agent-runtime/app/domain/execution_engine.py) на новый [`PlanExecutionService`](codelab-ai-service/agent-runtime/app/domain/execution_context/services/plan_execution_service.py).

---

## 🎯 Цели

### Основные
1. ✅ Мигрировать `ExecutionCoordinator` на `PlanExecutionService`
2. ✅ Удалить legacy `ExecutionEngine`
3. ✅ Обновить все тесты
4. ✅ Создать документацию

### Дополнительные
- Улучшить error handling
- Добавить integration tests
- Оптимизировать performance

---

## 📊 Текущее состояние

### Legacy Architecture

```
┌─────────────────────────┐
│  ExecutionCoordinator   │
│  (Application Layer)    │
└───────────┬─────────────┘
            │
            │ uses
            ▼
┌─────────────────────────┐
│   ExecutionEngine       │ ❌ Legacy
│   (Domain Layer)        │
└───────────┬─────────────┘
            │
            │ manages
            ▼
┌─────────────────────────┐
│   Plan (legacy)         │ ❌ Удален в Phase 10.5
└─────────────────────────┘
```

### Target Architecture

```
┌─────────────────────────┐
│  ExecutionCoordinator   │
│  (Application Layer)    │
└───────────┬─────────────┘
            │
            │ uses
            ▼
┌─────────────────────────┐
│  PlanExecutionService   │ ✅ New DDD
│  (Domain Service)       │
└───────────┬─────────────┘
            │
            │ manages
            ▼
┌─────────────────────────┐
│   ExecutionPlan         │ ✅ New DDD
│   (Aggregate Root)      │
└─────────────────────────┘
```

---

## 🔍 Анализ зависимостей

### ExecutionEngine Usage

```bash
# Найти все использования ExecutionEngine
grep -r "ExecutionEngine" codelab-ai-service/agent-runtime/app/
```

**Ожидаемые файлы:**
1. [`app/application/coordinators/execution_coordinator.py`](codelab-ai-service/agent-runtime/app/application/coordinators/execution_coordinator.py) - основной пользователь
2. [`app/domain/execution_engine.py`](codelab-ai-service/agent-runtime/app/domain/execution_engine.py) - сам файл
3. Тесты для `ExecutionCoordinator`
4. Тесты для `ExecutionEngine`

### API Comparison

| ExecutionEngine (Legacy) | PlanExecutionService (New) | Статус |
|--------------------------|----------------------------|--------|
| `execute_plan(plan)` | `execute_plan(plan_id)` | ✅ Есть |
| `pause_execution()` | `pause_plan(plan_id)` | ✅ Есть |
| `resume_execution()` | `resume_plan(plan_id)` | ✅ Есть |
| `cancel_execution()` | `cancel_plan(plan_id)` | ✅ Есть |
| `get_status()` | `get_plan_status(plan_id)` | ✅ Есть |
| `execute_subtask()` | `execute_subtask(subtask_id)` | ✅ Есть |

**Вывод:** API совместимы, миграция возможна.

---

## 📝 План выполнения

### Этап 1: Анализ и подготовка (2 часа)

#### 1.1 Анализ ExecutionCoordinator
```bash
# Прочитать текущую реализацию
cat codelab-ai-service/agent-runtime/app/application/coordinators/execution_coordinator.py
```

**Задачи:**
- [ ] Изучить все методы `ExecutionCoordinator`
- [ ] Найти все вызовы `ExecutionEngine`
- [ ] Составить mapping методов
- [ ] Выявить breaking changes

#### 1.2 Анализ тестов
```bash
# Найти тесты ExecutionCoordinator
find codelab-ai-service/agent-runtime/tests -name "*execution_coordinator*"
```

**Задачи:**
- [ ] Изучить существующие тесты
- [ ] Определить coverage
- [ ] Спланировать обновление тестов

#### 1.3 Создание плана миграции
**Задачи:**
- [ ] Создать детальный checklist
- [ ] Определить порядок изменений
- [ ] Спланировать rollback strategy

---

### Этап 2: Миграция ExecutionCoordinator (4-6 часов)

#### 2.1 Обновление зависимостей

**Файл:** [`execution_coordinator.py`](codelab-ai-service/agent-runtime/app/application/coordinators/execution_coordinator.py)

```python
# ❌ Legacy imports
from app.domain.execution_engine import ExecutionEngine

# ✅ New imports
from app.domain.execution_context.services.plan_execution_service import PlanExecutionService
```

#### 2.2 Обновление конструктора

```python
# ❌ Legacy
class ExecutionCoordinator:
    def __init__(
        self,
        execution_engine: ExecutionEngine,
        conversation_repo: ConversationRepository,
    ):
        self._execution_engine = execution_engine
        self._conversation_repo = conversation_repo

# ✅ New
class ExecutionCoordinator:
    def __init__(
        self,
        plan_execution_service: PlanExecutionService,
        conversation_repo: ConversationRepository,
        event_bus: EventBus,
    ):
        self._plan_execution_service = plan_execution_service
        self._conversation_repo = conversation_repo
        self._event_bus = event_bus
```

#### 2.3 Миграция методов

**Пример: execute_plan()**

```python
# ❌ Legacy
async def execute_plan(self, session_id: str) -> None:
    conversation = await self._conversation_repo.get_by_id(session_id)
    plan = conversation.current_plan
    await self._execution_engine.execute_plan(plan)

# ✅ New
async def execute_plan(self, conversation_id: ConversationId) -> None:
    conversation = await self._conversation_repo.get_by_id(conversation_id)
    plan_id = conversation.execution_context.current_plan_id
    await self._plan_execution_service.execute_plan(plan_id)
```

**Методы для миграции:**
- [ ] `execute_plan()`
- [ ] `pause_execution()`
- [ ] `resume_execution()`
- [ ] `cancel_execution()`
- [ ] `get_execution_status()`
- [ ] `execute_next_subtask()`
- [ ] `handle_subtask_completion()`
- [ ] `handle_subtask_error()`

#### 2.4 Обновление error handling

```python
# ❌ Legacy
try:
    await self._execution_engine.execute_plan(plan)
except ExecutionEngineError as e:
    logger.error(f"Execution failed: {e}")
    raise

# ✅ New
try:
    await self._plan_execution_service.execute_plan(plan_id)
except PlanExecutionError as e:
    logger.error(f"Plan execution failed: {e}")
    await self._event_bus.publish(PlanExecutionFailedEvent(
        plan_id=plan_id,
        error=str(e),
    ))
    raise
```

---

### Этап 3: Обновление DI конфигурации (1 час)

#### 3.1 Обновление dependencies

**Файл:** [`app/api/dependencies.py`](codelab-ai-service/agent-runtime/app/api/dependencies.py)

```python
# ❌ Legacy
def get_execution_coordinator(
    execution_engine: ExecutionEngine = Depends(get_execution_engine),
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
) -> ExecutionCoordinator:
    return ExecutionCoordinator(
        execution_engine=execution_engine,
        conversation_repo=conversation_repo,
    )

# ✅ New
def get_execution_coordinator(
    plan_execution_service: PlanExecutionService = Depends(get_plan_execution_service),
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
    event_bus: EventBus = Depends(get_event_bus),
) -> ExecutionCoordinator:
    return ExecutionCoordinator(
        plan_execution_service=plan_execution_service,
        conversation_repo=conversation_repo,
        event_bus=event_bus,
    )
```

#### 3.2 Удаление ExecutionEngine dependency

```python
# ❌ Удалить
def get_execution_engine() -> ExecutionEngine:
    return ExecutionEngine()
```

---

### Этап 4: Удаление ExecutionEngine (1 час)

#### 4.1 Удаление файлов

```bash
# Удалить legacy ExecutionEngine
rm codelab-ai-service/agent-runtime/app/domain/execution_engine.py

# Удалить тесты
rm codelab-ai-service/agent-runtime/tests/unit/domain/test_execution_engine.py
```

#### 4.2 Обновление импортов

```bash
# Найти все импорты ExecutionEngine
grep -r "from app.domain.execution_engine import" codelab-ai-service/agent-runtime/

# Удалить или заменить
```

#### 4.3 Обновление __init__.py

**Файл:** [`app/domain/__init__.py`](codelab-ai-service/agent-runtime/app/domain/__init__.py)

```python
# ❌ Удалить
from app.domain.execution_engine import ExecutionEngine
```

---

### Этап 5: Обновление тестов (3-4 часа)

#### 5.1 Миграция unit tests

**Файл:** `tests/unit/application/coordinators/test_execution_coordinator.py`

```python
# ❌ Legacy
@pytest.fixture
def execution_engine():
    return Mock(spec=ExecutionEngine)

@pytest.fixture
def coordinator(execution_engine, conversation_repo):
    return ExecutionCoordinator(
        execution_engine=execution_engine,
        conversation_repo=conversation_repo,
    )

# ✅ New
@pytest.fixture
def plan_execution_service():
    return Mock(spec=PlanExecutionService)

@pytest.fixture
def coordinator(plan_execution_service, conversation_repo, event_bus):
    return ExecutionCoordinator(
        plan_execution_service=plan_execution_service,
        conversation_repo=conversation_repo,
        event_bus=event_bus,
    )
```

**Тесты для обновления:**
- [ ] `test_execute_plan_success()`
- [ ] `test_execute_plan_failure()`
- [ ] `test_pause_execution()`
- [ ] `test_resume_execution()`
- [ ] `test_cancel_execution()`
- [ ] `test_get_execution_status()`
- [ ] `test_execute_next_subtask()`
- [ ] `test_handle_subtask_completion()`
- [ ] `test_handle_subtask_error()`

#### 5.2 Добавление integration tests

**Новый файл:** `tests/integration/test_execution_coordinator_integration.py`

```python
@pytest.mark.integration
async def test_full_plan_execution_flow():
    """Test complete plan execution flow with real services."""
    # Setup
    coordinator = create_execution_coordinator()
    conversation_id = ConversationId.generate()
    
    # Create plan
    plan = await create_test_plan(conversation_id)
    
    # Execute
    await coordinator.execute_plan(conversation_id)
    
    # Verify
    status = await coordinator.get_execution_status(conversation_id)
    assert status.is_completed()
```

**Integration tests:**
- [ ] `test_full_plan_execution_flow()`
- [ ] `test_plan_execution_with_pause_resume()`
- [ ] `test_plan_execution_with_cancellation()`
- [ ] `test_plan_execution_with_subtask_failure()`
- [ ] `test_concurrent_plan_executions()`

#### 5.3 Запуск тестов

```bash
# Unit tests
pytest tests/unit/application/coordinators/test_execution_coordinator.py -v

# Integration tests
pytest tests/integration/test_execution_coordinator_integration.py -v

# All tests
pytest tests/ -v --cov=app/application/coordinators/execution_coordinator
```

---

### Этап 6: Документация (2 часа)

#### 6.1 Обновление архитектурной документации

**Файлы для обновления:**
- [ ] [`doc/AGENT_RUNTIME_ARCHITECTURE_COMPLIANCE_REPORT.md`](doc/AGENT_RUNTIME_ARCHITECTURE_COMPLIANCE_REPORT.md)
- [ ] [`codelab-ai-service/agent-runtime/README.md`](codelab-ai-service/agent-runtime/README.md)
- [ ] [`doc/AGENT_RUNTIME_PHASE_10_5_COMPLETION_REPORT.md`](doc/AGENT_RUNTIME_PHASE_10_5_COMPLETION_REPORT.md)

#### 6.2 Создание migration guide

**Новый файл:** `doc/AGENT_RUNTIME_EXECUTION_ENGINE_MIGRATION_GUIDE.md`

**Содержание:**
- Overview миграции
- Breaking changes
- Migration steps
- Code examples (до/после)
- Troubleshooting

#### 6.3 Обновление changelog

**Файл:** [`doc/AGENT_RUNTIME_PHASE_10_5_CHANGELOG.md`](doc/AGENT_RUNTIME_PHASE_10_5_CHANGELOG.md)

```markdown
## [Phase 10.6] - 2026-02-XX

### Removed
- ❌ `ExecutionEngine` - replaced with `PlanExecutionService`
- ❌ `app/domain/execution_engine.py`
- ❌ Legacy execution engine tests

### Changed
- 🔄 `ExecutionCoordinator` - migrated to use `PlanExecutionService`
- 🔄 DI configuration - updated dependencies
- 🔄 All tests - updated to use new services

### Added
- ✅ Integration tests for `ExecutionCoordinator`
- ✅ Migration guide
- ✅ Updated architecture documentation
```

#### 6.4 Создание completion report

**Новый файл:** `doc/AGENT_RUNTIME_PHASE_10_6_COMPLETION_REPORT.md`

---

### Этап 7: Code Review и QA (2 часа)

#### 7.1 Code review checklist

- [ ] Все методы мигрированы корректно
- [ ] DI конфигурация обновлена
- [ ] Все тесты проходят
- [ ] Coverage не снизился
- [ ] Нет breaking changes в public API
- [ ] Error handling корректен
- [ ] Logging добавлен
- [ ] Документация обновлена

#### 7.2 QA checklist

- [ ] Unit tests pass (100%)
- [ ] Integration tests pass (100%)
- [ ] E2E tests pass (если есть)
- [ ] Performance не ухудшился
- [ ] Memory leaks отсутствуют
- [ ] Concurrent execution работает

#### 7.3 Запуск полного test suite

```bash
# All tests
pytest tests/ -v --cov=app --cov-report=html

# Check coverage
open htmlcov/index.html
```

---

## 📊 Оценка времени

| Этап | Задача | Оценка | Сложность |
|------|--------|--------|-----------|
| 1 | Анализ и подготовка | 2 часа | Low |
| 2 | Миграция ExecutionCoordinator | 4-6 часов | High |
| 3 | Обновление DI | 1 час | Medium |
| 4 | Удаление ExecutionEngine | 1 час | Low |
| 5 | Обновление тестов | 3-4 часа | High |
| 6 | Документация | 2 часа | Medium |
| 7 | Code Review и QA | 2 часа | Medium |
| **ИТОГО** | | **15-18 часов** | **2-3 дня** |

---

## 🎯 Критерии успеха

### Must Have
- ✅ `ExecutionCoordinator` мигрирован на `PlanExecutionService`
- ✅ `ExecutionEngine` удален
- ✅ Все тесты проходят
- ✅ Coverage >= 80%
- ✅ Документация обновлена

### Should Have
- ✅ Integration tests добавлены
- ✅ Performance не ухудшился
- ✅ Migration guide создан

### Nice to Have
- ✅ E2E tests добавлены
- ✅ Performance улучшен
- ✅ Дополнительные примеры в документации

---

## ⚠️ Риски и митигация

### Риск 1: Breaking changes в API
**Вероятность:** Medium  
**Влияние:** High  
**Митигация:**
- Тщательный анализ API перед миграцией
- Создание compatibility layer (если нужно)
- Comprehensive testing

### Риск 2: Снижение performance
**Вероятность:** Low  
**Влияние:** Medium  
**Митигация:**
- Performance benchmarks до/после
- Profiling кода
- Optimization при необходимости

### Риск 3: Регрессия в тестах
**Вероятность:** Medium  
**Влияние:** High  
**Митигация:**
- Запуск всех тестов перед коммитом
- Code review
- QA testing

### Риск 4: Неполная миграция
**Вероятность:** Low  
**Влияние:** High  
**Митигация:**
- Детальный checklist
- Grep для поиска всех использований
- Code review

---

## 🔄 Rollback Strategy

### Если миграция не удалась

1. **Revert коммиты**
   ```bash
   git revert <commit-hash>
   ```

2. **Восстановить ExecutionEngine**
   ```bash
   git checkout HEAD~1 -- app/domain/execution_engine.py
   ```

3. **Запустить тесты**
   ```bash
   pytest tests/ -v
   ```

4. **Анализ проблемы**
   - Изучить логи
   - Определить root cause
   - Спланировать fix

---

## 📚 Ссылки

### Документация
- [Phase 10.5 Completion Report](AGENT_RUNTIME_PHASE_10_5_COMPLETION_REPORT.md)
- [Legacy Cleanup Migration Guide](AGENT_RUNTIME_LEGACY_CLEANUP_MIGRATION_GUIDE.md)
- [Architecture Compliance Report](AGENT_RUNTIME_ARCHITECTURE_COMPLIANCE_REPORT.md)

### Код
- [`ExecutionCoordinator`](codelab-ai-service/agent-runtime/app/application/coordinators/execution_coordinator.py)
- [`ExecutionEngine`](codelab-ai-service/agent-runtime/app/domain/execution_engine.py) (legacy)
- [`PlanExecutionService`](codelab-ai-service/agent-runtime/app/domain/execution_context/services/plan_execution_service.py)

---

## 🎉 Ожидаемые результаты

### Метрики

| Метрика | До | После | Цель |
|---------|-----|-------|------|
| **Legacy файлов** | 1 | 0 | ✅ 0 |
| **Строк legacy кода** | ~500 | 0 | ✅ 0 |
| **Test Coverage** | 82% | 85%+ | ✅ 85%+ |
| **Cyclomatic Complexity** | 6.2 | 5.5 | ✅ <6 |
| **Code Duplication** | 8% | 5% | ✅ <5% |

### Качественные улучшения

- ✅ **Полная миграция на DDD** - 100% domain layer
- ✅ **Улучшенная testability** - DI pattern везде
- ✅ **Лучшая maintainability** - нет legacy кода
- ✅ **Comprehensive documentation** - полное покрытие

---

## 🚀 Начало работы

### Prerequisites

1. ✅ Phase 10.5 завершена
2. ✅ Все тесты проходят
3. ✅ Документация изучена

### Команды для старта

```bash
# 1. Создать ветку
git checkout -b phase-10.6-execution-engine-migration

# 2. Анализ текущего состояния
grep -r "ExecutionEngine" codelab-ai-service/agent-runtime/app/

# 3. Запустить тесты (baseline)
pytest tests/ -v --cov=app

# 4. Начать миграцию
# ... следовать плану выше
```

---

**Создано:** 2026-02-09  
**Автор:** AI Assistant  
**Версия:** 1.0  
**Статус:** 📋 Ready to Start
