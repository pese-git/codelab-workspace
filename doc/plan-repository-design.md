# Plan Repository - Детальный технический дизайн

**Версия:** 1.0  
**Дата:** 30 января 2026

---

## 1. Обзор компонента

Plan Repository отвечает за персистентность планов в базе данных. Это критически важно для:
- Сохранения планов между запросами
- Отслеживания истории планов
- Восстановления прогресса после перезагрузки
- Интеграции с Session

---

## 2. Структура файлов

```
app/domain/repositories/
└── plan_repository.py                    # Интерфейс

app/infrastructure/persistence/models/
└── plan.py                               # SQLAlchemy модели

app/infrastructure/persistence/mappers/
└── plan_mapper.py                        # Domain ↔ DB маппер

app/infrastructure/persistence/repositories/
└── plan_repository_impl.py               # Реализация

alembic/versions/
└── 001_add_planning_system.py            # Миграция БД

tests/
└── test_plan_repository.py               # Тесты
```

---

## 3. Реализация компонента

### 3.1 SQLAlchemy модели

```python
# app/infrastructure/persistence/models/plan.py

from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
import uuid

from .base import Base

class PlanModel(Base):
    """SQLAlchemy модель для План"""
    __tablename__ = "plans"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    goal = Column(String(4096), nullable=False)
    status = Column(String(20), nullable=False, default="draft")  # draft, approved, in_progress, completed, failed
    current_subtask_id = Column(UUID(as_uuid=True), nullable=True)
    metadata = Column(JSON, nullable=False, default={})
    
    approved_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Индексы для производительности
    __table_args__ = (
        Index("idx_plans_session_id", "session_id"),
        Index("idx_plans_status", "status"),
        Index("idx_plans_created_at", "created_at"),
    )


class SubtaskModel(Base):
    """SQLAlchemy модель для Subtask"""
    __tablename__ = "subtasks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("plans.id"), nullable=False)
    
    description = Column(String(4096), nullable=False)
    agent = Column(String(20), nullable=False)  # orchestrator, coder, architect, debug, ask
    status = Column(String(20), nullable=False, default="pending")  # pending, running, done, failed, blocked
    
    dependencies = Column(JSON, nullable=False, default=[])  # массив UUID
    estimated_time = Column(String(50), nullable=True)
    
    result = Column(String(4096), nullable=True)
    error = Column(String(4096), nullable=True)
    
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Индексы
    __table_args__ = (
        Index("idx_subtasks_plan_id", "plan_id"),
        Index("idx_subtasks_status", "status"),
    )
```

### 3.2 PlanMapper

```python
# app/infrastructure/persistence/mappers/plan_mapper.py

from typing import List
from app.domain.entities.plan import Plan, Subtask, SubtaskStatus, PlanStatus
from app.infrastructure.persistence.models.plan import PlanModel, SubtaskModel
from datetime import datetime, timezone

class PlanMapper:
    """Маппер между доменными моделями и БД моделями"""
    
    @staticmethod
    def to_domain(plan_model: PlanModel, subtask_models: List[SubtaskModel]) -> Plan:
        """Преобразовать DB модель в доменную сущность"""
        
        # Маппировать subtasks
        subtasks = [
            Subtask(
                id=st.id,
                description=st.description,
                agent=st.agent,
                dependencies=st.dependencies,
                status=SubtaskStatus(st.status),
                estimated_time=st.estimated_time,
                result=st.result,
                error=st.error,
                started_at=st.started_at,
                completed_at=st.completed_at,
                metadata={},
                created_at=st.created_at,
                updated_at=st.updated_at,
            )
            for st in subtask_models
        ]
        
        # Создать Plan
        plan = Plan(
            id=plan_model.id,
            session_id=plan_model.session_id,
            goal=plan_model.goal,
            subtasks=subtasks,
            status=PlanStatus(plan_model.status),
            current_subtask_id=plan_model.current_subtask_id,
            metadata=plan_model.metadata or {},
            approved_at=plan_model.approved_at,
            started_at=plan_model.started_at,
            completed_at=plan_model.completed_at,
            created_at=plan_model.created_at,
            updated_at=plan_model.updated_at,
        )
        
        return plan
    
    @staticmethod
    def to_persistence(plan: Plan) -> tuple[PlanModel, List[SubtaskModel]]:
        """Преобразовать доменную сущность в DB модели"""
        
        plan_model = PlanModel(
            id=plan.id,
            session_id=plan.session_id,
            goal=plan.goal,
            status=plan.status.value,
            current_subtask_id=plan.current_subtask_id,
            metadata=plan.metadata,
            approved_at=plan.approved_at,
            started_at=plan.started_at,
            completed_at=plan.completed_at,
            created_at=plan.created_at,
            updated_at=datetime.now(timezone.utc),
        )
        
        subtask_models = [
            SubtaskModel(
                id=st.id,
                plan_id=plan.id,
                description=st.description,
                agent=st.agent.value,
                status=st.status.value,
                dependencies=st.dependencies,
                estimated_time=st.estimated_time,
                result=st.result,
                error=st.error,
                started_at=st.started_at,
                completed_at=st.completed_at,
                created_at=st.created_at,
                updated_at=datetime.now(timezone.utc),
            )
            for st in plan.subtasks
        ]
        
        return plan_model, subtask_models
```

### 3.3 PlanRepository интерфейс

```python
# app/domain/repositories/plan_repository.py

from abc import ABC, abstractmethod
from typing import Optional, List
from uuid import UUID
from app.domain.entities.plan import Plan

class PlanRepository(ABC):
    """Интерфейс репозитория планов"""
    
    @abstractmethod
    async def save(self, plan: Plan) -> None:
        """Сохранить план в БД"""
        pass
    
    @abstractmethod
    async def find_by_id(self, plan_id: UUID) -> Optional[Plan]:
        """Получить план по ID"""
        pass
    
    @abstractmethod
    async def find_by_session_id(self, session_id: UUID) -> Optional[Plan]:
        """Получить активный план для сессии"""
        pass
    
    @abstractmethod
    async def find_all_by_session_id(self, session_id: UUID, limit: int = 50) -> List[Plan]:
        """Получить все планы для сессии"""
        pass
    
    @abstractmethod
    async def delete(self, plan_id: UUID) -> None:
        """Удалить план"""
        pass
```

### 3.4 PlanRepositoryImpl

```python
# app/infrastructure/persistence/repositories/plan_repository_impl.py

import logging
from typing import Optional, List
from uuid import UUID
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.repositories.plan_repository import PlanRepository
from app.domain.entities.plan import Plan, PlanStatus
from app.infrastructure.persistence.models.plan import PlanModel, SubtaskModel
from app.infrastructure.persistence.mappers.plan_mapper import PlanMapper

logger = logging.getLogger("agent-runtime.plan_repository_impl")

class PlanRepositoryImpl(PlanRepository):
    """Реализация репозитория планов"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.mapper = PlanMapper()
    
    async def save(self, plan: Plan) -> None:
        """Сохранить или обновить план"""
        try:
            plan_model, subtask_models = self.mapper.to_persistence(plan)
            
            # Сохранить план
            self.session.add(plan_model)
            
            # Удалить старые subtasks и добавить новые
            await self.session.execute(
                select(SubtaskModel).where(SubtaskModel.plan_id == plan.id)
            )
            result = await self.session.execute(
                select(SubtaskModel).where(SubtaskModel.plan_id == plan.id)
            )
            old_subtasks = result.scalars().all()
            for old_st in old_subtasks:
                await self.session.delete(old_st)
            
            for subtask_model in subtask_models:
                self.session.add(subtask_model)
            
            await self.session.commit()
            
            logger.debug(f"Plan saved: plan_id={plan.id}, subtasks={len(subtask_models)}")
        
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to save plan: {e}", exc_info=True)
            raise
    
    async def find_by_id(self, plan_id: UUID) -> Optional[Plan]:
        """Получить план по ID"""
        try:
            result = await self.session.execute(
                select(PlanModel).where(PlanModel.id == plan_id)
            )
            plan_model = result.scalar_one_or_none()
            
            if not plan_model:
                return None
            
            # Получить subtasks
            result = await self.session.execute(
                select(SubtaskModel).where(SubtaskModel.plan_id == plan_id)
            )
            subtask_models = result.scalars().all()
            
            return self.mapper.to_domain(plan_model, subtask_models)
        
        except Exception as e:
            logger.error(f"Failed to find plan: {e}")
            raise
    
    async def find_by_session_id(self, session_id: UUID) -> Optional[Plan]:
        """Получить активный (последний) план для сессии"""
        try:
            result = await self.session.execute(
                select(PlanModel)
                .where(
                    and_(
                        PlanModel.session_id == session_id,
                        PlanModel.status.in_([PlanStatus.IN_PROGRESS.value, PlanStatus.APPROVED.value])
                    )
                )
                .order_by(PlanModel.created_at.desc())
                .limit(1)
            )
            plan_model = result.scalar_one_or_none()
            
            if not plan_model:
                return None
            
            # Получить subtasks
            result = await self.session.execute(
                select(SubtaskModel).where(SubtaskModel.plan_id == plan_model.id)
            )
            subtask_models = result.scalars().all()
            
            return self.mapper.to_domain(plan_model, subtask_models)
        
        except Exception as e:
            logger.error(f"Failed to find plan by session: {e}")
            raise
    
    async def find_all_by_session_id(self, session_id: UUID, limit: int = 50) -> List[Plan]:
        """Получить все планы для сессии"""
        try:
            result = await self.session.execute(
                select(PlanModel)
                .where(PlanModel.session_id == session_id)
                .order_by(PlanModel.created_at.desc())
                .limit(limit)
            )
            plan_models = result.scalars().all()
            
            plans = []
            for plan_model in plan_models:
                result = await self.session.execute(
                    select(SubtaskModel).where(SubtaskModel.plan_id == plan_model.id)
                )
                subtask_models = result.scalars().all()
                plans.append(self.mapper.to_domain(plan_model, subtask_models))
            
            return plans
        
        except Exception as e:
            logger.error(f"Failed to find plans: {e}")
            raise
    
    async def delete(self, plan_id: UUID) -> None:
        """Удалить план и его subtasks"""
        try:
            # Удалить subtasks
            await self.session.execute(
                delete(SubtaskModel).where(SubtaskModel.plan_id == plan_id)
            )
            
            # Удалить план
            await self.session.execute(
                delete(PlanModel).where(PlanModel.id == plan_id)
            )
            
            await self.session.commit()
            
            logger.debug(f"Plan deleted: plan_id={plan_id}")
        
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to delete plan: {e}")
            raise
```

### 3.5 Миграция Alembic

```python
# alembic/versions/001_add_planning_system.py

"""Add planning system tables

Revision ID: 001
Revises: 
Create Date: 2026-01-30

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers
revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    """Создать таблицы для системы планирования"""
    
    # Таблица планов
    op.create_table(
        'plans',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('goal', sa.String(4096), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('current_subtask_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Индексы для планов
    op.create_index('idx_plans_session_id', 'plans', ['session_id'])
    op.create_index('idx_plans_status', 'plans', ['status'])
    op.create_index('idx_plans_created_at', 'plans', ['created_at'])
    
    # Таблица подзадач
    op.create_table(
        'subtasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('plan_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('description', sa.String(4096), nullable=False),
        sa.Column('agent', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('dependencies', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('estimated_time', sa.String(50), nullable=True),
        sa.Column('result', sa.String(4096), nullable=True),
        sa.Column('error', sa.String(4096), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['plan_id'], ['plans.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Индексы для subtasks
    op.create_index('idx_subtasks_plan_id', 'subtasks', ['plan_id'])
    op.create_index('idx_subtasks_status', 'subtasks', ['status'])


def downgrade():
    """Удалить таблицы"""
    op.drop_index('idx_subtasks_status', table_name='subtasks')
    op.drop_index('idx_subtasks_plan_id', table_name='subtasks')
    op.drop_table('subtasks')
    
    op.drop_index('idx_plans_created_at', table_name='plans')
    op.drop_index('idx_plans_status', table_name='plans')
    op.drop_index('idx_plans_session_id', table_name='plans')
    op.drop_table('plans')
```

---

## 4. Интеграция с Session

```python
# Обновления для Session entity

class Session(Entity):
    """Расширенная Session с поддержкой планов"""
    
    # Существующие поля...
    
    # НОВЫЕ ПОЛЯ:
    current_plan_id: Optional[str] = None
    plan_history: List[str] = []  # История всех планов по ID
```

---

## 5. Тестовые сценарии

```python
# tests/test_plan_repository.py

@pytest.mark.asyncio
async def test_save_and_find_plan():
    """Тест сохранения и получения плана"""
    repo = create_test_repository()
    plan = create_test_plan()
    
    await repo.save(plan)
    found = await repo.find_by_id(plan.id)
    
    assert found is not None
    assert found.id == plan.id
    assert len(found.subtasks) == len(plan.subtasks)

@pytest.mark.asyncio
async def test_find_by_session_id():
    """Тест поиска плана по session_id"""
    repo = create_test_repository()
    plan = create_test_plan(session_id="session-1")
    await repo.save(plan)
    
    found = await repo.find_by_session_id("session-1")
    
    assert found is not None
    assert found.session_id == "session-1"

@pytest.mark.asyncio
async def test_find_all_by_session_id():
    """Тест получения всех планов для сессии"""
    repo = create_test_repository()
    session_id = "session-1"
    
    for i in range(5):
        plan = create_test_plan(session_id=session_id)
        await repo.save(plan)
    
    plans = await repo.find_all_by_session_id(session_id)
    
    assert len(plans) == 5

@pytest.mark.asyncio
async def test_delete_plan():
    """Тест удаления плана"""
    repo = create_test_repository()
    plan = create_test_plan()
    await repo.save(plan)
    
    await repo.delete(plan.id)
    
    found = await repo.find_by_id(plan.id)
    assert found is None
```

---

## 6. Критерии готовности

- [ ] SQLAlchemy модели созданы
- [ ] Миграция Alembic работает
- [ ] PlanMapper корректно преобразует данные
- [ ] Все методы репозитория реализованы
- [ ] CRUD операции работают
- [ ] Индексы создаются
- [ ] Integration тесты проходят
- [ ] Performance приемлемый (< 100ms для query)

---

**Статус:** 🟢 Готов к реализации
