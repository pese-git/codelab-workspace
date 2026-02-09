# Migration Guide: Legacy Code Cleanup

**Версия:** Phase 10.5  
**Дата:** 2026-02-09  
**Статус:** Частично завершено (80%)

---

## 📋 Обзор

Этот guide поможет разработчикам мигрировать код с legacy компонентов на новую DDD архитектуру после Phase 10.5 Legacy Cleanup.

---

## 🔄 Миграция Plan Entity

### ❌ Legacy (УДАЛЕНО)

```python
from app.domain.entities.plan import Plan, Subtask, PlanStatus, SubtaskStatus

# Создание плана
plan = Plan(
    id="plan-123",
    session_id="session-456",
    goal="Create widget"
)

# Создание подзадачи
subtask = Subtask(
    id="st-1",
    description="Implement feature",
    agent=AgentType.CODER,
    dependencies=["st-0"]
)

# Проверка статуса
if plan.status == PlanStatus.APPROVED:
    print("Plan approved")

if subtask.status == SubtaskStatus.DONE:
    print("Subtask completed")
```

### ✅ New DDD

```python
from app.domain.execution_context.entities.execution_plan import ExecutionPlan
from app.domain.execution_context.entities.subtask import Subtask
from app.domain.execution_context.value_objects import (
    PlanId,
    SubtaskId,
    PlanStatus,
    SubtaskStatus
)
from app.domain.session_context.value_objects import ConversationId
from app.domain.agent_context.value_objects import AgentId

# Создание плана с Value Objects
plan = ExecutionPlan(
    id=PlanId("plan-123"),
    conversation_id=ConversationId("session-456"),
    goal="Create widget"
)

# Создание подзадачи с Value Objects
subtask = Subtask(
    id=SubtaskId("st-1"),
    description="Implement feature",
    agent_id=AgentId("coder"),
    dependencies=[SubtaskId("st-0")]
)

# Проверка статуса через методы
if plan.status.is_approved():
    print("Plan approved")

if subtask.status.is_done():
    print("Subtask completed")
```

### Ключевые изменения

| Legacy | New DDD | Тип |
|--------|---------|-----|
| `Plan` | `ExecutionPlan` | Entity |
| `plan.id: str` | `plan.id: PlanId` | Value Object |
| `plan.session_id: str` | `plan.conversation_id: ConversationId` | Value Object |
| `subtask.agent: AgentType` | `subtask.agent_id: AgentId` | Value Object |
| `subtask.dependencies: List[str]` | `subtask.dependencies: List[SubtaskId]` | Value Objects |
| `status == PlanStatus.APPROVED` | `status.is_approved()` | Метод |
| `status == SubtaskStatus.DONE` | `status.is_done()` | Метод |

---

## 🔄 Миграция Repository Aliases

### ❌ Legacy (УДАЛЕНО)

```python
# Infrastructure layer
from app.infrastructure.persistence.repositories import (
    SessionRepositoryImpl,
    AgentContextRepositoryImpl
)

# Domain layer
from app.domain.repositories import (
    SessionRepository,
    AgentContextRepository,
    PlanRepository
)
```

### ✅ New DDD

```python
# Infrastructure layer
from app.infrastructure.persistence.repositories import (
    ConversationRepositoryImpl,
    AgentRepositoryImpl
)

# Domain layer - импортируйте напрямую из контекстов
from app.domain.session_context.repositories import ConversationRepository
from app.domain.agent_context.repositories import AgentRepository
from app.domain.execution_context.repositories import ExecutionPlanRepository
```

### Таблица миграции

| Legacy Alias | New DDD Repository | Import Path |
|--------------|-------------------|-------------|
| `SessionRepository` | `ConversationRepository` | `app.domain.session_context.repositories` |
| `SessionRepositoryImpl` | `ConversationRepositoryImpl` | `app.infrastructure.persistence.repositories` |
| `AgentContextRepository` | `AgentRepository` | `app.domain.agent_context.repositories` |
| `AgentContextRepositoryImpl` | `AgentRepositoryImpl` | `app.infrastructure.persistence.repositories` |
| `PlanRepository` | `ExecutionPlanRepository` | `app.domain.execution_context.repositories` |

---

## 🔄 Миграция ApprovalManager в API

### ❌ Legacy

```python
@router.get("/approvals")
async def get_approvals(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    # Создание ApprovalManager вручную
    from app.infrastructure.persistence.repositories.approval_repository_impl import ApprovalRepositoryImpl
    from app.domain.services.approval_management import ApprovalManager
    from app.domain.entities.approval import ApprovalPolicy
    
    approval_repo = ApprovalRepositoryImpl(db)
    approval_manager = ApprovalManager(
        approval_repository=approval_repo,
        approval_policy=ApprovalPolicy.default()
    )
    
    return await approval_manager.get_all_pending(session_id)
```

### ✅ New DDD

```python
# Добавить dependency function в router
async def get_approval_manager(
    db: AsyncSession = Depends(get_db)
):
    """Dependency для ApprovalManager."""
    from app.infrastructure.persistence.repositories.approval_repository_impl import ApprovalRepositoryImpl
    from app.domain.services.approval_management import ApprovalManager
    from app.domain.entities.approval import ApprovalPolicy
    
    approval_repo = ApprovalRepositoryImpl(db)
    return ApprovalManager(
        approval_repository=approval_repo,
        approval_policy=ApprovalPolicy.default()
    )

# Использовать в endpoint
@router.get("/approvals")
async def get_approvals(
    session_id: str,
    approval_manager = Depends(get_approval_manager)
):
    return await approval_manager.get_all_pending(session_id)
```

---

## 🔄 Работа с Value Objects

### Создание Value Objects

```python
from app.domain.execution_context.value_objects import PlanId, SubtaskId
from app.domain.session_context.value_objects import ConversationId
from app.domain.agent_context.value_objects import AgentId

# Создание из строки
plan_id = PlanId("plan-123")
subtask_id = SubtaskId("st-456")
conversation_id = ConversationId("conv-789")
agent_id = AgentId("coder")

# Получение значения
print(plan_id.value)  # "plan-123"
```

### Сравнение Value Objects

```python
# Правильно - сравнение объектов
if subtask.id == SubtaskId("st-1"):
    print("Match!")

# Правильно - сравнение значений
if subtask.id.value == "st-1":
    print("Match!")

# НЕПРАВИЛЬНО - нельзя сравнивать с строкой напрямую
if subtask.id == "st-1":  # ❌ TypeError
    print("This won't work")
```

### Работа со списками Value Objects

```python
# Создание списка зависимостей
dependencies = [SubtaskId("st-0"), SubtaskId("st-1")]

# Извлечение значений для JSON
dep_values = [dep.value for dep in dependencies]
# ["st-0", "st-1"]

# Проверка наличия
if SubtaskId("st-0") in dependencies:
    print("Found!")

# Сравнение значений
completed_ids = {st.id.value for st in subtasks}
if dep.value in completed_ids:
    print("Dependency completed")
```

---

## 🔄 Работа со статусами

### Legacy Enum

```python
from app.domain.entities.plan import PlanStatus, SubtaskStatus

# Сравнение
if plan.status == PlanStatus.APPROVED:
    pass

if subtask.status == SubtaskStatus.DONE:
    pass

# Получение значения
status_str = plan.status.value  # "approved"
```

### New Value Objects

```python
from app.domain.execution_context.value_objects import PlanStatus, SubtaskStatus

# Создание
status = PlanStatus.approved()
status = SubtaskStatus.done()

# Проверка через методы
if plan.status.is_approved():
    pass

if subtask.status.is_done():
    pass

if subtask.status.is_pending():
    pass

if subtask.status.is_running():
    pass

if subtask.status.is_failed():
    pass

# Получение значения
status_str = plan.status.value  # "approved"

# Создание из строки
status = PlanStatus.from_string("approved")
status = SubtaskStatus.from_string("done")
```

---

## 🔄 Обновление Mappers

### Legacy Mapper

```python
# to_domain
plan = Plan(
    id=plan_model.id,
    session_id=plan_model.session_id,
    status=PlanStatus(plan_model.status)
)

# to_persistence
plan_model = PlanModel(
    id=plan.id,
    session_id=plan.session_id,
    status=plan.status.value
)
```

### New DDD Mapper

```python
# to_domain - создаем Value Objects
plan = ExecutionPlan(
    id=PlanId(plan_model.id),
    conversation_id=ConversationId(plan_model.session_id),
    status=PlanStatus.from_string(plan_model.status)
)

# to_persistence - извлекаем значения
plan_model = PlanModel(
    id=plan.id.value,
    session_id=plan.conversation_id.value,
    status=plan.status.value
)
```

---

## 🔄 Обновление тестов

### Legacy Tests

```python
from app.domain.entities.plan import Plan, Subtask, PlanStatus

def test_plan_creation():
    plan = Plan(
        id="plan-1",
        session_id="session-1",
        goal="Test"
    )
    assert plan.status == PlanStatus.DRAFT
```

### New DDD Tests

```python
from app.domain.execution_context.entities.execution_plan import ExecutionPlan
from app.domain.execution_context.value_objects import PlanId, PlanStatus
from app.domain.session_context.value_objects import ConversationId

def test_plan_creation():
    plan = ExecutionPlan(
        id=PlanId("plan-1"),
        conversation_id=ConversationId("session-1"),
        goal="Test"
    )
    assert plan.status.is_draft()
```

---

## ⚠️ Частые ошибки

### 1. Сравнение Value Object со строкой

```python
# ❌ НЕПРАВИЛЬНО
if plan.id == "plan-123":
    pass

# ✅ ПРАВИЛЬНО
if plan.id == PlanId("plan-123"):
    pass

# ✅ ИЛИ
if plan.id.value == "plan-123":
    pass
```

### 2. Забыли обернуть в Value Object

```python
# ❌ НЕПРАВИЛЬНО
plan = ExecutionPlan(
    id="plan-123",  # TypeError!
    conversation_id="session-456",
    goal="Test"
)

# ✅ ПРАВИЛЬНО
plan = ExecutionPlan(
    id=PlanId("plan-123"),
    conversation_id=ConversationId("session-456"),
    goal="Test"
)
```

### 3. Неправильное извлечение значений для БД

```python
# ❌ НЕПРАВИЛЬНО
plan_model = PlanModel(
    id=plan.id,  # Сохранит объект, а не строку!
    session_id=plan.conversation_id
)

# ✅ ПРАВИЛЬНО
plan_model = PlanModel(
    id=plan.id.value,
    session_id=plan.conversation_id.value
)
```

### 4. Сравнение статусов через ==

```python
# ⚠️ РАБОТАЕТ, но не рекомендуется
if plan.status == PlanStatus.approved():
    pass

# ✅ ЛУЧШЕ - использовать методы
if plan.status.is_approved():
    pass
```

---

## 🛠️ Инструменты для миграции

### Поиск legacy импортов

```bash
# Найти все импорты legacy Plan
grep -rn "from app.domain.entities.plan import" --include="*.py" app/

# Найти deprecated aliases
grep -rn "SessionRepository\|AgentContextRepository" --include="*.py" app/

# Проверить компиляцию
uv run python -m py_compile app/**/*.py
```

### Автоматическая замена (с осторожностью!)

```bash
# Заменить импорты (проверьте результат!)
find app/ -name "*.py" -exec sed -i '' 's/from app.domain.entities.plan import Plan/from app.domain.execution_context.entities.execution_plan import ExecutionPlan/g' {} +

# Заменить использование
find app/ -name "*.py" -exec sed -i '' 's/plan.session_id/plan.conversation_id.value/g' {} +
```

**⚠️ ВНИМАНИЕ:** Автоматическая замена может сломать код! Всегда проверяйте результат вручную.

---

## 📚 Дополнительные ресурсы

### Документация

- [AGENT_RUNTIME_LEGACY_CODE_ANALYSIS.md](./AGENT_RUNTIME_LEGACY_CODE_ANALYSIS.md) - полный анализ legacy кода
- [AGENT_RUNTIME_LEGACY_CLEANUP_EXECUTION_PLAN.md](./AGENT_RUNTIME_LEGACY_CLEANUP_EXECUTION_PLAN.md) - план рефакторинга
- [AGENT_RUNTIME_PHASE_10_5_STAGE_0_COMPLETION.md](./AGENT_RUNTIME_PHASE_10_5_STAGE_0_COMPLETION.md) - отчет о миграции Plan
- [AGENT_RUNTIME_PHASE_10_5_PROGRESS_REPORT.md](./AGENT_RUNTIME_PHASE_10_5_PROGRESS_REPORT.md) - общий прогресс

### Примеры кода

- [`architect_agent.py`](../codelab-ai-service/agent-runtime/app/agents/architect_agent.py) - использование ExecutionPlan
- [`plan_mapper.py`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/mappers/plan_mapper.py) - маппинг с Value Objects
- [`dependency_resolver.py`](../codelab-ai-service/agent-runtime/app/domain/services/dependency_resolver.py) - работа с Value Objects

---

## ❓ FAQ

### Q: Почему Value Objects вместо строк?

**A:** Value Objects обеспечивают:
- **Type Safety** - невозможно перепутать ID разных сущностей
- **Validation** - автоматическая проверка в конструкторе
- **Domain Logic** - методы инкапсулируют бизнес-логику
- **Immutability** - предотвращает случайные изменения

### Q: Как работать с Value Objects в JSON?

**A:** Используйте `.value` для сериализации:

```python
# Сериализация
data = {
    "plan_id": plan.id.value,
    "conversation_id": plan.conversation_id.value
}

# Десериализация
plan_id = PlanId(data["plan_id"])
conversation_id = ConversationId(data["conversation_id"])
```

### Q: Что делать с существующими данными в БД?

**A:** Ничего! Mapper автоматически конвертирует:
- БД хранит строки (как раньше)
- Mapper создает Value Objects при чтении
- Mapper извлекает значения при записи

### Q: Можно ли использовать legacy импорты?

**A:** НЕТ! Legacy файл `plan.py` удален. Используйте новые импорты из `execution_context`.

### Q: Что делать с ExecutionEngine?

**A:** ExecutionEngine пока остается (используется в ExecutionCoordinator). Миграция на `PlanExecutionService` будет выполнена в отдельной задаче.

---

## ✅ Checklist для миграции

При миграции вашего кода проверьте:

- [ ] Заменили `Plan` на `ExecutionPlan`
- [ ] Заменили `Subtask` на новый `Subtask` из `execution_context`
- [ ] Обернули ID в Value Objects (`PlanId`, `SubtaskId`, etc.)
- [ ] Заменили `session_id` на `conversation_id`
- [ ] Заменили `agent` на `agent_id`
- [ ] Используете методы статуса (`is_approved()`, `is_done()`)
- [ ] Обновили импорты на новые пути
- [ ] Обновили тесты
- [ ] Проверили компиляцию
- [ ] Запустили тесты

---

## 🎯 Преимущества новой архитектуры

### Type Safety

```python
# Legacy - можно перепутать ID
plan_id = "st-123"  # Это subtask ID, а не plan ID!
plan = await repo.find_by_id(plan_id)  # Ошибка не обнаружится

# New DDD - компилятор поймает ошибку
plan_id = SubtaskId("st-123")  # Type: SubtaskId
plan = await repo.find_by_id(plan_id)  # TypeError: expected PlanId, got SubtaskId
```

### Domain Logic

```python
# Legacy - логика размазана по коду
if plan.status == PlanStatus.APPROVED or plan.status == PlanStatus.IN_PROGRESS:
    can_execute = True

# New DDD - логика инкапсулирована
if plan.status.can_execute():
    can_execute = True
```

### Validation

```python
# Legacy - нужна ручная валидация
if not plan_id or len(plan_id) == 0:
    raise ValueError("Invalid plan ID")

# New DDD - автоматическая валидация
plan_id = PlanId("")  # ValueError: PlanId cannot be empty
```

---

## 📞 Поддержка

Если у вас возникли вопросы или проблемы при миграции:

1. Проверьте примеры в мигрированных файлах
2. Изучите тесты для понимания API
3. Обратитесь к документации DDD архитектуры
4. Создайте issue с описанием проблемы

---

**Последнее обновление:** 2026-02-09  
**Версия:** Phase 10.5  
**Статус миграции:** 80% завершено
