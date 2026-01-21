# Backlog - Планы развития

Этот документ содержит планы по развитию проекта benchmark-standalone.

## Приоритет: Высокий

### Параллельное выполнение задач

**Описание:** Добавить возможность параллельного выполнения нескольких задач для ускорения benchmark.

**Преимущества:**
- Значительное ускорение выполнения большого количества задач
- Более эффективное использование ресурсов

**Реализация:**
```python
# В main.py
async def run_tasks_parallel(tasks: List[Dict], max_concurrent: int = 5):
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def run_with_semaphore(task):
        async with semaphore:
            return await run_task(task)
    
    results = await asyncio.gather(*[run_with_semaphore(t) for t in tasks])
    return results
```

**Оценка:** 2-3 дня

---

### Web UI для просмотра результатов

**Описание:** Создать веб-интерфейс для просмотра метрик и результатов экспериментов.

**Функциональность:**
- Список экспериментов
- Детальный просмотр метрик
- Графики и визуализация
- Сравнение экспериментов
- Экспорт данных

**Технологии:**
- Backend: FastAPI
- Frontend: React или Vue.js
- Графики: Chart.js или Plotly

**Оценка:** 1-2 недели

---

### Поддержка PostgreSQL

**Описание:** Добавить поддержку PostgreSQL для больших объемов данных.

**Преимущества:**
- Лучшая производительность для больших объемов
- Concurrent access
- Расширенные возможности запросов

**Реализация:**
```yaml
# config.yaml
database:
  type: "postgresql"  # или "sqlite"
  url: "postgresql://user:pass@localhost/benchmark"
```

**Оценка:** 3-5 дней

---

## Приоритет: Средний

### Orchestrator с планированием задач

**Описание:** Добавить Orchestrator возможность разбивать сложные задачи на подзадачи.

**Детали:** См. [`ORCHESTRATOR_PLANNING_PROPOSAL.md`](../ORCHESTRATOR_PLANNING_PROPOSAL.md)

**Компоненты:**
- Новый tool: `create_plan`
- Обновленный промпт Orchestrator
- Хранение плана в сессии
- Последовательное выполнение подзадач

**Преимущества:**
- Лучшая организация сложных задач
- Отслеживание прогресса
- Меньше timeout
- Возможность паузы и продолжения

**Оценка:** 1-2 недели

---

### Визуализация метрик

**Описание:** Генерация графиков и диаграмм для метрик.

**Типы визуализаций:**
- Success rate по категориям (bar chart)
- Token usage по задачам (line chart)
- Tool calls distribution (pie chart)
- Time series для экспериментов (line chart)
- Agent switches flow (sankey diagram)

**Библиотеки:**
- matplotlib
- plotly
- seaborn

**Оценка:** 5-7 дней

---

### Экспорт метрик в CSV/JSON

**Описание:** Добавить возможность экспорта метрик в различные форматы.

**Форматы:**
- CSV - для анализа в Excel/Google Sheets
- JSON - для интеграции с другими системами
- Parquet - для больших объемов данных

**Реализация:**
```bash
# Экспорт эксперимента
uv run python export_metrics.py --experiment-id <id> --format csv

# Экспорт всех данных
uv run python export_metrics.py --all --format json
```

**Оценка:** 2-3 дня

---

### Интеграция с CI/CD

**Описание:** Автоматический запуск benchmark в CI/CD pipeline.

**Функциональность:**
- GitHub Actions / GitLab CI конфигурация
- Автоматический запуск при изменениях
- Сравнение с baseline
- Уведомления при деградации

**Пример GitHub Actions:**
```yaml
name: Benchmark
on: [push, pull_request]
jobs:
  benchmark:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run benchmark
        run: |
          cd benchmark-standalone
          uv sync
          uv run python main.py --limit 10 --generate-report
      - name: Upload results
        uses: actions/upload-artifact@v2
        with:
          name: benchmark-results
          path: benchmark-standalone/reports/
```

**Оценка:** 3-5 дней

---

## Приоритет: Низкий

### Проактивное обновление JWT токенов

**Описание:** Обновлять токены до истечения, используя `expires_in`.

**Реализация:**
```python
class AuthManager:
    def __init__(self):
        self.token_expires_at = None
    
    async def get_headers(self):
        # Обновить токен за 5 минут до истечения
        if self.token_expires_at and time.time() > self.token_expires_at - 300:
            await self.refresh_access_token()
        
        return await super().get_headers()
```

**Оценка:** 1-2 дня

---

### Кэширование токенов между запусками

**Описание:** Сохранять токены в файл для переиспользования.

**Реализация:**
```python
# Сохранение токена
with open('.token_cache', 'w') as f:
    json.dump({
        'access_token': self.access_token,
        'refresh_token': self.refresh_token,
        'expires_at': self.token_expires_at
    }, f)

# Загрузка токена
if os.path.exists('.token_cache'):
    with open('.token_cache', 'r') as f:
        cache = json.load(f)
        if cache['expires_at'] > time.time():
            self.access_token = cache['access_token']
```

**Оценка:** 1 день

---

### Поддержка других OAuth2 grant types

**Описание:** Добавить поддержку `client_credentials` grant type.

**Использование:**
```yaml
gateway:
  auth_type: "jwt"
  jwt:
    grant_type: "client_credentials"  # вместо "password"
    client_id: "benchmark-service"
    client_secret: "secret"
```

**Оценка:** 2-3 дня

---

### Метрики обновления токенов

**Описание:** Собирать метрики о частоте обновления токенов.

**Метрики:**
- Количество обновлений токенов
- Количество ошибок обновления
- Среднее время обновления
- Fallback на полную аутентификацию

**Таблица:**
```sql
CREATE TABLE token_refresh_metrics (
    id UUID PRIMARY KEY,
    refresh_type VARCHAR(50),  -- 'refresh_token' или 'full_auth'
    success BOOLEAN,
    duration_ms INTEGER,
    error TEXT,
    created_at TIMESTAMP
);
```

**Оценка:** 2 дня

---

### Real-time мониторинг выполнения

**Описание:** WebSocket endpoint для отслеживания выполнения в реальном времени.

**Функциональность:**
- Подключение к WebSocket
- Получение обновлений о прогрессе
- Отображение в Web UI

**Реализация:**
```python
# В main.py
async def broadcast_progress(websocket, progress):
    await websocket.send(json.dumps({
        'type': 'progress',
        'current': progress['current'],
        'total': progress['total'],
        'task_id': progress['task_id']
    }))
```

**Оценка:** 5-7 дней

---

### Сравнение с историческими результатами

**Описание:** Автоматическое сравнение текущих результатов с предыдущими экспериментами.

**Функциональность:**
- Baseline эксперимент
- Сравнение метрик
- Детектирование регрессий
- Уведомления о значительных изменениях

**Пример отчета:**
```markdown
## Сравнение с baseline

| Метрика | Baseline | Текущий | Изменение |
|---------|----------|---------|-----------|
| Success Rate | 85% | 90% | +5% ✅ |
| Avg Duration | 12.5s | 10.2s | -18% ✅ |
| Token Usage | 5000 | 5500 | +10% ⚠️ |
```

**Оценка:** 3-5 дней

---

### A/B тестирование конфигураций

**Описание:** Возможность запуска экспериментов с разными конфигурациями для сравнения.

**Использование:**
```bash
# Запуск A/B теста
uv run python main.py --ab-test \
  --config-a config-v1.yaml \
  --config-b config-v2.yaml \
  --limit 20
```

**Метрики сравнения:**
- Success rate
- Performance
- Token usage
- Cost

**Оценка:** 5-7 дней

---

### Поддержка gRPC протокола

**Описание:** Добавить поддержку gRPC в дополнение к WebSocket.

**Преимущества:**
- Лучшая производительность
- Строгая типизация
- Bi-directional streaming

**Оценка:** 1-2 недели

---

### Кастомные задачи через UI

**Описание:** Web интерфейс для создания и редактирования задач.

**Функциональность:**
- CRUD операции для задач
- Валидация задач
- Предпросмотр
- Экспорт в YAML

**Оценка:** 1 неделя

---

## Завершенные задачи

### ✅ Автоматическое обновление JWT токенов

**Дата завершения:** 2026-01-21

**Описание:** Реализована автоматическая обработка 401 ошибок с обновлением токенов.

**Детали:** См. [`AUTHENTICATION.md`](AUTHENTICATION.md)

---

### ✅ Улучшение промптов агентов

**Дата завершения:** 2026-01-13

**Описание:** Улучшены промпты для более проактивного поведения агентов.

**Детали:** См. [`../AGENT_IMPROVEMENTS.md`](../AGENT_IMPROVEMENTS.md)

---

### ✅ Динамический timeout для сложных задач

**Дата завершения:** 2026-01-13

**Описание:** Автоматическое увеличение timeout до 300s для complex/mixed задач.

**Реализация:** В [`src/client.py`](../src/client.py)

---

### ✅ Лимит на количество tool calls

**Дата завершения:** 2026-01-13

**Описание:** Добавлен лимит в 100 tool calls для предотвращения бесконечных циклов.

**Реализация:** В [`src/client.py`](../src/client.py)

---

## Отклоненные идеи

### ❌ Встроенный LLM proxy

**Причина:** Дублирование функциональности существующего llm-proxy сервиса.

**Альтернатива:** Использовать существующий llm-proxy через Gateway.

---

### ❌ Прямое подключение к agent-runtime

**Причина:** Нарушает принцип независимости benchmark-standalone.

**Альтернатива:** Все взаимодействие через Gateway WebSocket API.

---

## Процесс добавления в backlog

1. Создать issue в репозитории с описанием задачи
2. Обсудить с командой
3. Оценить приоритет и сложность
4. Добавить в соответствующий раздел этого документа
5. При начале работы переместить в "В работе"
6. При завершении переместить в "Завершенные задачи"

## Контакты

Для обсуждения новых идей и предложений создавайте issues в репозитории.
