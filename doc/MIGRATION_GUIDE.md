# 🔄 Migration Guide: Agent Runtime Refactoring

**Дата:** 7 февраля 2026  
**Версия:** 1.0  
**Статус:** ✅ Готов к использованию

---

## 📋 Обзор изменений

Архитектура Agent Runtime была рефакторена согласно принципам Clean Architecture и DDD. Основные изменения:

1. **Модульный DI** - [`dependencies.py`](../codelab-ai-service/agent-runtime/app/core/dependencies.py) уменьшен с 893 до ~280 строк
2. **Удален старый код** - [`session_legacy.py`](../codelab-ai-service/agent-runtime/app/domain/entities/session_legacy.py), [`message_orchestration.py`](../codelab-ai-service/agent-runtime/app/domain/services/message_orchestration.py)
3. **Удалены адаптеры** - Избыточные адаптеры для обратной совместимости
4. **Новая структура DI** - Модули для каждого Bounded Context

---

## 🚀 Быстрый старт

### Для разработчиков

#### 1. Обновить импорты

**❌ Старый код:**
```python
from app.domain.entities import Session
from app.domain.services import MessageOrchestrationService
```

**✅ Новый код:**
```python
from app.domain.session_context.entities import Conversation
from app.application.use_cases import ProcessMessageUseCase
```

#### 2. Использовать новый DI Container

**❌ Старый код:**
```python
from app.core.dependencies import get_message_orchestration_service

async def endpoint(
    service: MessageOrchestrationService = Depends(get_message_orchestration_service)
):
    async for chunk in service.process_message(...):
        yield chunk
```

**✅ Новый код:**
```python
from app.core.dependencies import get_process_message_use_case

async def endpoint(
    use_case: ProcessMessageUseCase = Depends(get_process_message_use_case)
):
    async for chunk in use_case.execute(request):
        yield chunk
```

---

## 📦 Детальная миграция по компонентам

### 1. Session → Conversation

#### Создание сессии

**❌ Старый код:**
```python
from app.domain.entities import Session

session = Session(
    id="session-123",
    title="My Session"
)
session.add_message(message)
```

**✅ Новый код:**
```python
from app.domain.session_context.entities import Conversation
from app.domain.session_context.value_objects import ConversationId

conversation = Conversation.create(
    conversation_id=ConversationId("session-123"),
    title="My Session"
)
conversation.add_message(message)
```

#### Работа с сообщениями

**❌ Старый код:**
```python
# Прямая работа со списком
messages = session.messages
recent = messages[-10:]
```

**✅ Новый код:**
```python
# Через Value Object
messages = conversation.messages
recent = messages.get_recent(limit=10)
llm_format = messages.to_llm_format()
```

### 2. MessageOrchestrationService → Use Cases

#### Обработка сообщения

**❌ Старый код:**
```python
from app.domain.services import MessageOrchestrationService

service = MessageOrchestrationService(...)
async for chunk in service.process_message(
    session_id="session-123",
    message="Hello",
    agent_type="coder"
):
    yield chunk
```

**✅ Новый код:**
```python
from app.application.use_cases import ProcessMessageUseCase, ProcessMessageRequest

use_case = ProcessMessageUseCase(...)
request = ProcessMessageRequest(
    session_id="session-123",
    message="Hello",
    agent_type=AgentType.CODER
)
async for chunk in use_case.execute(request):
    yield chunk
```

#### Переключение агента

**❌ Старый код:**
```python
async for chunk in service.switch_agent(
    session_id="session-123",
    new_agent_type="architect"
):
    yield chunk
```

**✅ Новый код:**
```python
from app.application.use_cases import SwitchAgentUseCase, SwitchAgentRequest

use_case = SwitchAgentUseCase(...)
request = SwitchAgentRequest(
    session_id="session-123",
    new_agent_type=AgentType.ARCHITECT
)
async for chunk in use_case.execute(request):
    yield chunk
```

### 3. Dependencies → Модульный DI

#### Получение зависимостей

**❌ Старый код:**
```python
# dependencies.py - 893 строки
from app.core.dependencies import (
    get_session_management_service,
    get_agent_orchestration_service,
    get_message_orchestration_service,
    # ... еще 50+ функций
)
```

**✅ Новый код:**
```python
# dependencies.py - ~280 строк
from app.core.dependencies import (
    get_process_message_use_case,
    get_switch_agent_use_case,
    get_di_container
)

# Или напрямую через контейнер
from app.core.di import get_container

container = get_container()
use_case = container.get_process_message_use_case(db)
```

#### Создание кастомных зависимостей

**❌ Старый код:**
```python
# Добавление в dependencies.py (893 строки)
async def get_my_custom_service(...):
    # Множество зависимостей
    session_service = ...
    agent_service = ...
    # ...
    return MyCustomService(...)
```

**✅ Новый код:**
```python
# Создание нового модуля в app/core/di/
class MyCustomModule:
    def provide_my_service(self, ...):
        return MyCustomService(...)

# Добавление в DIContainer
class DIContainer:
    def __init__(self):
        self.my_module = MyCustomModule()
```

### 4. Адаптеры → Прямое использование

#### Работа с репозиториями

**❌ Старый код:**
```python
from app.domain.adapters import SessionAdapter, ConversationServiceAdapter

# Через адаптер
adapter = SessionAdapter(session_service)
session = adapter.get_session(session_id)

# Или через другой адаптер
conv_adapter = ConversationServiceAdapter(conversation_service)
conversation = conv_adapter.get_conversation(session_id)
```

**✅ Новый код:**
```python
from app.domain.session_context.services import ConversationManagementService

# Прямое использование
service = ConversationManagementService(repository)
conversation = await service.get_conversation(conversation_id)
```

---

## 🔧 Обновление существующего кода

### Шаг 1: Найти использование старых импортов

```bash
# Найти использование Session
grep -r "from app.domain.entities import Session" .

# Найти использование MessageOrchestrationService
grep -r "MessageOrchestrationService" .

# Найти использование адаптеров
grep -r "from app.domain.adapters" .
```

### Шаг 2: Обновить импорты

```python
# Замените:
from app.domain.entities import Session
# На:
from app.domain.session_context.entities import Conversation

# Замените:
from app.domain.services import MessageOrchestrationService
# На:
from app.application.use_cases import ProcessMessageUseCase

# Замените:
from app.domain.adapters import SessionAdapter
# На:
from app.domain.session_context.services import ConversationManagementService
```

### Шаг 3: Обновить код

```python
# Замените:
session = Session(id="session-123")
# На:
conversation = Conversation.create(
    conversation_id=ConversationId("session-123")
)

# Замените:
service.process_message(session_id, message, agent_type)
# На:
use_case.execute(ProcessMessageRequest(
    session_id=session_id,
    message=message,
    agent_type=agent_type
))
```

### Шаг 4: Обновить тесты

```python
# Замените:
def test_session_creation():
    session = Session(id="test-session")
    assert session.id == "test-session"

# На:
def test_conversation_creation():
    conv_id = ConversationId("test-session")
    conversation = Conversation.create(conversation_id=conv_id)
    assert conversation.conversation_id.value == "test-session"
```

---

## 📚 Новая структура проекта

### Bounded Contexts

```
app/domain/
├── session_context/          # Session Bounded Context
│   ├── entities/
│   │   └── conversation.py   # Вместо Session
│   ├── value_objects/
│   │   ├── conversation_id.py
│   │   ├── message_collection.py
│   │   └── message_content.py
│   ├── services/
│   │   ├── conversation_management_service.py
│   │   ├── conversation_snapshot_service.py
│   │   └── tool_message_cleanup_service.py
│   └── repositories/
│
├── agent_context/            # Agent Bounded Context
│   ├── entities/
│   ├── value_objects/
│   ├── services/
│   └── repositories/
│
├── execution_context/        # Execution Bounded Context
├── approval_context/         # Approval Bounded Context
├── llm_context/              # LLM Bounded Context
└── shared/                   # Shared Kernel
```

### DI Modules

```
app/core/di/
├── __init__.py
├── container.py              # Центральный контейнер
├── session_module.py         # Session Context DI
├── agent_module.py           # Agent Context DI
├── execution_module.py       # Execution Context DI
└── infrastructure_module.py  # Infrastructure DI
```

---

## ⚠️ Breaking Changes

### 1. Удаленные файлы

- ❌ [`app/domain/entities/session_legacy.py`](../codelab-ai-service/agent-runtime/app/domain/entities/session_legacy.py) - Удален
- ❌ [`app/domain/entities/agent_context_legacy.py`](../codelab-ai-service/agent-runtime/app/domain/entities/agent_context_legacy.py) - Удален
- ❌ [`app/domain/services/message_orchestration.py`](../codelab-ai-service/agent-runtime/app/domain/services/message_orchestration.py) - Удален
- ❌ [`app/domain/adapters/`](../codelab-ai-service/agent-runtime/app/domain/adapters/) - Директория удалена
- ❌ [`app/infrastructure/adapters/session_manager_adapter.py`](../codelab-ai-service/agent-runtime/app/infrastructure/adapters/session_manager_adapter.py) - Удален
- ❌ [`app/infrastructure/adapters/agent_context_manager_adapter.py`](../codelab-ai-service/agent-runtime/app/infrastructure/adapters/agent_context_manager_adapter.py) - Удален
- ❌ [`app/infrastructure/adapters/legacy_repository_adapters.py`](../codelab-ai-service/agent-runtime/app/infrastructure/adapters/legacy_repository_adapters.py) - Удален

### 2. Изменения в API

**Внимание:** API endpoints **не изменились**. Все изменения внутренние.

```python
# API остается прежним
POST /sessions
GET  /sessions/{session_id}
POST /agent/message/stream
# ... и т.д.
```

### 3. Изменения в базе данных

**Внимание:** Схема БД **не изменилась**. Миграции не требуются.

---

## 🧪 Тестирование после миграции

### 1. Unit тесты

```bash
# Запустить все unit тесты
pytest tests/unit/

# Запустить тесты для Session Context
pytest tests/unit/domain/session_context/

# Запустить тесты для Use Cases
pytest tests/unit/application/use_cases/
```

### 2. Integration тесты

```bash
# Запустить integration тесты
pytest tests/integration/

# Проверить работу с БД
pytest tests/integration/test_repositories.py
```

### 3. E2E тесты

```bash
# Запустить E2E тесты
pytest tests/e2e/

# Проверить API endpoints
pytest tests/e2e/test_api.py
```

---

## 📊 Метрики улучшения

| Метрика | До | После | Улучшение |
|---------|-----|-------|-----------|
| **dependencies.py** | 893 строки | ~280 строк | ✅ -69% |
| **Session entity** | 501 строка | 290 строк | ✅ -42% |
| **MessageOrchestrationService** | 432 строки | Удален | ✅ -100% |
| **Количество адаптеров** | 10 | 1 | ✅ -90% |
| **Средний размер класса** | ~350 строк | ~150 строк | ✅ -57% |
| **Цикломатическая сложность** | 15-20 | 5-8 | ✅ -60% |

---

## 🆘 Troubleshooting

### Проблема 1: ImportError для Session

**Ошибка:**
```python
ImportError: cannot import name 'Session' from 'app.domain.entities'
```

**Решение:**
```python
# Замените:
from app.domain.entities import Session
# На:
from app.domain.session_context.entities import Conversation
```

### Проблема 2: MessageOrchestrationService не найден

**Ошибка:**
```python
ImportError: cannot import name 'MessageOrchestrationService'
```

**Решение:**
```python
# Замените:
from app.domain.services import MessageOrchestrationService
# На:
from app.application.use_cases import ProcessMessageUseCase
```

### Проблема 3: Адаптеры не найдены

**Ошибка:**
```python
ImportError: No module named 'app.domain.adapters'
```

**Решение:**
```python
# Адаптеры удалены. Используйте прямые сервисы:
from app.domain.session_context.services import ConversationManagementService
```

### Проблема 4: DIContainer не работает

**Ошибка:**
```python
AttributeError: 'DIContainer' object has no attribute 'get_message_orchestration_service'
```

**Решение:**
```python
# Используйте новые методы:
container.get_process_message_use_case(db)
container.get_switch_agent_use_case(db)
```

---

## 📞 Поддержка

Если у вас возникли вопросы или проблемы с миграцией:

1. Проверьте этот guide
2. Изучите примеры в [`tests/`](../codelab-ai-service/agent-runtime/tests/)
3. Посмотрите новую архитектуру в [`doc/AGENT_RUNTIME_ARCHITECTURE_ASSESSMENT.md`](AGENT_RUNTIME_ARCHITECTURE_ASSESSMENT.md)
4. Обратитесь к команде разработки

---

## ✅ Checklist миграции

- [ ] Обновлены все импорты `Session` → `Conversation`
- [ ] Обновлены все импорты `MessageOrchestrationService` → Use Cases
- [ ] Удалены использования адаптеров
- [ ] Обновлены зависимости в роутерах
- [ ] Обновлены unit тесты
- [ ] Обновлены integration тесты
- [ ] Запущены все тесты (100% pass)
- [ ] Проверена работа в dev окружении
- [ ] Обновлена документация

---

**Автор:** CodeLab Team  
**Дата:** 7 февраля 2026  
**Версия:** 1.0  
**Статус:** ✅ Готов к использованию
