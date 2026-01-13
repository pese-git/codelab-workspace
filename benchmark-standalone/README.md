# Benchmark Standalone

Независимое приложение для тестирования AI-агентов через Gateway WebSocket API.

## Особенности

✅ **Независимость** - не зависит от внутренних компонентов agent-runtime  
✅ **Простота** - общение только с Gateway через WebSocket  
✅ **Портативность** - можно запускать на любой машине  
✅ **Полнота** - 40 задач с автоматической валидацией  
✅ **Метрики** - комплексная система сбора и анализа  

## Архитектура

```
benchmark-standalone
    │
    ├─> Gateway WebSocket (ws://localhost:8000/ws/benchmark)
    │   └─> Agent Runtime → LLM Proxy
    │
    ├─> MockToolExecutor (локальное выполнение tools)
    │
    ├─> TaskValidator (автоматическая проверка)
    │
    ├─> MetricsCollector (SQLite база метрик)
    │
    └─> ReportGenerator (Markdown отчеты)
```

## Требования

- Python >= 3.12
- [uv](https://github.com/astral-sh/uv) - современный package manager (рекомендуется)
- Запущенный Gateway на порту 8000
- (Опционально) Flutter SDK для валидации

## Установка

### Через uv (рекомендуется)

```bash
cd benchmark-standalone

# Установить зависимости
uv sync

# Установить dev зависимости (ruff, ty, pytest)
uv sync --group dev
```

### Через pip

```bash
cd benchmark-standalone
pip install -e .

# Dev зависимости
pip install -e ".[dev]"
```

## Конфигурация

Отредактируйте [`config.yaml`](config.yaml):

```yaml
gateway:
  ws_url: "ws://localhost:8000/ws/benchmark"  # Gateway WebSocket URL
  timeout: 60

database:
  url: "sqlite:///data/metrics.db"  # Локальная база метрик

benchmark:
  tasks_file: "tasks.yaml"          # Файл с задачами
  test_project: "./test_project"    # Flutter проект для валидации
  enable_validation: true           # Включить автоматическую валидацию
```

## Development Tools

Проект использует современные инструменты разработки:

### uv - Package Manager

```bash
# Установить зависимости
uv sync

# Установить dev зависимости
uv sync --group dev

# Запустить скрипт
uv run python main.py --task-id task_001

# Добавить новую зависимость
uv add <package>
```

### ruff - Linting и форматирование

```bash
# Проверить код
uv run ruff check .

# Автоматическое исправление
uv run ruff check --fix .

# Форматирование кода
uv run ruff format .

# Проверка и форматирование
uv run ruff check --fix . && uv run ruff format .
```

### ty - Type Checking

```bash
# Проверить типы
uv run ty check src/

# С подробным выводом
uv run ty check --verbose src/

# Проверить конкретный файл
uv run ty check src/client.py
```

### pytest - Тестирование

```bash
# Запустить тесты (когда будут созданы)
uv run pytest

# С coverage
uv run pytest --cov=src

# Конкретный тест
uv run pytest tests/test_client.py
```

## Использование

### Быстрый старт

```bash
# Запустить одну задачу
uv run python main.py --task-id task_001

# Запустить с генерацией отчета
uv run python main.py --task-id task_001 --generate-report
```

### Фильтрация задач

```bash
# По категории
uv run python main.py --category simple

# По типу
uv run python main.py --type coding

# Диапазон задач
uv run python main.py --task-range 1-10

# Конкретные задачи
uv run python main.py --task-ids task_001,task_005,task_010

# Ограничить количество
uv run python main.py --limit 5
```

### Режимы выполнения

```bash
# Single-agent режим
uv run python main.py --mode single-agent --category simple

# Multi-agent режим (по умолчанию)
uv run python main.py --mode multi-agent --category simple

# Оба режима для сравнения
uv run python main.py --mode both --limit 10 --generate-report
```

### Генерация отчетов

```bash
# Автоматически после эксперимента
uv run python main.py --mode both --limit 5 --generate-report

# Вручную из существующих метрик
uv run python generate_report.py --latest

# Отчеты сохраняются в ./reports/
```

## Структура проекта

```
benchmark-standalone/
├── pyproject.toml              # Зависимости
├── config.yaml                 # Конфигурация
├── tasks.yaml                  # 40 benchmark задач
├── main.py                     # Главный скрипт
├── README.md                   # Эта документация
├── src/                        # Исходный код
│   ├── __init__.py
│   ├── client.py              # Gateway WebSocket клиент
│   ├── executor.py            # Локальное выполнение tools
│   ├── validator.py           # Автоматическая валидация
│   ├── models.py              # SQLAlchemy модели
│   ├── database.py            # Database управление
│   ├── collector.py           # Сбор метрик
│   └── reporter.py            # Генерация отчетов
├── data/                       # База данных
│   └── metrics.db
├── test_project/              # Flutter проект для валидации
│   ├── pubspec.yaml
│   └── lib/
└── reports/                    # Сгенерированные отчеты
    └── report_*.md
```

## Компоненты

### GatewayClient

WebSocket клиент для общения с Gateway:
- Отправка задач
- Получение ответов
- Обработка tool calls
- Отправка tool results

### MockToolExecutor

Локальное выполнение tools в test_project:
- `write_file` - создание/изменение файлов
- `read_file` - чтение файлов
- `list_files` - список файлов
- `search_in_code` - поиск в коде

### TaskValidator

Автоматическая проверка выполнения задач:
- `file_exists` - проверка существования файла
- `syntax_valid` - проверка синтаксиса Dart
- `contains_text` - поиск текста в файле
- `test_passes` - запуск Flutter тестов

### MetricsCollector

Сбор и хранение метрик в SQLite:
- Эксперименты
- Выполнение задач
- LLM вызовы
- Tool вызовы
- Переключения агентов
- Оценки качества
- Галлюцинации

### ReportGenerator

Генерация детальных Markdown отчетов:
- Executive Summary
- Детальные метрики
- Сравнительный анализ
- Рекомендации

## Примеры

### Пример 1: Тестирование одной задачи

```bash
# Убедитесь что Gateway запущен
# cd codelab-ai-service/gateway && uv run uvicorn app.main:app --port 8000

# Проверить подключение
uv run python test_connection.py

# Запустить задачу
uv run python main.py --task-id task_001 --generate-report
```

### Пример 2: Сравнение режимов

```bash
# Запустить 10 простых задач в обоих режимах
uv run python main.py --mode both --category simple --limit 10 --generate-report
```

### Пример 3: Полный эксперимент

```bash
# Запустить все 40 задач в multi-agent режиме
uv run python main.py --mode multi-agent --generate-report
```

### Пример 4: Development workflow

```bash
# Проверить код перед коммитом
uv run ruff check --fix .
uv run ruff format .
uv run ty check src/

# Запустить тесты
uv run pytest
```

## Метрики

Система собирает следующие метрики:

- **Task Success Rate (TSR)** - процент успешно выполненных задач
- **Time To Useful Answer (TTUA)** - время до получения результата
- **Token Usage** - количество input/output токенов
- **Cost** - оценочная стоимость выполнения
- **Tool Calls** - количество и успешность вызовов tools
- **Agent Switches** - переключения между агентами (multi-agent)
- **Hallucinations** - обнаруженные галлюцинации
- **Quality Score** - оценка качества результатов

## Troubleshooting

### Ошибка: "Failed to connect to Gateway"

**Причина:** Gateway не запущен

**Решение:**
```bash
cd codelab-ai-service/gateway
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Ошибка: "Tasks file not found"

**Причина:** Файл tasks.yaml не найден

**Решение:**
```bash
# Скопировать из benchmark
cp codelab-ai-service/benchmark/poc_benchmark_tasks.yaml benchmark-standalone/tasks.yaml
```

### Ошибка: "dart command not found"

**Причина:** Flutter SDK не установлен

**Решение:**
- Установите Flutter SDK или
- Отключите валидацию в config.yaml: `enable_validation: false`

## Отличия от оригинального benchmark

| Аспект | Оригинальный benchmark | benchmark-standalone |
|--------|------------------------|----------------------|
| Зависимости | agent-runtime модули | Минимальные (websockets, sqlalchemy) |
| Общение | Прямой импорт или HTTP/WS | Только Gateway WebSocket |
| База данных | Общая с agent-runtime | Независимая SQLite |
| Портативность | Требует agent-runtime | Полностью независимое |
| Сложность | Высокая | Низкая |

## Лицензия

MIT

## Автор

Создано на основе codelab-ai-service/benchmark
