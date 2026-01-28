# Анализ архитектуры Agent Runtime на ветке ref/event-drive

**Дата анализа:** 27 января 2026  
**Ветка:** ref/event-drive  
**Версия сервиса:** 0.3.0  
**Статус:** Production Ready ✅

---

## Оглавление

1. [Обзор](#обзор)
2. [Архитектурные принципы](#архитектурные-принципы)
3. [Структура проекта](#структура-проекта)
4. [Доменный слой (Domain Layer)](#доменный-слой-domain-layer)
5. [Инфраструктурный слой (Infrastructure Layer)](#инфраструктурный-слой-infrastructure-layer)
6. [Прикладной слой (Application Layer)](#прикладной-слой-application-layer)
7. [Слой представления (Presentation Layer)](#слой-представления-presentation-layer)
8. [Event-Driven Architecture](#event-driven-architecture)
9. [Мультиагентная система](#мультиагентная-система)
10. [Паттерны проектирования](#паттерны-проектирования)
11. [Ключевые отличия и особенности](#ключевые-отличия-и-особенности)
12. [Технологический стек](#технологический-стек)
13. [Выводы](#выводы)

---

## Обзор

Agent Runtime Service на ветке `ref/event-drive` представляет собой **полностью переработанную архитектуру** с применением современных паттернов проектирования и принципов Clean Architecture. Это микросервис на FastAPI, реализующий мультиагентную систему для AI-ассистента с поддержкой streaming, HITL (Human-in-the-Loop) и event-driven коммуникации.

### Ключевые характеристики

- **Архитектура:** Clean Architecture + DDD + Event-Driven
- **Паттерны:** Repository, CQRS, Event Sourcing (частично), Adapter, Strategy
- **Персистентность:** PostgreSQL/SQLite с async SQLAlchemy
- **Коммуникация:** Event Bus для внутренней коммуникации
- **Агенты:** 5 специализированных агентов + Orchestrator
- **Инструменты:** 9 реализованных инструментов с HITL поддержкой

---

## Архитектурные принципы

### 1. Clean Architecture

Проект строго следует принципам Clean Architecture с четким разделением на слои:

```
┌─────────────────────────────────────────────────────────┐
│                  Presentation Layer                      │
│              (API Routes, Middleware)                    │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                  Application Layer                       │
│           (Commands, Queries, Handlers, DTOs)            │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                    Domain Layer                          │
│    (Entities, Services, Repositories, Events)            │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                Infrastructure Layer                      │
│  (Persistence, Adapters, External Services, LLM)         │
└─────────────────────────────────────────────────────────┘
```

**Принципы:**
- Зависимости направлены внутрь (к доменному слою)
- Доменный слой не зависит от инфраструктуры
- Инверсия зависимостей через интерфейсы (Repository pattern)
- Изоляция бизнес-логики от технических деталей

### 2. Domain-Driven Design (DDD)

**Доменные сущности (Entities):**
- [`Session`](../codelab-ai-service/agent-runtime/app/domain/entities/session.py) - Сессия диалога с историей сообщений
- [`Message`](../codelab-ai-service/agent-runtime/app/domain/entities/message.py) - Сообщение в диалоге
- [`AgentContext`](../codelab-ai-service/agent-runtime/app/domain/entities/agent_context.py) - Контекст работы агента
- [`AgentSwitch`](../codelab-ai-service/agent-runtime/app/domain/entities/agent_context.py) - Запись о переключении агента
- [`Approval`](../codelab-ai-service/agent-runtime/app/domain/entities/approval.py) - Запрос на одобрение (HITL)

**Доменные сервисы:**
- [`SessionManagementService`](../codelab-ai-service/agent-runtime/app/domain/services/session_management.py) - Управление сессиями
- [`AgentOrchestrationService`](../codelab-ai-service/agent-runtime/app/domain/services/agent_orchestration.py) - Оркестрация агентов
- [`MessageOrchestrationService`](../codelab-ai-service/agent-runtime/app/domain/services/message_orchestration.py) - Оркестрация сообщений
- [`ApprovalManagementService`](../codelab-ai-service/agent-runtime/app/domain/services/approval_management.py) - Управление одобрениями

**Доменные события:**
- `SessionCreated`, `MessageReceived`, `SessionDeactivated`
- `AgentAssigned`, `AgentSwitched`, `TaskCompleted`
- `ApprovalRequested`, `ApprovalGranted`, `ApprovalRejected`

### 3. Event-Driven Architecture

Полностью реализованная event-driven архитектура с централизованной шиной событий:

**Компоненты:**
- [`EventBus`](../codelab-ai-service/agent-runtime/app/events/event_bus.py) - Централизованная шина событий (pub/sub)
- [`BaseEvent`](../codelab-ai-service/agent-runtime/app/events/base_event.py) - Базовый класс для всех событий
- [`EventType`](../codelab-ai-service/agent-runtime/app/events/event_types.py) - Типизированные события
- Подписчики: MetricsCollector, AuditLogger, AgentContextSubscriber

**Возможности:**
- Подписка по типу события или категории
- Wildcard подписки (все события)
- Приоритеты обработчиков
- Middleware для обработки событий
- Correlation ID для трейсинга
- Async обработка (fire-and-forget или wait-for-handlers)

---

## Структура проекта

```
app/
├── main.py                          # Точка входа FastAPI
├── core/                            # Ядро приложения
│   ├── config.py                   # Конфигурация
│   ├── dependencies.py             # Dependency Injection
│   └── errors/                     # Доменные и инфраструктурные ошибки
│       ├── base.py
│       ├── domain_errors.py
│       └── infrastructure_errors.py
│
├── domain/                          # Доменный слой (DDD)
│   ├── entities/                   # Доменные сущности
│   │   ├── base.py                # Базовая сущность
│   │   ├── session.py             # Сессия
│   │   ├── message.py             # Сообщение
│   │   ├── agent_context.py       # Контекст агента
│   │   ├── approval.py            # Одобрение (HITL)
│   │   └── hitl.py                # HITL состояние
│   │
│   ├── repositories/               # Интерфейсы репозиториев
│   │   ├── base.py                # Базовый репозиторий
│   │   ├── session_repository.py
│   │   ├── agent_context_repository.py
│   │   └── approval_repository.py
│   │
│   ├── services/                   # Доменные сервисы
│   │   ├── session_management.py
│   │   ├── agent_orchestration.py
│   │   ├── message_orchestration.py
│   │   ├── approval_management.py
│   │   ├── hitl_management.py
│   │   ├── agent_registry.py
│   │   └── tool_registry.py
│   │
│   └── events/                     # Доменные события
│       ├── base.py
│       ├── session_events.py
│       ├── agent_events.py
│       └── approval_events.py
│
├── application/                     # Прикладной слой (CQRS)
│   ├── commands/                   # Команды (изменение состояния)
│   │   ├── base.py
│   │   ├── create_session.py
│   │   ├── add_message.py
│   │   └── switch_agent.py
│   │
│   ├── queries/                    # Запросы (чтение данных)
│   │   ├── base.py
│   │   ├── get_session.py
│   │   ├── list_sessions.py
│   │   └── get_agent_context.py
│   │
│   └── dto/                        # Data Transfer Objects
│       ├── session_dto.py
│       ├── message_dto.py
│       └── agent_context_dto.py
│
├── infrastructure/                  # Инфраструктурный слой
│   ├── persistence/                # Персистентность
│   │   ├── database.py            # Конфигурация БД
│   │   ├── models/                # SQLAlchemy модели
│   │   │   ├── base.py
│   │   │   ├── session.py
│   │   │   ├── agent_context.py
│   │   │   └── hitl.py
│   │   │
│   │   ├── mappers/               # Маппинг Entity ↔ Model
│   │   │   ├── session_mapper.py
│   │   │   └── agent_context_mapper.py
│   │   │
│   │   └── repositories/          # Реализации репозиториев
│   │       ├── session_repository_impl.py
│   │       ├── agent_context_repository_impl.py
│   │       └── approval_repository_impl.py
│   │
│   ├── adapters/                   # Адаптеры для обратной совместимости
│   │   ├── session_manager_adapter.py
│   │   ├── agent_context_manager_adapter.py
│   │   └── event_publisher_adapter.py
│   │
│   ├── llm/                        # Интеграция с LLM
│   │   ├── client.py
│   │   ├── streaming.py
│   │   └── tool_parser.py
│   │
│   ├── concurrency/                # Управление конкурентностью
│   │   └── session_lock.py        # Блокировки сессий
│   │
│   ├── cleanup/                    # Сервисы очистки
│   │   └── session_cleanup.py
│   │
│   └── resilience/                 # Паттерны устойчивости
│       ├── circuit_breaker.py
│       └── retry_handler.py
│
├── events/                          # Event-Driven Architecture
│   ├── event_bus.py                # Шина событий
│   ├── base_event.py               # Базовое событие
│   ├── event_types.py              # Типы событий
│   ├── agent_events.py             # События агентов
│   ├── session_events.py           # События сессий
│   ├── tool_events.py              # События инструментов
│   ├── llm_events.py               # События LLM
│   │
│   └── subscribers/                # Подписчики событий
│       ├── metrics_collector.py
│       ├── audit_logger.py
│       ├── agent_context_subscriber.py
│       └── session_metrics_collector.py
│
├── agents/                          # Мультиагентная система
│   ├── base_agent.py               # Базовый класс агента
│   ├── orchestrator_agent.py       # Координатор
│   ├── coder_agent.py              # Разработчик
│   ├── architect_agent.py          # Архитектор
│   ├── debug_agent.py              # Отладчик
│   ├── ask_agent.py                # Консультант
│   ├── universal_agent.py          # Универсальный
│   │
│   └── prompts/                    # Системные промпты
│       ├── orchestrator.py
│       ├── coder.py
│       ├── architect.py
│       ├── debug.py
│       └── ask.py
│
├── api/                             # Слой представления (API)
│   ├── middleware/                 # Middleware
│   │   ├── internal_auth.py
│   │   └── rate_limit.py
│   │
│   └── v1/                         # API v1
│       ├── routers/                # Роутеры
│       │   ├── health_router.py
│       │   ├── sessions_router.py
│       │   ├── agents_router.py
│       │   ├── messages_router.py
│       │   └── events_router.py
│       │
│       └── schemas/                # Pydantic схемы для API
│           ├── session_schemas.py
│           ├── agent_schemas.py
│           ├── message_schemas.py
│           └── health_schemas.py
│
└── models/                          # Общие модели
    ├── schemas.py                  # StreamChunk и др.
    └── hitl_models.py              # HITL модели
```

---

## Доменный слой (Domain Layer)

### Сущности (Entities)

#### 1. Session (Сессия)

**Файл:** [`app/domain/entities/session.py`](../codelab-ai-service/agent-runtime/app/domain/entities/session.py)

**Ответственность:**
- Управление историей сообщений диалога
- Отслеживание активности сессии
- Валидация бизнес-правил (лимиты сообщений, активность)

**Ключевые методы:**
- `add_message(message)` - Добавить сообщение с валидацией
- `get_recent_messages(limit)` - Получить последние N сообщений
- `get_history_for_llm()` - Форматировать историю для LLM API
- `deactivate(reason)` - Деактивировать сессию
- `clear_messages()` - Очистить историю

**Бизнес-правила:**
- Максимум 1000 сообщений на сессию
- Неактивные сессии не принимают новые сообщения
- Автоматическая генерация заголовка из первого сообщения
- Обновление `last_activity` при каждом сообщении

#### 2. Message (Сообщение)

**Файл:** [`app/domain/entities/message.py`](../codelab-ai-service/agent-runtime/app/domain/entities/message.py)

**Ответственность:**
- Представление единицы коммуникации
- Поддержка различных ролей (user, assistant, system, tool)
- Поддержка tool calls и tool results

**Ключевые методы:**
- `to_llm_format()` - Преобразование в формат LLM API
- `from_llm_format(data)` - Создание из формата LLM API
- `is_user_message()`, `is_assistant_message()`, `is_tool_message()`
- `has_tool_calls()` - Проверка наличия вызовов инструментов

**Валидация:**
- Content обязателен для user, system, tool сообщений
- Content может быть пустым для assistant с tool_calls
- Поддержка tool_call_id для связи с результатами

#### 3. AgentContext (Контекст агента)

**Файл:** [`app/domain/entities/agent_context.py`](../codelab-ai-service/agent-runtime/app/domain/entities/agent_context.py)

**Ответственность:**
- Отслеживание текущего активного агента
- История переключений между агентами
- Защита от циклических переключений

**Ключевые методы:**
- `switch_to(target_agent, reason)` - Переключение агента с валидацией
- `can_switch_to(target_agent)` - Проверка возможности переключения
- `get_switch_history()` - История переключений
- `reset_to_orchestrator()` - Сброс к Orchestrator

**Бизнес-правила:**
- Нельзя переключиться на того же агента
- Максимум 50 переключений (защита от циклов)
- Каждое переключение записывается в историю
- Поддержка confidence level для LLM-based routing

#### 4. AgentSwitch (Переключение агента)

**Ответственность:**
- Запись о конкретном переключении агента
- Хранение метаданных переключения (причина, confidence, время)

**Поля:**
- `from_agent` - Исходный агент (может быть None для первого)
- `to_agent` - Целевой агент
- `reason` - Причина переключения
- `switched_at` - Время переключения
- `confidence` - Уровень уверенности (low/medium/high)

### Репозитории (Repository Interfaces)

#### Базовый репозиторий

**Файл:** [`app/domain/repositories/base.py`](../codelab-ai-service/agent-runtime/app/domain/repositories/base.py)

**Интерфейс:**
```python
class Repository(ABC, Generic[T]):
    async def get(id: str) -> Optional[T]
    async def save(entity: T) -> None
    async def delete(id: str) -> bool
    async def list(limit: int, offset: int) -> List[T]
    async def exists(id: str) -> bool
    async def count() -> int
```

**Специализированные репозитории:**
- `SessionRepository` - Дополнительные методы для сессий
  - `find_by_id(session_id)` - Поиск с загрузкой сообщений
  - `find_active(limit, offset)` - Активные сессии
  - `cleanup_old(max_age_hours)` - Очистка старых сессий
  
- `AgentContextRepository` - Методы для контекстов агентов
  - `find_by_session_id(session_id)` - Поиск по сессии
  - `get_agent_usage_stats()` - Статистика использования агентов

- `ApprovalRepository` - Методы для HITL одобрений
  - `find_pending_by_session(session_id)` - Pending одобрения
  - `find_by_request_id(request_id)` - Поиск по ID запроса

### Доменные сервисы

#### 1. SessionManagementService

**Файл:** [`app/domain/services/session_management.py`](../codelab-ai-service/agent-runtime/app/domain/services/session_management.py)

**Ответственность:**
- Координация операций с сессиями
- Публикация доменных событий
- Инкапсуляция бизнес-логики

**Ключевые методы:**
```python
async def create_session(session_id: Optional[str]) -> Session
async def get_session(session_id: str) -> Session
async def get_or_create_session(session_id: str) -> Session
async def add_message(session_id, role, content, ...) -> Message
async def add_tool_result(session_id, call_id, result, error) -> Message
async def deactivate_session(session_id, reason) -> Session
async def list_active_sessions(limit, offset) -> List[Session]
async def cleanup_old_sessions(max_age_hours) -> int
```

**События:**
- `SessionCreated` - При создании сессии
- `MessageReceived` - При добавлении сообщения
- `SessionDeactivated` - При деактивации

#### 2. AgentOrchestrationService

**Файл:** [`app/domain/services/agent_orchestration.py`](../codelab-ai-service/agent-runtime/app/domain/services/agent_orchestration.py)

**Ответственность:**
- Управление переключением агентов
- Создание и получение контекстов агентов
- Публикация событий переключения

**Ключевые методы:**
```python
async def get_or_create_context(session_id, initial_agent) -> AgentContext
async def switch_agent(session_id, target_agent, reason, confidence) -> AgentContext
async def get_current_agent(session_id) -> Optional[AgentType]
async def get_agent_usage_stats() -> dict
```

**События:**
- `AgentAssigned` - При назначении агента
- `AgentSwitchRequested` - При запросе переключения
- `AgentSwitched` - При успешном переключении

#### 3. MessageOrchestrationService

**Файл:** [`app/domain/services/message_orchestration.py`](../codelab-ai-service/agent-runtime/app/domain/services/message_orchestration.py)

**Ответственность:**
- Координация обработки сообщений через мульти-агентную систему
- Управление streaming ответов
- Обработка переключений агентов
- Обработка tool results и HITL решений

**Ключевые методы:**
```python
async def process_message(session_id, message, agent_type) -> AsyncGenerator[StreamChunk]
async def process_tool_result(session_id, call_id, result, error) -> AsyncGenerator[StreamChunk]
async def process_hitl_decision(session_id, call_id, decision, ...) -> AsyncGenerator[StreamChunk]
async def switch_agent(session_id, agent_type, reason) -> AsyncGenerator[StreamChunk]
async def get_current_agent(session_id) -> Optional[AgentType]
```

**Особенности:**
- Использует `SessionLockManager` для предотвращения race conditions
- Поддерживает автоматическое переключение агентов через Orchestrator
- Обрабатывает switch_agent chunks от агентов
- Добавляет tool_result для switch_mode в историю

---

## Инфраструктурный слой (Infrastructure Layer)

### Персистентность (Persistence)

#### SQLAlchemy модели

**Файл:** [`app/infrastructure/persistence/models/`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/models/)

**Модели:**
- `SessionModel` - Таблица sessions
- `MessageModel` - Таблица messages (связь с SessionModel)
- `AgentContextModel` - Таблица agent_contexts
- `AgentSwitchModel` - Таблица agent_switches
- `ApprovalModel` - Таблица approvals (HITL)

**Особенности:**
- Async SQLAlchemy (asyncpg для PostgreSQL, aiosqlite для SQLite)
- Soft delete (deleted_at поле)
- Timestamps (created_at, updated_at)
- Relationships с lazy loading

#### Mappers (Маппинг Entity ↔ Model)

**Файл:** [`app/infrastructure/persistence/mappers/`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/mappers/)

**Ответственность:**
- Преобразование доменных сущностей в модели БД и обратно
- Изоляция доменного слоя от деталей персистентности

**Пример:**
```python
class SessionMapper:
    async def to_entity(model: SessionModel, db: AsyncSession, load_messages: bool) -> Session
    async def to_model(entity: Session, db: AsyncSession) -> SessionModel
```

#### Реализации репозиториев

**Файл:** [`app/infrastructure/persistence/repositories/session_repository_impl.py`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/repositories/session_repository_impl.py)

**Особенности:**
- Реализация интерфейсов из доменного слоя
- Использование mappers для преобразований
- Оптимизация запросов (lazy loading, batch operations)
- Обработка ошибок с преобразованием в доменные исключения

**Пример:**
```python
class SessionRepositoryImpl(SessionRepository):
    def __init__(self, db: AsyncSession):
        self._db = db
        self._mapper = SessionMapper()
    
    async def find_by_id(self, session_id: str) -> Optional[Session]:
        # Получить модель из БД
        result = await self._db.execute(
            select(SessionModel).where(SessionModel.id == session_id)
        )
        model = result.scalar_one_or_none()
        
        # Преобразовать в сущность
        return await self._mapper.to_entity(model, self._db, load_messages=True)
```

### Адаптеры (Adapters)

**Файл:** [`app/infrastructure/adapters/`](../codelab-ai-service/agent-runtime/app/infrastructure/adapters/)

**Назначение:**
- Обеспечение обратной совместимости со старым кодом
- Адаптация новых доменных сервисов к старым интерфейсам

**Адаптеры:**
- `SessionManagerAdapter` - Адаптирует SessionManagementService
- `AgentContextManagerAdapter` - Адаптирует AgentOrchestrationService
- `EventPublisherAdapter` - Адаптирует EventBus для доменных событий

### LLM Integration

**Файл:** [`app/infrastructure/llm/`](../codelab-ai-service/agent-runtime/app/infrastructure/llm/)

**Компоненты:**
- `LLMClient` - Клиент для взаимодействия с LLM Proxy
- `LLMStreamService` - Сервис для streaming ответов
- `ToolParser` - Парсинг tool calls из LLM ответов

**Особенности:**
- Async streaming через httpx
- Обработка SSE (Server-Sent Events)
- Парсинг tool calls в реальном времени
- Retry механизмы

### Concurrency (Управление конкурентностью)

**Файл:** [`app/infrastructure/concurrency/session_lock.py`](../codelab-ai-service/agent-runtime/app/infrastructure/concurrency/session_lock.py)

**SessionLockManager:**
- Предотвращение race conditions при параллельной обработке
- Блокировки на уровне сессий
- Async context manager для удобного использования

```python
async with session_lock_manager.lock(session_id):
    # Критическая секция - только один поток может обрабатывать сессию
    await process_message(session_id, message)
```

### Resilience (Паттерны устойчивости)

**Файл:** [`app/infrastructure/resilience/`](../codelab-ai-service/agent-runtime/app/infrastructure/resilience/)

**Компоненты:**
- `CircuitBreaker` - Защита от каскадных сбоев
- `RetryHandler` - Повторные попытки с exponential backoff

---

## Прикладной слой (Application Layer)

### CQRS Pattern

Строгое разделение команд (изменение состояния) и запросов (чтение данных).

#### Commands (Команды)

**Файл:** [`app/application/commands/`](../codelab-ai-service/agent-runtime/app/application/commands/)

**Базовый класс:**
```python
class Command(BaseModel, ABC):
    class Config:
        frozen = True  # Неизменяемость
```

**Реализованные команды:**
- `CreateSessionCommand` - Создание сессии
- `AddMessageCommand` - Добавление сообщения
- `SwitchAgentCommand` - Переключение агента

**Command Handlers:**
```python
class CreateSessionHandler(CommandHandler[Session]):
    def __init__(self, service: SessionManagementService):
        self._service = service
    
    async def handle(self, command: CreateSessionCommand) -> Session:
        return await self._service.create_session(command.session_id)
```

#### Queries (Запросы)

**Файл:** [`app/application/queries/`](../codelab-ai-service/agent-runtime/app/application/queries/)

**Базовый класс:**
```python
class Query(BaseModel, ABC):
    class Config:
        frozen = True  # Неизменяемость
```

**Реализованные запросы:**
- `GetSessionQuery` - Получение сессии
- `ListSessionsQuery` - Список сессий
- `GetAgentContextQuery` - Получение контекста агента

**Query Handlers:**
```python
class GetSessionHandler(QueryHandler[SessionDTO]):
    def __init__(self, repository: SessionRepository):
        self._repository = repository
    
    async def handle(self, query: GetSessionQuery) -> SessionDTO:
        session = await self._repository.find_by_id(query.session_id)
        return SessionDTO.from_entity(session)
```

### DTOs (Data Transfer Objects)

**Файл:** [`app/application/dto/`](../codelab-ai-service/agent-runtime/app/application/dto/)

**Назначение:**
- Передача данных между слоями
- Изоляция внутренних структур от внешних API
- Валидация через Pydantic

**Примеры:**
- `SessionDTO` - DTO для сессии
- `MessageDTO` - DTO для сообщения
- `AgentContextDTO` - DTO для контекста агента

---

## Слой представления (Presentation Layer)

### API Routers

**Файл:** [`app/api/v1/routers/`](../codelab-ai-service/agent-runtime/app/api/v1/routers/)

**Роутеры:**
- `health_router.py` - Health check endpoints
- `sessions_router.py` - CRUD операции с сессиями
- `agents_router.py` - Информация об агентах
- `messages_router.py` - Обработка сообщений (streaming)
- `events_router.py` - Метрики и audit log

**Особенности:**
- Dependency Injection через FastAPI Depends
- Валидация через Pydantic schemas
- SSE streaming для real-time ответов
- Обработка ошибок с правильными HTTP статусами

### Middleware

**Файл:** [`app/api/middleware/`](../codelab-ai-service/agent-runtime/app/api/middleware/)

**Middleware:**
- `InternalAuthMiddleware` - Проверка X-Internal-Auth заголовка
- `RateLimitMiddleware` - Rate limiting (60 req/min)

### API Schemas

**Файл:** [`app/api/v1/schemas/`](../codelab-ai-service/agent-runtime/app/api/v1/schemas/)

**Pydantic схемы для API:**
- Request/Response модели для каждого endpoint
- Валидация входных данных
- Автоматическая генерация OpenAPI документации

---

## Event-Driven Architecture

### EventBus (Шина событий)

**Файл:** [`app/events/event_bus.py`](../codelab-ai-service/agent-runtime/app/events/event_bus.py)

**Возможности:**
- **Pub/Sub паттерн** - Издатели и подписчики слабо связаны
- **Подписка по типу** - `event_bus.subscribe(event_type=EventType.AGENT_SWITCHED)`
- **Подписка по категории** - `event_bus.subscribe(event_category=EventCategory.AGENT)`
- **Wildcard подписки** - Получение всех событий
- **Приоритеты** - Обработчики выполняются по приоритету (10 = высокий, 0 = низкий)
- **Middleware** - Обработка/фильтрация событий перед доставкой
- **Async обработка** - Fire-and-forget или wait-for-handlers
- **Статистика** - Метрики публикаций и обработчиков

**Пример использования:**
```python
# Подписка на событие
@event_bus.subscribe(event_type=EventType.AGENT_SWITCHED, priority=10)
async def on_agent_switched(event: BaseEvent):
    logger.info(f"Agent switched: {event.data}")

# Публикация события
await event_bus.publish(
    AgentSwitchedEvent(
        session_id="session-123",
        from_agent="orchestrator",
        to_agent="coder",
        reason="Coding task detected"
    ),
    wait_for_handlers=True
)
```

### Типы событий

**Файл:** [`app/events/event_types.py`](../codelab-ai-service/agent-runtime/app/events/event_types.py)

**Категории:**
- `EventCategory.AGENT` - События агентов
- `EventCategory.SESSION` - События сессий
- `EventCategory.TOOL` - События инструментов
- `EventCategory.HITL` - HITL события
- `EventCategory.SYSTEM` - Системные события
- `EventCategory.METRICS` - События метрик

**Конкретные типы:**
- `AGENT_SWITCHED`, `AGENT_PROCESSING_STARTED`, `AGENT_PROCESSING_COMPLETED`
- `SESSION_CREATED`, `MESSAGE_ADDED`, `SESSION_DEACTIVATED`
- `TOOL_EXECUTION_REQUESTED`, `TOOL_APPROVAL_REQUIRED`
- `HITL_DECISION_MADE`
- `SYSTEM_STARTUP`, `SYSTEM_SHUTDOWN`

### Подписчики (Subscribers)

**Файл:** [`app/events/subscribers/`](../codelab-ai-service/agent-runtime/app/events/subscribers/)

#### 1. MetricsCollector

**Ответственность:**
- Сбор метрик из событий
- Статистика переключений агентов
- Метрики выполнения инструментов
- HITL решения

**Собираемые метрики:**
```python
{
    "agent_switches": {
        "orchestrator_to_coder": 15,
        "coder_to_debug": 3
    },
    "agent_processing": {
        "coder": {
            "count": 20,
            "total_duration_ms": 30000,
            "success_count": 18,
            "failure_count": 2
        }
    },
    "tool_executions": {
        "write_file": {
            "requested": 10,
            "completed": 8,
            "failed": 2
        }
    },
    "hitl_decisions": {
        "write_file": {
            "APPROVE": 7,
            "EDIT": 2,
            "REJECT": 1
        }
    }
}
```

#### 2. AuditLogger

**Ответственность:**
- Логирование критичных событий для аудита
- Хранение истории операций
- Поддержка фильтрации по сессии и типу события

**Логируемые события:**
- Переключения агентов
- HITL решения
- Ошибки агентов
- Требования approval

#### 3. AgentContextSubscriber

**Ответственность:**
- Автоматическое обновление контекста агента при событиях
- Синхронизация состояния

#### 4. SessionMetricsCollector

**Ответственность:**
- Сбор метрик на уровне сессий
- Статистика активности сессий
- Мониторинг производительности

### Correlation ID и трейсинг

**Особенности:**
- Каждое событие имеет `correlation_id` для трейсинга связанных операций
- `causation_id` для отслеживания причинно-следственных связей
- Полная история операций для debugging

---

## Мультиагентная система

### Архитектура агентов

**Базовый класс:** [`app/agents/base_agent.py`](../codelab-ai-service/agent-runtime/app/agents/base_agent.py)

**Интерфейс:**
```python
class BaseAgent(ABC):
    def __init__(self, agent_type, system_prompt, allowed_tools, file_restrictions):
        pass
    
    @abstractmethod
    async def process(self, session_id, message, context, session, session_service) -> AsyncGenerator:
        pass
    
    def can_use_tool(self, tool_name: str) -> bool
    def can_edit_file(self, file_path: str) -> bool
```

### Специализированные агенты

#### 1. Orchestrator Agent 🎭

**Файл:** [`app/agents/orchestrator_agent.py`](../codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py)

**Роль:** Координатор и маршрутизатор задач

**Возможности:**
- LLM-based routing с fallback на ключевые слова
- Анализ задачи и выбор подходящего агента
- Только read-only инструменты (read_file, list_files, search_in_code)

**Инструменты:** 3 (только чтение)

**Логика маршрутизации:**
1. Анализ сообщения пользователя через LLM
2. Определение типа задачи
3. Выбор агента с confidence level
4. Возврат switch_agent chunk

#### 2. Coder Agent 💻

**Файл:** [`app/agents/coder_agent.py`](../codelab-ai-service/agent-runtime/app/agents/coder_agent.py)

**Роль:** Разработчик кода

**Возможности:**
- Полный доступ ко всем инструментам (9 инструментов)
- Написание и модификация кода
- Выполнение команд
- Применение diff патчей

**Инструменты:** Все 9 инструментов

**Ограничения:** Нет

#### 3. Architect Agent 🏗️

**Файл:** [`app/agents/architect_agent.py`](../codelab-ai-service/agent-runtime/app/agents/architect_agent.py)

**Роль:** Архитектор и проектировщик

**Возможности:**
- Проектирование архитектуры
- Написание документации
- Создание планов

**Инструменты:** read_file, write_file, list_files, search_in_code

**Ограничения:** Может редактировать только `.md` файлы

#### 4. Debug Agent 🐛

**Файл:** [`app/agents/debug_agent.py`](../codelab-ai-service/agent-runtime/app/agents/debug_agent.py)

**Роль:** Отладчик и исследователь

**Возможности:**
- Анализ кода и поиск ошибок
- Выполнение диагностических команд
- Исследование проекта

**Инструменты:** read_file, list_files, search_in_code, execute_command

**Ограничения:** Без write_file (read-only для файлов)

#### 5. Ask Agent 💬

**Файл:** [`app/agents/ask_agent.py`](../codelab-ai-service/agent-runtime/app/agents/ask_agent.py)

**Роль:** Консультант и помощник

**Возможности:**
- Ответы на вопросы
- Объяснение кода
- Консультации

**Инструменты:** read_file, search_in_code, list_files

**Ограничения:** Только чтение

### Agent Registry

**Файл:** [`app/domain/services/agent_registry.py`](../codelab-ai-service/agent-runtime/app/domain/services/agent_registry.py)

**Ответственность:**
- Регистрация и получение экземпляров агентов
- Singleton паттерн для агентов
- Маршрутизация к нужному агенту

**Использование:**
```python
from app.domain.services.agent_registry import agent_router

# Получить агента
coder = agent_router.get_agent(AgentType.CODER)

# Обработать сообщение
async for chunk in coder.process(session_id, message, context, session, session_service):
    yield chunk
```

### Tool Registry

**Файл:** [`app/domain/services/tool_registry.py`](../codelab-ai-service/agent-runtime/app/domain/services/tool_registry.py)

**Реализованные инструменты:**
1. `read_file` - Чтение файла
2. `write_file` - Запись файла (требует HITL approval)
3. `list_files` - Список файлов в директории
4. `search_in_code` - Поиск по коду (regex)
5. `execute_command` - Выполнение команды (требует HITL approval)
6. `apply_diff` - Применение diff патча
7. `ask_followup_question` - Вопрос пользователю
8. `attempt_completion` - Завершение задачи
9. `switch_mode` - Переключение режима/агента

**HITL (Human-in-the-Loop):**
- Опасные операции требуют одобрения пользователя
- `write_file`, `execute_command` - всегда требуют approval
- Пользователь может: approve, edit, reject
- Поддержка feedback при rejection

---

## Паттерны проектирования

### 1. Repository Pattern

**Назначение:** Абстракция доступа к данным

**Реализация:**
- Интерфейсы в доменном слое
- Реализации в инфраструктурном слое
- Изоляция доменной логики от деталей персистентности

### 2. CQRS (Command Query Responsibility Segregation)

**Назначение:** Разделение операций чтения и записи

**Реализация:**
- Commands для изменения состояния
- Queries для чтения данных
- Отдельные handlers для каждого типа

### 3. Event Sourcing (частично)

**Назначение:** Хранение истории изменений через события

**Реализация:**
- Все важные операции публикуют события
- События хранятся в audit log
- Возможность replay событий (в будущем)

### 4. Adapter Pattern

**Назначение:** Адаптация интерфейсов для обратной совместимости

**Реализация:**
- SessionManagerAdapter
- AgentContextManagerAdapter
- EventPublisherAdapter

### 5. Strategy Pattern

**Назначение:** Выбор алгоритма во время выполнения

**Реализация:**
- Различные агенты как стратегии обработки
- AgentRouter для выбора стратегии

### 6. Observer Pattern

**Назначение:** Уведомление о изменениях состояния

**Реализация:**
- EventBus как Subject
- Subscribers как Observers

### 7. Dependency Injection

**Назначение:** Инверсия зависимостей

**Реализация:**
- FastAPI Depends для DI
- Централизованный [`dependencies.py`](../codelab-ai-service/agent-runtime/app/core/dependencies.py)
- Request-scoped зависимости

### 8. Circuit Breaker

**Назначение:** Защита от каскадных сбоев

**Реализация:**
- CircuitBreaker для внешних сервисов
- Автоматическое открытие при ошибках
- Постепенное восстановление

### 9. Retry Pattern

**Назначение:** Повторные попытки при временных сбоях

**Реализация:**
- RetryHandler с exponential backoff
- Настраиваемое количество попыток
- Обработка специфичных исключений

---

## Ключевые отличия и особенности

### 1. Полная Clean Architecture

**Отличие от стандартной структуры:**
- Строгое разделение на 4 слоя (Domain, Application, Infrastructure, Presentation)
- Зависимости направлены внутрь (к доменному слою)
- Доменный слой полностью изолирован от инфраструктуры
- Использование интерфейсов (Repository) для инверсии зависимостей

**Преимущества:**
- Легкость тестирования (mock репозиториев)
- Независимость от фреймворков и БД
- Возможность замены инфраструктуры без изменения бизнес-логики

### 2. Event-Driven Architecture

**Отличие:**
- Централизованная шина событий (EventBus)
- Все важные операции публикуют события
- Слабая связанность компонентов через события
- Подписчики для метрик, аудита, синхронизации

**Преимущества:**
- Observability - полная история операций
- Расширяемость - легко добавлять новые подписчики
- Масштабируемость - готовность к distributed events (Redis Pub/Sub)

### 3. CQRS Pattern

**Отличие:**
- Строгое разделение Commands и Queries
- Отдельные handlers для каждого типа операции
- Оптимизация чтения и записи независимо

**Преимущества:**
- Четкое разделение ответственности
- Оптимизация производительности
- Упрощение тестирования

### 4. Domain-Driven Design

**Отличие:**
- Богатые доменные сущности с бизнес-логикой
- Доменные сервисы для сложной логики
- Доменные события для коммуникации
- Ubiquitous Language в коде

**Преимущества:**
- Бизнес-логика в одном месте
- Легкость понимания и поддержки
- Соответствие бизнес-требованиям

### 5. Async/Await везде

**Отличие:**
- Полностью асинхронный код
- Async SQLAlchemy
- Async event handlers
- Async streaming

**Преимущества:**
- Высокая производительность
- Эффективное использование ресурсов
- Поддержка большого количества одновременных соединений

### 6. Request-scoped Dependencies

**Отличие:**
- Database session создается для каждого запроса
- Автоматический commit/rollback
- Изоляция транзакций

**Преимущества:**
- Предотвращение утечек соединений
- Правильная обработка транзакций
- Thread-safety

### 7. Mappers для изоляции

**Отличие:**
- Отдельные mappers для преобразования Entity ↔ Model
- Доменные сущности не знают о БД
- SQLAlchemy модели не используются в доменном слое

**Преимущества:**
- Полная изоляция слоев
- Возможность изменения схемы БД без изменения доменных сущностей
- Легкость миграции на другую БД

### 8. Session Locking

**Отличие:**
- Блокировки на уровне сессий для предотвращения race conditions
- Async context manager для удобства
- Защита от параллельной обработки одной сессии

**Преимущества:**
- Консистентность данных
- Предотвращение конфликтов
- Правильная обработка параллельных запросов

### 9. Correlation ID для трейсинга

**Отличие:**
- Каждая операция имеет correlation_id
- Связанные события имеют одинаковый correlation_id
- Полная история операций для debugging

**Преимущества:**
- Легкость отладки
- Трейсинг распределенных операций
- Мониторинг и аналитика

### 10. Resilience Patterns

**Отличие:**
- Circuit Breaker для защиты от сбоев
- Retry с exponential backoff
- Graceful degradation

**Преимущества:**
- Устойчивость к сбоям
- Быстрое восстановление
- Предотвращение каскадных сбоев

---

## Технологический стек

### Backend Framework
- **FastAPI 0.104.1** - Современный async web framework
- **Uvicorn 0.24.0** - ASGI сервер
- **Pydantic 2.5.1** - Валидация данных

### Database
- **SQLAlchemy 2.0+** - ORM с async поддержкой
- **asyncpg 0.29.0** - Async PostgreSQL драйвер
- **aiosqlite 0.19.0** - Async SQLite драйвер
- **psycopg2-binary 2.9.9** - PostgreSQL адаптер

### LLM Integration
- **langchain 0.2.5+** - LLM фреймворк
- **smolagents 1.23.0+** - Agent framework
- **httpx 0.25.1** - Async HTTP клиент

### Event Streaming
- **sse-starlette 1.6.5** - Server-Sent Events для streaming

### Resilience
- **tenacity 8.2.3** - Retry механизмы

### Monitoring
- **structlog 24.1.0** - Структурированное логирование
- **prometheus-client 0.19.0** - Метрики для Prometheus

### Security
- **slowapi 0.1.9** - Rate limiting

### Development
- **pytest 9.0.2** - Тестирование
- **pytest-asyncio 1.3.0** - Async тесты
- **pytest-cov 7.0.0** - Coverage
- **ruff 0.14.8** - Linting и форматирование

---

## Выводы

### Сильные стороны архитектуры

1. **Чистая архитектура**
   - Четкое разделение ответственности
   - Легкость тестирования и поддержки
   - Независимость от фреймворков

2. **Event-Driven подход**
   - Слабая связанность компонентов
   - Отличная observability
   - Готовность к масштабированию

3. **Domain-Driven Design**
   - Бизнес-логика в центре
   - Богатые доменные модели
   - Ubiquitous Language

4. **CQRS Pattern**
   - Оптимизация чтения и записи
   - Четкое разделение операций
   - Упрощение кода

5. **Мультиагентная система**
   - Специализация агентов
   - Гибкая маршрутизация
   - Расширяемость

6. **Resilience Patterns**
   - Устойчивость к сбоям
   - Graceful degradation
   - Мониторинг и метрики

### Области для улучшения

1. **Event Store**
   - Сейчас события только в памяти (audit log)
   - Можно добавить персистентность событий в БД
   - Возможность replay событий

2. **Distributed Event Bus**
   - Текущий EventBus работает только в одном процессе
   - Для горизонтального масштабирования нужен Redis Pub/Sub
   - Поддержка distributed tracing

3. **Saga Pattern**
   - Для сложных распределенных транзакций
   - Координация между микросервисами
   - Компенсирующие транзакции

4. **Caching Layer**
   - Кэширование часто запрашиваемых данных
   - Redis для distributed cache
   - Cache invalidation через события

5. **API Versioning**
   - Сейчас только v1
   - Стратегия версионирования API
   - Backward compatibility

### Рекомендации

1. **Документация**
   - Отличная документация в коде
   - Можно добавить API документацию (Swagger UI уже есть)
   - Диаграммы архитектуры

2. **Тестирование**
   - Добавить больше integration тестов
   - E2E тесты для критичных сценариев
   - Performance тесты

3. **Мониторинг**
   - Интеграция с Prometheus/Grafana
   - Distributed tracing (Jaeger/Zipkin)
   - Alerting

4. **CI/CD**
   - Автоматические тесты
   - Автоматический деплой
   - Canary deployments

### Итоговая оценка

**Архитектура ветки ref/event-drive представляет собой образцовую реализацию современных паттернов проектирования:**

✅ **Clean Architecture** - Строгое разделение слоев  
✅ **DDD** - Богатые доменные модели  
✅ **Event-Driven** - Слабая связанность через события  
✅ **CQRS** - Разделение команд и запросов  
✅ **Repository Pattern** - Абстракция персистентности  
✅ **Dependency Injection** - Инверсия зависимостей  
✅ **Async/Await** - Высокая производительность  
✅ **Resilience Patterns** - Устойчивость к сбоям  
✅ **Observability** - Метрики, логи, трейсинг  
✅ **Testability** - Легкость тестирования  

**Статус:** Production Ready ✅

Архитектура готова к production использованию и может служить эталоном для других микросервисов проекта.

---

**Автор анализа:** AI Assistant  
**Дата:** 27 января 2026  
**Версия документа:** 1.0
