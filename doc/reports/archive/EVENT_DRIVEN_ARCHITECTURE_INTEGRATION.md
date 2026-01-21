# Event-Driven Architecture в рефакторинге Agent Runtime

**Статус:** EDA остается и улучшается  
**Дата:** 18 января 2026

---

## ✅ Да, Event-Driven Architecture полностью сохраняется!

Event-Driven Architecture - это **ключевая архитектурная особенность** agent-runtime, которая не только останется, но и будет **улучшена** в процессе рефакторинга.

---

## 🎯 Что сохраняется

### 1. Event Bus (без изменений)
```
app/infrastructure/events/
├── bus.py                    # EventBus (из event_bus.py)
├── base_event.py            # BaseEvent
├── event_types.py           # EventType, EventCategory
└── subscribers/             # Все подписчики
    ├── metrics_collector.py
    ├── audit_logger.py
    ├── persistence_subscriber.py
    ├── agent_context_subscriber.py
    └── session_metrics_collector.py
```

**Изменения:** Только перемещение в `infrastructure/events/` для лучшей организации.

### 2. Все существующие события
- ✅ `AgentSwitchedEvent`
- ✅ `AgentProcessingStartedEvent`
- ✅ `AgentProcessingCompletedEvent`
- ✅ `SessionCreatedEvent`
- ✅ `SessionUpdatedEvent`
- ✅ `MessageAddedEvent`
- ✅ `ToolExecutedEvent`
- ✅ И все остальные...

### 3. Все подписчики
- ✅ MetricsCollector
- ✅ AuditLogger
- ✅ PersistenceSubscriber
- ✅ AgentContextSubscriber
- ✅ SessionMetricsCollector

---

## 🚀 Что улучшается

### 1. **Добавление Domain Events**

Текущие события слишком технические. Добавим **доменные события** для бизнес-логики.

#### Новая структура событий:

```
app/domain/events/              # NEW - Доменные события
├── base.py                     # DomainEvent
├── session_events.py           # Доменные события сессий
└── agent_events.py             # Доменные события агентов

app/infrastructure/events/      # EXISTING - Технические события
├── bus.py                      # EventBus
├── base_event.py              # BaseEvent (технические)
└── subscribers/               # Подписчики
```

#### Пример доменных событий:

**`app/domain/events/base.py`**
```python
from abc import ABC
from datetime import datetime
from typing import Any, Dict
from pydantic import BaseModel, Field

class DomainEvent(BaseModel, ABC):
    """
    Базовое доменное событие.
    
    Доменные события описывают то, что произошло в бизнес-логике,
    а не технические детали реализации.
    """
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: datetime = Field(default_factory=datetime.utcnow)
    aggregate_id: str  # ID сущности, с которой произошло событие
    
    class Config:
        frozen = True  # События неизменяемы
```

**`app/domain/events/session_events.py`**
```python
from .base import DomainEvent

class SessionCreated(DomainEvent):
    """Сессия создана"""
    session_id: str
    created_by: str = "system"

class MessageReceived(DomainEvent):
    """Получено сообщение от пользователя"""
    session_id: str
    message_content: str
    message_length: int

class ConversationCompleted(DomainEvent):
    """Разговор завершен"""
    session_id: str
    total_messages: int
    duration_seconds: float

class SessionExpired(DomainEvent):
    """Сессия истекла"""
    session_id: str
    reason: str
```

**`app/domain/events/agent_events.py`**
```python
from .base import DomainEvent

class AgentAssigned(DomainEvent):
    """Агент назначен на задачу"""
    session_id: str
    agent_type: str
    reason: str

class TaskCompleted(DomainEvent):
    """Задача выполнена агентом"""
    session_id: str
    agent_type: str
    success: bool
    result_summary: str

class AgentSwitchRequested(DomainEvent):
    """Запрошено переключение агента"""
    session_id: str
    from_agent: str
    to_agent: str
    reason: str
```

### 2. **Двухуровневая система событий**

```
┌─────────────────────────────────────────────────────┐
│                 Domain Layer                        │
│  ┌──────────────────────────────────────────────┐  │
│  │  Domain Events (бизнес-события)              │  │
│  │  - SessionCreated                            │  │
│  │  - MessageReceived                           │  │
│  │  - AgentAssigned                             │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
                        ↓
                   Event Bus
                        ↓
┌─────────────────────────────────────────────────────┐
│            Infrastructure Layer                     │
│  ┌──────────────────────────────────────────────┐  │
│  │  Infrastructure Events (технические)         │  │
│  │  - SessionCreatedEvent                       │  │
│  │  - SessionUpdatedEvent                       │  │
│  │  - AgentSwitchedEvent                        │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

**Преимущества:**
- **Domain Events** - описывают бизнес-логику (что произошло)
- **Infrastructure Events** - технические детали (как это реализовано)
- Можно подписываться на любой уровень

### 3. **Event Sourcing (опционально)**

Добавим возможность восстановления состояния из событий:

**`app/infrastructure/events/event_store.py`**
```python
from typing import List, Optional
from datetime import datetime

class EventStore:
    """
    Хранилище событий для Event Sourcing.
    
    Позволяет:
    - Сохранять все события
    - Восстанавливать состояние из событий
    - Проигрывать события заново (replay)
    """
    
    async def append(self, event: DomainEvent) -> None:
        """Добавить событие в хранилище"""
        pass
    
    async def get_events(
        self, 
        aggregate_id: str,
        from_version: int = 0
    ) -> List[DomainEvent]:
        """Получить все события для сущности"""
        pass
    
    async def replay_events(
        self,
        aggregate_id: str,
        until: Optional[datetime] = None
    ) -> Any:
        """Восстановить состояние из событий"""
        pass
```

### 4. **Улучшенная обработка ошибок**

**`app/infrastructure/events/error_handling.py`**
```python
from typing import Callable
import asyncio
import logging

logger = logging.getLogger(__name__)

class EventHandlerWithRetry:
    """Обработчик событий с retry механизмом"""
    
    def __init__(
        self,
        handler: Callable,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        self.handler = handler
        self.max_retries = max_retries
        self.retry_delay = retry_delay
    
    async def __call__(self, event):
        """Вызвать обработчик с retry"""
        for attempt in range(self.max_retries):
            try:
                return await self.handler(event)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    logger.error(
                        f"Handler {self.handler.__name__} failed after "
                        f"{self.max_retries} attempts: {e}"
                    )
                    # Отправить в Dead Letter Queue
                    await self._send_to_dlq(event, e)
                    raise
                
                logger.warning(
                    f"Handler {self.handler.__name__} failed (attempt "
                    f"{attempt + 1}/{self.max_retries}), retrying..."
                )
                await asyncio.sleep(self.retry_delay * (attempt + 1))
    
    async def _send_to_dlq(self, event, error):
        """Отправить событие в Dead Letter Queue"""
        # Реализация DLQ
        pass
```

**Использование:**
```python
# Регистрация обработчика с retry
@event_bus.subscribe(event_type=EventType.AGENT_SWITCHED)
@EventHandlerWithRetry(max_retries=3)
async def handle_agent_switch(event):
    # Обработка события
    pass
```

### 5. **Event Correlation и Tracing**

**`app/infrastructure/events/correlation.py`**
```python
import contextvars
from typing import Optional

# Context variable для correlation ID
correlation_id_var = contextvars.ContextVar('correlation_id', default=None)

class EventCorrelation:
    """Корреляция событий для трассировки"""
    
    @staticmethod
    def set_correlation_id(correlation_id: str):
        """Установить correlation ID для текущего контекста"""
        correlation_id_var.set(correlation_id)
    
    @staticmethod
    def get_correlation_id() -> Optional[str]:
        """Получить correlation ID текущего контекста"""
        return correlation_id_var.get()
    
    @staticmethod
    def create_correlation_id() -> str:
        """Создать новый correlation ID"""
        return str(uuid.uuid4())
```

**Использование в orchestrator:**
```python
# В multi_agent_orchestrator.py
async def process_message(self, session_id: str, message: str):
    # Создать correlation ID для трассировки
    correlation_id = EventCorrelation.create_correlation_id()
    EventCorrelation.set_correlation_id(correlation_id)
    
    # Все события будут иметь этот correlation_id
    await event_bus.publish(
        AgentProcessingStartedEvent(
            session_id=session_id,
            correlation_id=correlation_id  # Автоматически из контекста
        )
    )
```

---

## 🔄 Интеграция с новой архитектурой

### 1. **Domain Services публикуют Domain Events**

**`app/domain/services/session_management.py`**
```python
from ..events.session_events import SessionCreated, MessageReceived
from ...infrastructure.events.bus import event_bus

class SessionManagementService:
    """Доменный сервис управления сессиями"""
    
    async def create_session(self, session_id: str) -> Session:
        """Создать новую сессию"""
        session = Session(id=session_id, ...)
        await self._repository.save(session)
        
        # Публикуем доменное событие
        await event_bus.publish(
            SessionCreated(
                aggregate_id=session_id,
                session_id=session_id
            )
        )
        
        return session
    
    async def add_message(self, session_id: str, message: Message):
        """Добавить сообщение"""
        session = await self._repository.find_by_id(session_id)
        session.add_message(message)
        await self._repository.save(session)
        
        # Публикуем доменное событие
        await event_bus.publish(
            MessageReceived(
                aggregate_id=session_id,
                session_id=session_id,
                message_content=message.content,
                message_length=len(message.content)
            )
        )
```

### 2. **Infrastructure Subscribers слушают Domain Events**

**`app/infrastructure/events/subscribers/domain_event_subscriber.py`**
```python
from ....domain.events.session_events import SessionCreated, MessageReceived
from ..bus import event_bus

class DomainEventSubscriber:
    """Подписчик на доменные события"""
    
    def __init__(self):
        self._setup_subscriptions()
    
    def _setup_subscriptions(self):
        """Настроить подписки"""
        event_bus.subscribe(
            event_type=SessionCreated,
            handler=self._on_session_created
        )
        
        event_bus.subscribe(
            event_type=MessageReceived,
            handler=self._on_message_received
        )
    
    async def _on_session_created(self, event: SessionCreated):
        """Обработать создание сессии"""
        # Логирование, метрики, персистентность
        logger.info(f"Session created: {event.session_id}")
    
    async def _on_message_received(self, event: MessageReceived):
        """Обработать получение сообщения"""
        # Обновить метрики
        metrics.increment("messages_received")
```

### 3. **Command Handlers публикуют события**

**`app/application/commands/create_session.py`**
```python
from ...domain.events.session_events import SessionCreated
from ...infrastructure.events.bus import event_bus

class CreateSessionHandler:
    """Обработчик команды создания сессии"""
    
    async def handle(self, command: CreateSessionCommand) -> Session:
        """Обработать команду"""
        # Создать сессию через доменный сервис
        session = await self._service.create_session(command.session_id)
        
        # Доменный сервис уже опубликовал SessionCreated
        # Можем опубликовать дополнительные технические события
        await event_bus.publish(
            SessionCreatedEvent(  # Infrastructure event
                session_id=session.id,
                system_prompt=command.system_prompt
            )
        )
        
        return session
```

---

## 📊 Сравнение: До и После

### До рефакторинга:
```python
# Все в одном месте - смешаны уровни абстракции
await event_bus.publish(
    SessionCreatedEvent(
        session_id=session_id,
        system_prompt=system_prompt
    )
)
```

### После рефакторинга:
```python
# Domain Layer - бизнес-события
await event_bus.publish(
    SessionCreated(
        aggregate_id=session_id,
        session_id=session_id,
        created_by="user"
    )
)

# Infrastructure Layer - технические события
await event_bus.publish(
    SessionCreatedEvent(
        session_id=session_id,
        system_prompt=system_prompt
    )
)
```

---

## 🎯 Преимущества улучшенной EDA

### 1. **Четкое разделение ответственности**
- Domain Events - бизнес-логика
- Infrastructure Events - технические детали

### 2. **Лучшая тестируемость**
```python
# Тестирование доменной логики
async def test_session_creation():
    service = SessionManagementService(mock_repository)
    
    # Проверяем, что событие опубликовано
    with event_bus.capture_events() as events:
        await service.create_session("session-1")
        
        assert len(events) == 1
        assert isinstance(events[0], SessionCreated)
        assert events[0].session_id == "session-1"
```

### 3. **Event Sourcing возможности**
- Восстановление состояния из событий
- Аудит всех изменений
- Time-travel debugging

### 4. **Улучшенная observability**
- Correlation ID для трассировки
- Метрики по событиям
- Детальный аудит

### 5. **Retry и Error Handling**
- Автоматический retry для failed handlers
- Dead Letter Queue для проблемных событий
- Graceful degradation

---

## 🔧 Миграционный план для EDA

### Этап 1: Подготовка (1 день)
- [ ] Создать `app/domain/events/`
- [ ] Создать базовый `DomainEvent`
- [ ] Добавить `EventStore` (опционально)

### Этап 2: Создание Domain Events (2 дня)
- [ ] Создать доменные события для сессий
- [ ] Создать доменные события для агентов
- [ ] Создать доменные события для сообщений

### Этап 3: Интеграция (2 дня)
- [ ] Обновить Domain Services для публикации Domain Events
- [ ] Создать подписчики на Domain Events
- [ ] Добавить маппинг Domain → Infrastructure Events

### Этап 4: Улучшения (2 дня)
- [ ] Добавить retry механизм
- [ ] Добавить Dead Letter Queue
- [ ] Добавить Event Correlation
- [ ] Добавить Event Sourcing (опционально)

### Этап 5: Миграция существующих подписчиков (1 день)
- [ ] Обновить MetricsCollector
- [ ] Обновить AuditLogger
- [ ] Обновить PersistenceSubscriber
- [ ] Обновить AgentContextSubscriber

---

## ✅ Итоговая структура EDA

```
app/
├── domain/
│   └── events/                    # NEW - Доменные события
│       ├── base.py               # DomainEvent
│       ├── session_events.py     # SessionCreated, MessageReceived
│       └── agent_events.py       # AgentAssigned, TaskCompleted
│
├── infrastructure/
│   └── events/                    # REFACTORED - Технические события
│       ├── bus.py                # EventBus (из event_bus.py)
│       ├── base_event.py         # BaseEvent
│       ├── event_types.py        # EventType, EventCategory
│       ├── correlation.py        # NEW - Event correlation
│       ├── error_handling.py     # NEW - Retry, DLQ
│       ├── event_store.py        # NEW - Event Sourcing (опционально)
│       └── subscribers/          # EXISTING - Все подписчики
│           ├── metrics_collector.py
│           ├── audit_logger.py
│           ├── persistence_subscriber.py
│           ├── agent_context_subscriber.py
│           ├── session_metrics_collector.py
│           └── domain_event_subscriber.py  # NEW
│
└── application/
    └── event_handlers/            # NEW - Application-level handlers
        ├── session_event_handler.py
        └── agent_event_handler.py
```

---

## 🎉 Заключение

**Event-Driven Architecture не только сохраняется, но и значительно улучшается:**

✅ **Сохраняется:**
- Event Bus
- Все существующие события
- Все подписчики
- Метрики и аудит

✅ **Добавляется:**
- Domain Events (бизнес-уровень)
- Event Sourcing (опционально)
- Retry механизм
- Dead Letter Queue
- Event Correlation
- Улучшенная обработка ошибок

✅ **Улучшается:**
- Четкое разделение уровней
- Лучшая тестируемость
- Observability
- Надежность

**EDA остается ключевой архитектурной особенностью и становится еще мощнее!**

---

**Автор:** AI Assistant  
**Дата:** 18 января 2026  
**Версия:** 1.0
