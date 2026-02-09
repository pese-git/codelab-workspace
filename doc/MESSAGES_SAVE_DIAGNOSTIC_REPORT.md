# Диагностический отчет: Проблема с сохранением сообщений в таблицу messages

**Дата:** 2026-02-08  
**Статус:** 🔴 КРИТИЧЕСКАЯ ПРОБЛЕМА ОБНАРУЖЕНА

## Краткое описание проблемы

Сообщения не сохраняются в таблицу `messages` из-за **несовместимости между FastAPI streaming responses и управлением транзакциями БД**.

## Корневая причина

### Проблема в архитектуре

В файле [`app/api/v1/routers/messages_router.py`](../codelab-ai-service/agent-runtime/app/api/v1/routers/messages_router.py) endpoint `/agent/message/stream` использует **Server-Sent Events (SSE)** для streaming ответов:

```python
@router.post("/stream")
async def message_stream_sse(
    request: MessageStreamRequest,
    process_message_use_case=Depends(get_process_message_use_case),  # ← Здесь создается DB session
    ...
):
    async def generate():
        async for chunk in process_message_use_case.execute(use_case_request):
            yield f"data: {chunk_json}\n\n"  # ← Streaming продолжается
    
    return StreamingResponse(generate(), ...)  # ← FastAPI сразу возвращает response
```

### Последовательность событий (проблемная)

1. **FastAPI вызывает dependency** `Depends(get_db)` → создается сессия БД
2. **Сессия передается** в `ProcessMessageUseCase` через DI
3. **Use Case начинает streaming** (возвращает async generator)
4. **FastAPI НЕМЕДЛЕННО возвращает** `StreamingResponse` клиенту
5. **Контекст `get_db()` завершается** → вызывается `await session.commit()` и `await session.close()`
6. **Streaming продолжается**, но сессия УЖЕ ЗАКРЫТА!
7. **Попытки сохранить сообщения** через `repository.save()` → `db.flush()` → **FAIL** (сессия закрыта)

### Доказательства

#### 1. get_db() делает commit сразу после yield

Файл: [`app/infrastructure/persistence/database.py:102-126`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/database.py)

```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            logger.debug(f"[DEBUG] get_db(): Session created, yielding to handler")
            yield session  # ← FastAPI получает сессию
            # ↓ Эта строка выполняется СРАЗУ после return StreamingResponse()
            logger.info(f"[DEBUG] get_db(): Handler completed, committing transaction NOW")
            await session.commit()  # ← Commit происходит ДО завершения streaming!
            logger.info(f"[DEBUG] get_db(): Transaction committed successfully")
        except Exception as e:
            logger.error(f"[DEBUG] get_db(): Exception occurred, rolling back: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()  # ← Сессия закрывается
            logger.debug(f"[DEBUG] get_db(): Session closed")
```

#### 2. Repository.save() только делает flush(), не commit()

Файл: [`app/infrastructure/persistence/repositories/conversation_repository_impl.py:207-218`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/repositories/conversation_repository_impl.py)

```python
async def save(self, conversation: Conversation) -> None:
    """Сохранить conversation."""
    await self._mapper.to_model(conversation, self._db)
    await self._db.flush()  # ← Только flush, НЕ commit!
    logger.debug(f"Saved conversation {conversation.conversation_id.value}")
```

#### 3. ConversationMapper.to_model() создает MessageModel

Файл: [`app/infrastructure/persistence/mappers/conversation_mapper.py:173-201`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/mappers/conversation_mapper.py)

```python
async def to_model(self, entity: Conversation, db: AsyncSession) -> SessionModel:
    # ... создание SessionModel ...
    
    # Сохранить сообщения (атомарная замена)
    await db.execute(
        delete(MessageModel).where(MessageModel.session_db_id == model.id)
    )
    
    # Добавить новые сообщения
    for message in entity.messages.messages:
        logger.debug(f"Adding message {message.id} ...")
        msg_model = MessageModel(
            id=message.id,
            session_db_id=model.id,
            role=message.role,
            content=message.content,
            # ...
        )
        db.add(msg_model)  # ← Добавляется в сессию, но сессия уже закрыта!
    
    return model
```

## Воздействие

- ❌ **Сообщения не сохраняются** в таблицу `messages`
- ❌ **История разговора теряется** после перезапуска сервиса
- ❌ **Невозможно восстановить контекст** при повторном подключении
- ⚠️ **Тесты могут проходить**, т.к. они используют `await db.commit()` явно

## Решение

### Вариант 1: Commit внутри streaming (РЕКОМЕНДУЕТСЯ)

Добавить явный commit после каждого важного события в streaming:

```python
# В MessageProcessor или StreamLLMResponseHandler
async def process(...):
    # Сохранить user message
    await self._conversation_service.add_message(...)
    await self._db.commit()  # ← Явный commit
    
    # Stream LLM response
    async for chunk in llm_stream:
        yield chunk
    
    # Сохранить assistant message
    await self._conversation_service.add_message(...)
    await self._db.commit()  # ← Явный commit
```

### Вариант 2: Использовать отдельную сессию для каждой операции

```python
# В ConversationManagementService
async def add_message(self, ...):
    # Создать новую сессию для этой операции
    async with async_session_maker() as db:
        repo = ConversationRepositoryImpl(db)
        await repo.save(conversation)
        await db.commit()  # Commit в той же сессии
```

### Вариант 3: Переделать на non-streaming для критичных операций

Сохранять сообщения синхронно, а streaming использовать только для токенов LLM.

## Рекомендации

1. **Немедленно**: Добавить явные `await db.commit()` после сохранения сообщений
2. **Краткосрочно**: Рефакторинг для использования отдельных сессий БД
3. **Долгосрочно**: Пересмотреть архитектуру управления транзакциями для streaming endpoints

## Файлы, требующие изменений

1. `app/domain/services/message_processor.py` - добавить commit после сохранения
2. `app/application/handlers/stream_llm_response_handler.py` - добавить commit
3. `app/domain/session_context/services/conversation_management_service.py` - опция для auto-commit
4. `app/infrastructure/persistence/repositories/conversation_repository_impl.py` - опция для commit

## Тестирование

После исправления проверить:

```bash
# 1. Отправить сообщение через API
curl -X POST http://localhost:8001/agent/message/stream \
  -H "Content-Type: application/json" \
  -d '{"session_id":"test-123","message":{"type":"user_message","content":"Hello"}}'

# 2. Проверить наличие сообщений в БД
sqlite3 data/agent_runtime.db "SELECT COUNT(*) FROM messages WHERE session_db_id='test-123';"
```

Ожидаемый результат: количество сообщений > 0

## Связанные файлы

- [`app/api/v1/routers/messages_router.py`](../codelab-ai-service/agent-runtime/app/api/v1/routers/messages_router.py)
- [`app/infrastructure/persistence/database.py`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/database.py)
- [`app/infrastructure/persistence/repositories/conversation_repository_impl.py`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/repositories/conversation_repository_impl.py)
- [`app/infrastructure/persistence/mappers/conversation_mapper.py`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/mappers/conversation_mapper.py)
- [`app/domain/services/message_processor.py`](../codelab-ai-service/agent-runtime/app/domain/services/message_processor.py)
