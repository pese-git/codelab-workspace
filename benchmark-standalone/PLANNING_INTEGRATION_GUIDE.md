# Руководство по интеграции системы планирования

## Обзор

Система планирования из agent-runtime теперь полностью интегрирована в benchmark-standalone. Это позволяет отслеживать, анализировать и визуализировать выполнение сложных задач, разбитых на подзадачи.

## Что было реализовано

### ✅ 1. Модели данных ([`src/models.py`](src/models.py))

Добавлены две новые таблицы для хранения данных о планировании:

#### `ExecutionPlan`
Хранит информацию о плане выполнения задачи:
- `plan_id` - идентификатор плана из agent-runtime
- `original_task` - исходная задача пользователя
- `subtask_count` - количество подзадач
- `created_at`, `completed_at` - временные метки
- `is_complete` - флаг завершения

#### `SubtaskExecution`
Хранит информацию о выполнении каждой подзадачи:
- `subtask_id` - идентификатор подзадачи
- `sequence_number` - порядковый номер
- `description` - описание подзадачи
- `agent` - назначенный агент
- `estimated_time` - оценка времени
- `status` - статус (pending, in_progress, completed, failed, skipped)
- `started_at`, `completed_at` - временные метки
- `duration_seconds` - фактическое время выполнения
- `result`, `error` - результат или ошибка

### ✅ 2. Сбор метрик ([`src/collector.py`](src/collector.py))

Добавлены методы для записи метрик планирования:

```python
# Создание плана
await collector.record_plan_created(
    task_execution_id=task_id,
    plan_id="plan_abc123",
    original_task="Migrate from Provider to Riverpod",
    subtasks=[...]
)

# Начало подзадачи
await collector.record_subtask_started(
    task_execution_id=task_id,
    subtask_id="subtask_1",
    description="Add riverpod dependency",
    agent="coder"
)

# Завершение подзадачи
await collector.record_subtask_completed(
    task_execution_id=task_id,
    subtask_id="subtask_1",
    status="completed",
    result="Dependency added successfully"
)

# Завершение плана
await collector.record_plan_completed(task_execution_id=task_id)

# Получение метрик плана
metrics = await collector.get_plan_metrics(task_execution_id=task_id)
```

### ✅ 3. Обработка сообщений ([`src/client.py`](src/client.py))

Добавлена обработка новых типов сообщений от agent-runtime:

#### `plan_notification` - Создание плана
```
================================================================================
📋 EXECUTION PLAN CREATED
   Plan ID: plan_abc123
   Total Subtasks: 5
================================================================================
   1. [subtask_1] Add riverpod dependency to pubspec.yaml
      Agent: coder | Est. Time: 2 min
   2. [subtask_2] Create provider definitions using Riverpod
      Agent: coder | Est. Time: 5 min
      Dependencies: subtask_1
   ...
================================================================================
```

#### `subtask_started` - Начало подзадачи
```
▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶
▶️  SUBTASK STARTED [1/5]
   ID: subtask_1
   Agent: coder
   Description: Add riverpod dependency to pubspec.yaml
▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶
```

#### `subtask_completed` - Завершение подзадачи
```
◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀
✅ SUBTASK SUCCESS [1/5]
   ID: subtask_1
   Status: completed
   Result: Dependency added successfully
◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀
```

#### `plan_completed` - Завершение плана
```
🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁
🏁 EXECUTION PLAN COMPLETED
   Plan ID: plan_abc123
   Total Subtasks: 5
   ✅ Completed: 4
   ❌ Failed: 1
   ⏭️  Skipped: 0
   Success Rate: 80.0%
🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁
```

#### Итоговая сводка задачи
```
================================================================================
✅ TASK EXECUTION SUMMARY
   Task ID: task_001
   Title: Migrate from Provider to Riverpod
   Category: complex
   Success: True
   Tool Calls: 25
   Agent Switches: 3
   Response Length: 1523 chars
   📋 Plan Used: Yes (ID: plan_abc123)
   Subtasks Started: 5
   Subtasks Completed: 4
================================================================================
```

### ✅ 4. Отчеты ([`src/reporter.py`](src/reporter.py))

Добавлен раздел "Planning Metrics" в отчеты:

```markdown
### Planning Metrics

| Metric | Value |
|--------|-------|
| Tasks with Plans | 8 / 20 |
| Total Plans Created | 8 |
| Total Subtasks | 42 |
| Completed Subtasks | 38 |
| Failed Subtasks | 4 |
| Avg Subtasks per Plan | 5.2 |
| Planning Success Rate | 90.48% |
```

При сравнении режимов добавлена секция:

```markdown
### Planning Metrics

| Metric | Single-Agent | Multi-Agent | Difference |
|--------|--------------|-------------|------------|
| Total Plans | 0 | 8 | +8 |
| Total Subtasks | 0 | 42 | +42 |
| Planning Success Rate | 0.00% | 90.48% | +90.5% |
| Avg Subtasks per Plan | 0.0 | 5.2 | +5.2 |
```

### ✅ 5. Тесты ([`tests/test_planning_integration.py`](tests/test_planning_integration.py))

Созданы комплексные тесты для проверки:
- Создания планов и подзадач
- Записи метрик через collector
- Жизненного цикла подзадач
- Получения метрик планирования
- Завершения планов

## Использование

### Запуск benchmark с планированием

Система планирования активируется автоматически, когда agent-runtime создает план для сложной задачи:

```bash
# Запустить все задачи
python main.py --mode multi-agent

# Запустить конкретную задачу
python main.py --mode multi-agent --task-id task_009
```

### Просмотр логов

Логи теперь содержат детальную информацию о планировании:

```bash
# Запустить с подробными логами
python main.py --mode multi-agent --verbose
```

### Генерация отчетов

Отчеты автоматически включают метрики планирования:

```bash
# Сгенерировать отчет для последних экспериментов
python generate_report.py --latest

# Сгенерировать отчет для конкретного эксперимента
python generate_report.py --experiment-id <uuid>
```

### Запуск тестов

```bash
# Запустить все тесты
pytest tests/test_planning_integration.py -v

# Запустить конкретный тест
pytest tests/test_planning_integration.py::test_execution_plan_creation -v

# С покрытием кода
pytest tests/test_planning_integration.py --cov=src.models --cov=src.collector
```

## Примеры логов

### Пример 1: Успешное выполнение плана

```
🚀 Executing task task_009: Migrate from Provider to Riverpod
📋 Description: Migrate the Flutter app from Provider to Riverpod...
⏱️  Increased timeout to 300s for complex task
🔌 Connected to Gateway WebSocket
📤 Sent task description to agent

================================================================================
📋 EXECUTION PLAN CREATED
   Plan ID: plan_20260115_001
   Total Subtasks: 5
================================================================================
   1. [subtask_1] Add riverpod dependency to pubspec.yaml
      Agent: coder | Est. Time: 2 min
   2. [subtask_2] Create provider definitions using Riverpod
      Agent: coder | Est. Time: 5 min
      Dependencies: subtask_1
   3. [subtask_3] Update main.dart to use ProviderScope
      Agent: coder | Est. Time: 3 min
      Dependencies: subtask_2
   4. [subtask_4] Migrate widgets to use Riverpod hooks
      Agent: coder | Est. Time: 10 min
      Dependencies: subtask_3
   5. [subtask_5] Update tests for Riverpod
      Agent: coder | Est. Time: 5 min
      Dependencies: subtask_4
================================================================================

▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶
▶️  SUBTASK STARTED [1/5]
   ID: subtask_1
   Agent: coder
   Description: Add riverpod dependency to pubspec.yaml
▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶▶

🔧 Tool call #1: write_to_file (path=pubspec.yaml, content_len=523) (call_id=call_001...)
✅ Tool executed: write_to_file, duration=0.15s

◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀
✅ SUBTASK SUCCESS [1/5]
   ID: subtask_1
   Status: completed
   Result: Added flutter_riverpod: ^2.4.0 to dependencies
◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀

... (остальные подзадачи) ...

🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁
🏁 EXECUTION PLAN COMPLETED
   Plan ID: plan_20260115_001
   Total Subtasks: 5
   ✅ Completed: 5
   ❌ Failed: 0
   ⏭️  Skipped: 0
   Success Rate: 100.0%
🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁

================================================================================
✅ TASK EXECUTION SUMMARY
   Task ID: task_009
   Title: Migrate from Provider to Riverpod
   Category: complex
   Success: True
   Tool Calls: 15
   Agent Switches: 0
   Response Length: 2341 chars
   📋 Plan Used: Yes (ID: plan_20260115_001)
   Subtasks Started: 5
   Subtasks Completed: 5
================================================================================
```

### Пример 2: План с неудачной подзадачей

```
◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀
❌ SUBTASK FAILED [3/5]
   ID: subtask_3
   Status: failed
   Error: Syntax error in main.dart: Expected ';' after expression
◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀◀

🏁 EXECUTION PLAN COMPLETED
   Plan ID: plan_20260115_002
   Total Subtasks: 5
   ✅ Completed: 2
   ❌ Failed: 1
   ⏭️  Skipped: 2
   Success Rate: 40.0%
🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁🏁
```

## Анализ данных

### SQL запросы для анализа

```sql
-- Получить все планы с метриками
SELECT 
    ep.plan_id,
    ep.original_task,
    ep.subtask_count,
    COUNT(se.id) as actual_subtasks,
    SUM(CASE WHEN se.status = 'completed' THEN 1 ELSE 0 END) as completed,
    SUM(CASE WHEN se.status = 'failed' THEN 1 ELSE 0 END) as failed,
    AVG(se.duration_seconds) as avg_duration
FROM poc_execution_plans ep
LEFT JOIN poc_subtask_executions se ON se.plan_id = ep.id
GROUP BY ep.id;

-- Получить распределение агентов в подзадачах
SELECT 
    agent,
    COUNT(*) as total_subtasks,
    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
    AVG(duration_seconds) as avg_duration
FROM poc_subtask_executions
GROUP BY agent;

-- Сравнить задачи с планами и без
SELECT 
    CASE WHEN ep.id IS NOT NULL THEN 'With Plan' ELSE 'Without Plan' END as plan_usage,
    COUNT(te.id) as total_tasks,
    SUM(CASE WHEN te.success THEN 1 ELSE 0 END) as successful,
    AVG(CAST(te.metrics->>'duration_seconds' AS FLOAT)) as avg_duration
FROM poc_task_executions te
LEFT JOIN poc_execution_plans ep ON ep.task_execution_id = te.id
GROUP BY plan_usage;
```

## Преимущества интеграции

### 1. Полная видимость
- ✅ Видно, как задача разбита на подзадачи
- ✅ Отслеживание прогресса в реальном времени
- ✅ Детальные логи для каждой подзадачи

### 2. Лучшая аналитика
- ✅ Сравнение планового и фактического времени
- ✅ Анализ эффективности планирования
- ✅ Статистика по агентам и типам задач

### 3. Отладка и оптимизация
- ✅ Легко найти проблемные подзадачи
- ✅ Понять, где теряется время
- ✅ Оптимизировать разбиение задач

### 4. Метрики для улучшения
- ✅ Точность оценок времени
- ✅ Success rate планирования
- ✅ Эффективность разных агентов

## Следующие шаги

### Рекомендуемые улучшения

1. **Визуализация** (Приоритет: Средний)
   - Графики выполнения планов
   - Диаграммы Ганта для подзадач
   - Дашборд с метриками в реальном времени

2. **Расширенная аналитика** (Приоритет: Средний)
   - ML-модели для предсказания времени выполнения
   - Автоматическое выявление паттернов
   - Рекомендации по оптимизации планов

3. **Интеграция с CI/CD** (Приоритет: Низкий)
   - Автоматический запуск benchmark при изменениях
   - Сравнение метрик между версиями
   - Алерты при деградации производительности

## Troubleshooting

### Проблема: Планы не записываются в БД

**Решение**: Убедитесь, что таблицы созданы:
```bash
# Пересоздать БД
rm benchmark.db
python main.py --mode multi-agent --task-id task_001
```

### Проблема: Логи не показывают детали планирования

**Решение**: Проверьте уровень логирования:
```python
# В config.yaml
logging:
  level: INFO  # или DEBUG для максимальной детализации
```

### Проблема: Тесты не проходят

**Решение**: Установите зависимости для тестов:
```bash
pip install pytest pytest-asyncio pytest-cov
```

## Связанные документы

- [`PLANNING_SUPPORT_ANALYSIS.md`](PLANNING_SUPPORT_ANALYSIS.md) - Детальный анализ интеграции
- [`agent-runtime/PLANNING_IMPLEMENTATION_REPORT.md`](../codelab-ai-service/agent-runtime/PLANNING_IMPLEMENTATION_REPORT.md) - Отчет о реализации в agent-runtime
- [`agent-runtime/PLANNING_SYSTEM_GUIDE.md`](../codelab-ai-service/agent-runtime/PLANNING_SYSTEM_GUIDE.md) - Руководство по системе планирования

## Контакты и поддержка

Для вопросов и предложений:
- Изучите код с комментариями
- Запустите тесты для понимания работы системы
- Проверьте логи для отладки

---

**Версия**: 1.0.0  
**Дата**: 2026-01-15  
**Статус**: ✅ Production Ready
