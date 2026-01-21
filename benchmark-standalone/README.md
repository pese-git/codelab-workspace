# Benchmark Standalone

Независимое приложение для тестирования AI-агентов через Gateway WebSocket API.

## Особенности

✅ **Независимость** - не зависит от внутренних компонентов agent-runtime  
✅ **Простота** - общение только с Gateway через WebSocket  
✅ **Портативность** - можно запускать на любой машине  
✅ **Полнота** - набор задач с автоматической валидацией  
✅ **Метрики** - комплексная система сбора и анализа  

## Архитектура

```
benchmark-standalone
    │
    ├─> Gateway WebSocket (ws://localhost:80/api/v1/ws)
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
- Запущенный Gateway (через nginx на порту 80 или напрямую на 8000)
- (Опционально) Flutter SDK для валидации

## Быстрый старт

### 1. Установка зависимостей

```bash
cd benchmark-standalone

# Установить зависимости через uv
uv sync

# Установить dev зависимости (ruff, ty, pytest)
uv sync --group dev
```

### 2. Конфигурация

Отредактируйте [`config.yaml`](config.yaml):

```yaml
gateway:
  base_url: "http://localhost:80"
  ws_url: "ws://localhost:80/api/v1/ws"
  
  # Аутентификация (выбрать один из вариантов)
  auth_type: "jwt"  # "internal" или "jwt"
  
  # Internal API Key (для auth_type: internal)
  api_key: "change-me-in-production"
  
  # JWT аутентификация (для auth_type: jwt)
  jwt:
    auth_url: "http://localhost:80/oauth/token"
    username: "admin"
    password: "admin"
    client_id: "codelab-flutter-app"

database:
  url: "sqlite:///data/metrics.db"

benchmark:
  tasks_file: "tasks-samples/tasks.yaml"
  test_project: "./_test_project"
  enable_validation: true
```

### 3. Проверка подключения

```bash
uv run python test_connection.py
```

### 4. Запуск задачи

```bash
# Запустить одну задачу
uv run python main.py --task-id task_001

# С генерацией отчета
uv run python main.py --task-id task_001 --generate-report
```

## Использование

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
├── pyproject.toml              # Зависимости проекта
├── config.yaml                 # Конфигурация
├── tasks.yaml                  # Benchmark задачи (deprecated, см. tasks-samples/)
├── main.py                     # Главный скрипт
├── generate_report.py          # Генератор отчетов
├── test_connection.py          # Тест подключения
├── test_token_refresh.py       # Тест обновления токенов
├── README.md                   # Эта документация
├── CHANGELOG.md                # История изменений
├── src/                        # Исходный код
│   ├── __init__.py
│   ├── auth.py                # Управление аутентификацией
│   ├── client.py              # Gateway WebSocket клиент
│   ├── executor.py            # Локальное выполнение tools
│   ├── validator.py           # Автоматическая валидация
│   ├── models.py              # SQLAlchemy модели
│   ├── database.py            # Database управление
│   ├── collector.py           # Сбор метрик
│   └── reporter.py            # Генерация отчетов
├── doc/                        # Документация
│   ├── ARCHITECTURE.md        # Архитектура системы
│   ├── QUICKSTART.md          # Быстрый старт
│   ├── AUTHENTICATION.md      # Аутентификация
│   └── DEVELOPMENT.md         # Разработка
├── data/                       # База данных (создается автоматически)
│   └── metrics.db
├── reports/                    # Отчеты (создается автоматически)
│   └── report_*.md
├── tasks-samples/             # Примеры задач
│   └── tasks.yaml
└── _test_project/             # Flutter проект для тестирования
```

## Компоненты

### GatewayClient

WebSocket клиент для общения с Gateway:
- Отправка задач
- Получение ответов
- Обработка tool calls
- Отправка tool results
- Автоматическое обновление JWT токенов

### AuthManager

Управление аутентификацией:
- Internal API Key аутентификация
- JWT OAuth2 аутентификация
- Автоматическое обновление токенов при 401
- Thread-safe refresh механизм

### MockToolExecutor

Локальное выполнение tools в test_project:
- `write_file` / `write_to_file` - создание/изменение файлов
- `read_file` - чтение файлов
- `list_files` - список файлов
- `search_in_code` / `search_files` - поиск в коде
- `apply_diff` - применение изменений

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

## Development Tools

Проект использует современные инструменты разработки:

### uv - Package Manager

```bash
# Установить зависимости
uv sync

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
```

### ty - Type Checking

```bash
# Проверить типы
uv run ty check src/

# С подробным выводом
uv run ty check --verbose src/
```

### pytest - Тестирование

```bash
# Запустить тесты
uv run pytest

# С coverage
uv run pytest --cov=src
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
# Проверить статус через docker-compose
cd codelab-ai-service
docker-compose ps

# Или запустить Gateway напрямую
cd codelab-ai-service/gateway
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Ошибка: "401 Unauthorized"

**Причина:** Неверные учетные данные или истекший токен

**Решение:**
- Проверьте настройки аутентификации в [`config.yaml`](config.yaml)
- Для JWT: убедитесь что auth-service запущен
- Для Internal: проверьте API ключ

### Ошибка: "Tasks file not found"

**Причина:** Файл tasks.yaml не найден

**Решение:**
```bash
# Использовать примеры задач
# В config.yaml установить: tasks_file: "tasks-samples/tasks.yaml"
```

### Ошибка: "dart command not found"

**Причина:** Flutter SDK не установлен

**Решение:**
- Установите Flutter SDK или
- Отключите валидацию в config.yaml: `enable_validation: false`

## Документация

- [`doc/ARCHITECTURE.md`](doc/ARCHITECTURE.md) - Архитектура системы
- [`doc/QUICKSTART.md`](doc/QUICKSTART.md) - Быстрый старт
- [`doc/AUTHENTICATION.md`](doc/AUTHENTICATION.md) - Настройка аутентификации
- [`doc/DEVELOPMENT.md`](doc/DEVELOPMENT.md) - Руководство разработчика
- [`CHANGELOG.md`](CHANGELOG.md) - История изменений

## Лицензия

MIT

## Автор

Создано на основе codelab-ai-service/benchmark
