# Архитектура Benchmark Standalone

## Обзор

Benchmark Standalone - это независимое приложение для тестирования AI-агентов, которое общается с backend **только через Gateway WebSocket API**.

## Принципы дизайна

1. **Независимость** - не зависит от внутренних модулей agent-runtime
2. **Простота** - единственная точка взаимодействия - Gateway WebSocket
3. **Портативность** - можно запускать на любой машине
4. **Изоляция** - собственная база данных метрик

## Архитектурная диаграмма

```
┌─────────────────────────────────────────────────────────┐
│              benchmark-standalone                        │
│                                                          │
│  ┌────────────────────────────────────────────┐         │
│  │           main.py (Entry Point)            │         │
│  └──────────────┬─────────────────────────────┘         │
│                 │                                        │
│  ┌──────────────▼─────────────────────────────┐         │
│  │         BenchmarkRunner                    │         │
│  │  - Загрузка задач из tasks.yaml           │         │
│  │  - Фильтрация задач                       │         │
│  │  - Управление экспериментом                │         │
│  └──────────────┬─────────────────────────────┘         │
│                 │                                        │
│     ┌───────────┼───────────┐                           │
│     │           │           │                           │
│  ┌──▼───────┐ ┌▼────────┐ ┌▼──────────┐               │
│  │ Gateway  │ │ Mock    │ │ Task      │               │
│  │ Client   │ │ Tool    │ │ Validator │               │
│  │          │ │ Executor│ │           │               │
│  └──┬───────┘ └─────────┘ └───────────┘               │
│     │                                                   │
│     │ WebSocket                                         │
│     │ ws://gateway/ws/benchmark                         │
│     │                                                   │
│  ┌──▼──────────────────────────────────────┐           │
│  │      Metrics Collector                  │           │
│  │  - Запись метрик в SQLite               │           │
│  └──┬──────────────────────────────────────┘           │
│     │                                                   │
│  ┌──▼──────────────────────────────────────┐           │
│  │      SQLite Database                    │           │
│  │  - poc_experiments                      │           │
│  │  - poc_task_executions                  │           │
│  │  - poc_llm_calls                        │           │
│  │  - poc_tool_calls                       │           │
│  │  - poc_agent_switches                   │           │
│  │  - poc_quality_evaluations              │           │
│  │  - poc_hallucinations                   │           │
│  └─────────────────────────────────────────┘           │
│                                                          │
└─────────────────────────────────────────────────────────┘
                     │
                     │ WebSocket
                     │
┌────────────────────▼─────────────────────────────────────┐
│                    Gateway                               │
│                  (порт 8000)                             │
│  - WebSocket endpoint: /ws/benchmark                     │
│  - Маршрутизация к agent-runtime                        │
│  - Управление сессиями                                  │
└──────────────────────────────────────────────────────────┘
                     │
                     │ Internal API
                     │
┌────────────────────▼─────────────────────────────────────┐
│                 Agent Runtime                            │
│                  (порт 8003)                             │
│  - Multi-agent orchestrator                             │
│  - Специализированные агенты                            │
│  - Tool registry                                        │
└──────────────────────────────────────────────────────────┘
                     │
                     │ Internal API
                     │
┌────────────────────▼─────────────────────────────────────┐
│                  LLM Proxy                               │
│                  (порт 8002)                             │
│  - LLM API вызовы                                       │
│  - Rate limiting                                        │
└──────────────────────────────────────────────────────────┘
```

## Компоненты

### 1. GatewayClient (src/client.py)

**Назначение:** WebSocket клиент для общения с Gateway

**Ключевые методы:**
- `execute_task()` - выполнение задачи через WebSocket
- `test_connection()` - проверка подключения к Gateway

**Протокол:**
```python
# Отправка задачи
→ {"type": "user_message", "content": "...", "role": "user"}

# Получение ответов
← {"type": "assistant_message", "token": "...", "is_final": false}
← {"type": "tool_call", "call_id": "...", "tool_name": "...", "arguments": {...}}
← {"type": "agent_switched", "from_agent": "...", "to_agent": "..."}

# Отправка результата tool
→ {"type": "tool_result", "call_id": "...", "result": {...}}
```

### 2. MockToolExecutor (src/executor.py)

**Назначение:** Локальное выполнение tools в test_project

**Поддерживаемые tools:**
- `write_file` / `write_to_file` - создание/изменение файлов
- `read_file` - чтение файлов
- `list_files` - список файлов (с поддержкой recursive)
- `search_in_code` / `search_files` - поиск в коде
- `apply_diff` - применение изменений

**Пример:**
```python
executor = MockToolExecutor(Path("./test_project"))
result = await executor.execute_tool("write_file", {
    "path": "lib/widgets/user_card.dart",
    "content": "class UserCard extends StatelessWidget {...}"
})
# → {"success": True, "path": "lib/widgets/user_card.dart"}
```

### 3. TaskValidator (src/validator.py)

**Назначение:** Автоматическая проверка выполнения задач

**Поддерживаемые проверки:**
- `file_exists` - проверка существования файла
- `syntax_valid` - проверка синтаксиса через `dart analyze`
- `contains_text` - поиск текста в файле
- `test_passes` - запуск тестов через `flutter test`

**Пример:**
```python
validator = TaskValidator(Path("./test_project"))
result = await validator.validate_task(task)
# → {
#   "total_checks": 2,
#   "passed_checks": 2,
#   "success_rate": 1.0,
#   "details": [...]
# }
```

### 4. MetricsCollector (src/collector.py)

**Назначение:** Сбор и хранение метрик в SQLite

**API:**
```python
collector = MetricsCollector(db_session)

# Эксперименты
exp_id = await collector.start_experiment("multi-agent", config)
await collector.complete_experiment(exp_id)

# Задачи
task_id = await collector.start_task(exp_id, "task_001", "simple", "coding", "multi-agent")
await collector.complete_task(task_id, success=True, metrics={...})

# Метрики
await collector.record_llm_call(task_id, "coder", 500, 200, "gpt-4", 2.5)
await collector.record_tool_call(task_id, "write_file", True, 0.1)
await collector.record_agent_switch(task_id, "orchestrator", "coder", "Coding task")
await collector.record_quality_evaluation(task_id, "syntax_check", 0.95, True)
await collector.record_hallucination(task_id, "import", "Non-existent import")

# Статистика
summary = await collector.get_experiment_summary(exp_id)
```

### 5. ReportGenerator (src/reporter.py)

**Назначение:** Генерация детальных Markdown отчетов

**Возможности:**
- Сравнительный анализ single-agent vs multi-agent
- Статистика по категориям и типам задач
- Расчет стоимости и token usage
- Визуализация в виде таблиц

## Поток данных

### Выполнение задачи

```
1. BenchmarkRunner загружает задачи из tasks.yaml
   ↓
2. Для каждой задачи:
   ├─> MetricsCollector.start_task()
   ├─> GatewayClient.execute_task()
   │   ├─> WebSocket: send({"type": "user_message", ...})
   │   ├─> WebSocket: recv() → {"type": "tool_call", ...}
   │   ├─> MockToolExecutor.execute_tool()
   │   ├─> WebSocket: send({"type": "tool_result", ...})
   │   ├─> WebSocket: recv() → {"type": "assistant_message", "is_final": true}
   │   └─> MetricsCollector.record_*()
   ├─> TaskValidator.validate_task()
   └─> MetricsCollector.complete_task()
   ↓
3. MetricsCollector.complete_experiment()
   ↓
4. ReportGenerator.generate_report()
```

### Обработка tool calls

```
Gateway → benchmark-standalone:
  {"type": "tool_call", "call_id": "123", "tool_name": "write_file", "arguments": {...}}
  
benchmark-standalone:
  1. MockToolExecutor.execute_tool("write_file", {...})
  2. Создает файл в test_project/
  3. Возвращает {"success": true, "path": "..."}
  
benchmark-standalone → Gateway:
  {"type": "tool_result", "call_id": "123", "result": {"success": true, ...}}
  
Gateway → Agent Runtime → продолжает обработку
```

## База данных

### Схема (7 таблиц)

```sql
-- Эксперименты
poc_experiments (id, mode, started_at, completed_at, config)

-- Выполнение задач
poc_task_executions (id, experiment_id, task_id, category, type, mode, success, metrics)

-- LLM вызовы
poc_llm_calls (id, task_execution_id, agent_type, input_tokens, output_tokens, model)

-- Tool вызовы
poc_tool_calls (id, task_execution_id, tool_name, success, duration_seconds)

-- Переключения агентов
poc_agent_switches (id, task_execution_id, from_agent, to_agent, reason)

-- Оценки качества
poc_quality_evaluations (id, task_execution_id, evaluation_type, score, passed)

-- Галлюцинации
poc_hallucinations (id, task_execution_id, hallucination_type, description)
```

### Связи

```
Experiment (1) ──< (N) TaskExecution
                        │
                        ├──< (N) LLMCall
                        ├──< (N) ToolCall
                        ├──< (N) AgentSwitch
                        ├──< (N) QualityEvaluation
                        └──< (N) Hallucination
```

## Конфигурация

### config.yaml

```yaml
gateway:
  ws_url: "ws://localhost:8000/ws/benchmark"  # Единственная точка взаимодействия
  timeout: 60
  reconnect_attempts: 3

database:
  url: "sqlite:///data/metrics.db"  # Локальная база

benchmark:
  tasks_file: "tasks.yaml"
  test_project: "./test_project"
  enable_validation: true
```

## Расширяемость

### Добавление новых tools

```python
# В src/executor.py
async def _my_custom_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
    """Custom tool implementation."""
    # Ваша логика
    return {"success": True, "result": "..."}

# В execute_tool()
elif tool_name == "my_custom_tool":
    return await self._my_custom_tool(arguments)
```

### Добавление новых проверок

```python
# В src/validator.py
async def _check_custom(self, params: Dict[str, Any]) -> Dict[str, Any]:
    """Custom validation check."""
    # Ваша логика
    return {"passed": True, "message": "..."}

# В _run_check()
elif check_type == "custom_check":
    return await self._check_custom(params)
```

### Добавление новых метрик

```python
# В src/models.py
class CustomMetric(Base):
    __tablename__ = "poc_custom_metrics"
    # Ваши поля

# В src/collector.py
async def record_custom_metric(self, task_id, data):
    """Record custom metric."""
    # Ваша логика
```

## Безопасность

### Изоляция

- Приложение не имеет прямого доступа к agent-runtime
- Все взаимодействие через Gateway WebSocket
- Tools выполняются только в изолированном test_project
- База данных метрик полностью независима

### Ограничения

- Tools не могут выйти за пределы test_project
- Timeout на WebSocket соединения (60 секунд)
- Максимальное количество итераций tool execution

## Производительность

### Оптимизации

- Async/await для всех I/O операций
- Batch операции с базой данных
- Переиспользование WebSocket соединений
- Кэширование результатов валидации

### Масштабируемость

- SQLite достаточно для тысяч задач
- Для больших объемов можно переключиться на PostgreSQL
- Параллельное выполнение задач (будущая функция)

## Мониторинг

### Логирование

```python
# Уровни логирования
DEBUG - детальная информация о каждом шаге
INFO - основные события (запуск задач, результаты)
WARNING - предупреждения (timeout, validation failed)
ERROR - ошибки выполнения
```

### Метрики

Все метрики сохраняются в базе данных и доступны для анализа:
- Success rate по категориям и типам
- Token usage и стоимость
- Время выполнения задач
- Частота tool calls
- Переключения агентов

## Сравнение с оригинальным benchmark

| Аспект | Оригинальный | benchmark-standalone |
|--------|--------------|----------------------|
| **Зависимости** | agent-runtime модули | Минимальные (websockets, sqlalchemy) |
| **Общение** | Прямой импорт / HTTP / WS | Только Gateway WebSocket |
| **База данных** | Общая с agent-runtime | Независимая SQLite |
| **Сложность** | Высокая (интеграция) | Низкая (изолированное приложение) |
| **Портативность** | Требует agent-runtime | Полностью независимое |
| **Развертывание** | Сложное | Простое (один скрипт) |

## Будущие улучшения

### Планируется

- [ ] Параллельное выполнение задач
- [ ] Поддержка PostgreSQL для больших объемов
- [ ] Визуализация метрик (графики)
- [ ] Web UI для просмотра результатов
- [ ] Экспорт метрик в CSV/JSON
- [ ] Интеграция с CI/CD

### Возможные расширения

- [ ] Поддержка других протоколов (gRPC)
- [ ] Кастомные задачи через UI
- [ ] Real-time мониторинг выполнения
- [ ] Сравнение с историческими результатами
- [ ] A/B тестирование разных конфигураций

## Ссылки

- [README.md](README.md) - основная документация
- [QUICKSTART.md](QUICKSTART.md) - быстрый старт
- [tasks.yaml](tasks.yaml) - 40 benchmark задач
- [config.yaml](config.yaml) - конфигурация

## Поддержка

При возникновении проблем:
1. Проверьте что Gateway запущен и доступен
2. Проверьте логи в `logs/benchmark.log`
3. Проверьте базу данных `data/metrics.db`
4. Изучите примеры в QUICKSTART.md
