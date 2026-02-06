# 📋 Детальный план выполнения Фазы 10.2

**Дата:** 6 февраля 2026  
**Автор:** Agent Runtime Team  
**Статус:** 📋 Готов к выполнению  
**Оценка:** 7 часов

---

## 🎯 Цель

Мигрировать Infrastructure Layer на новую DDD-архитектуру, создав компоненты для работы с `ExecutionPlan` entity.

---

## 📊 Общая структура

```
Фаза 10.2: Infrastructure Layer (7 часов)
├── Подготовка (15 минут)
├── Этап 1: ExecutionPlanMapper (2 часа)
├── Этап 2: ExecutionPlanRepositoryImpl (3 часа)
├── Этап 3: PlanMapper update (1 час)
├── Этап 4: PlanRepositoryImpl update (1 час)
└── Финализация (30 минут)
```

---

## 🚀 Подготовка (15 минут)

### Задачи

1. **Изучить существующие компоненты** (5 мин)
   - Прочитать `ConversationMapper` как reference
   - Прочитать `AgentMapper` как reference
   - Прочитать `ConversationRepositoryImpl` как reference

2. **Изучить domain entities** (5 мин)
   - Прочитать `ExecutionPlan` entity
   - Прочитать `Subtask` entity
   - Прочитать Value Objects: `PlanId`, `SubtaskId`, `PlanStatus`

3. **Изучить database models** (5 мин)
   - Прочитать `PlanModel`
   - Прочитать `SubtaskModel`
   - Понять структуру связей

### Файлы для изучения

```
Reference (существующие):
- app/infrastructure/persistence/mappers/conversation_mapper.py
- app/infrastructure/persistence/mappers/agent_mapper.py
- app/infrastructure/persistence/repositories/conversation_repository_impl.py

Domain (новые entities):
- app/domain/execution_context/entities/execution_plan.py
- app/domain/execution_context/entities/subtask.py
- app/domain/execution_context/value_objects/plan_id.py
- app/domain/execution_context/value_objects/subtask_id.py
- app/domain/execution_context/value_objects/plan_status.py

Database:
- app/infrastructure/persistence/models/plan.py
```

---

## 📝 Этап 1: ExecutionPlanMapper (2 часа)

### Цель

Создать mapper для преобразования между `ExecutionPlan` entity и `PlanModel`.

### Задача 1.1: Создать файл и структуру (15 мин)

**Действия:**
1. Создать файл `app/infrastructure/persistence/mappers/execution_plan_mapper.py`
2. Добавить imports
3. Создать класс `ExecutionPlanMapper`
4. Добавить docstring

**Код:**
```python
"""
Mapper для преобразования между ExecutionPlan Entity и PlanModel.

Изолирует доменный слой от деталей персистентности.
Использует новую ExecutionPlan entity вместо старой Plan.
"""

import json
import logging
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ....domain.execution_context.entities import ExecutionPlan, Subtask
from ....domain.execution_context.value_objects import (
    PlanId,
    SubtaskId,
    PlanStatus,
    SubtaskStatus,
)
from ....domain.session_context.value_objects import ConversationId
from ....domain.agent_context.value_objects import AgentType
from ..models import PlanModel, SubtaskModel

logger = logging.getLogger("agent-runtime.infrastructure.execution_plan_mapper")


class ExecutionPlanMapper:
    """
    Mapper между доменной сущностью ExecutionPlan и моделью БД PlanModel.
    
    Отвечает за преобразование данных между доменным слоем
    и слоем персистентности.
    
    Пример:
        >>> mapper = ExecutionPlanMapper()
        >>> # Entity -> Model
        >>> model = await mapper.to_model(execution_plan, db)
        >>> # Model -> Entity
        >>> entity = await mapper.to_entity(model, db)
    """
    pass
```

**Проверка:**
- ✅ Файл создан
- ✅ Imports корректны
- ✅ Класс создан с docstring

---

### Задача 1.2: Реализовать to_entity() (45 мин)

**Действия:**
1. Создать метод `to_entity()`
2. Загрузить subtasks из БД
3. Конвертировать subtasks в Subtask entities
4. Создать ExecutionPlan entity
5. Обработать все Value Objects

**Код:**
```python
async def to_entity(
    self,
    model: PlanModel,
    db: AsyncSession,
    load_subtasks: bool = True
) -> ExecutionPlan:
    """
    Преобразовать модель БД в доменную сущность ExecutionPlan.
    
    Args:
        model: Модель БД PlanModel
        db: Сессия БД для загрузки связанных данных
        load_subtasks: Загружать ли subtasks
        
    Returns:
        Доменная сущность ExecutionPlan
    """
    # Загрузить subtasks если требуется
    subtasks: List[Subtask] = []
    if load_subtasks:
        result = await db.execute(
            select(SubtaskModel)
            .where(SubtaskModel.plan_db_id == model.id)
            .order_by(SubtaskModel.order.asc())
        )
        subtask_models = result.scalars().all()
        
        # Преобразовать модели subtasks в entities
        for st_model in subtask_models:
            subtask = self._subtask_to_entity(st_model)
            subtasks.append(subtask)
    
    # Парсинг metadata
    metadata = {}
    if model.metadata_json:
        try:
            metadata = json.loads(model.metadata_json)
        except json.JSONDecodeError:
            logger.warning(
                f"Failed to parse metadata for plan {model.id}"
            )
    
    # Создать ExecutionPlan
    execution_plan = ExecutionPlan(
        id=PlanId(model.id),
        conversation_id=ConversationId(model.session_id),
        goal=model.goal,
        subtasks=subtasks,
        status=PlanStatus.from_string(model.status),
        current_subtask_id=SubtaskId(model.current_subtask_id) if model.current_subtask_id else None,
        metadata=metadata,
        approved_at=model.approved_at,
        started_at=model.started_at,
        completed_at=model.completed_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
    
    return execution_plan

def _subtask_to_entity(self, model: SubtaskModel) -> Subtask:
    """Преобразовать SubtaskModel в Subtask entity"""
    # Парсинг dependencies
    dependencies = []
    if model.dependencies_json:
        try:
            deps = json.loads(model.dependencies_json)
            dependencies = [SubtaskId(d) for d in deps]
        except json.JSONDecodeError:
            logger.warning(
                f"Failed to parse dependencies for subtask {model.id}"
            )
    
    # Парсинг metadata
    metadata = {}
    if model.metadata_json:
        try:
            metadata = json.loads(model.metadata_json)
        except json.JSONDecodeError:
            logger.warning(
                f"Failed to parse metadata for subtask {model.id}"
            )
    
    return Subtask(
        id=SubtaskId(model.id),
        title=model.title,
        description=model.description,
        agent_type=AgentType(model.agent) if model.agent else None,
        status=SubtaskStatus.from_string(model.status),
        dependencies=dependencies,
        order=model.order,
        result=model.result,
        error=model.error,
        metadata=metadata,
        started_at=model.started_at,
        completed_at=model.completed_at,
    )
```

**Проверка:**
- ✅ Метод to_entity() реализован
- ✅ Загрузка subtasks работает
- ✅ Value Objects конвертируются корректно
- ✅ Обработка None значений

---

### Задача 1.3: Реализовать to_model() (45 мин)

**Действия:**
1. Создать метод `to_model()`
2. Найти или создать PlanModel
3. Обновить поля модели
4. Сохранить/обновить subtasks
5. Конвертировать Value Objects в строки

**Код:**
```python
async def to_model(
    self,
    entity: ExecutionPlan,
    db: AsyncSession
) -> PlanModel:
    """
    Преобразовать доменную сущность в модель БД.
    
    Args:
        entity: Доменная сущность ExecutionPlan
        db: Сессия БД
        
    Returns:
        Модель БД PlanModel
    """
    # Найти существующую модель или создать новую
    result = await db.execute(
        select(PlanModel).where(PlanModel.id == entity.id.value)
    )
    model = result.scalar_one_or_none()
    
    if model is None:
        model = PlanModel(id=entity.id.value)
        db.add(model)
    
    # Обновить поля
    model.session_id = entity.conversation_id.value
    model.goal = entity.goal
    model.status = entity.status.value
    model.current_subtask_id = entity.current_subtask_id.value if entity.current_subtask_id else None
    model.metadata_json = json.dumps(entity.metadata) if entity.metadata else None
    model.approved_at = entity.approved_at
    model.started_at = entity.started_at
    model.completed_at = entity.completed_at
    model.updated_at = entity.updated_at
    
    # Сохранить subtasks
    await self._save_subtasks(entity, db)
    
    return model

async def _save_subtasks(
    self,
    entity: ExecutionPlan,
    db: AsyncSession
) -> None:
    """Сохранить subtasks в БД"""
    # Удалить старые subtasks (если есть)
    await db.execute(
        delete(SubtaskModel).where(
            SubtaskModel.plan_db_id == entity.id.value
        )
    )
    
    # Создать новые subtasks
    for subtask in entity.subtasks:
        st_model = SubtaskModel(
            id=subtask.id.value,
            plan_db_id=entity.id.value,
            title=subtask.title,
            description=subtask.description,
            agent=subtask.agent_type.value if subtask.agent_type else None,
            status=subtask.status.value,
            dependencies_json=json.dumps([d.value for d in subtask.dependencies]) if subtask.dependencies else None,
            order=subtask.order,
            result=subtask.result,
            error=subtask.error,
            metadata_json=json.dumps(subtask.metadata) if subtask.metadata else None,
            started_at=subtask.started_at,
            completed_at=subtask.completed_at,
        )
        db.add(st_model)
```

**Проверка:**
- ✅ Метод to_model() реализован
- ✅ Upsert логика работает
- ✅ Subtasks сохраняются корректно
- ✅ Value Objects → strings конвертация

---

### Задача 1.4: Написать тесты (15 мин)

**Действия:**
1. Создать файл `tests/unit/infrastructure/persistence/mappers/test_execution_plan_mapper.py`
2. Написать 15+ тестов
3. Запустить тесты

**Тесты:**
```python
import pytest
from datetime import datetime, timezone

from app.infrastructure.persistence.mappers.execution_plan_mapper import ExecutionPlanMapper
from app.domain.execution_context.entities import ExecutionPlan, Subtask
from app.domain.execution_context.value_objects import PlanId, SubtaskId, PlanStatus, SubtaskStatus
from app.domain.session_context.value_objects import ConversationId
from app.infrastructure.persistence.models.plan import PlanModel, SubtaskModel


@pytest.fixture
def mapper():
    return ExecutionPlanMapper()


@pytest.mark.asyncio
async def test_to_entity_basic(mapper, db_session):
    """Test basic to_entity conversion"""
    # Arrange
    model = PlanModel(
        id="plan-1",
        session_id="conv-1",
        goal="Test goal",
        status="draft",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(model)
    await db_session.flush()
    
    # Act
    entity = await mapper.to_entity(model, db_session, load_subtasks=False)
    
    # Assert
    assert isinstance(entity, ExecutionPlan)
    assert entity.id == PlanId("plan-1")
    assert entity.conversation_id == ConversationId("conv-1")
    assert entity.goal == "Test goal"
    assert entity.status == PlanStatus.draft()


@pytest.mark.asyncio
async def test_to_entity_with_subtasks(mapper, db_session):
    """Test to_entity with subtasks"""
    # ... (аналогично)


@pytest.mark.asyncio
async def test_to_model_basic(mapper, db_session):
    """Test basic to_model conversion"""
    # ... (аналогично)


@pytest.mark.asyncio
async def test_roundtrip(mapper, db_session):
    """Test entity -> model -> entity roundtrip"""
    # ... (аналогично)
```

**Команда:**
```bash
cd codelab-ai-service/agent-runtime
pytest tests/unit/infrastructure/persistence/mappers/test_execution_plan_mapper.py -v
```

**Проверка:**
- ✅ 15+ тестов написано
- ✅ Все тесты проходят
- ✅ Coverage > 90%

---

## 📝 Этап 2: ExecutionPlanRepositoryImpl (3 часа)

### Цель

Создать реализацию `ExecutionPlanRepository` для работы с БД.

### Задача 2.1: Создать файл и структуру (15 мин)

**Действия:**
1. Создать файл `app/infrastructure/persistence/repositories/execution_plan_repository_impl.py`
2. Добавить imports
3. Создать класс `ExecutionPlanRepositoryImpl`
4. Добавить конструктор

**Код:**
```python
"""
Реализация ExecutionPlanRepository с использованием SQLAlchemy.

Конкретная реализация интерфейса ExecutionPlanRepository для работы с БД.
"""

import logging
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from ....domain.execution_context.repositories import ExecutionPlanRepository
from ....domain.execution_context.entities import ExecutionPlan
from ....domain.execution_context.value_objects import PlanId
from ....domain.session_context.value_objects import ConversationId
from ..models import PlanModel
from ..mappers import ExecutionPlanMapper

logger = logging.getLogger("agent-runtime.infrastructure.execution_plan_repository")


class ExecutionPlanRepositoryImpl(ExecutionPlanRepository):
    """
    Реализация репозитория execution plans для SQLAlchemy.
    
    Использует ExecutionPlanMapper для преобразования между
    доменными сущностями и моделями БД.
    
    Атрибуты:
        _db: Сессия БД SQLAlchemy
        _mapper: Mapper для преобразования данных
    """
    
    def __init__(self, db: AsyncSession):
        """
        Инициализировать репозиторий.
        
        Args:
            db: Сессия БД SQLAlchemy
        """
        self._db = db
        self._mapper = ExecutionPlanMapper()
```

**Проверка:**
- ✅ Файл создан
- ✅ Класс создан
- ✅ Конструктор реализован

---

### Задача 2.2: Реализовать find_by_id() (30 мин)

**Код:**
```python
async def find_by_id(self, plan_id: PlanId) -> Optional[ExecutionPlan]:
    """
    Найти план по ID.
    
    Args:
        plan_id: ID плана
        
    Returns:
        ExecutionPlan или None если не найден
    """
    result = await self._db.execute(
        select(PlanModel).where(PlanModel.id == plan_id.value)
    )
    model = result.scalar_one_or_none()
    
    if not model:
        logger.debug(f"ExecutionPlan {plan_id.value} not found")
        return None
    
    plan = await self._mapper.to_entity(model, self._db)
    logger.debug(f"Found ExecutionPlan {plan_id.value}")
    return plan
```

---

### Задача 2.3: Реализовать find_by_conversation_id() (30 мин)

**Код:**
```python
async def find_by_conversation_id(
    self,
    conversation_id: ConversationId
) -> List[ExecutionPlan]:
    """
    Найти все планы для conversation.
    
    Args:
        conversation_id: ID conversation
        
    Returns:
        Список ExecutionPlan (может быть пустым)
    """
    result = await self._db.execute(
        select(PlanModel)
        .where(PlanModel.session_id == conversation_id.value)
        .order_by(PlanModel.created_at.desc())
    )
    models = result.scalars().all()
    
    plans = []
    for model in models:
        plan = await self._mapper.to_entity(model, self._db)
        plans.append(plan)
    
    logger.debug(
        f"Found {len(plans)} plans for conversation {conversation_id.value}"
    )
    return plans
```

---

### Задача 2.4: Реализовать save() (30 мин)

**Код:**
```python
async def save(self, plan: ExecutionPlan) -> None:
    """
    Сохранить план.
    
    Args:
        plan: ExecutionPlan entity
    """
    try:
        await self._mapper.to_model(plan, self._db)
        await self._db.flush()
        logger.debug(f"Saved ExecutionPlan {plan.id.value}")
    except Exception as e:
        logger.error(
            f"Error saving ExecutionPlan {plan.id.value}: {e}",
            exc_info=True
        )
        raise
```

---

### Задача 2.5: Реализовать delete() (15 мин)

**Код:**
```python
async def delete(self, plan_id: PlanId) -> None:
    """
    Удалить план.
    
    Args:
        plan_id: ID плана
    """
    try:
        await self._db.execute(
            delete(PlanModel).where(PlanModel.id == plan_id.value)
        )
        await self._db.flush()
        logger.debug(f"Deleted ExecutionPlan {plan_id.value}")
    except Exception as e:
        logger.error(
            f"Error deleting ExecutionPlan {plan_id.value}: {e}",
            exc_info=True
        )
        raise
```

---

### Задача 2.6: Написать тесты (1 час)

**Действия:**
1. Создать файл `tests/unit/infrastructure/persistence/repositories/test_execution_plan_repository_impl.py`
2. Написать 20+ тестов
3. Запустить тесты

**Команда:**
```bash
pytest tests/unit/infrastructure/persistence/repositories/test_execution_plan_repository_impl.py -v
```

**Проверка:**
- ✅ 20+ тестов написано
- ✅ Все тесты проходят
- ✅ Coverage > 90%

---

## 📝 Этап 3: PlanMapper update (1 час)

### Цель

Обновить существующий `PlanMapper` для совместимости с `PlanId` Value Object.

### Задача 3.1: Добавить поддержку PlanId (30 мин)

**Действия:**
1. Открыть `app/infrastructure/persistence/mappers/plan_mapper.py`
2. Добавить import для `PlanId`
3. Добавить helper метод для конвертации
4. Обновить методы

**Код:**
```python
# Добавить import
from ....domain.execution_context.value_objects import PlanId

# Добавить helper метод
@staticmethod
def _convert_plan_id(value: Union[str, PlanId]) -> str:
    """
    Конвертировать PlanId в строку для БД.
    
    Args:
        value: str или PlanId
        
    Returns:
        Строковое представление ID
    """
    if isinstance(value, PlanId):
        return value.value
    return value

# Обновить to_domain (если нужно)
@staticmethod
def to_domain(plan_model: PlanModel) -> Plan:
    """Преобразовать БД модель в доменную сущность."""
    # ... существующий код ...
    # Добавить поддержку PlanId если нужно
```

**Проверка:**
- ✅ Helper метод добавлен
- ✅ Поддержка PlanId работает
- ✅ Обратная совместимость сохранена

---

### Задача 3.2: Обновить тесты (30 мин)

**Действия:**
1. Открыть `tests/unit/infrastructure/persistence/mappers/test_plan_mapper.py`
2. Добавить тесты для PlanId
3. Запустить тесты

**Команда:**
```bash
pytest tests/unit/infrastructure/persistence/mappers/test_plan_mapper.py -v
```

**Проверка:**
- ✅ Тесты обновлены
- ✅ Все тесты проходят

---

## 📝 Этап 4: PlanRepositoryImpl update (1 час)

### Цель

Обновить `PlanRepositoryImpl` для работы с обновленным mapper и добавить snapshot методы.

### Задача 4.1: Добавить snapshot методы (30 мин)

**Действия:**
1. Открыть `app/infrastructure/persistence/repositories/plan_repository_impl.py`
2. Добавить class variable для snapshots
3. Добавить методы save_snapshot() и get_snapshot()

**Код:**
```python
class PlanRepositoryImpl(PlanRepository):
    """Реализация репозитория планов для SQLAlchemy."""
    
    # In-memory хранилище для snapshots (shared между всеми экземплярами)
    _snapshots: Dict[str, Dict[str, Any]] = {}
    
    # ... существующий код ...
    
    async def save_snapshot(
        self,
        snapshot_id: str,
        snapshot: Dict[str, Any]
    ) -> None:
        """
        Сохранить snapshot плана в in-memory хранилище.
        
        Args:
            snapshot_id: Уникальный ID snapshot
            snapshot: Данные snapshot
        """
        try:
            snapshot_with_meta = {
                **snapshot,
                "_saved_at": datetime.now(timezone.utc).isoformat()
            }
            
            PlanRepositoryImpl._snapshots[snapshot_id] = snapshot_with_meta
            
            logger.debug(f"Saved plan snapshot {snapshot_id}")
            
        except Exception as e:
            logger.error(f"Error saving snapshot {snapshot_id}: {e}")
            raise
    
    async def get_snapshot(
        self,
        snapshot_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Получить snapshot плана из in-memory хранилища.
        
        Args:
            snapshot_id: ID snapshot
            
        Returns:
            Данные snapshot или None
        """
        snapshot = PlanRepositoryImpl._snapshots.get(snapshot_id)
        
        if snapshot:
            logger.debug(f"Retrieved plan snapshot {snapshot_id}")
        else:
            logger.debug(f"Plan snapshot {snapshot_id} not found")
        
        return snapshot
```

**Проверка:**
- ✅ Snapshot методы добавлены
- ✅ Логирование работает

---

### Задача 4.2: Обновить тесты (30 мин)

**Действия:**
1. Открыть `tests/unit/infrastructure/persistence/repositories/test_plan_repository_impl.py`
2. Добавить тесты для snapshot методов
3. Запустить тесты

**Команда:**
```bash
pytest tests/unit/infrastructure/persistence/repositories/test_plan_repository_impl.py -v
```

**Проверка:**
- ✅ Тесты добавлены
- ✅ Все тесты проходят

---

## 🏁 Финализация (30 минут)

### Задача Ф.1: Обновить __init__.py файлы (10 мин)

**Действия:**
1. Обновить `app/infrastructure/persistence/mappers/__init__.py`
2. Обновить `app/infrastructure/persistence/repositories/__init__.py`

**Код:**
```python
# mappers/__init__.py
from .execution_plan_mapper import ExecutionPlanMapper

__all__ = [
    # ... существующие ...
    "ExecutionPlanMapper",
]

# repositories/__init__.py
from .execution_plan_repository_impl import ExecutionPlanRepositoryImpl

__all__ = [
    # ... существующие ...
    "ExecutionPlanRepositoryImpl",
]
```

---

### Задача Ф.2: Запустить все тесты (10 мин)

**Команды:**
```bash
cd codelab-ai-service/agent-runtime

# Запустить все unit тесты
pytest tests/unit/ -v

# Запустить тесты infrastructure
pytest tests/unit/infrastructure/ -v

# Проверить coverage
pytest tests/unit/infrastructure/ --cov=app/infrastructure --cov-report=term-missing
```

**Проверка:**
- ✅ Все unit тесты проходят
- ✅ Coverage > 85%

---

### Задача Ф.3: Проверить Docker (5 мин)

**Команды:**
```bash
cd codelab-ai-service

# Пересобрать контейнер
docker-compose build agent-runtime

# Запустить
docker-compose up agent-runtime

# Проверить логи
docker-compose logs agent-runtime | grep -i error
```

**Проверка:**
- ✅ Контейнер запускается
- ✅ Нет ошибок в логах

---

### Задача Ф.4: Создать отчет (5 мин)

**Действия:**
1. Создать файл `doc/agent-runtime-phase-10-2-report.md`
2. Заполнить результаты
3. Обновить `doc/agent-runtime-phase-10-progress.md`

**Шаблон отчета:**
```markdown
# 📊 Отчет о завершении Фазы 10.2

## Результаты
- ✅ ExecutionPlanMapper создан
- ✅ ExecutionPlanRepositoryImpl создан
- ✅ PlanMapper обновлен
- ✅ PlanRepositoryImpl обновлен
- ✅ Все тесты проходят

## Статистика
- Время: X часов
- Файлы: Y созданы, Z обновлены
- Тесты: N написано, все проходят
- Coverage: X%

## Коммиты
1. feat(infrastructure): Add ExecutionPlanMapper and repository
2. feat(infrastructure): Update PlanMapper for PlanId support
3. docs(agent-runtime): Add Phase 10.2 completion report
```

---

## 📊 Чеклист выполнения

### Подготовка
- [ ] Изучены существующие mappers
- [ ] Изучены domain entities
- [ ] Изучены database models

### Этап 1: ExecutionPlanMapper
- [ ] Файл создан
- [ ] to_entity() реализован
- [ ] to_model() реализован
- [ ] Тесты написаны (15+)
- [ ] Все тесты проходят

### Этап 2: ExecutionPlanRepositoryImpl
- [ ] Файл создан
- [ ] find_by_id() реализован
- [ ] find_by_conversation_id() реализован
- [ ] save() реализован
- [ ] delete() реализован
- [ ] Тесты написаны (20+)
- [ ] Все тесты проходят

### Этап 3: PlanMapper update
- [ ] PlanId поддержка добавлена
- [ ] Helper методы добавлены
- [ ] Тесты обновлены
- [ ] Все тесты проходят

### Этап 4: PlanRepositoryImpl update
- [ ] Snapshot методы добавлены
- [ ] Тесты обновлены
- [ ] Все тесты проходят

### Финализация
- [ ] __init__.py обновлены
- [ ] Все unit тесты проходят
- [ ] Docker работает
- [ ] Отчет создан
- [ ] Прогресс обновлен

---

## 🎯 Критерии приемки

- ✅ `ExecutionPlanMapper` создан и работает
- ✅ `ExecutionPlanRepositoryImpl` создан и работает
- ✅ `PlanMapper` обновлен
- ✅ `PlanRepositoryImpl` обновлен
- ✅ 40+ тестов написано и проходят
- ✅ Coverage > 85%
- ✅ Docker работает без ошибок
- ✅ Документация обновлена

---

## 🔗 Связанные документы

- [Анализ Infrastructure Layer](agent-runtime-phase-10-2-analysis.md)
- [Стратегия Фазы 10.2](agent-runtime-phase-10-2-strategy.md)
- [Прогресс Фазы 10](agent-runtime-phase-10-progress.md)

---

**Последнее обновление:** 6 февраля 2026, 19:25 UTC+3
