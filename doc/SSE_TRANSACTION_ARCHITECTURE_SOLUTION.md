# Архитектурное решение для управления транзакциями в SSE-сервисе

## Дата: 2026-02-08
## Статус: PROPOSED
## Автор: AI Assistant

---

## 1. Проблема

### 1.1 Корневая причина

Сообщения не сохраняются из-за **использования РАЗНЫХ сессий БД** в разных слоях приложения:

```
┌─────────────────────────────────────────────────────────────┐
│ FastAPI Handler (get_db)                                     │
│   ↓ Session A (через Depends)                               │
│   ├─> MessageProcessor (получает Session A)                 │
│   │     ├─> commit на Session A                             │
│   │     └─> ConversationManagementService                   │
│   │           └─> ConversationRepository                    │
│   │                 └─> Session B (НОВАЯ через repository!) │
│   │                       └─> Данные в Session B             │
│   └─> get_db() делает commit на Session A                   │
│         └─> Данные из Session B НЕ сохраняются!             │
└─────────────────────────────────────────────────────────────┘
```

**Результат**: `ForeignKeyViolationError` - данные из Session B не видны при commit Session A.

### 1.2 Специфика SSE (Server-Sent Events)

1. **Долгоживущие соединения**: SSE держит HTTP-соединение открытым минуты/часы
2. **Потоковая передача**: Данные отправляются чанками по мере генерации
3. **Высокая нагрузка**: Тысячи одновременных SSE-соединений
4. **Асинхронность**: Множество операций БД во время одного SSE-стрима

### 1.3 Конфликт требований

| Требование | SSE | Транзакции БД |
|------------|-----|---------------|
| Длительность | Минуты/часы | Миллисекунды |
| Изоляция | Не требуется | Критична |
| Блокировки | Недопустимы | Необходимы |
| Commit | Частые | Редкие |

---

## 2. Анализ текущей архитектуры

### 2.1 Точки создания сессий БД

#### A. FastAPI Dependency Injection
```python
# app/infrastructure/persistence/database.py
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
        await session.commit()  # ← Commit в конце запроса
```

#### B. DI Container
```python
# app/core/di/container.py
def get_process_message_use_case(self, db: AsyncSession):
    return ProcessMessageUseCase(
        message_processor=self._create_message_processor(db),  # ← Session A
        lock_manager=self._get_lock_manager()
    )
```

#### C. Repository Layer
```python
# app/core/di/session_module.py
def provide_conversation_repository(self, db: AsyncSession):
    return ConversationRepositoryImpl(db)  # ← Должна использовать ту же сессию!
```

### 2.2 Проблемные паттерны

❌ **Антипаттерн 1**: Создание новых сессий в репозиториях
```python
# НЕПРАВИЛЬНО
class SomeRepository:
    async def save(self, entity):
        async with async_session_maker() as db:  # ← НОВАЯ сессия!
            db.add(entity)
            await db.commit()
```

❌ **Антипаттерн 2**: Commit в середине SSE-стрима
```python
# НЕПРАВИЛЬНО
async def process_message():
    await session_service.add_message(...)
    await db.commit()  # ← Commit во время стрима
    async for chunk in llm_stream():
        yield chunk
```

❌ **Антипаттерн 3**: Долгоживущие транзакции
```python
# НЕПРАВИЛЬНО
async def sse_handler(db: AsyncSession):
    # Транзакция открыта весь SSE-стрим (минуты!)
    async for chunk in process_stream():
        yield chunk
    # Commit только в конце
```

---

## 3. Архитектурное решение

### 3.1 Принципы

1. **Одна сессия на запрос** - все операции используют одну и ту же сессию
2. **Короткие транзакции** - commit после каждой логической операции
3. **Явное управление** - контроль над границами транзакций
4. **Изоляция данных** - каждый SSE-стрим работает независимо

### 3.2 Паттерн: Unit of Work для SSE

```python
class SSEUnitOfWork:
    """
    Unit of Work для SSE-стримов с поддержкой микро-транзакций.
    
    Особенности:
    - Создает одну сессию на весь SSE-стрим
    - Поддерживает явные commit'ы после каждой операции
    - Автоматически rollback при ошибках
    - Закрывает сессию после завершения стрима
    """
    
    def __init__(self, session_factory):
        self._session_factory = session_factory
        self._session: Optional[AsyncSession] = None
    
    async def __aenter__(self):
        self._session = self._session_factory()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            await self._session.rollback()
        await self._session.close()
    
    @property
    def session(self) -> AsyncSession:
        """Получить текущую сессию БД."""
        return self._session
    
    async def commit(self):
        """
        Явный commit текущей транзакции.
        Используется после каждой логической операции.
        """
        await self._session.commit()
        logger.debug("UoW: Transaction committed")
    
    async def flush(self):
        """
        Flush без commit - для проверки FK constraints.
        """
        await self._session.flush()
        logger.debug("UoW: Session flushed")
```

### 3.3 Применение в SSE-обработчике

```python
@router.post("/sessions/{session_id}/messages")
async def process_message(
    session_id: str,
    request: MessageRequest,
    container: DIContainer = Depends(get_container)
):
    """
    SSE endpoint с правильным управлением транзакциями.
    """
    
    async def event_stream():
        # Создать UoW для всего SSE-стрима
        async with SSEUnitOfWork(async_session_maker) as uow:
            try:
                # 1. Создать use case с единой сессией
                use_case = container.get_process_message_use_case(uow.session)
                
                # 2. Обработать сообщение с явными commit'ами
                async for chunk in use_case.execute(
                    session_id=session_id,
                    message=request.message,
                    uow=uow  # ← Передаем UoW для явных commit'ов
                ):
                    yield f"data: {chunk.json()}\n\n"
                
            except Exception as e:
                logger.error(f"Error in SSE stream: {e}")
                error_chunk = StreamChunk(type="error", error=str(e))
                yield f"data: {error_chunk.json()}\n\n"
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream"
    )
```

### 3.4 Микро-транзакции в MessageProcessor

```python
class MessageProcessor:
    """
    Процессор сообщений с поддержкой микро-транзакций.
    """
    
    async def process(
        self,
        session_id: str,
        message: str,
        uow: SSEUnitOfWork  # ← Получаем UoW
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Обработка с явными границами транзакций.
        """
        
        # ТРАНЗАКЦИЯ 1: Создание сессии
        session = await self._session_service.get_or_create_conversation(session_id)
        await uow.commit()  # ← Явный commit
        logger.debug(f"✓ Session {session_id} persisted")
        
        # ТРАНЗАКЦИЯ 2: Добавление user message
        if message:
            await self._session_service.add_message(
                conversation_id=session_id,
                role="user",
                content=message
            )
            await uow.commit()  # ← Явный commit
            logger.debug(f"✓ User message persisted")
        
        # ТРАНЗАКЦИЯ 3: Создание агента
        agent = await self._agent_service.get_or_create_agent(
            session_id=session_id,
            initial_type=AgentType.ORCHESTRATOR
        )
        await uow.commit()  # ← Явный commit
        logger.debug(f"✓ Agent persisted")
        
        # Обработка через LLM (без транзакций - только чтение)
        async for chunk in self._process_with_agent(session_id, agent):
            # ТРАНЗАКЦИЯ 4: Сохранение assistant message
            if chunk.type == "assistant_message":
                await self._session_service.add_message(
                    conversation_id=session_id,
                    role="assistant",
                    content=chunk.content
                )
                await uow.commit()  # ← Явный commit
                logger.debug(f"✓ Assistant message persisted")
            
            yield chunk
```

---

## 4. Варианты реализации

### 4.1 Вариант A: Минимальные изменения (РЕКОМЕНДУЕТСЯ)

**Суть**: Убрать создание новых сессий, использовать переданную сессию везде.

#### Изменения:

1. **SessionModule**: Убедиться, что репозитории используют переданную сессию
```python
def provide_conversation_repository(self, db: AsyncSession):
    # Всегда использовать переданную сессию
    return ConversationRepositoryImpl(db)  # ← db из DI
```

2. **MessageProcessor**: Добавить явные commit'ы
```python
async def process(self, session_id: str, message: str):
    session = await self._session_service.get_or_create_conversation(session_id)
    await self._db.commit()  # ← Явный commit
    
    if message:
        await self._session_service.add_message(...)
        await self._db.commit()  # ← Явный commit
```

3. **StreamLLMResponseHandler**: Добавить commit после сохранения
```python
async def _handle_tool_call(self, ...):
    await self._session_service.add_message(...)
    if self._db:
        await self._db.commit()  # ← Явный commit
```

**Плюсы**:
- ✅ Минимальные изменения кода
- ✅ Быстрая реализация (1-2 часа)
- ✅ Решает текущую проблему

**Минусы**:
- ⚠️ Не решает проблему долгих транзакций
- ⚠️ Ручное управление commit'ами

### 4.2 Вариант B: Unit of Work Pattern

**Суть**: Внедрить паттерн Unit of Work для явного управления транзакциями.

#### Изменения:

1. Создать `SSEUnitOfWork` (см. раздел 3.2)
2. Обновить API handlers для использования UoW
3. Передавать UoW через все слои
4. Явные commit'ы через `uow.commit()`

**Плюсы**:
- ✅ Явное управление транзакциями
- ✅ Поддержка микро-транзакций
- ✅ Лучшая тестируемость
- ✅ Масштабируемость

**Минусы**:
- ⚠️ Требует рефакторинга (2-3 дня)
- ⚠️ Изменения во всех слоях
- ⚠️ Нужно обучить команду

### 4.3 Вариант C: Event-Driven с Outbox Pattern

**Суть**: Разделить SSE-стрим и персистентность через события.

#### Архитектура:

```
┌──────────────────────────────────────────────────────────┐
│ SSE Handler                                               │
│   ↓                                                       │
│   ├─> Process Message (in-memory)                        │
│   │     └─> Emit Events                                  │
│   │           ├─> MessageAdded                           │
│   │           ├─> AgentSwitched                          │
│   │           └─> ToolExecuted                           │
│   │                                                       │
│   └─> Background Worker                                  │
│         └─> Consume Events                               │
│               └─> Persist to DB (короткие транзакции)   │
└──────────────────────────────────────────────────────────┘
```

**Плюсы**:
- ✅ Полное разделение SSE и БД
- ✅ Короткие транзакции
- ✅ Высокая производительность
- ✅ Eventual consistency

**Минусы**:
- ⚠️ Сложная реализация (1-2 недели)
- ⚠️ Eventual consistency (не immediate)
- ⚠️ Требует message broker (Redis/RabbitMQ)

---

## 5. Рекомендации

### 5.1 Краткосрочное решение (1-2 дня)

**Вариант A: Минимальные изменения**

1. ✅ Аудит всех мест создания сессий БД
2. ✅ Убрать `async with async_session_maker()` из репозиториев
3. ✅ Добавить явные `commit()` после критических операций
4. ✅ Добавить логирование для отладки

### 5.2 Среднесрочное решение (1-2 недели)

**Вариант B: Unit of Work Pattern**

1. Реализовать `SSEUnitOfWork`
2. Обновить API handlers
3. Рефакторинг MessageProcessor и handlers
4. Добавить интеграционные тесты

### 5.3 Долгосрочное решение (1-2 месяца)

**Вариант C: Event-Driven Architecture**

1. Внедрить Event Bus
2. Реализовать Outbox Pattern
3. Создать Background Workers
4. Мониторинг и observability

---

## 6. План действий

### Фаза 1: Быстрое исправление (СЕЙЧАС)

```bash
# 1. Аудит создания сессий
grep -r "async_session_maker()" --include="*.py"

# 2. Проверить SessionModule
# Убедиться, что provide_conversation_repository использует переданную сессию

# 3. Добавить commit'ы в критических местах
# - MessageProcessor.process() после создания session
# - MessageProcessor.process() после добавления message
# - StreamLLMResponseHandler после сохранения assistant message

# 4. Тестирование
python diagnose_messages_save.py
```

### Фаза 2: Рефакторинг (СЛЕДУЮЩАЯ НЕДЕЛЯ)

1. Создать `SSEUnitOfWork`
2. Обновить `ProcessMessageUseCase`
3. Обновить API handlers
4. Написать тесты

### Фаза 3: Мониторинг (ПОСТОЯННО)

1. Добавить метрики:
   - Длительность транзакций
   - Количество commit'ов на запрос
   - Ошибки FK constraints
2. Настроить алерты
3. Dashboard в Grafana

---

## 7. Метрики успеха

### 7.1 Функциональные

- ✅ Все сообщения сохраняются в БД
- ✅ Нет `ForeignKeyViolationError`
- ✅ История сообщений доступна после перезапуска

### 7.2 Производительность

- ✅ Длительность транзакций < 100ms
- ✅ Количество commit'ов на запрос: 3-5
- ✅ Нет блокировок БД > 1s

### 7.3 Надежность

- ✅ 99.9% успешных сохранений
- ✅ Автоматический rollback при ошибках
- ✅ Нет потери данных при сбоях

---

## 8. Риски и митигация

### 8.1 Риск: Долгие транзакции блокируют БД

**Митигация**:
- Использовать микро-транзакции (commit после каждой операции)
- Мониторинг длительности транзакций
- Timeout для транзакций (30s)

### 8.2 Риск: Race conditions при параллельных запросах

**Митигация**:
- Использовать `SessionLockManager` для критических секций
- Оптимистичные блокировки (version field)
- Retry logic для конфликтов

### 8.3 Риск: Увеличение нагрузки на БД

**Митигация**:
- Connection pooling (уже есть)
- Read replicas для чтения
- Кэширование частых запросов

---

## 9. Примеры кода

### 9.1 Правильное использование сессии

```python
# ✅ ПРАВИЛЬНО
class MessageProcessor:
    def __init__(self, session_service, db: AsyncSession):
        self._session_service = session_service
        self._db = db  # ← Одна сессия на весь запрос
    
    async def process(self, session_id: str, message: str):
        # Операция 1
        session = await self._session_service.get_or_create_conversation(session_id)
        await self._db.commit()  # ← Явный commit
        
        # Операция 2
        await self._session_service.add_message(...)
        await self._db.commit()  # ← Явный commit
```

### 9.2 Неправильное использование сессии

```python
# ❌ НЕПРАВИЛЬНО
class MessageProcessor:
    async def process(self, session_id: str, message: str):
        # Создание новой сессии внутри метода
        async with async_session_maker() as db:  # ← ПЛОХО!
            session = await self._session_service.get_or_create_conversation(session_id)
            await db.commit()
```

### 9.3 Unit of Work в действии

```python
# ✅ ПРАВИЛЬНО с UoW
@router.post("/sessions/{session_id}/messages")
async def process_message(session_id: str, request: MessageRequest):
    async def event_stream():
        async with SSEUnitOfWork(async_session_maker) as uow:
            use_case = container.get_process_message_use_case(uow.session)
            
            async for chunk in use_case.execute(
                session_id=session_id,
                message=request.message,
                uow=uow
            ):
                yield f"data: {chunk.json()}\n\n"
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

---

## 10. Заключение

### 10.1 Текущее состояние

- ❌ Сообщения не сохраняются из-за разных сессий БД
- ❌ Commit'ы происходят на неправильной сессии
- ❌ ForeignKey constraints нарушаются

### 10.2 Целевое состояние

- ✅ Одна сессия БД на весь SSE-запрос
- ✅ Явные микро-транзакции после каждой операции
- ✅ Все данные корректно сохраняются
- ✅ Высокая производительность и надежность

### 10.3 Следующие шаги

1. **НЕМЕДЛЕННО**: Реализовать Вариант A (минимальные изменения)
2. **НА ЭТОЙ НЕДЕЛЕ**: Тестирование и мониторинг
3. **СЛЕДУЮЩАЯ НЕДЕЛЯ**: Начать рефакторинг к Варианту B (UoW)
4. **ЧЕРЕЗ МЕСЯЦ**: Оценить необходимость Варианта C (Event-Driven)

---

## Приложения

### A. Диагностический чеклист

```bash
# 1. Проверить создание сессий
grep -r "async_session_maker()" app/ --include="*.py"

# 2. Проверить commit'ы
grep -r "await.*commit()" app/ --include="*.py"

# 3. Проверить rollback'и
grep -r "await.*rollback()" app/ --include="*.py"

# 4. Запустить диагностику
python diagnose_messages_save.py
```

### B. Полезные ссылки

- [SQLAlchemy Async Sessions](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Unit of Work Pattern](https://martinfowler.com/eaaCatalog/unitOfWork.html)
- [Outbox Pattern](https://microservices.io/patterns/data/transactional-outbox.html)
- [FastAPI Streaming](https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse)

---

**Документ создан**: 2026-02-08  
**Последнее обновление**: 2026-02-08  
**Версия**: 1.0  
**Статус**: PROPOSED
