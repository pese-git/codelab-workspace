# Анализ поддержки системы планирования в benchmark-standalone

## Дата анализа: 2026-01-15

## Резюме

**❌ НЕТ - benchmark-standalone НЕ поддерживает систему планирования из agent-runtime**

Приложение benchmark-standalone не имеет поддержки новой системы планирования, реализованной в agent-runtime.

---

## Детальный анализ

### Что реализовано в agent-runtime

Согласно [`PLANNING_IMPLEMENTATION_REPORT.md`](../codelab-ai-service/agent-runtime/PLANNING_IMPLEMENTATION_REPORT.md), в agent-runtime реализована полноценная система планирования:

#### 1. **Новые модели данных** ([`schemas.py`](../codelab-ai-service/agent-runtime/app/models/schemas.py))
- `SubtaskStatus` - Enum для статусов подзадач (PENDING, IN_PROGRESS, COMPLETED, FAILED, SKIPPED)
- `Subtask` - Модель подзадачи с полями:
  - `id`, `description`, `agent`, `estimated_time`
  - `status`, `result`, `error`, `dependencies`
- `ExecutionPlan` - Модель плана выполнения с полями:
  - `plan_id`, `session_id`, `original_task`
  - `subtasks`, `created_at`, `current_subtask_index`, `is_complete`

#### 2. **Новый инструмент create_plan**
- Добавлен в [`tool_registry.py`](../codelab-ai-service/agent-runtime/app/services/tool_registry.py)
- Позволяет Orchestrator создавать планы выполнения
- Разбивает сложные задачи на управляемые подзадачи

#### 3. **Новые типы сообщений**
Согласно отчету, должны быть:
- `plan_notification` - уведомление о создании плана
- `plan_approval` - подтверждение плана
- Метаданные прогресса выполнения плана

#### 4. **Новые состояния сессии**
- `PLAN_PENDING_CONFIRMATION` - план ожидает подтверждения
- `PLAN_EXECUTING` - план выполняется

#### 5. **Управление планами в SessionManager**
Методы для работы с планами:
- `set_plan()`, `get_plan()`, `has_plan()`
- `mark_subtask_complete()`, `mark_subtask_failed()`
- `get_next_subtask()`, `clear_plan()`

#### 6. **Выполнение планов в MultiAgentOrchestrator**
- Метод `_execute_plan()` для последовательного выполнения подзадач
- Автоматическое переключение между агентами
- Обработка зависимостей и ошибок

---

### Что НЕ реализовано в benchmark-standalone

#### 1. **Обработка типов сообщений планирования**

В [`client.py`](src/client.py) обрабатываются только базовые типы сообщений:

```python
# Строки 154-261 в client.py
if msg_type == "assistant_message":
    # Обработка обычных сообщений
elif msg_type == "tool_call":
    # Обработка вызовов инструментов
elif msg_type == "agent_switched":
    # Обработка переключения агентов
elif msg_type == "error":
    # Обработка ошибок
```

**Отсутствуют обработчики для:**
- ❌ `plan_notification` - создание плана
- ❌ `plan_approval` - подтверждение плана
- ❌ Метаданные прогресса плана
- ❌ Статусы подзадач

#### 2. **Модели данных для планирования**

В [`models.py`](src/models.py) отсутствуют таблицы для хранения данных о планировании:

**Существующие таблицы:**
- ✅ `Experiment` - эксперименты
- ✅ `TaskExecution` - выполнение задач
- ✅ `LLMCall` - вызовы LLM
- ✅ `ToolCall` - вызовы инструментов
- ✅ `AgentSwitch` - переключения агентов
- ✅ `QualityEvaluation` - оценка качества
- ✅ `Hallucination` - галлюцинации

**Отсутствующие таблицы:**
- ❌ `ExecutionPlan` - планы выполнения
- ❌ `Subtask` - подзадачи
- ❌ `SubtaskExecution` - выполнение подзадач
- ❌ Связи между планами и задачами

#### 3. **Сбор метрик планирования**

В [`collector.py`](src/collector.py) нет методов для записи метрик планирования:

**Существующие методы:**
- ✅ `record_llm_call()` - запись вызова LLM
- ✅ `record_tool_call()` - запись вызова инструмента
- ✅ `record_agent_switch()` - запись переключения агента
- ✅ `record_quality_evaluation()` - запись оценки качества
- ✅ `record_hallucination()` - запись галлюцинации

**Отсутствующие методы:**
- ❌ `record_plan_created()` - запись создания плана
- ❌ `record_subtask_started()` - запись начала подзадачи
- ❌ `record_subtask_completed()` - запись завершения подзадачи
- ❌ `record_plan_completed()` - запись завершения плана
- ❌ `get_plan_metrics()` - получение метрик плана

#### 4. **Отчетность по планированию**

Отсутствует функциональность для:
- ❌ Анализа эффективности планирования
- ❌ Сравнения планового и фактического времени
- ❌ Статистики по подзадачам
- ❌ Визуализации выполнения планов

---

## Влияние на функциональность

### Текущее поведение

При выполнении сложных задач через benchmark-standalone:

1. **Orchestrator создает план** (в agent-runtime)
2. **План выполняется** (в agent-runtime)
3. **benchmark-standalone НЕ видит:**
   - Что был создан план
   - Какие подзадачи выполняются
   - Прогресс выполнения плана
   - Статистику по подзадачам

4. **benchmark-standalone видит только:**
   - ✅ Переключения агентов (`agent_switched`)
   - ✅ Вызовы инструментов (`tool_call`)
   - ✅ Финальный результат (`assistant_message`)

### Потеря данных

Из-за отсутствия поддержки планирования теряются важные метрики:

- **Структура задачи** - как задача была разбита на подзадачи
- **Время планирования** - сколько времени ушло на создание плана
- **Прогресс выполнения** - какие подзадачи выполнены, какие нет
- **Зависимости** - связи между подзадачами
- **Точность оценок** - сравнение estimated_time vs actual_time
- **Эффективность планирования** - помогло ли планирование или нет

---

## Рекомендации по интеграции

### Приоритет 1: Базовая поддержка (критично)

#### 1.1. Обработка сообщений планирования в client.py

```python
# Добавить в execute_task() после строки 261
elif msg_type == "plan_notification":
    plan_data = msg.get("metadata", {})
    plan_id = plan_data.get("plan_id")
    subtask_count = plan_data.get("subtask_count", 0)
    
    logger.info(f"📋 Plan created: {plan_id} with {subtask_count} subtasks")
    
    # Записать создание плана
    await collector.record_plan_created(
        task_execution_id=task_execution_id,
        plan_id=plan_id,
        subtask_count=subtask_count,
        subtasks=plan_data.get("subtasks", [])
    )

elif msg_type == "subtask_started":
    subtask_data = msg.get("metadata", {})
    subtask_id = subtask_data.get("subtask_id")
    subtask_description = subtask_data.get("description", "")
    
    logger.info(f"▶️  Subtask started: {subtask_id} - {subtask_description}")
    
    await collector.record_subtask_started(
        task_execution_id=task_execution_id,
        subtask_id=subtask_id,
        description=subtask_description,
        agent=subtask_data.get("agent")
    )

elif msg_type == "subtask_completed":
    subtask_data = msg.get("metadata", {})
    subtask_id = subtask_data.get("subtask_id")
    status = subtask_data.get("status")
    
    logger.info(f"✅ Subtask completed: {subtask_id} - {status}")
    
    await collector.record_subtask_completed(
        task_execution_id=task_execution_id,
        subtask_id=subtask_id,
        status=status,
        result=subtask_data.get("result"),
        error=subtask_data.get("error")
    )
```

#### 1.2. Новые модели данных в models.py

```python
class ExecutionPlan(Base):
    """Execution plan tracking"""
    __tablename__ = "poc_execution_plans"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_execution_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("poc_task_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    plan_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    original_task: Mapped[str] = mapped_column(Text, nullable=False)
    subtask_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    # Relationships
    task_execution = relationship("TaskExecution", back_populates="execution_plan")
    subtasks = relationship(
        "SubtaskExecution",
        back_populates="plan",
        cascade="all, delete-orphan"
    )


class SubtaskExecution(Base):
    """Subtask execution tracking"""
    __tablename__ = "poc_subtask_executions"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    plan_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("poc_execution_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    subtask_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    agent: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    estimated_time: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dependencies: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Relationships
    plan = relationship("ExecutionPlan", back_populates="subtasks")
```

#### 1.3. Новые методы в collector.py

```python
async def record_plan_created(
    self,
    task_execution_id: UUID,
    plan_id: str,
    subtask_count: int,
    subtasks: List[Dict[str, Any]]
) -> UUID:
    """Record execution plan creation"""
    # Реализация...

async def record_subtask_started(
    self,
    task_execution_id: UUID,
    subtask_id: str,
    description: str,
    agent: str
) -> UUID:
    """Record subtask start"""
    # Реализация...

async def record_subtask_completed(
    self,
    task_execution_id: UUID,
    subtask_id: str,
    status: str,
    result: Optional[str] = None,
    error: Optional[str] = None
) -> UUID:
    """Record subtask completion"""
    # Реализация...

async def get_plan_metrics(
    self,
    task_execution_id: UUID
) -> Dict[str, Any]:
    """Get planning metrics for a task"""
    # Реализация...
```

### Приоритет 2: Расширенная аналитика (важно)

#### 2.1. Анализ эффективности планирования

```python
async def analyze_planning_effectiveness(
    self,
    experiment_id: UUID
) -> Dict[str, Any]:
    """
    Analyze planning effectiveness:
    - Tasks with plans vs without plans
    - Success rate comparison
    - Time efficiency
    - Subtask accuracy
    """
    # Реализация...
```

#### 2.2. Отчеты по планированию

```python
def generate_planning_report(experiment_id: UUID) -> str:
    """
    Generate detailed planning report:
    - Plan creation statistics
    - Subtask execution statistics
    - Time estimation accuracy
    - Agent utilization in plans
    """
    # Реализация...
```

### Приоритет 3: Визуализация (желательно)

- Графики выполнения планов
- Диаграммы зависимостей подзадач
- Временные шкалы выполнения
- Сравнение планового и фактического времени

---

## Оценка трудозатрат

### Базовая поддержка (Приоритет 1)
- **Обработка сообщений**: 2-3 часа
- **Модели данных**: 2-3 часа
- **Методы collector**: 3-4 часа
- **Миграция БД**: 1 час
- **Тестирование**: 2-3 часа
- **Итого**: ~10-14 часов

### Расширенная аналитика (Приоритет 2)
- **Анализ эффективности**: 3-4 часа
- **Отчеты**: 2-3 часа
- **Тестирование**: 2 часа
- **Итого**: ~7-9 часов

### Визуализация (Приоритет 3)
- **Графики и диаграммы**: 5-8 часов
- **Интеграция в отчеты**: 2-3 часа
- **Итого**: ~7-11 часов

**Общая оценка**: 24-34 часа (3-4 рабочих дня)

---

## Альтернативные подходы

### Вариант 1: Минимальная интеграция
Записывать только факт создания плана и количество подзадач в поле `metrics` существующей таблицы `TaskExecution`:

```python
task_execution.metrics = {
    "has_plan": True,
    "plan_id": "plan_abc123",
    "subtask_count": 5,
    "duration_seconds": 120.5
}
```

**Плюсы**: Быстро (1-2 часа)
**Минусы**: Нет детальной информации о подзадачах

### Вариант 2: Логирование без БД
Записывать информацию о планировании только в логи, без сохранения в БД.

**Плюсы**: Очень быстро (30 минут)
**Минусы**: Нет структурированных данных для анализа

### Вариант 3: Полная интеграция (рекомендуется)
Реализовать все три приоритета для полноценной поддержки планирования.

**Плюсы**: Максимум данных и аналитики
**Минусы**: Требует времени (3-4 дня)

---

## Заключение

**Текущий статус**: ❌ benchmark-standalone НЕ поддерживает систему планирования

**Рекомендация**: Реализовать базовую поддержку (Приоритет 1) для сбора критичных метрик о планировании. Это позволит:

1. ✅ Отслеживать создание и выполнение планов
2. ✅ Собирать статистику по подзадачам
3. ✅ Анализировать эффективность планирования
4. ✅ Сравнивать подходы с планированием и без него

**Следующие шаги**:
1. Создать миграцию БД для новых таблиц
2. Обновить client.py для обработки сообщений планирования
3. Добавить методы в collector.py
4. Обновить generate_report.py для включения метрик планирования
5. Протестировать на сложных задачах

---

## Связанные документы

- [`agent-runtime/PLANNING_IMPLEMENTATION_REPORT.md`](../codelab-ai-service/agent-runtime/PLANNING_IMPLEMENTATION_REPORT.md) - Отчет о реализации планирования
- [`agent-runtime/PLANNING_SYSTEM_GUIDE.md`](../codelab-ai-service/agent-runtime/PLANNING_SYSTEM_GUIDE.md) - Руководство по системе планирования
- [`ORCHESTRATOR_PLANNING_PROPOSAL.md`](ORCHESTRATOR_PLANNING_PROPOSAL.md) - Первоначальное предложение
- [`agent-runtime/app/models/schemas.py`](../codelab-ai-service/agent-runtime/app/models/schemas.py) - Модели планирования

---

**Автор анализа**: AI Assistant  
**Дата**: 2026-01-15  
**Версия**: 1.0
