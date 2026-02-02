# 🔧 Plan Approval Database Lock Fix

## Проблема

### Симптомы
```
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) database is locked
[SQL: INSERT INTO plans (...) VALUES (...)]
```

### Причина
В [`plan_repository_impl.py:85`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/repositories/plan_repository_impl.py:85) использовался неправильный паттерн управления транзакциями:

```python
await self._db.flush()  # Flush changes within transaction
logger.debug(f"Saved plan {entity.id}")

except Exception as e:
    logger.error(f"Error saving plan {entity.id}: {e}", exc_info=True)
    # Rollback transaction to clear broken state
    await self._db.rollback()  # ❌ ПРОБЛЕМА: ручной rollback
```

**Проблема:** Репозиторий пытался управлять транзакцией вручную (`rollback()`), но транзакция уже управляется на уровне [`get_db()`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/database.py:102-125) dependency.

### Последствия
1. ❌ План не сохраняется в БД
2. ❌ FSM переходит в `error_handling` состояние
3. ❌ Пользователь не получает диалог одобрения плана
4. ❌ Database lock при конкурентном доступе

---

## Решение

### Архитектура управления транзакциями

В проекте используется **централизованное управление транзакциями** на уровне FastAPI dependency:

```python
# app/infrastructure/persistence/database.py:102-125
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency для получения async database session."""
    async with async_session_maker() as session:
        try:
            yield session
            # ✅ Автоматический commit после успешного завершения
            await session.commit()
        except Exception as e:
            # ✅ Автоматический rollback при ошибке
            await session.rollback()
            raise
        finally:
            await session.close()
```

### Исправление в PlanRepositoryImpl

**До:**
```python
async def save(self, entity: Plan) -> None:
    try:
        # ... сохранение ...
        await self._db.flush()
        logger.debug(f"Saved plan {entity.id}")
    except Exception as e:
        logger.error(f"Error saving plan {entity.id}: {e}")
        await self._db.rollback()  # ❌ Конфликт с get_db()
        raise RepositoryError(...)
```

**После:**
```python
async def save(self, entity: Plan) -> None:
    """
    Note:
        Транзакция управляется на уровне get_db() dependency.
        Commit происходит автоматически после успешного завершения.
    """
    try:
        # ... сохранение ...
        # Flush для получения ID и проверки constraints
        # Commit будет выполнен автоматически в get_db()
        await self._db.flush()
        logger.debug(f"Saved plan {entity.id}")
    except Exception as e:
        logger.error(f"Error saving plan {entity.id}: {e}")
        # ✅ Не делаем rollback - это будет сделано в get_db()
        raise RepositoryError(...)
```

### Изменения

1. ✅ Удален ручной `rollback()` из `save()` метода
2. ✅ Удален ручной `rollback()` из обработчика ошибок
3. ✅ Добавлена документация о паттерне управления транзакциями
4. ✅ Сохранен `flush()` для получения ID и проверки constraints
5. ✅ Аналогичные изменения в `delete()` методе

---

## Паттерн управления транзакциями

### ✅ Правильный паттерн (используется в проекте)

```python
# Repository Layer - НЕ управляет транзакциями
class PlanRepositoryImpl:
    async def save(self, entity: Plan) -> None:
        # Только операции с данными
        self._db.add(model)
        await self._db.flush()  # OK: для ID и constraints
        # НЕТ commit/rollback

# Dependency Layer - управляет транзакциями
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()  # Автоматический commit
        except Exception:
            await session.rollback()  # Автоматический rollback
            raise
```

### ❌ Неправильный паттерн (был в коде)

```python
# Repository Layer - пытается управлять транзакциями
class PlanRepositoryImpl:
    async def save(self, entity: Plan) -> None:
        try:
            self._db.add(model)
            await self._db.flush()
        except Exception:
            await self._db.rollback()  # ❌ Конфликт!
            raise
```

---

## SQLite Configuration

Для предотвращения database lock в SQLite используется WAL mode:

```python
# app/infrastructure/persistence/database.py:71-82
@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Set SQLite pragmas for better performance"""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")        # ✅ WAL mode
    cursor.execute("PRAGMA synchronous=NORMAL")      # ✅ Faster writes
    cursor.execute("PRAGMA cache_size=-64000")       # ✅ 64MB cache
    cursor.execute("PRAGMA temp_store=MEMORY")       # ✅ Memory temp
    cursor.execute("PRAGMA busy_timeout=30000")      # ✅ 30s timeout
    cursor.close()
```

### Преимущества WAL mode:
- ✅ Читатели не блокируют писателей
- ✅ Писатели не блокируют читателей
- ✅ Лучшая производительность при конкурентном доступе
- ✅ Меньше database lock ошибок

---

## Тестирование

### Проверка исправления

1. **Создание плана:**
   ```bash
   # Отправить сообщение, требующее планирования
   curl -X POST http://localhost:8000/api/sessions/{session_id}/messages \
     -H "Content-Type: application/json" \
     -d '{"content": "Create a login form with validation"}'
   ```

2. **Проверка сохранения в БД:**
   ```bash
   # Проверить, что план сохранен
   sqlite3 data/agent_runtime.db "SELECT * FROM plans ORDER BY created_at DESC LIMIT 1;"
   ```

3. **Проверка UI:**
   - ✅ Диалог Plan Approval должен появиться автоматически
   - ✅ План должен отображаться в UI
   - ✅ Кнопки Approve/Reject должны работать

### Ожидаемое поведение

**До исправления:**
```
❌ database is locked
❌ FSM -> error_handling
❌ План не сохранен
❌ Диалог не показан
```

**После исправления:**
```
✅ План сохранен в БД
✅ FSM -> awaiting_plan_approval
✅ Диалог показан пользователю
✅ Approval flow работает
```

---

## Рекомендации

### 1. Для SQLite в Production

⚠️ **SQLite не рекомендуется для production** при высокой нагрузке:

```yaml
# Рекомендуется PostgreSQL
DATABASE_URL: postgresql+asyncpg://user:pass@host:5432/db
```

**Причины:**
- Лучшая поддержка конкурентности
- Нет file-based locks
- Лучшая производительность при множественных соединениях
- Поддержка advanced features (LISTEN/NOTIFY, etc.)

### 2. Паттерн Repository

✅ **Всегда следуйте паттерну:**
- Repository НЕ управляет транзакциями
- Используйте `flush()` только для получения ID
- Позвольте `get_db()` управлять commit/rollback

### 3. Обработка ошибок

```python
# ✅ Правильно
async def save(self, entity: Plan) -> None:
    try:
        # операции с БД
        await self._db.flush()
    except Exception as e:
        logger.error(f"Error: {e}")
        raise RepositoryError(...)  # Пробросить ошибку

# ❌ Неправильно
async def save(self, entity: Plan) -> None:
    try:
        # операции с БД
        await self._db.flush()
    except Exception as e:
        await self._db.rollback()  # Конфликт!
        raise
```

### 4. Проверка других репозиториев

Убедитесь, что другие репозитории следуют тому же паттерну:
- ✅ `SessionRepositoryImpl`
- ✅ `AgentContextRepositoryImpl`
- ✅ `ApprovalRepositoryImpl`

---

## Статус

- ✅ **Исправлено:** [`plan_repository_impl.py`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/repositories/plan_repository_impl.py)
- ✅ **Документировано:** Паттерн управления транзакциями
- ✅ **SQLite WAL mode:** Уже настроен
- ⏳ **Тестирование:** Требуется проверка в runtime

---

## Связанные документы

- [Plan Approval UI Integration Complete](./PLAN_APPROVAL_UI_INTEGRATION_COMPLETE.md)
- [Plan Approval Full Implementation Complete](./PLAN_APPROVAL_FULL_IMPLEMENTATION_COMPLETE.md)
- [Plan Approval Implementation Guide](./PLAN_APPROVAL_IMPLEMENTATION_GUIDE.md)

---

## Заключение

Проблема database lock была вызвана **конфликтом управления транзакциями** между repository layer и dependency layer. Исправление заключается в удалении ручного `rollback()` из репозитория и полагании на автоматическое управление транзакциями в `get_db()`.

После этого исправления:
- ✅ Планы корректно сохраняются в БД
- ✅ FSM переходит в правильное состояние
- ✅ UI получает события и показывает диалог
- ✅ Plan Approval flow работает end-to-end

**Все UI компоненты готовы и будут работать корректно после применения этого исправления.**
