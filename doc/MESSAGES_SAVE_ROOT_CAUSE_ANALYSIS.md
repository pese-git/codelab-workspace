# Анализ корневой причины: Сообщения не сохраняются в таблицу messages

**Дата:** 2026-02-08  
**Статус:** 🔴 КРИТИЧЕСКАЯ АРХИТЕКТУРНАЯ ПРОБЛЕМА

## Корневая причина

Сообщения не сохраняются из-за **использования РАЗНЫХ сессий БД** в разных слоях приложения.

### Архитектурная проблема

```
[API Layer] → get_db() создает Session A
    ↓
[Use Case] → получает Session A
    ↓
[MessageProcessor] → получает Session A через DI
    ↓
[ConversationManagementService] → создает НОВУЮ Session B через repository!
    ↓
[Repository] → использует Session B для save()
    ↓
[Mapper] → db.add(message) в Session B
    ↓
[Repository] → db.flush() в Session B
    ↓
[MessageProcessor] → await self._db.commit() в Session A ❌
    ↓
Результат: Session B не зафиксирована, Session A пустая!
```

### Доказательства из логов

```
# Сессия создается
Session создана и зафиксирована в БД: 5a6c0bc0-9a02-4f1b-a6f0-38b44a8bbee6

# User message добавляется
Saving 1 messages for conversation 5a6c0bc0-9a02-4f1b-a6f0-38b44a8bbee6
Saved conversation 5a6c0bc0-9a02-4f1b-a6f0-38b44a8bbee6

# Но при создании agent_context:
ForeignKeyViolationError: Key (session_db_id)=(5a6c0bc0-9a02-4f1b-a6f0-38b44a8bbee6) 
is not present in table "sessions"
```

### Почему это происходит

1. **`SessionModule.provide_session_service()`** создает `ConversationRepositoryImpl` с НОВОЙ сессией БД
2. **`MessageProcessor`** получает ДРУГУЮ сессию БД через параметр `db`
3. Когда `MessageProcessor` вызывает `await self._db.commit()`, он фиксирует СВОЮ сессию
4. Но данные находятся в ДРУГОЙ сессии (в repository)!

### Код, подтверждающий проблему

**Файл:** `app/core/di/session_module.py`

```python
def provide_session_service(
    self,
    db: AsyncSession,  # ← Получает Session A
    event_publisher: Optional[EventPublisher] = None
) -> ConversationManagementService:
    # Создает repository с Session A
    conversation_repository = self.provide_conversation_repository(db)
    
    return ConversationManagementService(
        repository=conversation_repository,  # ← Использует Session A
        ...
    )
```

**НО!** В некоторых местах создается НОВАЯ сессия:

```python
# Где-то в коде (нужно найти)
async with async_session_maker() as db:  # ← Session B!
    repo = ConversationRepositoryImpl(db)
    service = ConversationManagementService(repo)
```

## Правильное решение

### Вариант 1: Единая сессия БД (РЕКОМЕНДУЕТСЯ)

Убедиться, что ВСЕ сервисы используют ОДНУ И ТУ ЖЕ сессию БД, переданную через DI:

```python
# В SessionModule
def provide_session_service(
    self,
    db: AsyncSession,  # ← Та же сессия
    event_publisher: Optional[EventPublisher] = None
) -> ConversationManagementService:
    # Использовать ТУ ЖЕ сессию db
    conversation_repository = ConversationRepositoryImpl(db)  # ← Та же сессия!
    
    return ConversationManagementService(
        repository=conversation_repository,
        ...
    )
```

### Вариант 2: Commit в repository.save()

Добавить параметр `commit` в `repository.save()`:

```python
async def save(self, conversation: Conversation, commit: bool = False) -> None:
    await self._mapper.to_model(conversation, self._db)
    await self._db.flush()
    if commit:
        await self._db.commit()  # ← Опциональный commit
```

### Вариант 3: Использовать Unit of Work pattern

Создать `UnitOfWork` для управления транзакциями:

```python
class UnitOfWork:
    def __init__(self, db: AsyncSession):
        self._db = db
        self.conversations = ConversationRepositoryImpl(db)
        self.agents = AgentRepositoryImpl(db)
    
    async def commit(self):
        await self._db.commit()
    
    async def rollback(self):
        await self._db.rollback()
```

## Немедленное решение

Проверить, что `SessionModule.provide_conversation_repository()` использует переданную сессию `db`, а НЕ создает новую.

## Файлы для проверки

1. `app/core/di/session_module.py` - как создается repository
2. `app/domain/session_context/services/conversation_management_service.py` - как используется repository
3. `app/infrastructure/persistence/repositories/conversation_repository_impl.py` - какая сессия используется

## Следующие шаги

1. Проверить `SessionModule.provide_conversation_repository()`
2. Убедиться, что используется переданная сессия `db`
3. Удалить все места, где создается новая сессия через `async_session_maker()`
4. Протестировать сохранение

## Связанные документы

- [Диагностический отчет](./MESSAGES_SAVE_DIAGNOSTIC_REPORT.md)
- [Попытка исправления](./MESSAGES_SAVE_FIX_SUMMARY.md)
