# Руководство разработчика

Это руководство описывает процесс разработки и внесения изменений в проект benchmark-standalone.

## Требования для разработки

- Python >= 3.12
- [uv](https://github.com/astral-sh/uv) - package manager
- Git
- (Опционально) Flutter SDK для тестирования валидации

## Установка окружения разработки

### 1. Клонирование репозитория

```bash
git clone <repository-url>
cd codelab-workspace/benchmark-standalone
```

### 2. Установка зависимостей

```bash
# Установить основные зависимости
uv sync

# Установить dev зависимости (ruff, ty, pytest)
uv sync --group dev
```

### 3. Настройка конфигурации

```bash
# Скопировать пример конфигурации
cp config.yaml config.local.yaml

# Отредактировать под свои нужды
vim config.local.yaml
```

## Инструменты разработки

### uv - Package Manager

[uv](https://github.com/astral-sh/uv) - современный быстрый package manager для Python.

```bash
# Установка зависимостей
uv sync

# Установка dev зависимостей
uv sync --group dev

# Запуск скрипта
uv run python main.py --task-id task_001

# Добавление новой зависимости
uv add <package>

# Добавление dev зависимости
uv add --group dev <package>

# Обновление зависимостей
uv sync --upgrade
```

### ruff - Linting и форматирование

[ruff](https://github.com/astral-sh/ruff) - быстрый linter и formatter для Python.

```bash
# Проверка кода
uv run ruff check .

# Автоматическое исправление
uv run ruff check --fix .

# Форматирование кода
uv run ruff format .

# Проверка и форматирование вместе
uv run ruff check --fix . && uv run ruff format .

# Проверка конкретного файла
uv run ruff check src/client.py
```

**Конфигурация** в [`pyproject.toml`](../pyproject.toml):

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = [
    "E",  # pycodestyle
    "F",  # pyflakes
    "I",  # isort
    "B",  # flake8-bugbear
]
```

### ty - Type Checking

[ty](https://github.com/astral-sh/ty) - type checker для Python.

```bash
# Проверка типов
uv run ty check src/

# С подробным выводом
uv run ty check --verbose src/

# Проверка конкретного файла
uv run ty check src/client.py
```

**Конфигурация** в [`ty.toml`](../ty.toml).

### pytest - Тестирование

```bash
# Запуск всех тестов
uv run pytest

# С coverage
uv run pytest --cov=src

# Конкретный тест
uv run pytest tests/test_client.py

# С подробным выводом
uv run pytest -v

# Остановка на первой ошибке
uv run pytest -x
```

## Структура проекта

```
benchmark-standalone/
├── src/                        # Исходный код
│   ├── __init__.py            # Экспорты модуля
│   ├── auth.py                # AuthManager - управление аутентификацией
│   ├── client.py              # GatewayClient - WebSocket клиент
│   ├── executor.py            # MockToolExecutor - выполнение tools
│   ├── validator.py           # TaskValidator - валидация задач
│   ├── models.py              # SQLAlchemy модели
│   ├── database.py            # Database управление
│   ├── collector.py           # MetricsCollector - сбор метрик
│   └── reporter.py            # ReportGenerator - генерация отчетов
├── doc/                        # Документация
│   ├── ARCHITECTURE.md        # Архитектура системы
│   ├── QUICKSTART.md          # Быстрый старт
│   ├── AUTHENTICATION.md      # Аутентификация
│   └── DEVELOPMENT.md         # Это руководство
├── tests/                      # Тесты (TODO)
├── main.py                     # Главный скрипт
├── generate_report.py          # Генератор отчетов
├── test_connection.py          # Тест подключения
├── test_token_refresh.py       # Тест обновления токенов
├── pyproject.toml              # Зависимости и настройки
├── config.yaml                 # Конфигурация
└── README.md                   # Основная документация
```

## Workflow разработки

### 1. Создание новой ветки

```bash
git checkout -b feature/my-feature
```

### 2. Внесение изменений

```bash
# Редактирование кода
vim src/client.py

# Проверка кода
uv run ruff check --fix .
uv run ruff format .
uv run ty check src/

# Тестирование
uv run pytest
```

### 3. Коммит изменений

```bash
git add .
git commit -m "feat: добавлена новая функциональность"
```

**Формат коммитов** (Conventional Commits):

- `feat:` - новая функциональность
- `fix:` - исправление ошибки
- `docs:` - изменения в документации
- `style:` - форматирование кода
- `refactor:` - рефакторинг
- `test:` - добавление тестов
- `chore:` - обновление зависимостей и т.д.

### 4. Push и Pull Request

```bash
git push origin feature/my-feature
```

Создайте Pull Request в GitHub/GitLab.

## Добавление новых компонентов

### Добавление нового tool

В [`src/executor.py`](../src/executor.py):

```python
async def _my_custom_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Custom tool implementation.
    
    Args:
        args: Tool arguments
        
    Returns:
        Tool result
    """
    try:
        # Ваша логика
        result = do_something(args)
        
        return {
            "success": True,
            "result": result
        }
    except Exception as e:
        logger.error(f"Error in my_custom_tool: {e}")
        return {
            "success": False,
            "error": str(e)
        }

# В execute_tool()
elif tool_name == "my_custom_tool":
    return await self._my_custom_tool(arguments)
```

### Добавление новой проверки валидации

В [`src/validator.py`](../src/validator.py):

```python
async def _check_custom(self, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Custom validation check.
    
    Args:
        params: Check parameters
        
    Returns:
        Check result
    """
    try:
        # Ваша логика проверки
        passed = check_something(params)
        
        return {
            "passed": passed,
            "message": "Check passed" if passed else "Check failed"
        }
    except Exception as e:
        return {
            "passed": False,
            "message": f"Error: {e}"
        }

# В _run_check()
elif check_type == "custom_check":
    return await self._check_custom(params)
```

### Добавление новой метрики

В [`src/models.py`](../src/models.py):

```python
class CustomMetric(Base):
    """Custom metric model."""
    __tablename__ = "poc_custom_metrics"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    task_execution_id: Mapped[UUID] = mapped_column(ForeignKey("poc_task_executions.id"))
    metric_value: Mapped[float]
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    
    # Relationship
    task_execution: Mapped["TaskExecution"] = relationship(back_populates="custom_metrics")
```

В [`src/collector.py`](../src/collector.py):

```python
async def record_custom_metric(
    self,
    task_execution_id: UUID,
    metric_value: float
) -> None:
    """
    Record custom metric.
    
    Args:
        task_execution_id: Task execution ID
        metric_value: Metric value
    """
    metric = CustomMetric(
        task_execution_id=task_execution_id,
        metric_value=metric_value
    )
    self.db.add(metric)
    await self.db.commit()
```

## Тестирование

### Запуск тестов

```bash
# Все тесты
uv run pytest

# С coverage
uv run pytest --cov=src --cov-report=html

# Конкретный модуль
uv run pytest tests/test_client.py

# Конкретный тест
uv run pytest tests/test_client.py::test_connection
```

### Написание тестов

Пример теста в `tests/test_client.py`:

```python
import pytest
from src import GatewayClient, AuthManager

@pytest.mark.asyncio
async def test_connection():
    """Test Gateway connection."""
    config = {
        'auth_type': 'internal',
        'api_key': 'test-key'
    }
    
    auth_manager = AuthManager(config)
    client = GatewayClient(
        base_url="http://localhost:8000",
        ws_url="ws://localhost:8000/ws",
        auth_manager=auth_manager
    )
    
    # Test connection
    result = await client.test_connection()
    assert result is True
```

## Отладка

### Логирование

Настройка уровня логирования в [`config.yaml`](../config.yaml):

```yaml
logging:
  level: "DEBUG"  # DEBUG, INFO, WARNING, ERROR
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: "logs/benchmark.log"
```

Использование в коде:

```python
import logging

logger = logging.getLogger("benchmark.mymodule")

logger.debug("Детальная информация")
logger.info("Информационное сообщение")
logger.warning("Предупреждение")
logger.error("Ошибка")
```

### Отладка WebSocket

```python
# В src/client.py добавить детальное логирование
logger.debug(f"Sending message: {json.dumps(message)}")
logger.debug(f"Received message: {json.dumps(msg)}")
```

### Отладка базы данных

```bash
# Просмотр базы данных
sqlite3 data/metrics.db

# Список таблиц
.tables

# Просмотр данных
SELECT * FROM poc_experiments;
SELECT * FROM poc_task_executions;

# Выход
.quit
```

## Обновление зависимостей

```bash
# Обновить все зависимости
uv sync --upgrade

# Обновить конкретную зависимость
uv add --upgrade <package>

# Проверить устаревшие зависимости
uv pip list --outdated
```

## Документация

### Обновление документации

При добавлении новой функциональности обновите:

1. [`README.md`](../README.md) - если изменился API или использование
2. [`doc/ARCHITECTURE.md`](ARCHITECTURE.md) - если изменилась архитектура
3. [`CHANGELOG.md`](../CHANGELOG.md) - добавьте запись об изменении
4. Docstrings в коде - документируйте все публичные функции

### Формат docstrings

```python
def my_function(arg1: str, arg2: int) -> bool:
    """
    Краткое описание функции.
    
    Более детальное описание, если необходимо.
    
    Args:
        arg1: Описание первого аргумента
        arg2: Описание второго аргумента
        
    Returns:
        Описание возвращаемого значения
        
    Raises:
        ValueError: Когда возникает эта ошибка
        
    Example:
        >>> my_function("test", 42)
        True
    """
    pass
```

## Производительность

### Профилирование

```bash
# Профилирование с cProfile
python -m cProfile -o profile.stats main.py --task-id task_001

# Анализ результатов
python -m pstats profile.stats
```

### Оптимизация

- Используйте `async/await` для I/O операций
- Избегайте блокирующих операций в async функциях
- Используйте batch операции с базой данных
- Кэшируйте результаты где возможно

## Troubleshooting

### Проблема: "Module not found"

```bash
# Переустановить зависимости
uv sync --reinstall
```

### Проблема: "Database locked"

```bash
# Закрыть все соединения с базой
rm data/metrics.db
# База будет создана заново при следующем запуске
```

### Проблема: "Type checking errors"

```bash
# Обновить type stubs
uv add --group dev types-<package>
```

## Полезные команды

```bash
# Очистка кэша Python
find . -type d -name "__pycache__" -exec rm -r {} +
find . -type f -name "*.pyc" -delete

# Очистка базы данных
rm -f data/metrics.db

# Очистка отчетов
rm -f reports/*.md

# Очистка логов
rm -f logs/*.log

# Полная очистка
rm -rf data/ reports/ logs/ .ruff_cache/
```

## Ресурсы

- [uv Documentation](https://github.com/astral-sh/uv)
- [ruff Documentation](https://docs.astral.sh/ruff/)
- [pytest Documentation](https://docs.pytest.org/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [websockets Documentation](https://websockets.readthedocs.io/)

## Контакты

При возникновении вопросов или проблем:

1. Проверьте существующую документацию
2. Изучите примеры в коде
3. Создайте issue в репозитории
