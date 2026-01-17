# Миграция БД для поддержки планирования

## Быстрый старт

Если у вас уже есть существующая база данных benchmark.db, выполните следующие шаги:

### Вариант 1: Пересоздать БД (рекомендуется для тестирования)

```bash
# Удалить старую БД
rm benchmark.db

# Запустить benchmark - БД создастся автоматически с новыми таблицами
python main.py --mode multi-agent --task-id task_001
```

### Вариант 2: Сохранить существующие данные

Если вам нужно сохранить существующие метрики:

```bash
# 1. Создать резервную копию
cp benchmark.db benchmark.db.backup

# 2. Запустить Python для добавления таблиц
python3 << 'EOF'
import asyncio
from src.database import init_database, init_db

async def migrate():
    init_database("sqlite+aiosqlite:///benchmark.db", echo=True)
    await init_db()
    print("✓ Migration completed successfully")

asyncio.run(migrate())
EOF
```

## Проверка миграции

Проверьте, что новые таблицы созданы:

```bash
sqlite3 benchmark.db << 'EOF'
.tables
EOF
```

Вы должны увидеть:
- `poc_execution_plans` - таблица планов
- `poc_subtask_executions` - таблица подзадач

## Структура новых таблиц

### poc_execution_plans

```sql
CREATE TABLE poc_execution_plans (
    id VARCHAR(36) PRIMARY KEY,
    task_execution_id VARCHAR(36) NOT NULL UNIQUE,
    plan_id VARCHAR(100) NOT NULL,
    original_task TEXT NOT NULL,
    subtask_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE,
    is_complete BOOLEAN NOT NULL DEFAULT 0,
    metadata JSON,
    FOREIGN KEY(task_execution_id) REFERENCES poc_task_executions(id) ON DELETE CASCADE
);

CREATE INDEX idx_poc_plans_task_plan ON poc_execution_plans(task_execution_id, plan_id);
CREATE INDEX idx_poc_plans_complete ON poc_execution_plans(is_complete);
```

### poc_subtask_executions

```sql
CREATE TABLE poc_subtask_executions (
    id VARCHAR(36) PRIMARY KEY,
    plan_id VARCHAR(36) NOT NULL,
    subtask_id VARCHAR(100) NOT NULL,
    sequence_number INTEGER NOT NULL,
    description TEXT NOT NULL,
    agent VARCHAR(50) NOT NULL,
    estimated_time VARCHAR(50),
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_seconds FLOAT,
    result TEXT,
    error TEXT,
    dependencies JSON,
    FOREIGN KEY(plan_id) REFERENCES poc_execution_plans(id) ON DELETE CASCADE
);

CREATE INDEX idx_poc_subtasks_plan_seq ON poc_subtask_executions(plan_id, sequence_number);
CREATE INDEX idx_poc_subtasks_status ON poc_subtask_executions(status);
CREATE INDEX idx_poc_subtasks_agent ON poc_subtask_executions(agent);
```

## Проверка работоспособности

После миграции запустите тесты:

```bash
# Установить зависимости для тестов (если еще не установлены)
pip install pytest pytest-asyncio

# Запустить тесты планирования
pytest tests/test_planning_integration.py -v
```

Ожидаемый результат:
```
tests/test_planning_integration.py::test_execution_plan_creation PASSED
tests/test_planning_integration.py::test_collector_record_plan_created PASSED
tests/test_planning_integration.py::test_collector_subtask_lifecycle PASSED
tests/test_planning_integration.py::test_collector_get_plan_metrics PASSED
tests/test_planning_integration.py::test_plan_completion PASSED
```

## Откат миграции

Если что-то пошло не так:

```bash
# Восстановить из резервной копии
rm benchmark.db
cp benchmark.db.backup benchmark.db
```

## Проверка данных

Посмотреть созданные планы:

```bash
sqlite3 benchmark.db << 'EOF'
SELECT 
    ep.plan_id,
    ep.original_task,
    ep.subtask_count,
    ep.is_complete,
    COUNT(se.id) as actual_subtasks
FROM poc_execution_plans ep
LEFT JOIN poc_subtask_executions se ON se.plan_id = ep.id
GROUP BY ep.id;
EOF
```

## Troubleshooting

### Ошибка: "no such table: poc_execution_plans"

**Решение**: Таблицы не созданы. Запустите миграцию (Вариант 2 выше).

### Ошибка: "UNIQUE constraint failed"

**Решение**: Возможно, таблицы уже существуют. Проверьте:
```bash
sqlite3 benchmark.db ".schema poc_execution_plans"
```

### Ошибка: "FOREIGN KEY constraint failed"

**Решение**: Убедитесь, что таблица `poc_task_executions` существует и содержит данные.

## Дополнительная информация

- [`PLANNING_INTEGRATION_GUIDE.md`](PLANNING_INTEGRATION_GUIDE.md) - Полное руководство по использованию
- [`PLANNING_SUPPORT_ANALYSIS.md`](PLANNING_SUPPORT_ANALYSIS.md) - Анализ интеграции
- [`src/models.py`](src/models.py) - Определения моделей

---

**Примечание**: SQLAlchemy автоматически создает таблицы при первом запуске, если они не существуют. Миграция требуется только если у вас уже есть данные в БД.
