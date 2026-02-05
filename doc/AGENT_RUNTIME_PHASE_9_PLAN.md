# 🚀 Agent Runtime Refactoring — Фаза 9: Integration

**Дата начала:** 5 февраля 2026  
**Статус:** 🔄 В процессе  
**Цель:** Интеграция всех рефакторенных компонентов в существующую кодовую базу

---

## 📋 Обзор

Фаза 9 — финальная фаза рефакторинга, где мы интегрируем все созданные компоненты (Фазы 1-8) в существующую систему. Основная задача — обеспечить плавную миграцию без breaking changes и сохранить 100% обратную совместимость.

### Завершенные фазы (8 из 9)

1. ✅ **Фаза 1: Подготовка** — Shared Kernel и структура
2. ✅ **Фаза 2: Session Context** — 13 файлов, 44 теста
3. ✅ **Фаза 3: Agent Context** — 10 файлов, 44 теста
4. ✅ **Фаза 4: Use Cases** — 10 файлов, 35 тестов
5. ✅ **Фаза 5: Execution Context** — 9 файлов
6. ✅ **Фаза 6: Approval Context** — 21 файл, 74 теста
7. ✅ **Фаза 7: LLM Context** — 21 файл, 94 теста
8. ✅ **Фаза 8: Tool Context** — 27 файлов, 124 теста

**Всего создано:** ~132 файла, ~13,230 строк кода, 505+ тестов

---

## 🎯 Цели Фазы 9

### Основные цели

1. **Интеграция Domain Layer** — Подключить новые bounded contexts
2. **Миграция Infrastructure** — Обновить repositories и adapters
3. **Обновление Application Layer** — Интегрировать Use Cases
4. **Обратная совместимость** — Создать адаптеры для старых API
5. **Integration тесты** — Проверить работу всей системы
6. **Документация** — Обновить все документы

### Критерии успеха

- ✅ Все существующие API работают без изменений
- ✅ Все существующие тесты проходят
- ✅ Новые компоненты полностью интегрированы
- ✅ Integration тесты покрывают основные сценарии
- ✅ Документация актуализирована

---

## 📊 Анализ текущей структуры

### Старые компоненты (требуют миграции)

#### Domain Entities (старые)
```
app/domain/entities/
├── session.py (502 строки)          → Заменить на session_context/
├── agent_context.py (350 строк)     → Заменить на agent_context/
├── plan.py (483 строки)             → Заменить на execution_context/
├── approval.py                      → Заменить на approval_context/
├── llm_response.py                  → Заменить на llm_context/
├── message.py                       → Интегрировать в session_context/
├── hitl.py                          → Заменить на approval_context/
└── base.py                          → Уже заменен на shared/base_entity.py
```

#### Domain Services (старые)
```
app/domain/services/
├── message_orchestration.py (433)   → Заменен на use_cases/
├── message_processor.py             → Обновить для новых entities
├── agent_switcher.py                → Обновить для agent_context/
├── session_management.py            → Обновить для session_context/
├── execution_engine.py              → Обновить для execution_context/
├── approval_management.py           → Заменен на approval_context/services/
├── hitl_policy.py                   → Заменен на approval_context/services/
├── subtask_executor.py              → Обновить для execution_context/
└── tool_result_handler.py           → Обновить для tool_context/
```

#### Infrastructure (требует обновления)
```
app/infrastructure/
├── persistence/repositories/
│   ├── agent_context_repository_impl.py  → Обновить для новых entities
│   ├── approval_repository_impl.py       → Обновить для approval_context/
│   └── session_repository_impl.py        → Создать для session_context/
├── persistence/mappers/
│   ├── session_mapper.py                 → Обновить
│   ├── agent_context_mapper.py           → Обновить
│   └── plan_mapper.py                    → Обновить
└── adapters/
    ├── session_manager_adapter.py        → Обновить
    └── agent_context_manager_adapter.py  → Обновить
```

### Новые компоненты (созданы в Фазах 1-8)

#### Domain Layer
```
app/domain/
├── shared/                          ✅ Готово (Фаза 1)
│   ├── base_entity.py
│   ├── value_object.py
│   ├── domain_event.py
│   └── repository.py
├── session_context/                 ✅ Готово (Фаза 2)
│   ├── entities/
│   ├── value_objects/
│   ├── services/
│   ├── repositories/
│   └── events/
├── agent_context/                   ✅ Готово (Фаза 3)
│   ├── entities/
│   ├── value_objects/
│   ├── services/
│   ├── repositories/
│   └── events/
├── execution_context/               ✅ Готово (Фаза 5)
│   ├── entities/
│   ├── value_objects/
│   ├── services/
│   ├── repositories/
│   └── events/
├── approval_context/                ✅ Готово (Фаза 6)
│   ├── entities/
│   ├── value_objects/
│   ├── services/
│   ├── repositories/
│   └── events/
├── llm_context/                     ✅ Готово (Фаза 7)
│   ├── entities/
│   ├── value_objects/
│   ├── services/
│   ├── ports/
│   └── events/
└── tool_context/                    ✅ Готово (Фаза 8)
    ├── entities/
    ├── value_objects/
    ├── services/
    ├── ports/
    └── events/
```

#### Application Layer
```
app/application/
└── use_cases/                       ✅ Готово (Фаза 4)
    ├── base_use_case.py
    ├── process_message_use_case.py
    ├── switch_agent_use_case.py
    ├── process_tool_result_use_case.py
    └── handle_approval_use_case.py
```

---

## 🗺️ План интеграции

### Этап 1: Адаптеры обратной совместимости (2-3 часа)

**Цель:** Создать адаптеры, которые позволят старому коду работать с новыми entities

#### 1.1. Session Adapter
```python
# app/domain/adapters/session_adapter.py
class SessionAdapter:
    """Адаптер между старой Session и новой Conversation."""
    
    @staticmethod
    def to_conversation(session: OldSession) -> Conversation:
        """Конвертировать старую Session в новую Conversation."""
        pass
    
    @staticmethod
    def from_conversation(conversation: Conversation) -> OldSession:
        """Конвертировать новую Conversation в старую Session."""
        pass
```

#### 1.2. AgentContext Adapter
```python
# app/domain/adapters/agent_context_adapter.py
class AgentContextAdapter:
    """Адаптер между старым AgentContext и новым Agent."""
    
    @staticmethod
    def to_agent(old_context: OldAgentContext) -> Agent:
        """Конвертировать старый AgentContext в новый Agent."""
        pass
    
    @staticmethod
    def from_agent(agent: Agent) -> OldAgentContext:
        """Конвертировать новый Agent в старый AgentContext."""
        pass
```

#### 1.3. Plan Adapter
```python
# app/domain/adapters/plan_adapter.py
class PlanAdapter:
    """Адаптер между старым Plan и новым ExecutionPlan."""
    
    @staticmethod
    def to_execution_plan(old_plan: OldPlan) -> ExecutionPlan:
        """Конвертировать старый Plan в новый ExecutionPlan."""
        pass
    
    @staticmethod
    def from_execution_plan(plan: ExecutionPlan) -> OldPlan:
        """Конвертировать новый ExecutionPlan в старый Plan."""
        pass
```

**Файлы для создания:**
- `app/domain/adapters/__init__.py`
- `app/domain/adapters/session_adapter.py`
- `app/domain/adapters/agent_context_adapter.py`
- `app/domain/adapters/plan_adapter.py`
- `app/domain/adapters/approval_adapter.py`

**Тесты:**
- `tests/unit/domain/adapters/test_session_adapter.py`
- `tests/unit/domain/adapters/test_agent_context_adapter.py`
- `tests/unit/domain/adapters/test_plan_adapter.py`

---

### Этап 2: Infrastructure Layer (3-4 часа)

**Цель:** Обновить repositories и mappers для работы с новыми entities

#### 2.1. Conversation Repository Implementation
```python
# app/infrastructure/persistence/repositories/conversation_repository_impl.py
class ConversationRepositoryImpl(ConversationRepository):
    """SQLAlchemy реализация ConversationRepository."""
    
    async def find_by_id(self, conversation_id: ConversationId) -> Optional[Conversation]:
        """Найти conversation по ID."""
        pass
    
    async def save(self, conversation: Conversation) -> None:
        """Сохранить conversation."""
        pass
```

#### 2.2. Agent Repository Implementation
```python
# app/infrastructure/persistence/repositories/agent_repository_impl.py
class AgentRepositoryImpl(AgentRepository):
    """SQLAlchemy реализация AgentRepository."""
    
    async def find_by_session_id(self, session_id: str) -> Optional[Agent]:
        """Найти agent по session_id."""
        pass
    
    async def save(self, agent: Agent) -> None:
        """Сохранить agent."""
        pass
```

#### 2.3. ExecutionPlan Repository Implementation
```python
# app/infrastructure/persistence/repositories/execution_plan_repository_impl.py
class ExecutionPlanRepositoryImpl(ExecutionPlanRepository):
    """SQLAlchemy реализация ExecutionPlanRepository."""
    
    async def find_by_id(self, plan_id: PlanId) -> Optional[ExecutionPlan]:
        """Найти plan по ID."""
        pass
    
    async def save(self, plan: ExecutionPlan) -> None:
        """Сохранить plan."""
        pass
```

#### 2.4. Mappers (ORM ↔ Domain)
```python
# app/infrastructure/persistence/mappers/conversation_mapper.py
class ConversationMapper:
    """Маппер между ORM моделью и Conversation entity."""
    
    @staticmethod
    def to_domain(orm_session: SessionModel) -> Conversation:
        """Конвертировать ORM модель в domain entity."""
        pass
    
    @staticmethod
    def to_orm(conversation: Conversation) -> SessionModel:
        """Конвертировать domain entity в ORM модель."""
        pass
```

**Файлы для создания/обновления:**
- `app/infrastructure/persistence/repositories/conversation_repository_impl.py`
- `app/infrastructure/persistence/repositories/agent_repository_impl.py`
- `app/infrastructure/persistence/repositories/execution_plan_repository_impl.py`
- `app/infrastructure/persistence/mappers/conversation_mapper.py`
- `app/infrastructure/persistence/mappers/agent_mapper.py`
- `app/infrastructure/persistence/mappers/execution_plan_mapper.py`

**Тесты:**
- `tests/integration/infrastructure/test_conversation_repository.py`
- `tests/integration/infrastructure/test_agent_repository.py`
- `tests/integration/infrastructure/test_execution_plan_repository.py`

---

### Этап 3: Application Layer Integration (2-3 часа)

**Цель:** Интегрировать Use Cases в существующую систему

#### 3.1. Обновить DI Container
```python
# app/core/di/container.py
def setup_use_cases(container):
    """Настроить Use Cases в DI контейнере."""
    
    # Process Message Use Case
    container.register(
        ProcessMessageUseCase,
        factory=lambda: ProcessMessageUseCase(
            message_processor=container.resolve(MessageProcessor),
            lock_manager=container.resolve(SessionLockManager)
        )
    )
    
    # Switch Agent Use Case
    container.register(
        SwitchAgentUseCase,
        factory=lambda: SwitchAgentUseCase(
            agent_switcher=container.resolve(AgentSwitcher),
            lock_manager=container.resolve(SessionLockManager)
        )
    )
    
    # ... остальные Use Cases
```

#### 3.2. Обновить API Routers
```python
# app/api/v1/routers/messages_router.py
@router.post("/sessions/{session_id}/messages")
async def process_message(
    session_id: str,
    request: MessageRequest,
    use_case: ProcessMessageUseCase = Depends(get_process_message_use_case)
):
    """Обработать сообщение через Use Case."""
    
    # Используем новый Use Case вместо старого фасада
    async for chunk in use_case.execute(
        ProcessMessageRequest(
            session_id=session_id,
            message=request.message,
            user_id=request.user_id
        )
    ):
        yield chunk
```

**Файлы для обновления:**
- `app/core/di/container.py`
- `app/api/v1/routers/messages_router.py`
- `app/api/v1/routers/agents_router.py`
- `app/api/v1/routers/sessions_router.py`

---

### Этап 4: Domain Services Migration (2-3 часа)

**Цель:** Обновить существующие domain services для работы с новыми entities

#### 4.1. MessageProcessor
```python
# app/domain/services/message_processor.py
class MessageProcessor:
    """Обновленный процессор сообщений."""
    
    def __init__(
        self,
        conversation_repo: ConversationRepository,  # Новый!
        agent_repo: AgentRepository,                # Новый!
        llm_provider: LLMProvider,                  # Новый!
        # ... остальные зависимости
    ):
        self._conversation_repo = conversation_repo
        self._agent_repo = agent_repo
        self._llm_provider = llm_provider
    
    async def process(
        self,
        session_id: str,
        message: str,
        user_id: str
    ) -> AsyncGenerator[StreamChunk, None]:
        """Обработать сообщение с новыми entities."""
        
        # Загрузить conversation (вместо session)
        conversation = await self._conversation_repo.find_by_id(
            ConversationId(session_id)
        )
        
        # Загрузить agent
        agent = await self._agent_repo.find_by_session_id(session_id)
        
        # ... остальная логика
```

#### 4.2. AgentSwitcher
```python
# app/domain/services/agent_switcher.py
class AgentSwitcher:
    """Обновленный switcher агентов."""
    
    def __init__(
        self,
        agent_repo: AgentRepository,                # Новый!
        conversation_repo: ConversationRepository,  # Новый!
        cleanup_service: ToolMessageCleanupService  # Новый!
    ):
        self._agent_repo = agent_repo
        self._conversation_repo = conversation_repo
        self._cleanup_service = cleanup_service
    
    async def switch(
        self,
        session_id: str,
        target_agent: AgentType,
        reason: str
    ) -> None:
        """Переключить агента с новыми entities."""
        
        # Загрузить agent
        agent = await self._agent_repo.find_by_session_id(session_id)
        
        # Переключить
        agent.switch_to(target_agent, reason)
        
        # Очистить tool messages
        conversation = await self._conversation_repo.find_by_id(
            ConversationId(session_id)
        )
        self._cleanup_service.cleanup(conversation)
        
        # Сохранить
        await self._agent_repo.save(agent)
        await self._conversation_repo.save(conversation)
```

**Файлы для обновления:**
- `app/domain/services/message_processor.py`
- `app/domain/services/agent_switcher.py`
- `app/domain/services/tool_result_handler.py`
- `app/domain/services/execution_engine.py`

---

### Этап 5: Integration Tests (2-3 часа)

**Цель:** Создать integration тесты для проверки работы всей системы

#### 5.1. End-to-End тесты
```python
# tests/integration/test_message_flow.py
async def test_complete_message_flow():
    """Тест полного flow обработки сообщения."""
    
    # 1. Создать сессию
    session_id = await create_session(user_id="user-1")
    
    # 2. Отправить сообщение
    response = await process_message(
        session_id=session_id,
        message="Создай файл test.py"
    )
    
    # 3. Проверить, что агент переключился на CODER
    agent = await get_agent(session_id)
    assert agent.current_agent == AgentType.CODER
    
    # 4. Проверить, что есть tool calls
    assert len(response.tool_calls) > 0
    
    # 5. Одобрить tool call
    await approve_tool_call(
        session_id=session_id,
        tool_call_id=response.tool_calls[0].id
    )
    
    # 6. Проверить результат
    conversation = await get_conversation(session_id)
    assert len(conversation.messages) > 0
```

#### 5.2. Repository Integration Tests
```python
# tests/integration/test_repositories.py
async def test_conversation_repository():
    """Тест ConversationRepository."""
    
    # Создать conversation
    conversation = Conversation(
        id=ConversationId.generate(),
        user_id="user-1"
    )
    
    # Сохранить
    await conversation_repo.save(conversation)
    
    # Загрузить
    loaded = await conversation_repo.find_by_id(conversation.id)
    
    # Проверить
    assert loaded is not None
    assert loaded.id == conversation.id
    assert loaded.user_id == conversation.user_id
```

**Файлы для создания:**
- `tests/integration/test_message_flow.py`
- `tests/integration/test_agent_switching.py`
- `tests/integration/test_plan_execution.py`
- `tests/integration/test_approval_flow.py`
- `tests/integration/test_repositories.py`

---

### Этап 6: Документация (1-2 часа)

**Цель:** Обновить всю документацию

#### 6.1. Обновить README
- Добавить информацию о новой архитектуре
- Обновить примеры использования
- Добавить диаграммы

#### 6.2. Создать Migration Guide
```markdown
# Migration Guide: Old → New Architecture

## Session → Conversation

**Было:**
```python
session = Session(id="session-1")
session.add_message(message)
```

**Стало:**
```python
conversation = Conversation(id=ConversationId("session-1"))
conversation.add_message(message)
```

## AgentContext → Agent

**Было:**
```python
context = AgentContext(session_id="session-1")
context.switch_agent(AgentType.CODER)
```

**Стало:**
```python
agent = Agent(id=AgentId.from_session_id("session-1"))
agent.switch_to(AgentType.CODER, reason="User request")
```

#### 6.3. Обновить Architecture Documentation
- Добавить описание всех bounded contexts
- Обновить диаграммы
- Добавить примеры использования

**Файлы для создания/обновления:**
- `doc/MIGRATION_GUIDE.md`
- `doc/ARCHITECTURE_V2.md`
- `doc/BOUNDED_CONTEXTS.md`
- `README.md` (в agent-runtime)

---

## 📋 Чеклист выполнения

### Этап 1: Адаптеры (2-3 часа)
- [ ] Создать `SessionAdapter`
- [ ] Создать `AgentContextAdapter`
- [ ] Создать `PlanAdapter`
- [ ] Создать `ApprovalAdapter`
- [ ] Написать unit тесты для адаптеров
- [ ] Проверить обратную совместимость

### Этап 2: Infrastructure (3-4 часа)
- [ ] Создать `ConversationRepositoryImpl`
- [ ] Создать `AgentRepositoryImpl`
- [ ] Создать `ExecutionPlanRepositoryImpl`
- [ ] Создать `ConversationMapper`
- [ ] Создать `AgentMapper`
- [ ] Создать `ExecutionPlanMapper`
- [ ] Написать integration тесты для repositories

### Этап 3: Application Layer (2-3 часа)
- [ ] Обновить DI Container
- [ ] Обновить API Routers
- [ ] Интегрировать Use Cases
- [ ] Проверить работу API endpoints

### Этап 4: Domain Services (2-3 часа)
- [ ] Обновить `MessageProcessor`
- [ ] Обновить `AgentSwitcher`
- [ ] Обновить `ToolResultHandler`
- [ ] Обновить `ExecutionEngine`
- [ ] Проверить работу всех services

### Этап 5: Integration Tests (2-3 часа)
- [ ] Создать end-to-end тесты
- [ ] Создать repository integration тесты
- [ ] Создать API integration тесты
- [ ] Проверить все сценарии

### Этап 6: Документация (1-2 часа)
- [ ] Создать Migration Guide
- [ ] Обновить Architecture Documentation
- [ ] Обновить README
- [ ] Создать примеры использования

### Финализация
- [ ] Запустить все тесты (unit + integration)
- [ ] Проверить code coverage
- [ ] Создать финальный отчет
- [ ] Создать коммит

---

## 📊 Метрики успеха

### Количественные метрики

| Метрика | Цель | Текущее |
|---------|------|---------|
| Unit тесты | 600+ | 505 |
| Integration тесты | 50+ | 0 |
| Code coverage | 90%+ | - |
| Адаптеры | 5 | 0 |
| Repositories | 8 | 0 |
| Mappers | 6 | 0 |

### Качественные метрики

- ✅ Все существующие API работают
- ✅ Все существующие тесты проходят
- ✅ Новые компоненты интегрированы
- ✅ Документация актуальна
- ✅ Migration guide создан

---

## ⚠️ Риски и митигация

### Риск 1: Breaking Changes
**Вероятность:** Средняя  
**Влияние:** Высокое  
**Митигация:** Адаптеры обратной совместимости, тщательное тестирование

### Риск 2: Performance Degradation
**Вероятность:** Низкая  
**Влияние:** Среднее  
**Митигация:** Benchmarking, оптимизация критических путей

### Риск 3: Data Migration Issues
**Вероятность:** Средняя  
**Влияние:** Высокое  
**Митигация:** Тщательное тестирование mappers, rollback план

---

## 🎯 Ожидаемые результаты

### После завершения Фазы 9

1. **Полная интеграция** — Все новые компоненты работают в production
2. **Обратная совместимость** — Старый код продолжает работать
3. **100% тестирование** — Unit + Integration тесты
4. **Актуальная документация** — Migration guide, architecture docs
5. **Готовность к production** — Система готова к деплою

### Следующие шаги (после Фазы 9)

1. **Постепенная миграция** — Переписать старые services на новые entities
2. **Удаление legacy кода** — Удалить старые entities после полной миграции
3. **Оптимизация** — Улучшить performance критических путей
4. **Мониторинг** — Добавить метрики и алерты

---

**Автор:** Sergey Penkovsky  
**Дата создания:** 5 февраля 2026  
**Последнее обновление:** 5 февраля 2026
