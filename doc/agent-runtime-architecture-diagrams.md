# Диаграммы архитектуры Agent Runtime
## Сравнение текущей и целевой архитектуры

**Дата создания:** 27 января 2026  
**Версия:** 1.0  
**Статус:** Reference Document

---

## 1. Текущая архитектура develop (v2.0.0)

```mermaid
graph TD
    subgraph "API/Presentation Layer"
        API["🎨 API Routes<br/>v1/sessions<br/>v1/messages<br/>v1/agents"]
        Middleware["Middleware<br/>Auth, RateLimit"]
    end
    
    subgraph "Application Layer"
        Handlers["📋 Handlers<br/>смешанные<br/>read/write<br/>операции"]
        DTOs["DTOs<br/>SessionDTO<br/>MessageDTO<br/>AgentContextDTO"]
    end
    
    subgraph "Domain Layer"
        Entities["📦 Entities<br/>Session<br/>Message<br/>AgentContext<br/>Approval"]
        DomainServices["⚙️ Domain Services<br/>SessionManagement<br/>AgentOrchestration<br/>MessageOrchestration"]
        DomainRepos["🔌 Repository<br/>Interfaces"]
        DomainEvents["📢 Domain Events<br/>базовые"]
    end
    
    subgraph "Infrastructure Layer"
        DB["🗄️ ORM Models<br/>SQLAlchemy<br/>неявный маппинг<br/>Entity связаны с Model"]
        Adapters["Adapters<br/>SessionManager<br/>AgentContextManager"]
        EventBus["📡 Event Bus<br/>базовая pub/sub<br/>нет приоритетов<br/>нет middleware"]
        Subscribers["Subscribers<br/>MetricsCollector<br/>AuditLogger"]
        LLM["LLM Integration<br/>Streaming<br/>Tool Parser"]
    end
    
    Middleware -->|uses| API
    API -->|uses| Handlers
    Handlers -->|mixed read/write| DTOs
    Handlers -->|uses| DomainServices
    DTOs -->|неявное маппинг| Entities
    DomainServices -->|uses| DomainRepos
    DomainServices -->|publishes| DomainEvents
    DomainRepos -->|implements| DB
    DB -->|связаны с| Entities
    Adapters -->|wraps| DomainServices
    EventBus -->|publishes| DomainEvents
    Subscribers -->|subscribes| EventBus
    LLM -->|calls| DomainServices
    
    classDef problem fill:#ffcccc,stroke:#cc0000,stroke-width:2px
    classDef good fill:#ccffcc,stroke:#00cc00,stroke-width:2px
    
    class Handlers,DB problem
    class DomainServices,Entities,DomainEvents good
```

**Характеристики текущей архитектуры:**
- ⚠️ **Handlers смешивают** операции чтения и записи (не явная CQRS)
- ⚠️ **Маппинг неявный** - Entity ↔ Model связь не всегда четкая
- ⚠️ **Event Bus базовая** - нет приоритетов, middleware, wildcard подписок
- ⚠️ **Нет явного управления конкурентностью** на уровне сессий
- ⚠️ **Domain слой может случайно использовать** ORM модели
- ✅ **Event-driven система** уже реализована
- ✅ **Domain Services** хорошо структурированы

---

## 2. Целевая архитектура (после внедрения best practices)

```mermaid
graph TD
    subgraph "Presentation Layer"
        API["🎨 API Routes v1<br/>Sessions, Messages<br/>Agents, Events"]
        Schemas["Pydantic Schemas<br/>Request/Response<br/>type-safe validation"]
        Middleware["Middleware<br/>Auth, RateLimit<br/>Logging, Tracing"]
    end
    
    subgraph "Application Layer (CQRS)"
        Commands["📤 Commands<br/>CreateSession<br/>AddMessage<br/>SwitchAgent<br/>state changes"]
        CommandHandlers["Command Handlers<br/>explicit handling<br/>with DI"]
        Queries["📥 Queries<br/>GetSession<br/>ListSessions<br/>GetContext<br/>read-only"]
        QueryHandlers["Query Handlers<br/>explicit queries<br/>with DI"]
        DTOs["📊 DTOs<br/>type-safe<br/>Transfer objects"]
    end
    
    subgraph "Domain Layer (Clean DDD)"
        Entities["📦 Rich Entities<br/>Session, Message<br/>AgentContext, Approval<br/>with business logic"]
        DomainServices["⚙️ Domain Services<br/>SessionManagement<br/>AgentOrchestration<br/>MessageOrchestration<br/>ApprovalManagement"]
        DomainRepos["🔌 Repository<br/>Interfaces<br/>fully abstracted<br/>no ORM leaks"]
        DomainEvents["📢 Domain Events<br/>correlation IDs<br/>causation tracking<br/>explicit flow"]
    end
    
    subgraph "Infrastructure Layer"
        Persistence["🔐 Persistence"]
        Models["SQLAlchemy Models<br/>clean schema<br/>no domain logic"]
        Mappers["🔄 Mappers<br/>SessionMapper<br/>MessageMapper<br/>AgentContextMapper<br/>explicit conversions"]
        RepoImpl["Repository Impl<br/>concrete classes<br/>using mappers"]
        LockManager["🔒 SessionLockManager<br/>explicit concurrency<br/>async locks<br/>timeout handling"]
        EventBusExt["📡 Extended Event Bus<br/>priority handlers<br/>middleware support<br/>wildcard subscriptions"]
        Subscribers["Subscribers<br/>MetricsCollector<br/>AuditLogger<br/>SessionMetrics"]
    end
    
    subgraph "Cross-cutting Concerns"
        Resilience["⚡ Resilience<br/>CircuitBreaker<br/>Retry + Backoff<br/>error handling"]
        Observability["📊 Observability<br/>Prometheus metrics<br/>Correlation ID<br/>Structured Logging<br/>distributed tracing"]
        DI["💉 Dependency<br/>Injection<br/>centralized<br/>container"]
    end
    
    Middleware -->|uses| API
    API -->|Commands| Commands
    API -->|Queries| Queries
    Commands -->|uses| CommandHandlers
    Queries -->|uses| QueryHandlers
    CommandHandlers -->|returns| DTOs
    QueryHandlers -->|returns| DTOs
    
    CommandHandlers -->|uses| DomainServices
    QueryHandlers -->|uses| DomainRepos
    DomainServices -->|uses| DomainRepos
    DomainServices -->|publishes| DomainEvents
    DomainServices -->|operates on| Entities
    
    DomainRepos -->|interface to| RepoImpl
    RepoImpl -->|uses| Mappers
    Mappers -->|converts| Models
    Mappers -->|converts| Entities
    RepoImpl -->|queries with| Models
    
    LockManager -->|protects| RepoImpl
    EventBusExt -->|publishes| DomainEvents
    Subscribers -->|subscribes| EventBusExt
    
    CommandHandlers -->|uses| DI
    RepoImpl -->|uses| Observability
    DomainServices -->|uses| Resilience
    DomainServices -->|uses| Observability
    
    classDef presentation fill:#e1f5ff,stroke:#01579b,stroke-width:2px
    classDef application fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef domain fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px
    classDef infra fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef crosscutting fill:#fce4ec,stroke:#880e4f,stroke-width:2px
    
    class API,Schemas,Middleware presentation
    class Commands,CommandHandlers,Queries,QueryHandlers,DTOs application
    class Entities,DomainServices,DomainRepos,DomainEvents domain
    class Persistence,Models,Mappers,RepoImpl,LockManager,EventBusExt,Subscribers infra
    class Resilience,Observability,DI crosscutting
```

**Преимущества целевой архитектуры:**
- ✅ **CQRS явная** - четкое разделение Commands и Queries
- ✅ **Mappers явные** - полная изоляция Domain от Infrastructure  
- ✅ **SessionLockManager** - явное управление конкурентностью
- ✅ **Event Bus расширенная** - приоритеты, middleware, wildcard
- ✅ **Resilience patterns** - Circuit Breaker, exponential backoff
- ✅ **Observability** - Prometheus, correlation ID, structured logging
- ✅ **Clean Architecture** - идеальное разделение слоев
- ✅ **DDD** - богатые entities, domain services, domain events
- ✅ **Type-safe** - Pydantic models, type hints везде

---

## 3. Сравнение зависимостей: Before vs After

```mermaid
graph LR
    subgraph current["❌ BEFORE: develop v2.0.0<br/>Тесная связанность"]
        direction TB
        
        subgraph b_api["API Layer"]
            b_h["Handlers"]
        end
        
        subgraph b_domain["Domain Layer"]
            b_s["Services"]
            b_e["Entities"]
        end
        
        subgraph b_infra["Infrastructure"]
            b_db["ORM Models<br/>SQLAlchemy"]
        end
        
        b_h -->|direct<br/>access| b_db
        b_s -->|sometimes<br/>uses| b_db
        b_e -->|coupled| b_db
        b_h -->|uses| b_s
        
        classDef badpractice fill:#ffcccc,stroke:#ff0000,stroke-width:2px
        classDef neutral fill:#ffffcc,stroke:#ff9900,stroke-width:2px
        class b_h badpractice
        class b_s,b_e neutral
    end
    
    subgraph target["✅ AFTER: Best Practices<br/>Слабая связанность"]
        direction TB
        
        subgraph a_api["API Layer"]
            a_cmd["Commands<br/>Queries"]
        end
        
        subgraph a_app["Application Layer"]
            a_hdl["CQRS Handlers<br/>with DI"]
        end
        
        subgraph a_domain["Domain Layer<br/>ISOLATED"]
            a_ent["Entities<br/>Services<br/>Events<br/>Repositories"]
        end
        
        subgraph a_infra["Infrastructure<br/>IMPLEMENTATION"]
            a_map["Mappers<br/>Entity↔Model"]
            a_repos["Repository Impl"]
            a_db["ORM Models"]
        end
        
        a_cmd -->|uses| a_hdl
        a_hdl -->|uses| a_domain
        a_domain -->|interface| a_infra
        a_map -->|converts| a_ent
        a_map -->|converts| a_db
        a_repos -->|uses| a_map
        
        classDef goodpractice fill:#ccffcc,stroke:#00cc00,stroke-width:2px
        classDef isolated fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px
        class a_hdl,a_repos,a_map goodpractice
        class a_ent,a_domain isolated
    end
    
    current -.->|migration<br/>3.5 months| target
```

**Ключевые отличия:**

| Аспект | Before | After |
|--------|--------|-------|
| **Связанность слоев** | Тесная | Слабая (через интерфейсы) |
| **Domain изоляция** | Неполная (ORM утечки) | Полная (через Mappers) |
| **Entity в Domain** | Знает про ORM | Не знает про ORM |
| **Обработка команд** | Смешанная (read/write) | Разделенная (Commands/Queries) |
| **Маппинг данных** | Неявный | Явный (Mappers) |
| **Конкурентность** | На уровне БД | На уровне приложения |

---

## 4. Слой-за-слоем: От текущего к целевому

### API/Presentation Layer

```mermaid
graph LR
    subgraph before["Before"]
        API1["API Routes<br/>v1/sessions<br/>v1/messages"]
        Middleware1["Middleware<br/>Auth, RateLimit"]
    end
    
    subgraph after["After"]
        API2["API Routes v1<br/>Sessions, Messages<br/>Agents, Events"]
        Schemas["Pydantic Schemas<br/>validated"]
        Middleware2["Middleware<br/>Auth, RateLimit<br/>Logging, Tracing"]
    end
    
    before -.->|improve| after
    
    classDef before_style fill:#ffcccc,stroke:#cc0000
    classDef after_style fill:#ccffcc,stroke:#00cc00
    class before before_style
    class after after_style
```

**Улучшения:**
- Добавить Pydantic Schemas для API
- Добавить logging middleware
- Добавить tracing support

---

### Application Layer

```mermaid
graph LR
    subgraph before["Before: Mixed Handlers"]
        H1["Handlers<br/>read + write<br/>mixed concerns"]
    end
    
    subgraph after["After: CQRS Pattern"]
        CMD["Commands<br/>CreateSession<br/>AddMessage<br/>state change"]
        CMDH["Command Handlers"]
        QRY["Queries<br/>GetSession<br/>ListSessions<br/>read-only"]
        QRYH["Query Handlers"]
    end
    
    before -.->|refactor to| after
    CMD -->|uses| CMDH
    QRY -->|uses| QRYH
    
    classDef before_style fill:#ffcccc,stroke:#cc0000
    classDef after_style fill:#ccffcc,stroke:#00cc00
    class before before_style
    class CMD,CMDH,QRY,QRYH after_style
```

**Улучшения:**
- Разделить handlers на Commands и Queries
- Явная CQRS реализация
- Добавить Command/Query Handlers
- Централизованное управление DI

---

### Domain Layer

```mermaid
graph LR
    subgraph before["Before"]
        E1["Entities"]
        S1["Services"]
        R1["Repositories<br/>Interfaces"]
    end
    
    subgraph after["After: Rich DDD"]
        E2["Rich Entities<br/>+ business logic"]
        S2["Domain Services<br/>+ event publishing"]
        R2["Repository Interfaces<br/>fully abstracted"]
        EV["Domain Events<br/>+ correlation IDs"]
    end
    
    before -.->|improve DDD| after
    
    classDef before_style fill:#ffffcc,stroke:#ff9900
    classDef after_style fill:#e8f5e9,stroke:#1b5e20
    class before before_style
    class E2,S2,R2,EV after_style
```

**Улучшения:**
- Обогатить Entities бизнес-логикой
- Улучшить Domain Services
- Явные Domain Events
- Корреляционные ID для трейсинга

---

### Infrastructure Layer

```mermaid
graph LR
    subgraph before["Before: Implicit Mapping"]
        M1["Models<br/>SQLAlchemy"]
        R1["Repositories<br/>direct use"]
        E1["Entities<br/>loosely connected"]
    end
    
    subgraph after["After: Explicit Mapping"]
        M2["Models<br/>SQLAlchemy"]
        MP["Mappers<br/>SessionMapper<br/>MessageMapper<br/>explicit conversion"]
        R2["Repository Impl<br/>using mappers"]
        L["SessionLockManager<br/>concurrency"]
        E2["Entities<br/>fully isolated"]
    end
    
    before -.->|refactor to| after
    M2 <-->|converts| MP
    MP <-->|converts| E2
    R2 -->|uses| MP
    L -->|protects| R2
    
    classDef before_style fill:#ffcccc,stroke:#cc0000
    classDef after_style fill:#fff3e0,stroke:#e65100
    class before before_style
    class M2,MP,R2,L,E2 after_style
```

**Улучшения:**
- Явные Mappers для Entity ↔ Model
- SessionLockManager для конкурентности
- Расширенный Event Bus (приоритеты, middleware)
- Улучшенная структура Repository

---

## 5. Как зависимости изменяются по фазам

```mermaid
graph TD
    Phase1["Фаза 1: CQRS<br/>Commands/Queries"]
    Phase2["Фаза 2: Mappers<br/>Domain/Infra разделение"]
    Phase3["Фаза 3: SessionLockManager<br/>+ Event Bus расширения"]
    Phase4["Фаза 4: Test fixtures<br/>+ Resilience"]
    Phase5["Фаза 5: Observability<br/>+ Metrics"]
    Phase6["Фаза 6: Documentation<br/>+ Type-safety"]
    
    Phase1 -->|foundation| Phase2
    Phase2 -->|enables| Phase3
    Phase3 -->|supports| Phase4
    Phase4 -->|improves| Phase5
    Phase5 -->|completes| Phase6
    
    classDef critical fill:#ff9999,stroke:#cc0000,stroke-width:2px
    classDef high fill:#ffcc99,stroke:#ff6600,stroke-width:2px
    classDef medium fill:#ccffcc,stroke:#00cc00,stroke-width:2px
    
    class Phase1,Phase2 critical
    class Phase3,Phase4 high
    class Phase5,Phase6 medium
```

---

## 6. Dependency Injection Flow

### Before: Loose DI

```mermaid
graph TB
    Request["HTTP Request"]
    Route["API Route"]
    Handler["Handler"]
    Service["Service"]
    Repo["Repository"]
    DB["Database"]
    
    Request -->|FastAPI Depends| Route
    Route -->|creates| Handler
    Handler -->|creates or gets| Service
    Service -->|creates or gets| Repo
    Repo -->|queries| DB
    
    classDef loose fill:#ffcccc,stroke:#cc0000,stroke-width:2px
    class Handler,Service,Repo loose
```

### After: Centralized DI Container

```mermaid
graph TB
    Request["HTTP Request"]
    Route["API Route"]
    DIContainer["DI Container<br/>centralized<br/>managed"]
    
    Handler["Handler"]
    CommandHandler["Command Handler"]
    QueryHandler["Query Handler"]
    Service["Domain Service"]
    Repo["Repository"]
    DB["Database"]
    
    Request -->|FastAPI Depends| Route
    Route -->|requests| DIContainer
    DIContainer -->|provides| Handler
    DIContainer -->|provides| CommandHandler
    DIContainer -->|provides| QueryHandler
    DIContainer -->|provides| Service
    DIContainer -->|provides| Repo
    Repo -->|queries| DB
    
    classDef good fill:#ccffcc,stroke:#00cc00,stroke-width:2px
    classDef container fill:#e1f5ff,stroke:#01579b,stroke-width:2px
    class DIContainer container
    class Handler,CommandHandler,QueryHandler,Service,Repo good
```

---

## 7. Event Flow: Before vs After

### Before: Simple Event Bus

```mermaid
sequenceDiagram
    Handler->>Service: add_message()
    Service->>EventBus: publish(MessageReceived)
    EventBus->>MetricsCollector: handle(event)
    EventBus->>AuditLogger: handle(event)
    
    Note over EventBus: Basic pub/sub<br/>No priorities<br/>No middleware<br/>No wildcard
```

### After: Advanced Event Bus

```mermaid
sequenceDiagram
    Handler->>CommandHandler: handle(AddMessageCommand)
    CommandHandler->>Service: add_message()
    Service->>EventBus: publish(MessageReceived, correlation_id)
    
    EventBus->>Middleware: process_event()
    Middleware->>Middleware: filter & enrich
    
    par Handlers by Priority
        EventBus->>MetricsCollector: handle(10-priority)
        EventBus->>AuditLogger: handle(5-priority)
        EventBus->>SessionMetrics: handle(5-priority)
    end
    
    Note over EventBus: Extended features<br/>Priorities<br/>Middleware<br/>Correlation IDs<br/>Wildcard subscriptions
```

---

## 8. Clean Architecture Compliance

```mermaid
graph TB
    subgraph before["Before: Clean Architecture<br/>Compliance: 85%"]
        direction LR
        API_B["API Layer"]
        App_B["Application"]
        Domain_B["Domain<br/>⚠️ ORM leaks"]
        Infra_B["Infrastructure"]
        
        API_B -->|depends| App_B
        App_B -->|depends| Domain_B
        Domain_B -->|✗ violates| Infra_B
        Infra_B -->|provides| Domain_B
    end
    
    subgraph after["After: Clean Architecture<br/>Compliance: 100%"]
        direction LR
        API_A["API Layer"]
        App_A["Application"]
        Domain_A["Domain<br/>✅ fully isolated"]
        Infra_A["Infrastructure"]
        
        API_A -->|depends| App_A
        App_A -->|depends| Domain_A
        Domain_A -->|interface| Infra_A
        Infra_A -->|implements| Domain_A
    end
    
    classDef bad fill:#ffcccc,stroke:#cc0000,stroke-width:2px
    classDef good fill:#ccffcc,stroke:#00cc00,stroke-width:2px
    class Domain_B bad
    class Domain_A good
```

---

**Заключение:**

Переход от текущей архитектуры к целевой обеспечивает:
1. ✅ **100% Clean Architecture Compliance** - полная изоляция слоев
2. ✅ **Явная CQRS** - четкое разделение read/write операций
3. ✅ **Полная типизация** - type-safe код
4. ✅ **Лучшая масштабируемость** - ready для горизонтального масштабирования
5. ✅ **Улучшенная поддерживаемость** - лучше для новых разработчиков

**Документ подготовлен:** 27 января 2026  
**Версия:** 1.0
