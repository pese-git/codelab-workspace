# 🚀 Фаза 10.5: Отчет о готовности к миграции

**Дата:** 6 февраля 2026, 00:21 MSK  
**Статус:** ✅ Готов к выполнению  
**Ветка:** `feature/phase-10-5-legacy-cleanup`  
**Baseline тесты:** 2 ошибки импорта (ожидаемо)

---

## 📊 Текущее состояние

### Этап 1: Подготовка ✅ ЗАВЕРШЕН

- ✅ Создана ветка `feature/phase-10-5-legacy-cleanup`
- ✅ Закоммичены изменения Фазы 10.4
- ✅ Запущены baseline тесты через `uv run pytest`
- ✅ Обнаружено 2 ошибки импорта (ожидаемо):
  - `test_plan_mapper_updates.py` - не может импортировать `PlanMapper`
  - `test_plan_repository_updates.py` - не может импортировать `PlanRepositoryImpl`

---

## 🎯 Анализ зависимостей

### Legacy Repositories (нужно удалить)

#### 1. SessionRepositoryImpl
**Файл:** `app/infrastructure/persistence/repositories/session_repository_impl.py`  
**Размер:** 536 строк  
**Использования:** 2 места в `dependencies.py`

```python
# Строка 882
async def get_get_session_handler(
    repository: SessionRepositoryImpl = Depends(get_session_repository)
) -> GetSessionHandler:

# Строка 897
async def get_list_sessions_handler(
    session_repository: SessionRepositoryImpl = Depends(get_session_repository),
    context_repository: AgentContextRepositoryImpl = Depends(get_agent_context_repository)
) -> ListSessionsHandler:
```

**Замена:** `ConversationRepositoryImpl` (уже создан)

---

#### 2. AgentContextRepositoryImpl
**Файл:** `app/infrastructure/persistence/repositories/agent_context_repository_impl.py`  
**Размер:** 374 строки  
**Использования:** 2 места в `dependencies.py`

```python
# Строка 898
async def get_list_sessions_handler(
    session_repository: SessionRepositoryImpl = Depends(get_session_repository),
    context_repository: AgentContextRepositoryImpl = Depends(get_agent_context_repository)
) -> ListSessionsHandler:

# Строка 914
async def get_get_agent_context_handler(
    repository: AgentContextRepositoryImpl = Depends(get_agent_context_repository)
) -> GetAgentContextHandler:
```

**Замена:** `AgentRepositoryImpl` (уже создан)

---

#### 3. PlanRepositoryImpl
**Файл:** `app/infrastructure/persistence/repositories/plan_repository_impl.py`  
**Размер:** 516 строк  
**Использования:** 5 мест в `dependencies.py`

```python
# Строка 449
async def get_plan_approval_handler(
    approval_manager = Depends(get_approval_manager),
    plan_repository = Depends(get_plan_repository)
):

# Строка 561
async def get_architect_agent_for_planning(
    plan_repository = Depends(get_plan_repository)
):

# Строка 638
async def get_execution_coordinator(
    execution_engine = Depends(get_execution_engine),
    plan_repository = Depends(get_plan_repository)
):

# Строка 717
async def get_orchestrator_agent(
    fsm_orchestrator = Depends(get_fsm_orchestrator),
    plan_repository = Depends(get_plan_repository)
):

# Строка 769
async def get_universal_agent(
    plan_approval_handler = Depends(get_plan_approval_handler),
    plan_repository = Depends(get_plan_repository),
    execution_coordinator = Depends(get_execution_coordinator),
):
```

**Замена:** `ExecutionPlanRepositoryImpl` (уже создан)

---

### Новые Repositories (уже созданы)

#### 1. ConversationRepositoryImpl ✅
**Файл:** `app/infrastructure/persistence/repositories/conversation_repository_impl.py`  
**Статус:** Создан в Фазе 10.2  
**Dependency функция:** `get_conversation_repository()` (строка 104)

#### 2. AgentRepositoryImpl ✅
**Файл:** `app/infrastructure/persistence/repositories/agent_repository_impl.py`  
**Статус:** Создан в Фазе 10.2  
**Dependency функция:** `get_agent_repository()` (строка 119)

#### 3. ExecutionPlanRepositoryImpl ✅
**Файл:** `app/infrastructure/persistence/repositories/execution_plan_repository_impl.py`  
**Статус:** Создан в Фазе 10.2  
**Dependency функция:** `get_execution_plan_repository()` (строка 576)

---

## 📋 План миграции

### Этап 2: Infrastructure - Repositories (2 часа)

#### 2.1 Обновить dependencies.py (1 час)

**Задача:** Заменить все использования legacy repositories на новые

**Изменения:**

```python
# ============= БЫЛО =============

# Строка 74-86
async def get_session_repository(
    db: AsyncSession = Depends(get_db_session)
) -> SessionRepositoryImpl:
    return SessionRepositoryImpl(db)

# Строка 89-101
async def get_agent_context_repository(
    db: AsyncSession = Depends(get_db_session)
) -> AgentContextRepositoryImpl:
    return AgentContextRepositoryImpl(db)

# Строка 134-147
async def get_plan_repository(
    db: AsyncSession = Depends(get_db_session)
):
    from ..infrastructure.persistence.repositories.plan_repository_impl import PlanRepositoryImpl
    return PlanRepositoryImpl(db)

# ============= СТАЛО =============

# УДАЛИТЬ get_session_repository - использовать get_conversation_repository
# УДАЛИТЬ get_agent_context_repository - использовать get_agent_repository  
# УДАЛИТЬ get_plan_repository - использовать get_execution_plan_repository
```

**Замены в использованиях:**

1. **get_get_session_handler (строка 882)**
```python
# Было:
async def get_get_session_handler(
    repository: SessionRepositoryImpl = Depends(get_session_repository)
) -> GetSessionHandler:

# Стало:
async def get_get_session_handler(
    repository: ConversationRepositoryImpl = Depends(get_conversation_repository)
) -> GetSessionHandler:
```

2. **get_list_sessions_handler (строка 897)**
```python
# Было:
async def get_list_sessions_handler(
    session_repository: SessionRepositoryImpl = Depends(get_session_repository),
    context_repository: AgentContextRepositoryImpl = Depends(get_agent_context_repository)
) -> ListSessionsHandler:

# Стало:
async def get_list_sessions_handler(
    session_repository: ConversationRepositoryImpl = Depends(get_conversation_repository),
    context_repository: AgentRepositoryImpl = Depends(get_agent_repository)
) -> ListSessionsHandler:
```

3. **get_get_agent_context_handler (строка 914)**
```python
# Было:
async def get_get_agent_context_handler(
    repository: AgentContextRepositoryImpl = Depends(get_agent_context_repository)
) -> GetAgentContextHandler:

# Стало:
async def get_get_agent_context_handler(
    repository: AgentRepositoryImpl = Depends(get_agent_repository)
) -> GetAgentContextHandler:
```

4. **Все использования get_plan_repository (5 мест)**
```python
# Заменить все:
Depends(get_plan_repository)

# На:
Depends(get_execution_plan_repository)
```

---

#### 2.2 Обновить __init__.py (15 мин)

**Файл:** `app/infrastructure/persistence/repositories/__init__.py`

```python
# Было:
from .session_repository_impl import SessionRepositoryImpl
from .agent_context_repository_impl import AgentContextRepositoryImpl

# Стало:
from .conversation_repository_impl import ConversationRepositoryImpl
from .agent_repository_impl import AgentRepositoryImpl
from .execution_plan_repository_impl import ExecutionPlanRepositoryImpl

# Для обратной совместимости (временно):
SessionRepositoryImpl = ConversationRepositoryImpl  # Alias
AgentContextRepositoryImpl = AgentRepositoryImpl  # Alias
```

---

#### 2.3 Обновить handlers (30 мин)

**Проверить и обновить:**
- `GetSessionHandler` - должен работать с `ConversationRepositoryImpl`
- `ListSessionsHandler` - должен работать с `ConversationRepositoryImpl` и `AgentRepositoryImpl`
- `GetAgentContextHandler` - должен работать с `AgentRepositoryImpl`

---

#### 2.4 Удалить legacy repositories (15 мин)

**После проверки всех зависимостей:**

```bash
# Переименовать в legacy (для отката)
mv app/infrastructure/persistence/repositories/session_repository_impl.py \
   app/infrastructure/persistence/repositories/session_repository_impl_legacy.py

mv app/infrastructure/persistence/repositories/agent_context_repository_impl.py \
   app/infrastructure/persistence/repositories/agent_context_repository_impl_legacy.py

mv app/infrastructure/persistence/repositories/plan_repository_impl.py \
   app/infrastructure/persistence/repositories/plan_repository_impl_legacy.py
```

---

### Этап 3: Application Layer (1.5 часа)

#### 3.1 Проверить handlers (30 мин)

**Файлы для проверки:**
- `app/application/handlers/get_session_handler.py`
- `app/application/handlers/list_sessions_handler.py`
- `app/application/handlers/get_agent_context_handler.py`

**Задача:** Убедиться, что handlers совместимы с новыми repositories

---

#### 3.2 Обновить DTOs (30 мин)

**Проверить:**
- `app/application/dto/session_dto.py` - уже обновлен в Фазе 10.4
- `app/application/dto/agent_context_dto.py` - нужно проверить

---

#### 3.3 Обновить Commands и Use Cases (30 мин)

**Файлы:**
- `app/application/commands/create_session.py`
- `app/application/commands/switch_agent.py`
- `app/application/use_cases/switch_agent_use_case.py`
- `app/application/use_cases/process_message_use_case.py`

---

### Этап 4: Adapters (30 мин)

#### 4.1 Обновить SessionManagerAdapter

**Файл:** `app/infrastructure/adapters/session_manager_adapter.py`

```python
# Было:
from app.domain.entities.session import Session

# Стало:
from app.domain.session_context.entities.conversation import Conversation as Session
```

---

#### 4.2 Обновить AgentContextManagerAdapter

**Файл:** `app/infrastructure/adapters/agent_context_manager_adapter.py`

```python
# Было:
from app.domain.entities.agent_context import AgentContext

# Стало:
from app.domain.agent_context.entities.agent import Agent as AgentContext
```

---

### Этап 5: Domain - Удаление Legacy (1 час)

#### 5.1 Обновить __init__.py (15 мин)

**Файл:** `app/domain/entities/__init__.py`

```python
# Удалить:
from .session import Session
from .agent_context import AgentContext, AgentType, AgentSwitch
from .execution_plan import Plan

# Добавить алиасы для обратной совместимости:
from app.domain.session_context.entities.conversation import Conversation as Session
from app.domain.agent_context.entities.agent import Agent as AgentContext
from app.domain.agent_context.value_objects.agent_capabilities import AgentType
from app.domain.execution_context.entities.execution_plan import ExecutionPlan as Plan
```

---

#### 5.2 Удалить legacy entities (15 мин)

```bash
# Переименовать для отката
mv app/domain/entities/session.py app/domain/entities/session_legacy.py
mv app/domain/entities/agent_context.py app/domain/entities/agent_context_legacy.py
mv app/domain/entities/execution_plan.py app/domain/entities/execution_plan_legacy.py
```

---

#### 5.3 Удалить legacy repositories interfaces (15 мин)

```bash
mv app/domain/repositories/session_repository.py app/domain/repositories/session_repository_legacy.py
mv app/domain/repositories/agent_context_repository.py app/domain/repositories/agent_context_repository_legacy.py
mv app/domain/repositories/plan_repository.py app/domain/repositories/plan_repository_legacy.py
```

---

#### 5.4 Обновить __init__.py в repositories (15 мин)

**Файл:** `app/domain/repositories/__init__.py`

---

### Этап 6: Dependencies & DI (30 мин)

#### 6.1 Финальная проверка dependencies.py

**Убедиться:**
- ✅ Все legacy функции удалены
- ✅ Все использования заменены на новые
- ✅ Импорты обновлены

---

#### 6.2 Обновить импорты

**Проверить все файлы на наличие:**
```python
from app.domain.entities.session import Session
from app.domain.entities.agent_context import AgentContext
from app.domain.entities.execution_plan import Plan
```

---

### Этап 7: Тестирование (1.5 часа)

#### 7.1 Исправить тестовые импорты (30 мин)

**Файлы с ошибками:**
- `tests/unit/infrastructure/test_plan_mapper_updates.py`
- `tests/unit/infrastructure/test_plan_repository_updates.py`

**Обновить импорты:**
```python
# Было:
from app.infrastructure.persistence.mappers import PlanMapper
from app.infrastructure.persistence.repositories import PlanRepositoryImpl

# Стало:
from app.infrastructure.persistence.mappers.execution_plan_mapper import ExecutionPlanMapper
from app.infrastructure.persistence.repositories.execution_plan_repository_impl import ExecutionPlanRepositoryImpl
```

---

#### 7.2 Запустить все тесты (30 мин)

```bash
uv run pytest tests/ -v --tb=short
```

**Ожидаемые проблемы:**
- Тесты используют legacy entities
- Моки и фикстуры нужно обновить

---

#### 7.3 Исправить failing тесты (30 мин)

**Обновить:**
- Фикстуры для использования новых entities
- Моки для новых repositories
- Assertions для новых типов

---

### Этап 8: Финализация (30 мин)

#### 8.1 Проверка импортов (15 мин)

```bash
# Найти все оставшиеся импорты legacy кода
grep -r "from app.domain.entities.session import" app/
grep -r "from app.domain.entities.agent_context import" app/
grep -r "from app.domain.entities.execution_plan import" app/
```

---

#### 8.2 Финальное тестирование (10 мин)

```bash
uv run pytest tests/ -v
```

---

#### 8.3 Создание отчета (5 мин)

**Создать:**
- `doc/PHASE_10_5_COMPLETION_REPORT.md`
- Обновить `doc/PHASE_10_PROGRESS_DASHBOARD.md`

---

## ⚠️ Критические точки

### 1. Handlers совместимость

**Проблема:** Handlers могут ожидать специфичные методы legacy repositories

**Решение:** 
- Проверить каждый handler
- Убедиться, что новые repositories имеют те же методы
- Создать адаптеры при необходимости

---

### 2. Тесты

**Проблема:** 13+ тестовых файлов используют legacy код

**Решение:**
- Обновить импорты
- Обновить фикстуры
- Обновить моки

---

### 3. Обратная совместимость

**Проблема:** Внешние зависимости могут использовать legacy типы

**Решение:**
- Использовать алиасы в `__init__.py`
- Постепенная миграция
- Документировать breaking changes

---

## 📊 Оценка времени

| Этап | Задача | Время | Риск |
|------|--------|-------|------|
| 2.1 | Обновить dependencies.py | 1ч | 🟡 Средний |
| 2.2 | Обновить __init__.py | 15мин | 🟢 Низкий |
| 2.3 | Обновить handlers | 30мин | 🟡 Средний |
| 2.4 | Удалить legacy repos | 15мин | 🟢 Низкий |
| 3.1 | Проверить handlers | 30мин | 🟡 Средний |
| 3.2 | Обновить DTOs | 30мин | 🟢 Низкий |
| 3.3 | Обновить Commands/UseCases | 30мин | 🟡 Средний |
| 4.1 | Обновить SessionManagerAdapter | 15мин | 🟢 Низкий |
| 4.2 | Обновить AgentContextManagerAdapter | 15мин | 🟢 Низкий |
| 5.1 | Обновить entities __init__ | 15мин | 🟡 Средний |
| 5.2 | Удалить legacy entities | 15мин | 🟢 Низкий |
| 5.3 | Удалить legacy repo interfaces | 15мин | 🟢 Низкий |
| 5.4 | Обновить repos __init__ | 15мин | 🟢 Низкий |
| 6.1 | Проверка dependencies | 15мин | 🟢 Низкий |
| 6.2 | Обновить импорты | 15мин | 🟡 Средний |
| 7.1 | Исправить тестовые импорты | 30мин | 🟡 Средний |
| 7.2 | Запустить тесты | 30мин | 🔴 Высокий |
| 7.3 | Исправить failing тесты | 30мин | 🔴 Высокий |
| 8.1 | Проверка импортов | 15мин | 🟢 Низкий |
| 8.2 | Финальное тестирование | 10мин | 🟡 Средний |
| 8.3 | Создание отчета | 5мин | 🟢 Низкий |
| **Итого** | | **6ч 30мин** | |

**С учетом непредвиденных проблем:** 7-8 часов

---

## ✅ Критерии успеха

- [ ] Все legacy repositories удалены
- [ ] Все legacy entities удалены
- [ ] Все тесты проходят (100%)
- [ ] Нет импортов legacy кода
- [ ] Dependencies обновлены
- [ ] Handlers работают корректно
- [ ] Документация обновлена

---

## 🔄 План отката

**Если что-то пойдет не так:**

```bash
# Вернуться на предыдущий коммит
git reset --hard HEAD~1

# Или вернуться на main
git checkout main

# Legacy файлы сохранены с суффиксом _legacy
# Можно быстро восстановить
```

---

## 📚 Следующие шаги

1. **Начать с Этапа 2.1** - обновить `dependencies.py`
2. **Тестировать после каждого этапа**
3. **Коммитить после каждого успешного этапа**
4. **Документировать проблемы и решения**

---

**Дата создания:** 6 февраля 2026, 00:21 MSK  
**Статус:** ✅ Готов к выполнению  
**Ветка:** `feature/phase-10-5-legacy-cleanup`  
**Следующий шаг:** Этап 2.1 - Обновить dependencies.py
