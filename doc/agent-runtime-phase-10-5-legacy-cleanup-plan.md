# 📋 План Фазы 10.5: Полная очистка от Legacy кода

**Дата:** 6 февраля 2026  
**Оценка:** 5-7 часов  
**Статус:** ⏳ Готов к выполнению

---

## 🎯 Цель фазы

Полностью удалить legacy код и завершить миграцию на DDD-архитектуру:
- Удалить legacy entities (`Session`, `AgentContext`, `ExecutionPlan`)
- Удалить legacy repositories
- Удалить legacy services
- Обновить все зависимости (35+ файлов)
- Финальное тестирование

---

## 📊 Текущее состояние

### ✅ Уже выполнено (Фаза 10.4)

1. **Обновлено 15 файлов:**
   - 3 файла: `AgentType` импорты
   - 4 файла: `PlanRepository` импорты (TYPE_CHECKING)
   - 7 файлов: `Session` импорты в agents
   - 1 файл: backup файлы удалены

2. **Создана новая архитектура:**
   - ✅ `ConversationManagementService` (Фаза 10.1.1)
   - ✅ `AgentCoordinationService` (Фаза 10.1.2)
   - ✅ `PlanExecutionService` (Фаза 10.1.3)
   - ✅ `ExecutionPlanRepositoryImpl` (Фаза 10.2)
   - ✅ Адаптеры для обратной совместимости

### ⚠️ Осталось выполнить

**35+ файлов с зависимостями от legacy кода:**

#### Session зависимости (11 файлов):
1. `app/application/commands/create_session.py`
2. `app/application/dto/session_dto.py` ✅ (частично)
3. `app/domain/entities/__init__.py` ✅ (частично)
4. `app/infrastructure/adapters/session_manager_adapter.py`
5. `app/infrastructure/persistence/repositories/session_repository_impl.py`
6. `app/infrastructure/persistence/mappers/session_mapper.py`
7-13. `app/agents/*.py` ✅ (обновлено)

#### AgentContext зависимости (7 файлов):
1. `app/application/dto/agent_context_dto.py`
2. `app/application/commands/switch_agent.py`
3. `app/application/use_cases/switch_agent_use_case.py`
4. `app/application/use_cases/process_message_use_case.py`
5. `app/infrastructure/adapters/agent_context_manager_adapter.py`
6. `app/infrastructure/persistence/repositories/agent_context_repository_impl.py`
7. `app/infrastructure/persistence/mappers/agent_context_mapper.py`

#### PlanRepository зависимости (1 файл):
1. `app/infrastructure/persistence/repositories/plan_repository_impl.py` ⚠️ (проблема)

---

## 📋 Детальный план выполнения

### Этап 1: Подготовка (30 мин)

#### 1.1 Создать ветку для миграции
```bash
cd codelab-ai-service/agent-runtime
git checkout -b feature/phase-10-5-legacy-cleanup
```

#### 1.2 Создать резервную копию
```bash
git add -A
git commit -m "WIP: Before legacy cleanup"
```

#### 1.3 Запустить все тесты (baseline)
```bash
pytest tests/ -v --tb=short > /tmp/tests-before.log
```

---

### Этап 2: Infrastructure Layer - Repositories (2 часа)

#### 2.1 Обновить `session_repository_impl.py` (30 мин)

**Файл:** `app/infrastructure/persistence/repositories/session_repository_impl.py`

**Проблема:** Использует legacy `Session` entity и `SessionRepository` interface

**Решение:**
```python
# Было:
from app.domain.entities.session import Session
from app.domain.repositories.session_repository import SessionRepository

# Стало:
from app.domain.session_context.entities.conversation import Conversation
from app.domain.session_context.repositories.conversation_repository import ConversationRepository

class SessionRepositoryImpl(ConversationRepository):  # Изменить наследование
    # Обновить все методы для работы с Conversation
```

**Действия:**
1. Изменить импорты
2. Изменить наследование: `SessionRepository` → `ConversationRepository`
3. Обновить методы: `Session` → `Conversation`
4. Обновить типы: `session_id: str` → `conversation_id: ConversationId`
5. Запустить тесты

---

#### 2.2 Обновить `agent_context_repository_impl.py` (30 мин)

**Файл:** `app/infrastructure/persistence/repositories/agent_context_repository_impl.py`

**Проблема:** Использует legacy `AgentContext` entity

**Решение:**
```python
# Было:
from app.domain.entities.agent_context import AgentContext
from app.domain.repositories.agent_context_repository import AgentContextRepository

# Стало:
from app.domain.agent_context.entities.agent import Agent
from app.domain.agent_context.repositories.agent_repository import AgentRepository

class AgentContextRepositoryImpl(AgentRepository):
    # Обновить все методы для работы с Agent
```

---

#### 2.3 Заменить `plan_repository_impl.py` (30 мин)

**Файл:** `app/infrastructure/persistence/repositories/plan_repository_impl.py`

**Проблема:** Реализует старый `PlanRepository` для legacy `Plan` entity

**Решение:** Использовать уже существующий `ExecutionPlanRepositoryImpl` из Фазы 10.2

**Действия:**
1. Переименовать текущий `plan_repository_impl.py` → `plan_repository_impl_legacy.py`
2. Использовать `execution_plan_repository_impl.py` как основной
3. Обновить `dependencies.py`:
   ```python
   # Было:
   from app.infrastructure.persistence.repositories.plan_repository_impl import PlanRepositoryImpl
   
   # Стало:
   from app.infrastructure.persistence.repositories.execution_plan_repository_impl import ExecutionPlanRepositoryImpl
   
   def get_plan_repository(db: AsyncSession = Depends(get_db)):
       return ExecutionPlanRepositoryImpl(db)  # Вместо PlanRepositoryImpl
   ```

---

#### 2.4 Обновить mappers (30 мин)

**Файлы:**
- `app/infrastructure/persistence/mappers/session_mapper.py`
- `app/infrastructure/persistence/mappers/agent_context_mapper.py`

**Решение:**
```python
# session_mapper.py
from app.domain.session_context.entities.conversation import Conversation

class SessionMapper:
    @staticmethod
    def to_domain(model: SessionModel) -> Conversation:
        # Конвертировать в Conversation
        
# agent_context_mapper.py  
from app.domain.agent_context.entities.agent import Agent

class AgentContextMapper:
    @staticmethod
    def to_domain(model: AgentContextModel) -> Agent:
        # Конвертировать в Agent
```

---

### Этап 3: Application Layer (1.5 часа)

#### 3.1 Обновить DTOs (30 мин)

**Файлы:**
- `app/application/dto/session_dto.py` ✅ (частично обновлен)
- `app/application/dto/agent_context_dto.py`

**Решение:**
```python
# session_dto.py - уже обновлен в Фазе 10.4
from app.domain.session_context.entities.conversation import Conversation

# agent_context_dto.py
from app.domain.agent_context.entities.agent import Agent
from app.domain.agent_context.value_objects.agent_capabilities import AgentType

class AgentContextDTO(BaseModel):
    # Обновить поля для Agent
```

---

#### 3.2 Обновить Commands (30 мин)

**Файлы:**
- `app/application/commands/create_session.py`
- `app/application/commands/switch_agent.py`

**Решение:**
```python
# create_session.py
from app.domain.session_context.entities.conversation import Conversation
from app.domain.session_context.value_objects import ConversationId

class CreateSessionCommand:
    async def execute(self) -> Conversation:
        # Создать Conversation вместо Session

# switch_agent.py
from app.domain.agent_context.value_objects.agent_capabilities import AgentType

class SwitchAgentCommand:
    # Использовать новый AgentType
```

---

#### 3.3 Обновить Use Cases (30 мин)

**Файлы:**
- `app/application/use_cases/switch_agent_use_case.py`
- `app/application/use_cases/process_message_use_case.py`

**Решение:**
```python
# switch_agent_use_case.py
from app.domain.agent_context.value_objects.agent_capabilities import AgentType
from app.domain.agent_context.services.agent_coordination_service import AgentCoordinationService

class SwitchAgentUseCase:
    def __init__(self, agent_service: AgentCoordinationService):
        # Использовать новый сервис

# process_message_use_case.py
from app.domain.session_context.services.conversation_management_service import ConversationManagementService

class ProcessMessageUseCase:
    def __init__(self, conversation_service: ConversationManagementService):
        # Использовать новый сервис
```

---

### Этап 4: Adapters (30 мин)

#### 4.1 Обновить `session_manager_adapter.py`

**Файл:** `app/infrastructure/adapters/session_manager_adapter.py`

**Решение:**
```python
# Было:
from app.domain.entities.session import Session

# Стало:
from app.domain.session_context.entities.conversation import Conversation as Session

class SessionManagerAdapter:
    def __init__(self, conversation_service: ConversationManagementService):
        self._service = conversation_service
    
    # Методы остаются, но используют Conversation внутри
```

---

#### 4.2 Обновить `agent_context_manager_adapter.py`

**Файл:** `app/infrastructure/adapters/agent_context_manager_adapter.py`

**Решение:**
```python
# Было:
from app.domain.entities.agent_context import AgentContext

# Стало:
from app.domain.agent_context.entities.agent import Agent as AgentContext

class AgentContextManagerAdapter:
    def __init__(self, agent_service: AgentCoordinationService):
        self._service = agent_service
```

---

### Этап 5: Domain Layer - Удаление Legacy (1 час)

#### 5.1 Обновить `__init__.py` файлы (15 мин)

**Файл:** `app/domain/entities/__init__.py`

```python
# Удалить:
from .session import Session
from .agent_context import AgentContext, AgentType, AgentSwitch

# Добавить алиасы для обратной совместимости (временно):
from app.domain.session_context.entities.conversation import Conversation as Session
from app.domain.agent_context.entities.agent import Agent as AgentContext
from app.domain.agent_context.value_objects.agent_capabilities import AgentType

__all__ = [
    "Entity",
    "Message",
    "Session",  # Алиас
    "AgentContext",  # Алиас
    "AgentType",
    # ... остальное
]
```

---

#### 5.2 Удалить legacy entities (15 мин)

**После проверки всех зависимостей:**

```bash
# Удалить файлы
rm app/domain/entities/session.py
rm app/domain/entities/agent_context.py
rm app/domain/entities/execution_plan.py  # Если не используется

# Проверить компиляцию
python -m py_compile app/**/*.py
```

---

#### 5.3 Удалить legacy repositories (15 мин)

```bash
rm app/domain/repositories/session_repository.py
rm app/domain/repositories/agent_context_repository.py
rm app/domain/repositories/plan_repository.py
```

---

#### 5.4 Удалить legacy services (15 мин)

**Проверить использование:**
```bash
grep -r "from app.domain.services.session_management import" app/
grep -r "from app.domain.services.agent_orchestration import" app/
```

**Если используются только через адаптеры - удалить:**
```bash
rm app/domain/services/session_management.py
rm app/domain/services/agent_orchestration.py
```

---

### Этап 6: Dependencies & DI Container (30 мин)

#### 6.1 Обновить `dependencies.py`

**Файл:** `app/core/dependencies.py`

**Изменения:**
```python
# Repositories
def get_conversation_repository(db: AsyncSession = Depends(get_db)):
    from app.infrastructure.persistence.repositories.conversation_repository_impl import ConversationRepositoryImpl
    return ConversationRepositoryImpl(db)

def get_agent_repository(db: AsyncSession = Depends(get_db)):
    from app.infrastructure.persistence.repositories.agent_repository_impl import AgentRepositoryImpl
    return AgentRepositoryImpl(db)

def get_execution_plan_repository(db: AsyncSession = Depends(get_db)):
    from app.infrastructure.persistence.repositories.execution_plan_repository_impl import ExecutionPlanRepositoryImpl
    return ExecutionPlanRepositoryImpl(db)

# Services - использовать напрямую новые сервисы
def get_conversation_service(
    repo: ConversationRepository = Depends(get_conversation_repository)
):
    from app.domain.session_context.services.conversation_management_service import ConversationManagementService
    return ConversationManagementService(repo)

def get_agent_service(
    repo: AgentRepository = Depends(get_agent_repository)
):
    from app.domain.agent_context.services.agent_coordination_service import AgentCoordinationService
    return AgentCoordinationService(repo)

def get_execution_service(
    repo: ExecutionPlanRepository = Depends(get_execution_plan_repository)
):
    from app.domain.execution_context.services.plan_execution_service import PlanExecutionService
    return PlanExecutionService(repo)

# Удалить старые функции:
# - get_session_management_service()
# - get_agent_orchestration_service()
# - get_execution_engine()
```

---

### Этап 7: Тестирование (1.5 часа)

#### 7.1 Unit тесты (30 мин)

```bash
# Запустить все unit тесты
pytest tests/unit/ -v --tb=short

# Проверить покрытие
pytest tests/unit/ --cov=app --cov-report=html
```

**Ожидаемые проблемы:**
- Тесты используют legacy entities
- Нужно обновить моки и фикстуры

**Решение:**
- Обновить тесты для использования новых entities
- Обновить фикстуры

---

#### 7.2 Integration тесты (30 мин)

```bash
# Запустить integration тесты
pytest tests/integration/ -v --tb=short
```

**Проверить:**
- Работа с БД
- API endpoints
- Сервисы

---

#### 7.3 Docker тестирование (30 мин)

```bash
# Пересобрать образ
cd codelab-ai-service
docker compose build agent-runtime

# Запустить
docker compose up -d agent-runtime

# Проверить логи
docker compose logs agent-runtime --tail=100

# Проверить health
curl http://localhost:8001/health

# Проверить API
curl http://localhost:8001/api/v1/sessions
```

---

### Этап 8: Финализация (30 мин)

#### 8.1 Обновить документацию (15 мин)

**Создать файлы:**
1. `doc/agent-runtime-phase-10-5-completion-report.md`
2. `doc/agent-runtime-phase-10-final-report.md`
3. Обновить `doc/agent-runtime-phase-10-progress.md`

---

#### 8.2 Создать коммит (15 мин)

```bash
git add -A
git commit -m "feat(agent-runtime): Phase 10.5 - Complete legacy code removal

- Removed legacy entities (Session, AgentContext, ExecutionPlan)
- Removed legacy repositories
- Removed legacy services
- Updated 35+ files to use new DDD architecture
- All tests passing
- Docker working

BREAKING CHANGE: Legacy entities and repositories removed
"
```

---

## 📊 Оценка времени

| Этап | Задача | Время |
|------|--------|-------|
| 1 | Подготовка | 30 мин |
| 2 | Infrastructure - Repositories | 2 часа |
| 3 | Application Layer | 1.5 часа |
| 4 | Adapters | 30 мин |
| 5 | Domain - Удаление Legacy | 1 час |
| 6 | Dependencies & DI | 30 мин |
| 7 | Тестирование | 1.5 часа |
| 8 | Финализация | 30 мин |
| **Итого** | | **8 часов** |

**С учетом непредвиденных проблем:** 8-10 часов

---

## ⚠️ Риски и митигация

### Риск 1: Сломанные тесты

**Вероятность:** Высокая  
**Влияние:** Среднее

**Митигация:**
- Запускать тесты после каждого этапа
- Обновлять тесты параллельно с кодом
- Использовать TDD подход

---

### Риск 2: Несовместимость API

**Вероятность:** Средняя  
**Влияние:** Высокое

**Митигация:**
- Сохранить алиасы в `__init__.py`
- Использовать адаптеры
- Постепенная миграция

---

### Риск 3: Проблемы с БД

**Вероятность:** Низкая  
**Влияние:** Высокое

**Митигация:**
- Тестировать на dev БД
- Создать backup перед миграцией
- Использовать транзакции

---

## ✅ Критерии успеха

1. ✅ Все legacy entities удалены
2. ✅ Все legacy repositories удалены
3. ✅ Все legacy services удалены
4. ✅ 35+ файлов обновлено
5. ✅ Все unit тесты проходят (100%)
6. ✅ Все integration тесты проходят (100%)
7. ✅ Docker запускается без ошибок
8. ✅ API работает корректно
9. ✅ Нет импортов legacy кода
10. ✅ Документация обновлена

---

## 🎯 Ожидаемый результат

После завершения Фазы 10.5:

```
✅ Domain Layer: 100% DDD
✅ Infrastructure Layer: 100% DDD
✅ Application Layer: 100% DDD
✅ Legacy Code: 0%

🎯 Миграция завершена на 100%!
```

**Архитектура:**
- ✅ Clean Architecture
- ✅ Domain-Driven Design
- ✅ SOLID принципы
- ✅ Типобезопасность (Value Objects)
- ✅ Тестируемость
- ✅ Масштабируемость

---

## 📚 Связанные документы

1. [`agent-runtime-phase-10-4-dependency-analysis.md`](agent-runtime-phase-10-4-dependency-analysis.md) - анализ зависимостей
2. [`agent-runtime-phase-10-4-completion-report.md`](agent-runtime-phase-10-4-completion-report.md) - отчет Фазы 10.4
3. [`agent-runtime-phase-10-progress.md`](agent-runtime-phase-10-progress.md) - общий прогресс

---

## 🚀 Готовность к выполнению

**Статус:** ✅ Готов

**Предварительные условия:**
- ✅ Фаза 10.4 завершена
- ✅ Анализ зависимостей выполнен
- ✅ Новая архитектура создана
- ✅ Адаптеры работают
- ✅ Система стабильна

**Следующий шаг:** Начать Этап 1 - Подготовка

---

**Создано:** 6 февраля 2026  
**Автор:** AI Assistant  
**Версия:** 1.0
