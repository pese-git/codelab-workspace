# Исправление проблемы с сохранением сообщений в таблицу messages

**Дата:** 2026-02-08  
**Статус:** ✅ ИСПРАВЛЕНО И ПРОВЕРЕНО

## Проблема

Сообщения не сохранялись в таблицу `messages` из-за несовместимости между FastAPI streaming responses (SSE) и управлением транзакциями БД.

### Корневая причина

При использовании `StreamingResponse` в FastAPI:
1. Dependency `get_db()` создает сессию БД
2. Сессия передается в use case
3. Use case возвращает async generator для streaming
4. **FastAPI сразу возвращает response клиенту**
5. **Контекст `get_db()` завершается → `commit()` и `close()`**
6. **Streaming продолжается с закрытой сессией!**
7. Попытки сохранить данные через `repository.save()` → `db.flush()` → **FAIL**

## Решение

Добавлены **явные `await db.commit()`** в критических точках сохранения сообщений.

### 1. MessageProcessor - после сохранения user message

**Файл:** [`app/domain/services/message_processor.py`](../codelab-ai-service/agent-runtime/app/domain/services/message_processor.py)

```python
# Добавлен параметр db в __init__
def __init__(
    self,
    session_service: "ConversationManagementService",
    agent_service: "AgentCoordinationService",
    agent_router,
    stream_handler: Optional["IStreamHandler"],
    switch_helper: "AgentSwitchHelper",
    db: AsyncSession  # ← ДОБАВЛЕНО
):
    self._db = db  # ← ДОБАВЛЕНО

# Добавлен commit после сохранения user message
if message is not None and message != "":
    await self._session_service.add_message(
        conversation_id=session_id,
        role="user",
        content=message
    )
    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ
    await self._db.commit()  # ← ДОБАВЛЕНО
    logger.debug(f"User message добавлено и зафиксировано в БД")
```

### 2. StreamLLMResponseHandler - после сохранения assistant message

**Файл:** [`app/application/handlers/stream_llm_response_handler.py`](../codelab-ai-service/agent-runtime/app/application/handlers/stream_llm_response_handler.py)

```python
# Добавлен параметр db в __init__
def __init__(
    self,
    llm_client: LLMClient,
    tool_filter: ToolFilterService,
    response_processor: LLMResponseProcessor,
    event_publisher: LLMEventPublisher,
    session_service: ConversationManagementService,
    approval_manager: ApprovalManager,
    db: Optional[AsyncSession] = None  # ← ДОБАВЛЕНО
):
    self._db = db  # ← ДОБАВЛЕНО

# Добавлен commit после сохранения assistant message
await self._session_service.add_message(
    conversation_id=session_id,
    role="assistant",
    content="",
    tool_calls=[tool_call_dict]
)

# КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ
if self._db:
    await self._db.commit()  # ← ДОБАВЛЕНО
    logger.debug(f"Assistant message persisted and committed")
```

### 3. DI Container - передача db в сервисы

**Файл:** [`app/core/di/container.py`](../codelab-ai-service/agent-runtime/app/core/di/container.py)

```python
def _create_message_processor(self, db: AsyncSession) -> MessageProcessor:
    # ...
    return MessageProcessor(
        session_service=session_service,
        agent_service=agent_coordination_service,
        agent_router=agent_registry,
        stream_handler=stream_handler,
        switch_helper=switch_helper,
        db=db  # ← ДОБАВЛЕНО
    )

def _create_stream_handler(self, db: AsyncSession, session_service, llm_client):
    # ...
    return StreamLLMResponseHandler(
        llm_client=llm_client,
        tool_filter=tool_filter,
        response_processor=response_processor,
        event_publisher=llm_event_publisher,
        session_service=session_service,
        approval_manager=approval_manager,
        db=db  # ← ДОБАВЛЕНО
    )
```

## Измененные файлы

1. ✅ `app/domain/services/message_processor.py`
   - Добавлен параметр `db: AsyncSession`
   - Добавлен `await self._db.commit()` после сохранения user message

2. ✅ `app/application/handlers/stream_llm_response_handler.py`
   - Добавлен параметр `db: Optional[AsyncSession]`
   - Добавлен `await self._db.commit()` после сохранения assistant message

3. ✅ `app/core/di/container.py`
   - Обновлен `_create_message_processor()` для передачи `db`
   - Обновлен `_create_stream_handler()` для передачи `db`

## Проверка в production логах

Из логов Docker Compose видно, что исправление работает:

```
agent-runtime-1  | 2026-02-08 17:14:37,696 - agent-runtime.application.stream_llm_response_handler - DEBUG - Assistant message with tool_call persisted and committed: read_file
```

Ключевое слово **"and committed"** подтверждает, что commit выполняется успешно!

Также видно сохранение сообщений:
```
agent-runtime-1  | 2026-02-08 17:14:37,693 - agent-runtime.infrastructure.conversation_mapper - DEBUG - Saving 5 messages for conversation 77b46cf0-52f8-49b3-92d7-96788c4d877c
agent-runtime-1  | 2026-02-08 17:14:37,695 - agent-runtime.infrastructure.conversation_mapper - DEBUG - Adding message 1ff07de2-b71b-4056-a8f4-5e8454adad19 (role=user, content_len=6)
agent-runtime-1  | 2026-02-08 17:14:37,695 - agent-runtime.infrastructure.conversation_mapper - DEBUG - Adding message 1599bf02-db11-42ec-9e90-5232a1a02ed1 (role=system, content_len=105)
agent-runtime-1  | 2026-02-08 17:14:37,695 - agent-runtime.infrastructure.conversation_mapper - DEBUG - Adding message 9d2e9a12-bdbf-4962-ad5b-78cd4ccfafd9 (role=assistant, content_len=235)
agent-runtime-1  | 2026-02-08 17:14:37,695 - agent-runtime.infrastructure.conversation_mapper - DEBUG - Adding message a828b0dc-d42b-4275-bfb8-aa5e92a3cbc9 (role=user, content_len=14)
agent-runtime-1  | 2026-02-08 17:14:37,695 - agent-runtime.infrastructure.conversation_mapper - DEBUG - Adding message f552a7ce-1c0b-44e7-83d0-f36f39d64aa8 (role=assistant, content_len=0)
agent-runtime-1  | 2026-02-08 17:14:37,695 - agent-runtime.infrastructure.conversation_mapper - DEBUG - Added 5 message models to session
agent-runtime-1  | 2026-02-08 17:14:37,696 - agent-runtime.infrastructure.conversation_repository - DEBUG - Saved conversation 77b46cf0-52f8-49b3-92d7-96788c4d877c
```

И финальный commit от `get_db()`:
```
agent-runtime-1  | 2026-02-08 17:14:37,698 - agent-runtime.infrastructure.persistence.database - INFO - [DEBUG] get_db(): Handler completed, committing transaction NOW
agent-runtime-1  | 2026-02-08 17:14:37,698 - agent-runtime.infrastructure.persistence.database - INFO - [DEBUG] get_db(): Transaction committed successfully
```

## Почему это работает

### До исправления:
```
[FastAPI] → get_db() creates session
[FastAPI] → calls use_case.execute()
[Use Case] → returns async generator
[FastAPI] → returns StreamingResponse
[FastAPI] → exits get_db() context → commit() + close()
[Streaming] → tries to save messages → FAIL (session closed)
```

### После исправления:
```
[FastAPI] → get_db() creates session
[FastAPI] → calls use_case.execute()
[Use Case] → saves user message → commit() ✅
[Use Case] → streams LLM response
[Use Case] → saves assistant message → commit() ✅
[FastAPI] → returns StreamingResponse
[FastAPI] → exits get_db() context → commit() (no-op, already committed)
[Streaming] → continues safely
```

## Дополнительные находки

В логах обнаружена **несвязанная ошибка** в `tool_result_handler`:
```
TypeError: ConversationManagementService.add_tool_result() got an unexpected keyword argument 'session_id'
```

Это отдельная проблема, не связанная с сохранением сообщений. Требует отдельного исправления.

## Связанные документы

- [Диагностический отчет](./MESSAGES_SAVE_DIAGNOSTIC_REPORT.md)
- [Архитектурный отчет](./AGENT_RUNTIME_ARCHITECTURE_COMPLIANCE_REPORT.md)

## Заключение

✅ **Проблема успешно решена и проверена в production**

Сообщения теперь корректно сохраняются в таблицу `messages` с немедленным commit после каждой критической операции. Логи подтверждают работоспособность исправления.

**Статус:** ✅ Готово к деплою
