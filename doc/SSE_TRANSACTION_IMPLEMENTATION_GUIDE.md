# Руководство по реализации решения для транзакций в SSE

## Дата: 2026-02-08
## Статус: IMPLEMENTATION GUIDE

---

## 1. Быстрое исправление (Вариант A) - РЕКОМЕНДУЕТСЯ СЕЙЧАС

### 1.1 Цель

Исправить проблему с сохранением сообщений минимальными изменениями кода.

### 1.2 Шаги реализации

#### Шаг 1: Аудит создания сессий БД

```bash
# Найти все места, где создаются новые сессии
cd codelab-ai-service/agent-runtime
grep -r "async_session_maker()" app/ --include="*.py" -n

# Ожидаемый результат: должны быть только в:
# - app/infrastructure/persistence/database.py (get_db)
# - app/main.py (cleanup tasks)
```

**Действие**: Если найдены другие места - удалить их!

#### Шаг 2: Проверить SessionModule

Файл: [`app/core/di/session_module.py`](codelab-ai-service/agent-runtime/app/core/di/session_module.py:49)

```python
def provide_conversation_repository(
    self,
    db: AsyncSession  # ← Должна использовать эту сессию!
) -> ConversationRepository:
    """Предоставить репозиторий conversations."""
    return ConversationRepositoryImpl(db)  # ← Передаем db из параметра
```

**Проверка**: Убедиться, что НЕ создается новая сессия внутри.

#### Шаг 3: Добавить commit'ы в MessageProcessor

Файл: [`app/domain/services/message_processor.py`](codelab-ai-service/agent-runtime/app/domain/services/message_processor.py:117)

**УЖЕ ИСПРАВЛЕНО** ✅:
- Строка 119: `await self._db.commit()` после создания session
- Строка 143: `await self._db.commit()` после создания agent

**Проверка**: Убедиться, что commit'ы на месте.

#### Шаг 4: Добавить commit'ы в StreamLLMResponseHandler

Файл: [`app/application/handlers/stream_llm_response_handler.py`](codelab-ai-service/agent-runtime/app/application/handlers/stream_llm_response_handler.py:334)

**УЖЕ ИСПРАВЛЕНО** ✅:
- Строка 335: `await self._db.commit()` после tool_call message
- Строка 401: `await self._db.commit()` после assistant message

**Проверка**: Убедиться, что commit'ы на месте.

#### Шаг 5: Тестирование

```bash
# Запустить диагностический скрипт
cd codelab-ai-service/agent-runtime
python diagnose_messages_save.py

# Ожидаемый результат:
# ✅ Session создана и зафиксирована в БД
# ✅ User message добавлено
# ✅ Assistant message сохранено
# ✅ Все сообщения найдены в БД
```

### 1.3 Чеклист проверки

- [ ] Нет `async_session_maker()` в репозиториях
- [ ] Нет `async_session_maker()` в сервисах
- [ ] Commit после создания session в MessageProcessor
- [ ] Commit после создания agent в MessageProcessor
- [ ] Commit после сохранения assistant message в StreamLLMResponseHandler
- [ ] Диагностический скрипт проходит успешно
- [ ] Нет ForeignKeyViolationError в логах

---

## 2. Рефакторинг с Unit of Work (Вариант B) - СЛЕДУЮЩИЙ ЭТАП

### 2.1 Цель

Внедрить паттерн Unit of Work для явного управления транзакциями.

### 2.2 Шаги реализации

#### Шаг 1: Создать SSEUnitOfWork

**УЖЕ СОЗДАНО** ✅: [`app/infrastructure/persistence/unit_of_work.py`](codelab-ai-service/agent-runtime/app/infrastructure/persistence/unit_of_work.py)

#### Шаг 2: Обновить ProcessMessageUseCase

Файл: [`app/application/use_cases/process_message_use_case.py`](codelab-ai-service/agent-runtime/app/application/use_cases/process_message_use_case.py)

```python
from typing import AsyncGenerator, Optional
from ...infrastructure.persistence.unit_of_work import SSEUnitOfWork
from ...models.schemas import StreamChunk

class ProcessMessageUseCase:
    """Use Case для обработки сообщений с UoW."""
    
    def __init__(self, message_processor, lock_manager):
        self._message_processor = message_processor
        self._lock_manager = lock_manager
    
    async def execute(
        self,
        session_id: str,
        message: Optional[str],
        agent_type: Optional[str] = None,
        uow: Optional[SSEUnitOfWork] = None  # ← Добавить параметр
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Обработать сообщение с поддержкой UoW.
        
        Args:
            session_id: ID сессии
            message: Сообщение пользователя
            agent_type: Тип агента (опционально)
            uow: Unit of Work для управления транзакциями
        """
        async with self._lock_manager.acquire(session_id):
            # Передать UoW в message_processor
            async for chunk in self._message_processor.process(
                session_id=session_id,
                message=message,
                agent_type=agent_type,
                uow=uow  # ← Передать UoW
            ):
                yield chunk
```

#### Шаг 3: Обновить MessageProcessor

Файл: [`app/domain/services/message_processor.py`](codelab-ai-service/agent-runtime/app/domain/services/message_processor.py:78)

```python
async def process(
    self,
    session_id: str,
    message: Optional[str],
    agent_type: Optional[AgentType] = None,
    correlation_id: Optional[str] = None,
    uow: Optional[SSEUnitOfWork] = None  # ← Добавить параметр
) -> AsyncGenerator[StreamChunk, None]:
    """Обработать сообщение с поддержкой UoW."""
    
    # Использовать UoW если передан, иначе self._db
    db = uow.session if uow else self._db
    
    # ТРАНЗАКЦИЯ 1: Создание сессии
    session = await self._session_service.get_or_create_conversation(session_id)
    if uow:
        await uow.commit()  # ← Явный commit через UoW
    else:
        await db.commit()   # ← Fallback на старый способ
    
    # ТРАНЗАКЦИЯ 2: Добавление user message
    if message:
        await self._session_service.add_message(...)
        if uow:
            await uow.commit()
        else:
            await db.commit()
    
    # ... остальной код
```

#### Шаг 4: Обновить API handler

Файл: [`app/api/v1/routers/messages_router.py`](codelab-ai-service/agent-runtime/app/api/v1/routers/messages_router.py)

```python
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from app.infrastructure.persistence.database import async_session_maker
from app.infrastructure.persistence.unit_of_work import SSEUnitOfWork

@router.post("/sessions/{session_id}/messages")
async def process_message(
    session_id: str,
    request: MessageRequest,
    container = Depends(get_container)
):
    """SSE endpoint с Unit of Work."""
    
    async def event_stream():
        # Создать UoW для всего SSE-стрима
        async with SSEUnitOfWork(async_session_maker) as uow:
            try:
                # Создать use case с сессией из UoW
                use_case = container.get_process_message_use_case(uow.session)
                
                # Обработать с передачей UoW
                async for chunk in use_case.execute(
                    session_id=session_id,
                    message=request.message,
                    agent_type=request.agent_type,
                    uow=uow  # ← Передать UoW
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

#### Шаг 5: Тестирование

```python
# tests/integration/test_sse_unit_of_work.py
import pytest
from app.infrastructure.persistence.unit_of_work import SSEUnitOfWork
from app.infrastructure.persistence.database import async_session_maker

@pytest.mark.asyncio
async def test_uow_commit():
    """Тест commit через UoW."""
    async with SSEUnitOfWork(async_session_maker) as uow:
        # Создать сессию
        session = SessionModel(session_db_id="test-123")
        uow.session.add(session)
        await uow.commit()
        
        # Проверить, что сохранилось
        result = await uow.session.execute(
            select(SessionModel).where(SessionModel.session_db_id == "test-123")
        )
        assert result.scalar_one_or_none() is not None

@pytest.mark.asyncio
async def test_uow_rollback_on_error():
    """Тест rollback при ошибке."""
    try:
        async with SSEUnitOfWork(async_session_maker) as uow:
            session = SessionModel(session_db_id="test-456")
            uow.session.add(session)
            await uow.commit()
            
            # Вызвать ошибку
            raise ValueError("Test error")
    except ValueError:
        pass
    
    # Проверить, что данные НЕ откатились (commit уже был)
    async with SSEUnitOfWork(async_session_maker) as uow:
        result = await uow.session.execute(
            select(SessionModel).where(SessionModel.session_db_id == "test-456")
        )
        assert result.scalar_one_or_none() is not None
```

### 2.3 Чеклист проверки

- [ ] SSEUnitOfWork создан и протестирован
- [ ] ProcessMessageUseCase обновлен
- [ ] MessageProcessor поддерживает UoW
- [ ] StreamLLMResponseHandler поддерживает UoW
- [ ] API handlers используют UoW
- [ ] Интеграционные тесты написаны и проходят
- [ ] Документация обновлена

---

## 3. Мониторинг и метрики

### 3.1 Добавить логирование транзакций

```python
# app/infrastructure/persistence/database.py
import time

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency с метриками."""
    start_time = time.time()
    commit_count = 0
    
    async with async_session_maker() as session:
        try:
            # Обернуть commit для подсчета
            original_commit = session.commit
            
            async def tracked_commit():
                nonlocal commit_count
                commit_count += 1
                await original_commit()
            
            session.commit = tracked_commit
            
            yield session
            
            await session.commit()
            commit_count += 1
            
        except Exception as e:
            await session.rollback()
            raise
        finally:
            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                f"DB Session: duration={duration_ms:.2f}ms, "
                f"commits={commit_count}"
            )
            await session.close()
```

### 3.2 Prometheus метрики

```python
# app/infrastructure/monitoring/metrics.py
from prometheus_client import Counter, Histogram

# Метрики транзакций
db_transaction_duration = Histogram(
    'db_transaction_duration_seconds',
    'Duration of database transactions',
    ['operation']
)

db_commits_total = Counter(
    'db_commits_total',
    'Total number of database commits',
    ['endpoint']
)

db_rollbacks_total = Counter(
    'db_rollbacks_total',
    'Total number of database rollbacks',
    ['endpoint', 'error_type']
)

# Использование
with db_transaction_duration.labels(operation='create_session').time():
    await session_service.create_conversation(session_id)
    await db.commit()
    db_commits_total.labels(endpoint='process_message').inc()
```

### 3.3 Алерты

```yaml
# prometheus/alerts.yml
groups:
  - name: database
    rules:
      # Долгие транзакции
      - alert: LongDatabaseTransaction
        expr: db_transaction_duration_seconds > 1
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "Долгая транзакция БД"
          description: "Транзакция {{ $labels.operation }} длится > 1s"
      
      # Частые rollback'и
      - alert: HighRollbackRate
        expr: rate(db_rollbacks_total[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Высокий процент rollback'ов"
          description: "Rollback rate > 10% на {{ $labels.endpoint }}"
      
      # FK violations
      - alert: ForeignKeyViolations
        expr: rate(db_rollbacks_total{error_type="ForeignKeyViolation"}[5m]) > 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Foreign Key Violations обнаружены"
          description: "FK violations на {{ $labels.endpoint }}"
```

---

## 4. Миграция существующего кода

### 4.1 Поиск проблемных мест

```bash
# Найти все места с commit
grep -r "await.*\.commit()" app/ --include="*.py" -n

# Найти все места с rollback
grep -r "await.*\.rollback()" app/ --include="*.py" -n

# Найти все создания сессий
grep -r "async_session_maker()" app/ --include="*.py" -n
```

### 4.2 Паттерны замены

#### До (неправильно):
```python
async def some_operation():
    async with async_session_maker() as db:
        result = await db.execute(query)
        await db.commit()
        return result
```

#### После (правильно):
```python
async def some_operation(db: AsyncSession):
    result = await db.execute(query)
    # Commit вызывается снаружи
    return result
```

### 4.3 Рефакторинг репозиториев

#### До:
```python
class SomeRepository:
    def __init__(self):
        pass
    
    async def save(self, entity):
        async with async_session_maker() as db:
            db.add(entity)
            await db.commit()
```

#### После:
```python
class SomeRepository:
    def __init__(self, db: AsyncSession):
        self._db = db
    
    async def save(self, entity):
        self._db.add(entity)
        # Commit вызывается через UoW
```

---

## 5. Troubleshooting

### 5.1 Проблема: ForeignKeyViolationError

**Симптомы**:
```
sqlalchemy.exc.IntegrityError: (psycopg2.errors.ForeignKeyViolation) 
Key (session_db_id)=(xxx) is not present in table "sessions"
```

**Диагностика**:
```python
# Добавить логирование перед каждым commit
logger.info(f"About to commit: session_id={session_id}")
await db.commit()
logger.info(f"Committed successfully: session_id={session_id}")
```

**Решение**:
1. Убедиться, что parent entity создана и зафиксирована ПЕРЕД child entity
2. Проверить, что используется одна и та же сессия БД
3. Добавить `await db.flush()` перед проверкой FK

### 5.2 Проблема: Долгие транзакции блокируют БД

**Симптомы**:
- Timeout при сохранении
- Deadlock errors
- Медленные запросы

**Диагностика**:
```sql
-- PostgreSQL: найти долгие транзакции
SELECT pid, now() - xact_start AS duration, state, query
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY duration DESC;
```

**Решение**:
1. Использовать микро-транзакции (commit после каждой операции)
2. Уменьшить scope транзакций
3. Использовать `READ COMMITTED` isolation level

### 5.3 Проблема: Race conditions при параллельных запросах

**Симптомы**:
- Дублирование данных
- Lost updates
- Inconsistent state

**Решение**:
```python
# Использовать SessionLockManager
async with self._lock_manager.acquire(session_id):
    # Критическая секция
    session = await self._session_service.get_or_create_conversation(session_id)
    await uow.commit()
```

---

## 6. Чеклист готовности к продакшену

### 6.1 Функциональность

- [ ] Все сообщения сохраняются в БД
- [ ] Нет ForeignKeyViolationError
- [ ] История сообщений доступна после перезапуска
- [ ] SSE-стримы работают корректно
- [ ] Tool calls сохраняются правильно

### 6.2 Производительность

- [ ] Длительность транзакций < 100ms
- [ ] Количество commit'ов на запрос: 3-5
- [ ] Нет блокировок БД > 1s
- [ ] Connection pool настроен правильно
- [ ] Нет утечек соединений

### 6.3 Надежность

- [ ] Автоматический rollback при ошибках
- [ ] Graceful shutdown закрывает все соединения
- [ ] Retry logic для transient errors
- [ ] Circuit breaker для БД
- [ ] Health checks работают

### 6.4 Мониторинг

- [ ] Метрики транзакций в Prometheus
- [ ] Алерты настроены
- [ ] Dashboard в Grafana
- [ ] Логирование транзакций
- [ ] Distributed tracing (опционально)

### 6.5 Документация

- [ ] Архитектурное решение задокументировано
- [ ] Руководство по реализации создано
- [ ] API документация обновлена
- [ ] Runbook для операторов
- [ ] Примеры кода

---

## 7. Следующие шаги

### Неделя 1: Быстрое исправление
- [x] Создать документацию
- [x] Создать SSEUnitOfWork
- [ ] Аудит создания сессий
- [ ] Проверить commit'ы
- [ ] Тестирование

### Неделя 2: Рефакторинг
- [ ] Обновить ProcessMessageUseCase
- [ ] Обновить MessageProcessor
- [ ] Обновить API handlers
- [ ] Написать тесты
- [ ] Code review

### Неделя 3: Мониторинг
- [ ] Добавить метрики
- [ ] Настроить алерты
- [ ] Создать dashboard
- [ ] Load testing
- [ ] Performance tuning

### Неделя 4: Продакшен
- [ ] Staging deployment
- [ ] Smoke tests
- [ ] Production deployment
- [ ] Мониторинг 24/7
- [ ] Postmortem (если нужно)

---

## Приложения

### A. Полезные команды

```bash
# Проверить состояние БД
psql -U postgres -d agent_runtime -c "SELECT * FROM sessions LIMIT 10;"

# Найти долгие транзакции
psql -U postgres -d agent_runtime -c "
SELECT pid, now() - xact_start AS duration, state, query
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY duration DESC;
"

# Убить долгую транзакцию
psql -U postgres -d agent_runtime -c "SELECT pg_terminate_backend(PID);"

# Проверить размер БД
psql -U postgres -d agent_runtime -c "
SELECT pg_size_pretty(pg_database_size('agent_runtime'));
"
```

### B. Примеры тестов

```python
# tests/integration/test_transaction_management.py
import pytest
from sqlalchemy import select
from app.infrastructure.persistence.models import SessionModel, MessageModel

@pytest.mark.asyncio
async def test_message_saved_after_commit(db_session):
    """Тест: сообщение сохраняется после commit."""
    # Создать session
    session = SessionModel(session_db_id="test-123")
    db_session.add(session)
    await db_session.commit()
    
    # Создать message
    message = MessageModel(
        session_db_id="test-123",
        role="user",
        content="Hello"
    )
    db_session.add(message)
    await db_session.commit()
    
    # Проверить
    result = await db_session.execute(
        select(MessageModel).where(MessageModel.session_db_id == "test-123")
    )
    messages = result.scalars().all()
    assert len(messages) == 1
    assert messages[0].content == "Hello"

@pytest.mark.asyncio
async def test_fk_violation_without_commit(db_session):
    """Тест: FK violation если parent не зафиксирован."""
    # Создать session БЕЗ commit
    session = SessionModel(session_db_id="test-456")
    db_session.add(session)
    # НЕ делаем commit!
    
    # Попытаться создать message
    message = MessageModel(
        session_db_id="test-456",
        role="user",
        content="Hello"
    )
    db_session.add(message)
    
    # Должна быть ошибка FK при commit
    with pytest.raises(Exception):  # ForeignKeyViolation
        await db_session.commit()
```

---

**Документ создан**: 2026-02-08  
**Последнее обновление**: 2026-02-08  
**Версия**: 1.0  
**Статус**: IMPLEMENTATION GUIDE
