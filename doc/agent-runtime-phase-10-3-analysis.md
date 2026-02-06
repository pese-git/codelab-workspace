# 📊 Фаза 10.3 - Application Layer: Анализ и план миграции

**Дата:** 6 февраля 2026  
**Статус:** 🎯 Готов к выполнению  
**Оценка:** 3-4 часа

---

## 🎯 Цель фазы

Обновить Application Layer для использования новых адаптеров и сервисов из Фазы 10.1, обеспечив полную интеграцию с обновленной архитектурой.

---

## 📊 Текущее состояние Application Layer

### Структура компонентов

```
app/application/
├── commands/           # CQRS Commands
│   ├── base.py
│   ├── create_session.py      # ✅ Использует SessionManagementService
│   ├── add_message.py          # ✅ Использует SessionManagementService
│   └── switch_agent.py         # ⚠️ Использует AgentOrchestrationService (legacy)
├── queries/            # CQRS Queries
│   ├── base.py
│   ├── get_session.py          # ⚠️ Использует SessionRepository напрямую
│   ├── list_sessions.py        # ⚠️ Использует SessionRepository напрямую
│   └── get_agent_context.py    # ⚠️ Использует AgentContextRepository напрямую
├── use_cases/          # Application Use Cases
│   ├── base_use_case.py
│   ├── process_message_use_case.py    # ✅ Использует MessageProcessor
│   ├── switch_agent_use_case.py       # ✅ Использует AgentSwitcher
│   ├── handle_approval_use_case.py    # ✅ Использует HITLHandler + PlanApprovalHandler
│   └── process_tool_result_use_case.py # ✅ Использует ToolResultHandler
├── coordinators/       # Application Coordinators
│   └── execution_coordinator.py # ⚠️ Использует ExecutionEngine + PlanRepository
├── handlers/           # Stream Handlers
│   └── stream_llm_response_handler.py # ✅ Использует LLMResponseProcessor
└── dto/                # Data Transfer Objects
    ├── session_dto.py          # ⚠️ Конвертирует Session entity
    ├── message_dto.py          # ⚠️ Конвертирует Message entity
    └── agent_context_dto.py    # ⚠️ Конвертирует AgentContext entity
```

---

## 🔍 Анализ зависимостей

### 1. Commands (CQRS)

| Command | Текущие зависимости | Статус | Требуется обновление |
|---------|---------------------|--------|---------------------|
| [`CreateSessionCommand`](../codelab-ai-service/agent-runtime/app/application/commands/create_session.py:16) | `SessionManagementService` | ⚠️ | Использовать адаптер |
| [`AddMessageCommand`](../codelab-ai-service/agent-runtime/app/application/commands/add_message.py:15) | `SessionManagementService` | ⚠️ | Использовать адаптер |
| [`SwitchAgentCommand`](../codelab-ai-service/agent-runtime/app/application/commands/switch_agent.py:16) | `AgentOrchestrationService` | ❌ | Использовать адаптер |

**Проблема:** Commands используют legacy сервисы напрямую вместо адаптеров.

**Решение:** Обновить DI для инъекции адаптеров вместо legacy сервисов.

### 2. Queries (CQRS)

| Query | Текущие зависимости | Статус | Требуется обновление |
|-------|---------------------|--------|---------------------|
| [`GetSessionQuery`](../codelab-ai-service/agent-runtime/app/application/queries/get_session.py:15) | `SessionRepository` | ⚠️ | Использовать через сервис |
| [`ListSessionsQuery`](../codelab-ai-service/agent-runtime/app/application/queries/list_sessions.py:16) | `SessionRepository`, `AgentContextRepository` | ⚠️ | Использовать через сервис |
| [`GetAgentContextQuery`](../codelab-ai-service/agent-runtime/app/application/queries/get_agent_context.py:15) | `AgentContextRepository` | ⚠️ | Использовать через сервис |

**Проблема:** Queries обращаются к repositories напрямую, минуя Domain Services.

**Решение:** 
- Создать Query Services или использовать существующие адаптеры
- Альтернатива: Оставить прямой доступ к repositories (допустимо для queries по CQRS)

### 3. Use Cases

| Use Case | Текущие зависимости | Статус |
|----------|---------------------|--------|
| [`ProcessMessageUseCase`](../codelab-ai-service/agent-runtime/app/application/use_cases/process_message_use_case.py:41) | `MessageProcessor`, `SessionLockManager` | ✅ |
| [`SwitchAgentUseCase`](../codelab-ai-service/agent-runtime/app/application/use_cases/switch_agent_use_case.py:40) | `AgentSwitcher`, `SessionLockManager` | ✅ |
| [`HandleApprovalUseCase`](../codelab-ai-service/agent-runtime/app/application/use_cases/handle_approval_use_case.py:61) | `HITLDecisionHandler`, `PlanApprovalHandler` | ✅ |
| [`ProcessToolResultUseCase`](../codelab-ai-service/agent-runtime/app/application/use_cases/process_tool_result_use_case.py:40) | `ToolResultHandler`, `PlanRepository`, `ExecutionCoordinator` | ⚠️ |

**Статус:** Use Cases в основном используют правильные Domain Services.

**Проблема:** `ProcessToolResultUseCase` использует `PlanRepository` напрямую.

### 4. Coordinators

| Coordinator | Текущие зависимости | Статус |
|-------------|---------------------|--------|
| [`ExecutionCoordinator`](../codelab-ai-service/agent-runtime/app/application/coordinators/execution_coordinator.py:32) | `ExecutionEngine`, `PlanRepository` | ⚠️ |

**Проблема:** 
- Использует `ExecutionEngine` напрямую (должен использовать `ExecutionEngineAdapter`)
- Использует `PlanRepository` напрямую (допустимо, но лучше через сервис)

### 5. DTOs

| DTO | Конвертирует | Статус |
|-----|--------------|--------|
| [`SessionDTO`](../codelab-ai-service/agent-runtime/app/application/dto/session_dto.py:16) | `Session` entity | ⚠️ |
| [`MessageDTO`](../codelab-ai-service/agent-runtime/app/application/dto/message_dto.py:14) | `Message` entity | ⚠️ |
| [`AgentContextDTO`](../codelab-ai-service/agent-runtime/app/application/dto/agent_context_dto.py:66) | `AgentContext` entity | ⚠️ |

**Проблема:** DTOs конвертируют legacy entities.

**Решение:** 
- Обновить для работы с новыми entities (`Conversation`, `Agent`)
- Создать адаптеры конвертации если нужна обратная совместимость

---

## 🎯 План миграции

### Этап 1: Обновление Commands (1 час)

**Задачи:**
1. ✅ Обновить `CreateSessionCommand` для использования `ConversationServiceAdapter`
2. ✅ Обновить `AddMessageCommand` для использования `ConversationServiceAdapter`
3. ✅ Обновить `SwitchAgentCommand` для использования `AgentOrchestrationAdapter`
4. ✅ Обновить DI Container для инъекции адаптеров

**Файлы:**
- `app/application/commands/create_session.py`
- `app/application/commands/add_message.py`
- `app/application/commands/switch_agent.py`
- `app/core/dependencies.py`

**Тесты:**
- Обновить существующие тесты commands
- Проверить интеграцию с адаптерами

### Этап 2: Обновление Queries (0.5 часа)

**Решение:** Оставить queries с прямым доступом к repositories (допустимо по CQRS).

**Альтернатива (если нужно):**
- Создать `ConversationQueryService` для queries
- Обновить queries для использования сервиса

**Файлы:**
- `app/application/queries/get_session.py` (опционально)
- `app/application/queries/list_sessions.py` (опционально)
- `app/application/queries/get_agent_context.py` (опционально)

### Этап 3: Обновление Coordinators (1 час)

**Задачи:**
1. ✅ Обновить `ExecutionCoordinator` для использования `ExecutionEngineAdapter`
2. ✅ Рефакторинг для использования `PlanExecutionService` через адаптер
3. ✅ Обновить тесты coordinator

**Файлы:**
- `app/application/coordinators/execution_coordinator.py`
- `tests/unit/application/coordinators/test_execution_coordinator.py`

### Этап 4: Обновление DTOs (0.5 часа)

**Задачи:**
1. ✅ Создать адаптеры конвертации для обратной совместимости
2. ✅ Обновить DTOs для работы с новыми entities
3. ✅ Сохранить обратную совместимость API

**Файлы:**
- `app/application/dto/session_dto.py`
- `app/application/dto/agent_context_dto.py`
- `app/domain/adapters/dto_adapters.py` (новый)

### Этап 5: Обновление Use Cases (0.5 часа)

**Задачи:**
1. ✅ Обновить `ProcessToolResultUseCase` для использования сервисов
2. ✅ Проверить все use cases на совместимость
3. ✅ Обновить тесты

**Файлы:**
- `app/application/use_cases/process_tool_result_use_case.py`
- `tests/unit/application/use_cases/test_process_tool_result_use_case.py`

### Этап 6: Интеграционное тестирование (0.5 часа)

**Задачи:**
1. ✅ Запустить все тесты Application Layer
2. ✅ Проверить интеграцию с Domain Layer
3. ✅ Проверить работу через API endpoints
4. ✅ Исправить найденные проблемы

---

## 📋 Детальный чеклист

### Commands

- [ ] Обновить `CreateSessionCommand` handler
  - [ ] Инъекция `ConversationServiceAdapter`
  - [ ] Обновить вызовы методов
  - [ ] Обновить тесты
- [ ] Обновить `AddMessageCommand` handler
  - [ ] Инъекция `ConversationServiceAdapter`
  - [ ] Обновить вызовы методов
  - [ ] Обновить тесты
- [ ] Обновить `SwitchAgentCommand` handler
  - [ ] Инъекция `AgentOrchestrationAdapter`
  - [ ] Обновить вызовы методов
  - [ ] Обновить тесты

### Coordinators

- [ ] Обновить `ExecutionCoordinator`
  - [ ] Инъекция `ExecutionEngineAdapter`
  - [ ] Обновить метод `execute_plan()`
  - [ ] Обновить метод `_validate_plan_ready()`
  - [ ] Обновить тесты

### DTOs

- [ ] Создать `DTOAdapters` класс
  - [ ] `session_to_conversation()` - Session → Conversation
  - [ ] `conversation_to_session()` - Conversation → Session
  - [ ] `agent_context_to_agent()` - AgentContext → Agent
  - [ ] `agent_to_agent_context()` - Agent → AgentContext
- [ ] Обновить `SessionDTO`
  - [ ] Поддержка Conversation entity
  - [ ] Обратная совместимость
- [ ] Обновить `AgentContextDTO`
  - [ ] Поддержка Agent entity
  - [ ] Обратная совместимость

### Use Cases

- [ ] Обновить `ProcessToolResultUseCase`
  - [ ] Использовать сервис вместо repository
  - [ ] Обновить тесты

### DI Container

- [ ] Обновить `dependencies.py`
  - [ ] Регистрация адаптеров для commands
  - [ ] Регистрация адаптеров для coordinators
  - [ ] Проверка всех зависимостей

### Тестирование

- [ ] Unit тесты commands (3 файла)
- [ ] Unit тесты coordinators (1 файл)
- [ ] Unit тесты use cases (1 файл)
- [ ] Integration тесты Application Layer
- [ ] E2E тесты через API

---

## 🔧 Примеры изменений

### 1. CreateSessionCommand - До

```python
class CreateSessionHandler(CommandHandler[SessionDTO]):
    def __init__(self, session_service: SessionManagementService):
        self._session_service = session_service
    
    async def handle(self, command: CreateSessionCommand) -> SessionDTO:
        session = await self._session_service.create_session(
            session_id=command.session_id
        )
        return SessionDTO.from_entity(session, include_messages=False)
```

### 1. CreateSessionCommand - После

```python
class CreateSessionHandler(CommandHandler[SessionDTO]):
    def __init__(self, conversation_service: ConversationServiceAdapter):
        self._conversation_service = conversation_service
    
    async def handle(self, command: CreateSessionCommand) -> SessionDTO:
        # Адаптер возвращает Session для обратной совместимости
        session = await self._conversation_service.create_session(
            session_id=command.session_id
        )
        return SessionDTO.from_entity(session, include_messages=False)
```

### 2. ExecutionCoordinator - До

```python
class ExecutionCoordinator:
    def __init__(
        self,
        execution_engine: ExecutionEngine,
        plan_repository: PlanRepository
    ):
        self.execution_engine = execution_engine
        self.plan_repository = plan_repository
```

### 2. ExecutionCoordinator - После

```python
class ExecutionCoordinator:
    def __init__(
        self,
        execution_engine: ExecutionEngineAdapter,  # Используем адаптер
        plan_repository: PlanRepository  # Оставляем для queries
    ):
        self.execution_engine = execution_engine
        self.plan_repository = plan_repository
```

### 3. SessionDTO - До

```python
@classmethod
def from_entity(cls, session: Session, include_messages: bool = False) -> "SessionDTO":
    return cls(
        id=session.id,
        created_at=session.created_at,
        # ...
    )
```

### 3. SessionDTO - После

```python
@classmethod
def from_entity(cls, entity: Union[Session, Conversation], include_messages: bool = False) -> "SessionDTO":
    # Поддержка обоих типов для обратной совместимости
    if isinstance(entity, Conversation):
        # Конвертировать Conversation → Session через адаптер
        session = DTOAdapters.conversation_to_session(entity)
    else:
        session = entity
    
    return cls(
        id=session.id,
        created_at=session.created_at,
        # ...
    )
```

---

## 📊 Оценка времени

| Этап | Задача | Время |
|------|--------|-------|
| 1 | Обновление Commands | 1.0ч |
| 2 | Обновление Queries | 0.5ч |
| 3 | Обновление Coordinators | 1.0ч |
| 4 | Обновление DTOs | 0.5ч |
| 5 | Обновление Use Cases | 0.5ч |
| 6 | Интеграционное тестирование | 0.5ч |
| **Итого** | | **4.0ч** |

**Буфер:** 0.5 часа на непредвиденные проблемы

**Общая оценка:** 3.5-4 часа

---

## ⚠️ Риски и митигация

### Риск 1: Breaking changes в API

**Вероятность:** Средняя  
**Влияние:** Высокое

**Митигация:**
- Сохранить обратную совместимость через адаптеры
- Тщательное тестирование API endpoints
- Использовать DTOAdapters для конвертации

### Риск 2: Проблемы с DI Container

**Вероятность:** Средняя  
**Влияние:** Среднее

**Митигация:**
- Постепенное обновление зависимостей
- Тестирование после каждого изменения
- Использование TYPE_CHECKING для избежания circular imports

### Риск 3: Несовместимость тестов

**Вероятность:** Высокая  
**Влияние:** Низкое

**Митигация:**
- Обновлять тесты параллельно с кодом
- Использовать моки адаптеров
- Сохранить структуру тестов

---

## ✅ Критерии завершения

- [ ] Все Commands используют адаптеры
- [ ] ExecutionCoordinator использует ExecutionEngineAdapter
- [ ] DTOs поддерживают новые entities
- [ ] Обратная совместимость сохранена
- [ ] Все unit тесты проходят (100%)
- [ ] Integration тесты проходят
- [ ] API endpoints работают корректно
- [ ] Документация обновлена
- [ ] Код готов к code review

---

## 🔗 Связанные документы

- [Фаза 10.1.1 - ConversationManagementService](agent-runtime-phase-10-1-1-report.md)
- [Фаза 10.1.2 - AgentCoordinationService](agent-runtime-phase-10-1-2-report.md)
- [Фаза 10.1.4 - DI Container Update](agent-runtime-phase-10-1-4-report.md)
- [Фаза 10.2 - Infrastructure Layer](agent-runtime-phase-10-2-tests-fixed.md)
- [Общий прогресс Фазы 10](agent-runtime-phase-10-progress.md)

---

**Статус:** 🎯 Готов к выполнению  
**Следующий шаг:** Начать с Этапа 1 - Обновление Commands
