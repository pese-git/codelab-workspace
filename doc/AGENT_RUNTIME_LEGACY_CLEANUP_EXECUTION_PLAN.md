# План выполнения очистки Legacy кода в Agent Runtime

**Дата создания:** 2026-02-09  
**Ветка:** feature/phase-10-5-legacy-cleanup  
**Базовый документ:** [AGENT_RUNTIME_LEGACY_CODE_ANALYSIS.md](./AGENT_RUNTIME_LEGACY_CODE_ANALYSIS.md)  
**Исполнитель:** Roo Code AI (автоматический рефакторинг)

## Статус: 🚀 Готов к выполнению

---

## Резюме

На основе проведенного анализа создан пошаговый план по **автоматическому удалению legacy кода** из agent-runtime. Я буду выполнять рефакторинг самостоятельно, заменяя deprecated компоненты на новые DDD-архитектурные решения.

**Общая оценка времени:** 7-11 дней  
**Критичность:** Высокая (затрагивает core компоненты)  
**Режим работы:** Автоматический рефакторинг с тестированием

---

## Этап 1: Рефакторинг Deprecated Aliases

**Длительность:** 2-3 дня  
**Приоритет:** ⚠️ Высокий  
**Режим:** Автоматический рефакторинг

### Что я буду делать:

#### 1.1 Анализ использования

Найду все места использования deprecated aliases:

```bash
# Session → Conversation
grep -rn "from.*domain.entities import.*Session" --include="*.py" codelab-ai-service/agent-runtime/app/
grep -rn ": Session" --include="*.py" codelab-ai-service/agent-runtime/app/

# AgentContext → Agent
grep -rn "from.*domain.entities import.*AgentContext" --include="*.py" codelab-ai-service/agent-runtime/app/
grep -rn ": AgentContext" --include="*.py" codelab-ai-service/agent-runtime/app/

# AgentSwitch → AgentSwitchRecord
grep -rn "from.*domain.entities import.*AgentSwitch" --include="*.py" codelab-ai-service/agent-runtime/app/

# Legacy репозитории
grep -rn "SessionRepository\|AgentContextRepository" --include="*.py" codelab-ai-service/agent-runtime/app/
```

#### 1.2 Автоматическая замена импортов

Я выполню замену в каждом файле:

**Паттерны замены:**

```python
# 1. Session → Conversation
# БЫЛО:
from app.domain.entities import Session
session: Session = ...

# СТАНЕТ:
from app.domain.session_context.entities.conversation import Conversation
session: Conversation = ...

# 2. AgentContext → Agent
# БЫЛО:
from app.domain.entities import AgentContext
agent: AgentContext = ...

# СТАНЕТ:
from app.domain.agent_context.entities.agent import Agent
agent: Agent = ...

# 3. AgentSwitch → AgentSwitchRecord
# БЫЛО:
from app.domain.entities import AgentSwitch
switch: AgentSwitch = ...

# СТАНЕТ:
from app.domain.agent_context.entities.agent import AgentSwitchRecord
switch: AgentSwitchRecord = ...

# 4. SessionRepository → ConversationRepository
# БЫЛО:
from app.domain.repositories import SessionRepository
repo: SessionRepository = ...

# СТАНЕТ:
from app.domain.session_context.repositories.conversation_repository import ConversationRepository
repo: ConversationRepository = ...
```

#### 1.3 Обновление файлов

Я обновлю следующие файлы (примерный список):

- [`app/agents/orchestrator_agent.py`](../codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py)
- [`app/agents/coder_agent.py`](../codelab-ai-service/agent-runtime/app/agents/coder_agent.py)
- [`app/agents/architect_agent.py`](../codelab-ai-service/agent-runtime/app/agents/architect_agent.py)
- [`app/application/use_cases/*.py`](../codelab-ai-service/agent-runtime/app/application/use_cases/)
- [`app/api/routes/*.py`](../codelab-ai-service/agent-runtime/app/api/routes/)
- Все тесты в [`tests/`](../codelab-ai-service/agent-runtime/tests/)

#### 1.4 Удаление deprecated aliases

После замены всех использований, я удалю:

**Файл:** [`app/domain/entities/__init__.py`](../codelab-ai-service/agent-runtime/app/domain/entities/__init__.py)

```python
# УДАЛЮ весь блок:
def __getattr__(name):
    """Lazy loading для deprecated aliases."""
    if name == "Session":
        from ..session_context.entities.conversation import Conversation
        return Conversation
    elif name == "AgentContext":
        from ..agent_context.entities.agent import Agent
        return Agent
    elif name == "AgentSwitch":
        from ..agent_context.entities.agent import AgentSwitchRecord
        return AgentSwitchRecord
    # ... и т.д.
```

**Файл:** [`app/domain/repositories/__init__.py`](../codelab-ai-service/agent-runtime/app/domain/repositories/__init__.py)

```python
# УДАЛЮ алиасы:
from ..session_context.repositories.conversation_repository import ConversationRepository as SessionRepository
from ..agent_context.repositories.agent_repository import AgentRepository as AgentContextRepository
```

#### 1.5 Проверка и тестирование

```bash
# Проверю что код компилируется
cd codelab-ai-service/agent-runtime
python -m py_compile app/**/*.py

# Запущу тесты
pytest tests/unit/ -v
pytest tests/integration/ -v

# Проверю что не осталось deprecated импортов
! grep -r "from.*domain.entities import.*Session\|AgentContext\|AgentSwitch" --include="*.py" app/
```

### Критерии успеха:
- ✅ Все deprecated aliases заменены на прямые импорты
- ✅ Удален `__getattr__` из `domain/entities/__init__.py`
- ✅ Удалены алиасы из `domain/repositories/__init__.py`
- ✅ Все тесты проходят
- ✅ Код компилируется без ошибок

---

## Этап 2: Рефакторинг Global ApprovalManager

**Длительность:** 2-3 дня  
**Приоритет:** 🔴 Критический  
**Режим:** Автоматический рефакторинг с DI

### Что я буду делать:

#### 2.1 Анализ использования

Найду все места использования global singleton:

```bash
# Поиск импортов
grep -rn "from.*approval_management import approval_manager" --include="*.py" codelab-ai-service/agent-runtime/app/

# Поиск использования
grep -rn "approval_manager\." --include="*.py" codelab-ai-service/agent-runtime/app/

# Поиск в тестах
grep -rn "approval_manager" --include="*.py" codelab-ai-service/agent-runtime/tests/
```

#### 2.2 Рефакторинг FastAPI endpoints

Я обновлю все endpoints для использования DI:

**Пример рефакторинга:**

```python
# ФАЙЛ: app/api/routes/approvals.py

# БЫЛО:
from app.domain.services.approval_management import approval_manager

@router.post("/approvals")
async def create_approval(request: ApprovalRequest):
    approval = await approval_manager.create_approval(
        request_id=request.request_id,
        request_type=request.request_type,
        subject=request.subject,
        details=request.details,
    )
    return approval

# СТАНЕТ:
from app.domain.services.approval_management import ApprovalManager
from app.infrastructure.persistence.repositories.approval_repository import ApprovalRepositoryImpl
from app.infrastructure.persistence.database import get_db

async def get_approval_manager(
    db: AsyncSession = Depends(get_db)
) -> ApprovalManager:
    """Dependency provider for ApprovalManager."""
    from app.domain.services.approval_management import get_approval_manager_with_db
    repo = ApprovalRepositoryImpl(db)
    return get_approval_manager_with_db(repo)

@router.post("/approvals")
async def create_approval(
    request: ApprovalRequest,
    approval_manager: ApprovalManager = Depends(get_approval_manager)
):
    approval = await approval_manager.create_approval(
        request_id=request.request_id,
        request_type=request.request_type,
        subject=request.subject,
        details=request.details,
    )
    return approval
```

#### 2.3 Рефакторинг агентов

Я обновлю конструкторы агентов для использования DI:

**Пример рефакторинга:**

```python
# ФАЙЛ: app/agents/orchestrator_agent.py

# БЫЛО:
class OrchestratorAgent:
    def __init__(
        self,
        llm_client: LLMClient,
        session_service: ConversationManagementService,
        # ... другие зависимости
    ):
        self.llm_client = llm_client
        self.session_service = session_service
        # Импорт global singleton
        from app.domain.services.approval_management import approval_manager
        self.approval_manager = approval_manager
    
    async def request_approval(self, plan_id: str):
        await self.approval_manager.create_approval(...)

# СТАНЕТ:
class OrchestratorAgent:
    def __init__(
        self,
        llm_client: LLMClient,
        session_service: ConversationManagementService,
        approval_manager: ApprovalManager,  # Добавлен в конструктор
        # ... другие зависимости
    ):
        self.llm_client = llm_client
        self.session_service = session_service
        self.approval_manager = approval_manager  # Инжектируется через DI
    
    async def request_approval(self, plan_id: str):
        await self.approval_manager.create_approval(...)
```

#### 2.4 Обновление DI контейнера

Я проверю и обновлю DI конфигурацию:

**Файл:** [`app/core/di/approval_module.py`](../codelab-ai-service/agent-runtime/app/core/di/approval_module.py)

```python
from injector import Module, provider, singleton
from app.domain.services.approval_management import ApprovalManager, get_approval_manager_with_db
from app.domain.repositories.approval_repository import ApprovalRepository

class ApprovalModule(Module):
    @provider
    @singleton
    def provide_approval_manager(
        self,
        approval_repository: ApprovalRepository,
    ) -> ApprovalManager:
        """Provide ApprovalManager with injected repository."""
        return get_approval_manager_with_db(approval_repository)
```

#### 2.5 Удаление global singleton

После миграции всех зависимостей, я удалю:

**Файл:** [`app/domain/services/approval_management.py`](../codelab-ai-service/agent-runtime/app/domain/services/approval_management.py)

```python
# УДАЛЮ весь блок:

# DEPRECATED: Global singleton for backward compatibility
# This will be removed in future versions
_global_approval_manager: Optional[ApprovalManager] = None

def _get_global_approval_manager() -> ApprovalManager:
    """
    Get global approval manager (DEPRECATED).
    
    This creates a manager that manages its own DB sessions.
    Use get_approval_manager_with_db() with dependency injection instead.
    """
    global _global_approval_manager
    if _global_approval_manager is None:
        from app.infrastructure.persistence.repositories.self_managed_repository import (
            SelfManagedApprovalRepository,
        )
        repo = SelfManagedApprovalRepository()
        _global_approval_manager = get_approval_manager_with_db(repo)
    return _global_approval_manager

# Global instance (DEPRECATED - use dependency injection instead)
approval_manager = _get_global_approval_manager()
```

#### 2.6 Удаление SelfManagedRepository

**Файл:** [`app/infrastructure/persistence/repositories/self_managed_repository.py`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/repositories/self_managed_repository.py)

Я удалю весь файл, если он используется только для global singleton.

#### 2.7 Обновление тестов

Я обновлю все тесты для использования DI вместо global singleton:

```python
# БЫЛО:
def test_approval_creation():
    from app.domain.services.approval_management import approval_manager
    approval = await approval_manager.create_approval(...)

# СТАНЕТ:
@pytest.fixture
def approval_manager(db_session):
    repo = ApprovalRepositoryImpl(db_session)
    return get_approval_manager_with_db(repo)

def test_approval_creation(approval_manager):
    approval = await approval_manager.create_approval(...)
```

#### 2.8 Проверка и тестирование

```bash
# Запущу все тесты
pytest tests/unit/domain/services/test_approval_management.py -v
pytest tests/integration/test_approval_flow.py -v
pytest tests/e2e/test_hitl_workflow.py -v

# Проверю что не осталось использования singleton
! grep -r "from.*approval_management import approval_manager" --include="*.py" app/
! grep -r "_get_global_approval_manager" --include="*.py" app/
```

### Критерии успеха:
- ✅ Удален global singleton `approval_manager`
- ✅ Все зависимости используют DI
- ✅ Удален `SelfManagedRepository`
- ✅ Обновлены все endpoints, агенты, use cases
- ✅ Обновлены все тесты
- ✅ Все тесты проходят
- ✅ HITL workflow работает корректно

---

## Этап 3: Рефакторинг ExecutionEngine → PlanExecutionService

**Длительность:** 3-5 дней  
**Приоритет:** 🔴 Критический  
**Режим:** Автоматический рефакторинг с адаптером

### Что я буду делать:

#### 3.1 Анализ использования

Найду все места использования ExecutionEngine:

```bash
# Поиск импортов
grep -rn "from.*execution_engine import ExecutionEngine" --include="*.py" codelab-ai-service/agent-runtime/app/

# Поиск в DI
grep -rn "ExecutionEngine" --include="*.py" codelab-ai-service/agent-runtime/app/core/di/

# Поиск в агентах
grep -rn "execution_engine" --include="*.py" codelab-ai-service/agent-runtime/app/agents/

# Поиск в use cases
grep -rn "ExecutionEngine" --include="*.py" codelab-ai-service/agent-runtime/app/application/
```

#### 3.2 Создание mapping таблицы API

Я создам таблицу соответствия методов:

| ExecutionEngine (Legacy) | PlanExecutionService (New) | Изменения |
|--------------------------|----------------------------|-----------|
| `execute_plan(plan_id)` | `execute_plan(plan_id, context)` | Добавлен execution context |
| `pause_execution(plan_id)` | `pause_plan(plan_id)` | Переименован метод |
| `resume_execution(plan_id)` | `resume_plan(plan_id)` | Переименован метод |
| `cancel_execution(plan_id)` | `cancel_plan(plan_id)` | Переименован метод |
| `get_execution_status(plan_id)` | `get_plan_status(plan_id)` | Переименован метод |
| `get_current_step(plan_id)` | `get_current_step(plan_id)` | Без изменений |

#### 3.3 Рефакторинг агентов

Я обновлю агенты для использования PlanExecutionService:

**Пример рефакторинга:**

```python
# ФАЙЛ: app/agents/orchestrator_agent.py

# БЫЛО:
from app.domain.services.execution_engine import ExecutionEngine

class OrchestratorAgent:
    def __init__(
        self,
        execution_engine: ExecutionEngine,
        # ... другие зависимости
    ):
        self.execution_engine = execution_engine
    
    async def execute_plan(self, plan_id: str):
        result = await self.execution_engine.execute_plan(plan_id)
        return result
    
    async def pause_plan(self, plan_id: str):
        await self.execution_engine.pause_execution(plan_id)

# СТАНЕТ:
from app.domain.execution_context.services.plan_execution_service import PlanExecutionService
from app.domain.execution_context.value_objects.execution_context import ExecutionContext

class OrchestratorAgent:
    def __init__(
        self,
        plan_execution_service: PlanExecutionService,
        # ... другие зависимости
    ):
        self.plan_execution_service = plan_execution_service
    
    async def execute_plan(self, plan_id: str):
        # Создать execution context
        context = ExecutionContext(
            conversation_id=self.conversation_id,
            agent_id=self.agent_id,
            user_id=self.user_id,
        )
        result = await self.plan_execution_service.execute_plan(plan_id, context)
        return result
    
    async def pause_plan(self, plan_id: str):
        await self.plan_execution_service.pause_plan(plan_id)
```

#### 3.4 Рефакторинг use cases

Я обновлю все use cases:

**Пример рефакторинга:**

```python
# ФАЙЛ: app/application/use_cases/execute_plan_use_case.py

# БЫЛО:
from app.domain.services.execution_engine import ExecutionEngine

class ExecutePlanUseCase:
    def __init__(self, execution_engine: ExecutionEngine):
        self.execution_engine = execution_engine
    
    async def execute(self, plan_id: str) -> ExecutionResult:
        return await self.execution_engine.execute_plan(plan_id)

# СТАНЕТ:
from app.domain.execution_context.services.plan_execution_service import PlanExecutionService
from app.domain.execution_context.value_objects.execution_context import ExecutionContext

class ExecutePlanUseCase:
    def __init__(self, plan_execution_service: PlanExecutionService):
        self.plan_execution_service = plan_execution_service
    
    async def execute(
        self, 
        plan_id: str, 
        context: ExecutionContext
    ) -> ExecutionResult:
        return await self.plan_execution_service.execute_plan(plan_id, context)
```

#### 3.5 Обновление DI контейнера

Я обновлю DI конфигурацию:

**Файл:** [`app/core/di/execution_module.py`](../codelab-ai-service/agent-runtime/app/core/di/execution_module.py)

```python
# УДАЛЮ:
@provider
def provide_execution_engine(
    self,
    plan_repository: PlanRepository,
    session_service: ConversationManagementService,
    approval_manager: ApprovalManager,
) -> ExecutionEngine:
    """
    Предоставить legacy ExecutionEngine.
    
    DEPRECATED: Use PlanExecutionService instead.
    """
    return ExecutionEngine(
        plan_repository=plan_repository,
        session_service=session_service,
        approval_manager=approval_manager,
    )

# Оставлю только:
@provider
def provide_plan_execution_service(
    self,
    execution_plan_repository: ExecutionPlanRepository,
    # ... другие зависимости
) -> PlanExecutionService:
    """Provide PlanExecutionService."""
    return PlanExecutionService(
        execution_plan_repository=execution_plan_repository,
        # ... другие зависимости
    )
```

#### 3.6 Удаление legacy ExecutionEngine

После миграции всех зависимостей, я удалю:

**Файл:** [`app/domain/services/execution_engine.py`](../codelab-ai-service/agent-runtime/app/domain/services/execution_engine.py)

Я удалю весь файл.

#### 3.7 Обновление тестов

Я обновлю все тесты:

```python
# БЫЛО:
@pytest.fixture
def execution_engine(plan_repository, session_service, approval_manager):
    return ExecutionEngine(
        plan_repository=plan_repository,
        session_service=session_service,
        approval_manager=approval_manager,
    )

def test_execute_plan(execution_engine):
    result = await execution_engine.execute_plan(plan_id)

# СТАНЕТ:
@pytest.fixture
def plan_execution_service(execution_plan_repository, ...):
    return PlanExecutionService(
        execution_plan_repository=execution_plan_repository,
        ...
    )

def test_execute_plan(plan_execution_service):
    context = ExecutionContext(...)
    result = await plan_execution_service.execute_plan(plan_id, context)
```

#### 3.8 Проверка и тестирование

```bash
# Запущу все тесты
pytest tests/unit/domain/services/test_plan_execution_service.py -v
pytest tests/integration/test_plan_execution.py -v
pytest tests/e2e/test_full_plan_execution.py -v

# Проверю что не осталось использования ExecutionEngine
! grep -r "from.*execution_engine import ExecutionEngine" --include="*.py" app/
! grep -r "ExecutionEngine" --include="*.py" app/core/di/
```

### Критерии успеха:
- ✅ Удален legacy ExecutionEngine
- ✅ Все агенты используют PlanExecutionService
- ✅ Все use cases обновлены
- ✅ Обновлен DI контейнер
- ✅ Обновлены все тесты
- ✅ Все тесты проходят
- ✅ План execution работает корректно

---

## Этап 4: Финальная очистка

**Длительность:** 1-2 дня  
**Приоритет:** 🟡 Средний  
**Режим:** Автоматическая очистка

### Что я буду делать:

#### 4.1 Удаление deprecated методов

Я удалю устаревшие методы:

**Файл:** [`app/agents/orchestrator_agent.py`](../codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py)

```python
# УДАЛЮ:
async def classify_task_with_llm(self, message: str) -> tuple[AgentType, Dict[str, Any]]:
    """
    Legacy method - redirects to Planning System classifier.
    
    Kept for backward compatibility. New code should use
    _classify_with_planning_system() directly.
    """
    logger.warning(
        "classify_task_with_llm() is deprecated. "
        "Use _classify_with_planning_system() instead."
    )
    return await self._classify_with_planning_system(message)
```

#### 4.2 Очистка импортов

Я выполню автоматическую очистку:

```bash
cd codelab-ai-service/agent-runtime

# Удалю неиспользуемые импорты
autoflake --remove-all-unused-imports --recursive --in-place app/

# Отсортирую импорты
isort app/

# Форматирование кода
black app/
```

#### 4.3 Финальная проверка legacy кода

```bash
# Проверю оставшиеся упоминания
grep -r "DEPRECATED\|deprecated\|backward compatibility\|legacy" --include="*.py" codelab-ai-service/agent-runtime/app/ > legacy_final_check.txt

# Проанализирую результаты
cat legacy_final_check.txt
```

**Ожидаемые оставшиеся упоминания:**
- Legacy DB поля в `hitl.py` (для API совместимости) ✅
- Legacy OpenAI parser в `tool_parser.py` (для LLM совместимости) ✅

#### 4.4 Запуск полного test suite

```bash
cd codelab-ai-service/agent-runtime

# Все тесты
pytest tests/ -v --cov=app --cov-report=html --cov-report=term

# Проверка покрытия
open htmlcov/index.html
```

### Критерии успеха:
- ✅ Удалены все deprecated методы
- ✅ Очищены импорты
- ✅ Отформатирован код
- ✅ Осталось только необходимое legacy (DB поля, LLM parsers)
- ✅ Все тесты проходят с покрытием >80%

---

## Этап 5: Документация

**Длительность:** 1 день  
**Приоритет:** 🟡 Средний  
**Режим:** Создание документации

### Что я буду делать:

#### 5.1 Создание Migration Guide

Я создам файл [`doc/LEGACY_TO_DDD_MIGRATION_GUIDE.md`](./LEGACY_TO_DDD_MIGRATION_GUIDE.md):

```markdown
# Migration Guide: Legacy → DDD Architecture

## Deprecated Aliases

### Session → Conversation
```python
# OLD:
from app.domain.entities import Session
session: Session = ...

# NEW:
from app.domain.session_context.entities.conversation import Conversation
session: Conversation = ...
```

### AgentContext → Agent
```python
# OLD:
from app.domain.entities import AgentContext
agent: AgentContext = ...

# NEW:
from app.domain.agent_context.entities.agent import Agent
agent: Agent = ...
```

## Global Singleton → Dependency Injection

### ApprovalManager
```python
# OLD:
from app.domain.services.approval_management import approval_manager
result = await approval_manager.create_approval(...)

# NEW (FastAPI):
async def get_approval_manager(db: AsyncSession = Depends(get_db)) -> ApprovalManager:
    repo = ApprovalRepositoryImpl(db)
    return get_approval_manager_with_db(repo)

@router.post("/approvals")
async def create_approval(
    approval_manager: ApprovalManager = Depends(get_approval_manager)
):
    result = await approval_manager.create_approval(...)

# NEW (Agent with DI):
class MyAgent:
    def __init__(self, approval_manager: ApprovalManager):
        self.approval_manager = approval_manager
```

## ExecutionEngine → PlanExecutionService

```python
# OLD:
execution_engine.execute_plan(plan_id)

# NEW:
context = ExecutionContext(
    conversation_id=conversation_id,
    agent_id=agent_id,
    user_id=user_id,
)
plan_execution_service.execute_plan(plan_id, context)
```

## Method Renames

| Old Method | New Method |
|------------|------------|
| `pause_execution(plan_id)` | `pause_plan(plan_id)` |
| `resume_execution(plan_id)` | `resume_plan(plan_id)` |
| `cancel_execution(plan_id)` | `cancel_plan(plan_id)` |
| `get_execution_status(plan_id)` | `get_plan_status(plan_id)` |
```

#### 5.2 Обновление CHANGELOG

Я обновлю [`CHANGELOG.md`](../codelab-ai-service/agent-runtime/CHANGELOG.md):

```markdown
# Changelog

## [Phase 10.5] - 2026-02-09

### Removed (Breaking Changes)

#### Deprecated Aliases
- `Session` → use `Conversation` from `domain.session_context.entities.conversation`
- `AgentContext` → use `Agent` from `domain.agent_context.entities.agent`
- `AgentSwitch` → use `AgentSwitchRecord` from `domain.agent_context.entities.agent`
- `SessionRepository` → use `ConversationRepository` from `domain.session_context.repositories`
- `AgentContextRepository` → use `AgentRepository` from `domain.agent_context.repositories`

#### Global Singletons
- `approval_manager` global instance removed
- Use dependency injection with `ApprovalManager` instead
- `SelfManagedRepository` removed

#### Legacy Services
- `ExecutionEngine` removed → use `PlanExecutionService` from `domain.execution_context.services`
- Methods renamed:
  - `pause_execution()` → `pause_plan()`
  - `resume_execution()` → `resume_plan()`
  - `cancel_execution()` → `cancel_plan()`
  - `get_execution_status()` → `get_plan_status()`

#### Deprecated Methods
- `OrchestratorAgent.classify_task_with_llm()` removed
- Use `_classify_with_planning_system()` instead

### Migration

See [LEGACY_TO_DDD_MIGRATION_GUIDE.md](./doc/LEGACY_TO_DDD_MIGRATION_GUIDE.md) for detailed migration instructions.

### Kept for Compatibility

- Legacy database fields (`call_id`, `tool_name`, `arguments` in approvals table) - kept for API backward compatibility
- Legacy OpenAI `function_call` parser - kept for LLM compatibility

### Architecture

- ✅ 100% DDD compliance
- ✅ Full dependency injection
- ✅ Clean architecture boundaries
- ✅ Event-driven design
```

#### 5.3 Обновление README

Я обновлю основную документацию, удалив упоминания legacy компонентов.

### Критерии успеха:
- ✅ Создан Migration Guide
- ✅ Обновлен CHANGELOG
- ✅ Обновлен README
- ✅ Документация актуальна

---

## Общий чеклист выполнения

### Этап 1: Deprecated Aliases ⚠️
- [ ] Проанализировать использование deprecated aliases
- [ ] Заменить все импорты Session → Conversation
- [ ] Заменить все импорты AgentContext → Agent
- [ ] Заменить все импорты AgentSwitch → AgentSwitchRecord
- [ ] Заменить все импорты SessionRepository → ConversationRepository
- [ ] Обновить все type hints
- [ ] Удалить `__getattr__` из `domain/entities/__init__.py`
- [ ] Удалить алиасы из `domain/repositories/__init__.py`
- [ ] Обновить тесты
- [ ] Запустить тесты - все проходят

### Этап 2: Global ApprovalManager 🔴
- [ ] Проанализировать использование global singleton
- [ ] Обновить все FastAPI endpoints на DI
- [ ] Обновить все агенты на DI
- [ ] Обновить все use cases на DI
- [ ] Проверить DI контейнер
- [ ] Удалить global singleton из `approval_management.py`
- [ ] Удалить `SelfManagedRepository`
- [ ] Обновить тесты
- [ ] Запустить тесты - все проходят

### Этап 3: ExecutionEngine 🔴
- [ ] Проанализировать использование ExecutionEngine
- [ ] Создать mapping таблицу API
- [ ] Обновить все агенты на PlanExecutionService
- [ ] Обновить все use cases
- [ ] Обновить DI контейнер
- [ ] Удалить `execution_engine.py`
- [ ] Обновить тесты
- [ ] Запустить тесты - все проходят

### Этап 4: Финальная очистка 🟡
- [ ] Удалить deprecated методы
- [ ] Очистить импорты (autoflake)
- [ ] Отсортировать импорты (isort)
- [ ] Отформатировать код (black)
- [ ] Финальная проверка legacy кода
- [ ] Запустить полный test suite с покрытием

### Этап 5: Документация 📝
- [ ] Создать Migration Guide
- [ ] Обновить CHANGELOG
- [ ] Обновить README
- [ ] Проверить актуальность документации

---

## Метрики успеха

### Количественные:
- ✅ **0** использований deprecated aliases
- ✅ **0** использований global singleton
- ✅ **0** использований ExecutionEngine
- ✅ **>80%** покрытие тестами
- ✅ **<5** упоминаний legacy в коде (только необходимые)

### Качественные:
- ✅ Код соответствует DDD принципам
- ✅ Все зависимости через DI
- ✅ Чистая архитектура без legacy
- ✅ Документация актуальна
- ✅ Migration guide создан

---

## Риски и митигация

### Риск 1: Поломка существующего кода
**Вероятность:** Средняя  
**Влияние:** Высокое

**Митигация:**
- Тщательное тестирование после каждого этапа
- Использование feature branch
- Постепенный рефакторинг
- Проверка компиляции после каждого изменения

### Риск 2: Пропущенные зависимости
**Вероятность:** Средняя  
**Влияние:** Среднее

**Митигация:**
- Автоматический поиск через grep
- Проверка всех импортов
- Статический анализ кода
- Запуск тестов после каждого этапа

### Риск 3: Регрессия в тестах
**Вероятность:** Средняя  
**Влияние:** Среднее

**Митигация:**
- Запуск полного test suite после каждого этапа
- Integration и E2E тесты
- Проверка покрытия кода
- Manual testing критических сценариев

---

## Команды для выполнения

```bash
# 1. Создать feature branch
git checkout -b feature/phase-10-5-legacy-cleanup-execution

# 2. Анализ deprecated aliases
grep -rn "from.*domain.entities import.*Session\|AgentContext\|AgentSwitch" --include="*.py" codelab-ai-service/agent-runtime/app/

# 3. Анализ Global ApprovalManager
grep -rn "from.*approval_management import approval_manager" --include="*.py" codelab-ai-service/agent-runtime/app/

# 4. Анализ ExecutionEngine
grep -rn "from.*execution_engine import ExecutionEngine" --include="*.py" codelab-ai-service/agent-runtime/app/

# 5. После каждого этапа - тесты
cd codelab-ai-service/agent-runtime
pytest tests/ -v

# 6. Финальная проверка legacy
grep -r "DEPRECATED\|deprecated" --include="*.py" app/ | wc -l

# 7. Финальные тесты с покрытием
pytest tests/ -v --cov=app --cov-report=html
```

---

## Следующие шаги после завершения

1. **Code Review** - детальный review всех изменений
2. **Staging Deployment** - развернуть на staging
3. **Performance Testing** - проверить производительность
4. **Production Deployment** - постепенный rollout
5. **Monitoring** - мониторинг метрик и ошибок
6. **Retrospective** - анализ процесса миграции

---

## Ссылки

### Документация:
- [Legacy Code Analysis](./AGENT_RUNTIME_LEGACY_CODE_ANALYSIS.md)
- [Phase 10 Progress](./PHASE_10_PROGRESS_DASHBOARD.md)
- [DDD Architecture](./agent-runtime-clean-architecture-audit.md)

### Код для рефакторинга:
- [`app/domain/entities/__init__.py`](../codelab-ai-service/agent-runtime/app/domain/entities/__init__.py) - Deprecated aliases
- [`app/domain/repositories/__init__.py`](../codelab-ai-service/agent-runtime/app/domain/repositories/__init__.py) - Repository aliases
- [`app/domain/services/approval_management.py`](../codelab-ai-service/agent-runtime/app/domain/services/approval_management.py) - Global singleton
- [`app/domain/services/execution_engine.py`](../codelab-ai-service/agent-runtime/app/domain/services/execution_engine.py) - Legacy ExecutionEngine
- [`app/agents/orchestrator_agent.py`](../codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py) - Deprecated methods

---

**Автор:** Roo Code AI  
**Дата:** 2026-02-09  
**Версия:** 1.0  
**Статус:** 🚀 Готов к выполнению  
**Режим:** Автоматический рефакторинг
