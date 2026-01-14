# Быстрый старт - Benchmark Standalone

## Предварительные требования

- Python >= 3.12
- [uv](https://github.com/astral-sh/uv) - установить: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Запущенный Gateway на порту 8000

## Шаг 1: Установка

```bash
cd benchmark-standalone

# Установить зависимости через uv
uv sync

# Установить dev зависимости (ruff, ty, pytest)
uv sync --group dev
```

## Шаг 2: Запуск Gateway

В отдельном терминале:

```bash
cd codelab-ai-service/gateway
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Убедитесь что Gateway запустился и доступен на `http://localhost:8000`

## Шаг 3: Проверка подключения

```bash
# Тест подключения к Gateway
uv run python test_connection.py
```

## Шаг 4: Запуск первой задачи

```bash
# Запустить простую задачу
uv run python main.py --task-id task_001

# С генерацией отчета
uv run python main.py --task-id task_001 --generate-report
```

## Шаг 5: Запуск нескольких задач

```bash
# Все простые задачи
uv run python main.py --category simple --generate-report

# Первые 5 задач
uv run python main.py --task-range 1-5 --generate-report

# Конкретные задачи
uv run python main.py --task-ids task_001,task_005,task_010 --generate-report
```

## Шаг 6: Сравнение режимов

```bash
# Запустить в обоих режимах для сравнения
uv run python main.py --mode both --limit 10 --generate-report
```

## Шаг 7: Просмотр результатов

```bash
# Отчеты сохраняются в ./reports/
ls -la reports/

# Просмотреть последний отчет
cat reports/report_*.md | tail -n 100
```

## Структура после запуска

```
benchmark-standalone/
├── data/
│   └── metrics.db              # База данных с метриками
├── reports/
│   └── report_1234567890.md   # Сгенерированные отчеты
├── logs/
│   └── benchmark.log           # Логи выполнения
└── test_project/               # Flutter проект (если создан)
    └── lib/
        └── widgets/
            └── user_card.dart  # Созданные агентом файлы
```

## Примеры команд

### Тестирование

```bash
# Одна простая задача
uv run python main.py --task-id task_001

# Все простые задачи
uv run python main.py --category simple

# Все coding задачи
uv run python main.py --type coding

# Первые 10 задач
uv run python main.py --task-range 1-10
```

### Полный эксперимент

```bash
# Все 40 задач в multi-agent режиме
uv run python main.py --mode multi-agent --generate-report

# Сравнение single-agent vs multi-agent (10 задач)
uv run python main.py --mode both --limit 10 --generate-report
```

### Отладка

```bash
# С подробными логами
uv run python main.py --task-id task_001 2>&1 | tee debug.log

# Проверить базу данных
sqlite3 data/metrics.db "SELECT * FROM poc_experiments;"

# Проверить код
uv run ruff check .
uv run ty check src/
```

## Troubleshooting

### Gateway не отвечает

```bash
# Проверить что Gateway запущен
curl http://localhost:8000/health

# Проверить логи Gateway
cd codelab-ai-service/gateway
tail -f logs/gateway.log
```

### Задачи не выполняются

```bash
# Проверить что agent-runtime запущен
curl http://localhost:8003/health

# Проверить что LLM proxy запущен
curl http://localhost:8002/health
```

### Валидация не работает

```bash
# Проверить Flutter SDK
flutter --version

# Отключить валидацию
# В config.yaml: enable_validation: false
```

## Следующие шаги

1. Запустите несколько задач для тестирования
2. Проверьте метрики в базе данных
3. Изучите сгенерированные отчеты
4. Адаптируйте задачи под свои нужды
5. Добавьте свои метрики и проверки

## Полезные команды

```bash
# Просмотр метрик в базе
sqlite3 data/metrics.db <<EOF
SELECT 
    mode,
    COUNT(*) as total_tasks,
    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
    ROUND(AVG(CASE WHEN success = 1 THEN 1.0 ELSE 0.0 END) * 100, 2) as success_rate
FROM poc_task_executions
GROUP BY mode;
EOF

# Очистка базы данных
rm -f data/metrics.db

# Очистка test_project
rm -rf test_project/lib/widgets test_project/lib/models
```
