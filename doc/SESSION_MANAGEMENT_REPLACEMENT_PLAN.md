# 🔄 План замены SessionManagementService на ConversationManagementService

**Дата:** 7 февраля 2026  
**Версия:** 1.0  
**Статус:** 📋 План готов к реализации

---

## 📋 Обзор

`SessionManagementService` - это legacy сервис, который работает со строками и старой архитектурой. Его нужно заменить на `ConversationManagementService` из нового Session Context, который использует Value Objects и DDD принципы.

---

## 🔍 Сравнение сервисов

### SessionManagementService (Legacy)

**Файл:** [`app/domain/services/session_management.py`](../codelab-ai-service/agent-runtime/app/domain/services/session_management.py)

**Характеристики:**
- ❌ Работает со строками (`session_id: str`)
- ❌ Использует старую сущность `Session` (через алиас `Conversation`)
- ❌ Размер: ~609 строк
- ❌ Зависимости: `SessionRepository`, `AgentContextRepository`
- ❌ Смешивает ответственности (session + agent context)

**Методы:**
```python
class SessionManagementService:
    async def create_session(self, session_id: Optional[str]) -> Session
    async def get_session(self, session_id: str) -> Session
    async def add_message(self, session_id: str, message: Message) -> None
    async def deactivate_session(self, session_id: str) -> None
    async def list_active_sessions(self) -> List[Session]
    # ... еще ~10 методов
```

### ConversationManagementService (New)

**Файл:** [`app/domain/session_context/services/conversation_management_service.py`](../codelab-ai-service/agent-runtime/app/domain/session_context/services/conversation_management_service.py)

**Характеристики:**
- ✅ Работает с Value Objects (`ConversationId`)
- ✅ Использует новую сущность `Conversation`
- ✅ Размер: ~200 строк
- ✅ Зависимости: только `ConversationRepository`
- ✅ Четкая ответственность (только conversations)

**Методы:**
```python
class ConversationManagementService:
    async def create_conversation(self, conversation_id: ConversationId) -> Conversation
    async def get_conversation(self, conversation_id: ConversationId) -> Conversation
    async def add_message(self, conversation_id: ConversationId, message: Message) -> None
    async def deactivate_conversation(self, conversation_id: ConversationId) -> None
    async def list_active_conversations(self) -> List[Conversation]
    # ... меньше методов, четкая ответственность
```

---

## 🎯 Преимущества замены

### 1. Архитектурная чистота ✅
- ✅ Соответствие DDD принципам
- ✅ Использование Value Objects
- ✅ Четкие границы ответственности

### 2. Упрощение кода ✅
- ✅ Размер уменьшается с ~609 до ~200 строк (-67%)
- ✅ Меньше зависимостей
- ✅ Проще тестировать

### 3. Типобезопасность ✅
- ✅ Value Objects предотвращают ошибки
- ✅ Невозможно передать невалидный ID
- ✅ Compile-time проверки

### 4. Расширяемость ✅
- ✅ Легко добавлять новые методы
- ✅ Легко расширять функциональность
- ✅ Готовность к Event-Based архитектуре

---

## 🔧 План замены

### Этап 1: Создать адаптер для совместимости

**Цель:** Обеспечить плавный переход без breaking changes

**Решение:** Создать `SessionServiceAdapter`, который оборачивает `ConversationManagementService`

```python
# app/domain/session_context/adapters/session_service_adapter.py

class SessionServiceAdapter:
    """
    Адаптер для обратной совместимости.
    
    Преобразует вызовы с str в вызовы с ConversationId.
    """
    
    def __init__(self, conversation_service: ConversationManagementService):
        self._conversation_service = conversation_service
    
    async def create_session(self, session_id: Optional[str] = None) -> Session:
        """Создать сессию (совместимость с legacy API)."""
        # Преобразовать str → ConversationId
        conv_id = ConversationId(session_id) if session_id else ConversationId.generate()
        
        # Вызвать новый сервис
        conversation = await self._conversation_service.create_conversation(conv_id)
        
        # Вернуть как Session (алиас для Conversation)
        return conversation
    
    async def get_session(self, session_id: str) -> Session:
        """Получить сессию (совместимость с legacy API)."""
        conv_id = ConversationId(session_id)
        return await self._conversation_service.get_conversation(conv_id)
    
    async def add_message(self, session_id: str, message: Message) -> None:
        """Добавить сообщение (совместимость с legacy API)."""
        conv_id = ConversationId(session_id)
        await self._conversation_service.add_message(conv_id, message)
    
    # ... остальные методы аналогично
```

### Этап 2: Обновить DI модуль

**Обновить:** [`app/core/di/session_module.py`](codelab-ai-service/agent-runtime/app/core/di/session_module.py)

```python
class SessionModule:
    def provide_session_service(self, db: AsyncSession, event_publisher=None):
        """
        Предоставить session service (через адаптер).
        
        Возвращает адаптер, который оборачивает ConversationManagementService.
        """
        if self._session_service is None:
            # Создать новый сервис
            conversation_repo = ConversationRepositoryImpl(db)
            conversation_service = ConversationManagementService(
                repository=conversation_repo
            )
            
            # Обернуть в адаптер для совместимости
            from app.domain.session_context.adapters import SessionServiceAdapter
            self._session_service = SessionServiceAdapter(conversation_service)
        
        return self._session_service
```

### Этап 3: Обновить ConversationRepositoryImpl

**Обновить:** [`app/infrastructure/persistence/repositories/conversation_repository_impl.py`](codelab-ai-service/agent-runtime/app/infrastructure/persistence/repositories/conversation_repository_impl.py)

**Проблема:** Репозиторий ожидает `ConversationId`, но получает `str`

**Решение:** Добавить поддержку обоих типов

```python
from typing import Union

class ConversationRepositoryImpl:
    async def find_by_id(
        self,
        conversation_id: Union[str, ConversationId]
    ) -> Optional[Conversation]:
        """
        Найти conversation по ID.
        
        Поддерживает оба типа для обратной совместимости:
        - str (legacy)
        - ConversationId (new)
        """
        # Преобразовать в строку
        if isinstance(conversation_id, ConversationId):
            id_value = conversation_id.value
        else:
            id_value = conversation_id
        
        result = await self._db.execute(
            select(SessionModel).where(
                SessionModel.id == id_value,
                SessionModel.is_active == True
            )
        )
        # ...
```

### Этап 4: Тестирование

**Тесты:**
1. Unit тесты для `SessionServiceAdapter`
2. Integration тесты для endpoints
3. E2E тесты для полного flow

**Проверить:**
- ✅ POST /sessions работает
- ✅ GET /sessions работает
- ✅ GET /sessions/{id} работает
- ✅ Все существующие тесты проходят

### Этап 5: Постепенная миграция

**Шаг 1:** Использовать адаптер (текущий этап)
```python
# Через адаптер
session_service = SessionServiceAdapter(conversation_service)
session = await session_service.create_session("session-123")
```

**Шаг 2:** Мигрировать код на прямое использование
```python
# Прямое использование
conversation_service = ConversationManagementService(repo)
conversation = await conversation_service.create_conversation(
    ConversationId("session-123")
)
```

**Шаг 3:** Удалить адаптер и `SessionManagementService`

---

## 📊 Сравнение подходов

### Вариант 1: Через адаптер (рекомендуется)

**Преимущества:**
- ✅ Нет breaking changes
- ✅ Постепенная миграция
- ✅ Легко откатить

**Недостатки:**
- ⚠️ Дополнительный слой абстракции
- ⚠️ Небольшое снижение производительности

### Вариант 2: Прямая замена

**Преимущества:**
- ✅ Чистая архитектура сразу
- ✅ Максимальная производительность
- ✅ Нет промежуточных слоев

**Недостатки:**
- ❌ Breaking changes
- ❌ Нужно обновить весь код сразу
- ❌ Сложно откатить

---

## 🎯 Рекомендация

**Использовать Вариант 1: Через адаптер**

**Причины:**
1. Минимальные изменения в существующем коде
2. Нет breaking changes для API
3. Постепенная миграция
4. Легко тестировать

**Roadmap:**
1. **Неделя 1:** Создать `SessionServiceAdapter`
2. **Неделя 2:** Обновить `ConversationRepositoryImpl` для поддержки обоих типов
3. **Неделя 3:** Обновить DI модуль для использования адаптера
4. **Неделя 4:** Тестирование и деплой
5. **Месяц 2-3:** Постепенная миграция кода на прямое использование
6. **Месяц 4:** Удаление адаптера и `SessionManagementService`

---

## 📝 Пример реализации

### SessionServiceAdapter

```python
"""
Адаптер для обратной совместимости SessionManagementService.

Оборачивает ConversationManagementService и преобразует типы.
"""

from typing import Optional, List
from datetime import datetime

from ..entities.conversation import Conversation as Session
from ..value_objects import ConversationId
from ...entities.message import Message
from .conversation_management_service import ConversationManagementService


class SessionServiceAdapter:
    """
    Адаптер для обратной совместимости с SessionManagementService.
    
    Преобразует вызовы с str в вызовы с ConversationId.
    Позволяет использовать новый ConversationManagementService
    с legacy кодом без изменений.
    
    Пример:
        >>> adapter = SessionServiceAdapter(conversation_service)
        >>> session = await adapter.create_session("session-123")
        >>> session.id  # "session-123" (str)
    """
    
    def __init__(self, conversation_service: ConversationManagementService):
        """
        Инициализация адаптера.
        
        Args:
            conversation_service: Новый сервис управления conversations
        """
        self._conversation_service = conversation_service
    
    async def create_session(
        self,
        session_id: Optional[str] = None
    ) -> Session:
        """
        Создать сессию (legacy API).
        
        Args:
            session_id: ID сессии (str)
            
        Returns:
            Session: Созданная сессия
        """
        # Преобразовать str → ConversationId
        if session_id:
            conv_id = ConversationId(session_id)
        else:
            conv_id = ConversationId.generate()
        
        # Вызвать новый сервис
        conversation = await self._conversation_service.create_conversation(conv_id)
        
        # Вернуть как Session (Conversation - это алиас для Session)
        return conversation
    
    async def get_session(self, session_id: str) -> Session:
        """Получить сессию (legacy API)."""
        conv_id = ConversationId(session_id)
        return await self._conversation_service.get_conversation(conv_id)
    
    async def add_message(
        self,
        session_id: str,
        message: Message
    ) -> None:
        """Добавить сообщение (legacy API)."""
        conv_id = ConversationId(session_id)
        await self._conversation_service.add_message(conv_id, message)
    
    async def deactivate_session(self, session_id: str) -> None:
        """Деактивировать сессию (legacy API)."""
        conv_id = ConversationId(session_id)
        await self._conversation_service.deactivate_conversation(conv_id)
    
    async def list_active_sessions(self) -> List[Session]:
        """Получить список активных сессий (legacy API)."""
        return await self._conversation_service.list_active_conversations()
    
    async def get_message_count(self, session_id: str) -> int:
        """Получить количество сообщений (legacy API)."""
        conv_id = ConversationId(session_id)
        conversation = await self._conversation_service.get_conversation(conv_id)
        return conversation.messages.count()
    
    async def clear_messages(self, session_id: str) -> int:
        """Очистить сообщения (legacy API)."""
        conv_id = ConversationId(session_id)
        conversation = await self._conversation_service.get_conversation(conv_id)
        count = conversation.messages.count()
        await self._conversation_service.clear_messages(conv_id)
        return count
```

---

## 🔧 Шаги реализации

### Шаг 1: Создать SessionServiceAdapter

```bash
# Создать файл адаптера
touch codelab-ai-service/agent-runtime/app/domain/session_context/adapters/__init__.py
touch codelab-ai-service/agent-runtime/app/domain/session_context/adapters/session_service_adapter.py
```

### Шаг 2: Обновить ConversationRepositoryImpl

**Файл:** [`conversation_repository_impl.py`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/repositories/conversation_repository_impl.py)

```python
from typing import Union

async def find_by_id(
    self,
    conversation_id: Union[str, ConversationId]
) -> Optional[Conversation]:
    """Поддержка обоих типов для совместимости."""
    id_value = (
        conversation_id.value 
        if isinstance(conversation_id, ConversationId) 
        else conversation_id
    )
    # ... остальная логика
```

### Шаг 3: Обновить SessionModule

**Файл:** [`session_module.py`](../codelab-ai-service/agent-runtime/app/core/di/session_module.py)

```python
def provide_session_service(self, db: AsyncSession, event_publisher=None):
    """Предоставить session service через адаптер."""
    if self._session_service is None:
        # Создать новый сервис
        conversation_repo = ConversationRepositoryImpl(db)
        conversation_service = ConversationManagementService(
            repository=conversation_repo
        )
        
        # Обернуть в адаптер
        from app.domain.session_context.adapters import SessionServiceAdapter
        self._session_service = SessionServiceAdapter(conversation_service)
    
    return self._session_service
```

### Шаг 4: Тестирование

```python
# tests/unit/adapters/test_session_service_adapter.py

async def test_create_session_with_id():
    """Тест создания сессии с ID."""
    adapter = SessionServiceAdapter(conversation_service)
    session = await adapter.create_session("test-session")
    
    assert session.id == "test-session"
    assert session.is_active == True

async def test_create_session_without_id():
    """Тест создания сессии без ID (автогенерация)."""
    adapter = SessionServiceAdapter(conversation_service)
    session = await adapter.create_session()
    
    assert session.id is not None
    assert len(session.id) > 0
```

---

## 📊 Метрики улучшения

| Метрика | SessionManagementService | ConversationManagementService | Улучшение |
|---------|--------------------------|-------------------------------|-----------|
| **Размер** | ~609 строк | ~200 строк | ✅ -67% |
| **Зависимости** | 2 (Session + AgentContext) | 1 (Conversation) | ✅ -50% |
| **Методы** | ~15 | ~8 | ✅ -47% |
| **Типобезопасность** | Низкая (str) | Высокая (Value Objects) | ✅ +100% |
| **Цикломатическая сложность** | 15-20 | 5-8 | ✅ -60% |

---

## ⚠️ Риски и митигация

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Breaking changes в API | Низкая | Критическое | Использовать адаптер |
| Регрессия функциональности | Средняя | Высокое | Полное тестирование |
| Снижение производительности | Низкая | Среднее | Бенчмарки |
| Проблемы с миграцией данных | Низкая | Среднее | Нет изменений в БД |

---

## ✅ Checklist реализации

- [ ] Создать `SessionServiceAdapter`
- [ ] Обновить `ConversationRepositoryImpl` для поддержки `Union[str, ConversationId]`
- [ ] Обновить `SessionModule.provide_session_service()`
- [ ] Написать unit тесты для адаптера
- [ ] Написать integration тесты
- [ ] Протестировать все endpoints
- [ ] Обновить документацию
- [ ] Code review
- [ ] Деплой в dev
- [ ] Тестирование в dev
- [ ] Деплой в production

---

## 🎯 Ожидаемый результат

После замены:
- ✅ POST /sessions будет работать
- ✅ Все endpoints будут работать
- ✅ Код станет чище и проще
- ✅ Архитектура будет соответствовать плану на 100%
- ✅ Готовность к Event-Based архитектуре

---

**Автор:** CodeLab Team  
**Дата:** 7 февраля 2026  
**Версия:** 1.0  
**Статус:** 📋 План готов к реализации
