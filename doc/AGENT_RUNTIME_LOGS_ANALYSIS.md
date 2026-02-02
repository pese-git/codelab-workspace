# Анализ логов Agent Runtime (Docker Compose)

**Дата:** 2026-02-01  
**Время:** 18:43-18:47 UTC  
**Статус:** Критическая ошибка обнаружена

---

## 🔴 Критическая проблема: SQLite Database Locked

### Основная ошибка

```
sqlalchemy.exc.PendingRollbackError: This Session's transaction has been rolled back 
due to a previous exception during flush. To begin a new transaction with this Session, 
first issue Session.rollback(). 

Original exception was: (sqlite3.OperationalError) database is locked
```

### Контекст ошибки

**Операция:** Сохранение плана в БД  
**Файл:** [`plan_repository_impl.py:73-90`](codelab-ai-service/agent-runtime/app/infrastructure/persistence/repositories/plan_repository_impl.py:73)  
**Вызов:** [`architect_agent.py:243`](codelab-ai-service/agent-runtime/app/agents/architect_agent.py:243)

**SQL запрос:**
```sql
INSERT INTO plans (
  id, session_id, goal, status, current_subtask_id, 
  metadata_json, approved_at, started_at, completed_at, 
  created_at, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
```

**Параметры:**
- `plan_id`: `cfda95c7-beae-4ba9-b1bb-80dc284b6b1b`
- `session_id`: `0ba76b61-4e22-4a43-9f49-a0b1cad7f0c1`
- `goal`: "открыт пустой проект, создай тестовое приложение на flutter"
- `status`: `approved` ⚠️ (план сразу approved, минуя PLAN_REVIEW!)

---

## 🐛 Выявленные проблемы

### 1. SQLite Database Locking (Критично)

**Причина:** SQLite не поддерживает параллельные записи. В многопоточной среде Docker возникают блокировки.

**Симптомы:**
- ❌ `database is locked` при INSERT операциях
- ❌ `PendingRollbackError` - транзакция откатилась, но сессия не сброшена
- ❌ Повторные попытки записи падают с той же ошибкой

**Решение:**
- 🔧 **Краткосрочное:** Добавить retry логику с rollback
- ✅ **Долгосрочное:** Мигрировать на PostgreSQL (уже есть `POSTGRES_MIGRATION_SUMMARY.md`)

### 2. План создается со статусом 'approved' (Критично)

**Проблема:** План сохраняется со статусом `approved` вместо `draft`.

**Код:** [`architect_agent.py`](codelab-ai-service/agent-runtime/app/agents/architect_agent.py:243)

```python
# План создается и сразу approve() вызывается?
plan = Plan(...)
plan.approve()  # ⚠️ Не должно быть здесь!
await self.plan_repository.save(plan)
```

**Последствия:**
- ❌ Пропускается состояние `PLAN_REVIEW`
- ❌ Пользователь не видит запрос на approval
- ❌ FSM workflow нарушен

**Ожидаемый flow:**
```
1. План создается со статусом 'draft'
2. FSM: ARCHITECT_PLANNING → PLAN_REVIEW
3. Отправка plan_approval_required
4. Ожидание решения пользователя
5. После approve: план.approve() → статус 'approved'
6. FSM: PLAN_REVIEW → PLAN_EXECUTION
```

**Текущий flow (неправильный):**
```
1. План создается со статусом 'approved' ❌
2. FSM: ARCHITECT_PLANNING → PLAN_REVIEW
3. Отправка plan_approval_required (но план уже approved!)
4. Попытка сохранить → database locked
```

### 3. Отсутствие обработки ошибок транзакций

**Проблема:** После `database is locked` сессия не выполняет `rollback()`.

**Код:** [`plan_repository_impl.py:73-90`](codelab-ai-service/agent-runtime/app/infrastructure/persistence/repositories/plan_repository_impl.py:73)

```python
async def save(self, plan: Plan) -> None:
    try:
        # ... INSERT operation
        await self._db.flush()
    except Exception as e:
        # ❌ Нет rollback!
        raise RepositoryError(...)
```

**Решение:**
```python
async def save(self, plan: Plan) -> None:
    try:
        # ... INSERT operation
        await self._db.flush()
    except Exception as e:
        await self._db.rollback()  # ✅ Добавить rollback
        raise RepositoryError(...)
```

---

## 📊 Последовательность событий (Timeline)

```
18:43:19.531 - План создается (id: cfda95c7-beae-4ba9-b1bb-80dc284b6b1b)
18:43:19.532 - approved_at устанавливается (план уже approved!)
18:43:19.536 - Попытка INSERT в таблицу plans
18:43:19.xxx - SQLite: database is locked ❌
18:43:19.xxx - Transaction rollback (автоматический)
18:43:19.xxx - Попытка повторного INSERT
18:43:19.xxx - PendingRollbackError (сессия не сброшена) ❌
18:43:56.096 - Ошибка пробрасывается в orchestrator
18:43:56.096 - FSM: architect_planning → error_handling
18:43:56.097 - Обработка завершена с ошибкой
18:43:56.108 - Commit транзакции (пустой, т.к. rollback был)
```

---

## 🔧 Рекомендуемые исправления

### Приоритет 1: Исправить статус плана при создании

**Файл:** [`architect_agent.py`](codelab-ai-service/agent-runtime/app/agents/architect_agent.py:243)

```python
# Создать план со статусом 'draft'
plan = Plan(
    id=plan_id,
    session_id=session_id,
    goal=task,
    status=PlanStatus.DRAFT,  # ✅ НЕ approved!
    # ...
)

# НЕ вызывать approve() здесь!
# plan.approve()  # ❌ Удалить

# Сохранить план
await self.plan_repository.save(plan)

# Approve будет вызван позже, после решения пользователя
# в PlanApprovalHandler.handle()
```

### Приоритет 2: Добавить rollback в обработку ошибок

**Файл:** [`plan_repository_impl.py`](codelab-ai-service/agent-runtime/app/infrastructure/persistence/repositories/plan_repository_impl.py:73-90)

```python
async def save(self, plan: Plan) -> None:
    try:
        # Check if plan exists
        result = await self._db.execute(
            select(PlanModel).where(PlanModel.id == plan.id)
        )
        existing_model = result.scalar_one_or_none()
        
        if existing_model:
            # Update existing
            # ...
        else:
            # Create new
            plan_model = PlanMapper.to_model(plan)
            self._db.add(plan_model)
        
        await self._db.flush()
        
    except Exception as e:
        # ✅ Добавить rollback
        logger.error(f"Error saving plan {plan.id}: {e}")
        await self._db.rollback()
        
        raise RepositoryError(
            operation="save",
            entity_type="Plan",
            reason=str(e),
            details={"plan_id": plan.id}
        ) from e
```

### Приоритет 3: Мигрировать на PostgreSQL

**Статус:** Документация уже существует  
**Файлы:**
- [`POSTGRES_MIGRATION_SUMMARY.md`](codelab-ai-service/POSTGRES_MIGRATION_SUMMARY.md)
- [`POSTGRES_QUICKSTART.md`](codelab-ai-service/POSTGRES_QUICKSTART.md)

**Преимущества PostgreSQL:**
- ✅ Поддержка параллельных записей (MVCC)
- ✅ Лучшая производительность для многопользовательских систем
- ✅ Расширенные возможности (JSON, полнотекстовый поиск)
- ✅ Production-ready

---

## 📈 Метрики из логов

**Обработка сообщения:**
- Длительность: 41,788.52 ms (~42 секунды)
- Успех: True (но с ошибкой внутри)
- Агент: orchestrator

**FSM переходы:**
1. `architect_planning` → `error_handling` (event: `planning_failed`)

**Health checks:**
- Интервал: каждые 30 секунд
- Статус: 200 OK (сервис работает)

---

## 🎯 Выводы

### Основные проблемы:

1. ❌ **SQLite database locking** - блокирует сохранение планов
2. ❌ **План создается approved** - пропускается PLAN_REVIEW
3. ❌ **Нет rollback** - сессия остается в broken state

### Связь с plan approval:

Проблема с approval **частично связана** с database locking:
- План не может быть сохранен из-за блокировки БД
- Даже если бы сохранился, он уже `approved` (неправильно)
- Пользователь не получает запрос на approval

### Приоритет исправлений:

1. 🔴 **Высокий:** Исправить статус плана при создании (draft вместо approved)
2. 🟡 **Средний:** Добавить rollback в обработку ошибок
3. 🟢 **Низкий:** Мигрировать на PostgreSQL (долгосрочное решение)

---

## 📝 Связанные документы

- [`PLAN_APPROVAL_MECHANISM_ISSUE_ANALYSIS.md`](doc/PLAN_APPROVAL_MECHANISM_ISSUE_ANALYSIS.md) - Анализ проблемы approval на клиенте
- [`POSTGRES_MIGRATION_SUMMARY.md`](codelab-ai-service/POSTGRES_MIGRATION_SUMMARY.md) - План миграции на PostgreSQL
- [`POSTGRES_QUICKSTART.md`](codelab-ai-service/POSTGRES_QUICKSTART.md) - Быстрый старт с PostgreSQL

---

## 🚀 Следующие шаги

1. Исправить создание плана в [`architect_agent.py`](codelab-ai-service/agent-runtime/app/agents/architect_agent.py:243)
2. Добавить rollback в [`plan_repository_impl.py`](codelab-ai-service/agent-runtime/app/infrastructure/persistence/repositories/plan_repository_impl.py:73)
3. Протестировать plan approval flow
4. Рассмотреть миграцию на PostgreSQL для production
