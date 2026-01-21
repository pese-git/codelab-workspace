# CodeLab Workspace

**CodeLab Workspace** — это AI-powered IDE с мультиагентной системой, построенная на современном технологическом стеке. Проект объединяет кроссплатформенный Flutter-интерфейс и микросервисную архитектуру AI-сервиса для эффективной разработки кода.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Flutter](https://img.shields.io/badge/Flutter-3.38.5-02569B?logo=flutter)
![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python)
![Status](https://img.shields.io/badge/status-MVP-green)

**Версия**: 1.0 (MVP)
**Дата обновления**: 21 января 2026

## 🎯 Основные возможности

### IDE (Flutter)
- ✅ **Кроссплатформенность** - Windows, Linux, macOS
- ✅ **Редактор кода** - Подсветка синтаксиса для множества языков (Dart, Python, JavaScript, TypeScript, Java, C/C++, HTML/CSS и др.)
- ✅ **Навигация по проекту** - Дерево файлов с быстрым поиском
- ✅ **Встроенный терминал** - Выполнение команд и скриптов
- ✅ **AI Ассистент** - Интеллектуальная помощь в написании кода
- ✅ **Модульная архитектура** - Чистое разделение ответственности

### AI Service (Python)
- ✅ **Микросервисная архитектура** - 4 сервиса (Gateway, Agent Runtime, LLM Proxy, Auth Service)
- ✅ **Мультиагентная система** - 5 специализированных агентов (🎭 Orchestrator, 💻 Coder, 🏗️ Architect, 🐛 Debug, 💬 Ask)
- ✅ **OAuth2 аутентификация** - JWT токены (RS256) с refresh token rotation
- ✅ **Поддержка множества LLM** - OpenAI, Anthropic, Ollama (локальные модели)
- ✅ **WebSocket API** - Потоковая передача данных в реальном времени
- ✅ **HITL (Human-in-the-Loop)** - Контроль опасных операций с database persistence
- ✅ **Session persistence** - Async database (PostgreSQL/SQLite)
- ✅ **9 реализованных tools** - Файловые операции, команды, поиск в коде

## 📁 Структура проекта

```
codelab-workspace/
├── codelab_ide/              # Flutter IDE приложение
│   ├── apps/
│   │   └── codelab_ide/      # Основное приложение
│   ├── packages/
│   │   ├── codelab_core/     # Основные сервисы (файлы, проекты)
│   │   ├── codelab_engine/   # Бизнес-логика и UI виджеты
│   │   ├── codelab_ai_assistant/  # Интеграция AI ассистента
│   │   ├── codelab_uikit/    # UI компоненты и темы
│   │   └── codelab_version_control/  # Git интеграция
│   └── README.md             # Подробная документация IDE
│
├── codelab-ai-service/       # AI сервис (микросервисы)
│   ├── gateway/              # WebSocket прокси (порт 8000)
│   ├── agent-runtime/        # AI логика и мультиагентная система (порт 8001)
│   ├── llm-proxy/            # Унифицированный доступ к LLM (порт 8002)
│   ├── auth-service/         # OAuth2 Authorization Server (порт 8003)
│   └── README.md             # Подробная документация AI сервиса
│
├── website/                  # Документация (Docusaurus)
│   └── docs/                 # Полная документация проекта
│
├── doc/                      # Техническая документация
│   ├── design_doc.md         # Дизайн-документ проекта
│   ├── product_description.md # Описание продукта
│   ├── competitive_analysis.md # Конкурентный анализ
│   ├── PROJECT_ROADMAP_2026.md # Roadmap на 2026 год
│   ├── DOCUMENTATION_AUDIT_REPORT.md # Аудит документации
│   ├── poc/                  # Proof of Concept документация
│   └── reports/archive/      # Архив исторических отчетов
│
├── benchmark-standalone/     # Standalone бенчмарк система
└── codelab-chart/           # Kubernetes Helm charts
```

## 🚀 Быстрый старт

### Системные требования

#### Для IDE (Flutter)
- **Dart SDK**: 3.10.1+
- **Flutter SDK**: 3.38.5 (рекомендуется через FVM)
- **Git**: для клонирования репозитория
- **Минимум 4 GB RAM** (рекомендуется 8 GB)

#### Для AI Service (Python)
- **Python**: 3.12+
- **Docker & Docker Compose**: для запуска микросервисов
- **uv**: быстрый менеджер пакетов Python

### Установка

#### 1. Клонирование репозитория

```bash
# Клонировать с подмодулями
git clone --recursive https://github.com/pese-git/codelab-workspace.git
cd codelab-workspace

# Если уже клонировали без --recursive
git submodule update --init --recursive
```

#### 2. Настройка IDE (Flutter)

```bash
cd codelab_ide

# Установить FVM (если не установлен)
dart pub global activate fvm

# Установить Flutter через FVM
fvm install
fvm use 3.38.5

# Установить Melos для управления монорепозиторием
dart pub global activate melos

# Установить зависимости
melos bootstrap

# Запустить IDE
melos run:codelab_ide
```

**Подробная документация:** [`codelab_ide/README.md`](codelab_ide/README.md)

#### 3. Настройка AI Service (Python)

```bash
cd codelab-ai-service

# Установить uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Создать .env файл
cp .env.example .env
# Отредактируйте .env и добавьте API ключи для OpenAI/Anthropic

# Запустить все сервисы через Docker
docker compose up -d

# Проверить статус
curl http://localhost:8000/health  # gateway
curl http://localhost:8001/health  # agent-runtime
curl http://localhost:8002/health  # llm-proxy
curl http://localhost:8003/health  # auth-service
```

**Подробная документация:** [`codelab-ai-service/README.md`](codelab-ai-service/README.md)

**Полная документация**: [website/docs/](website/docs/) (Docusaurus)

## 🔌 Интеграция компонентов

### Архитектура взаимодействия

```
┌─────────────────┐
│   CodeLab IDE   │  (Flutter Desktop App)
│   (Frontend)    │
└────────┬────────┘
         │ WebSocket
         ↓
┌─────────────────┐
│    Gateway      │  (WebSocket Proxy)
│   Port: 8000    │
└────────┬────────┘
         │ HTTP/SSE
         ↓
┌─────────────────┐
│ Agent Runtime   │  (AI Logic & Orchestration)
│   Port: 8001    │
└────────┬────────┘
         │ HTTP/SSE
         ↓
┌─────────────────┐
│   LLM Proxy     │  (Unified LLM Access)
│   Port: 8002    │
└────────┬────────┘
         │
    ┌────┴────┬──────────┐
    ↓         ↓          ↓
┌────────┐ ┌──────┐ ┌────────┐
│ OpenAI │ │Claude│ │ Ollama │
└────────┘ └──────┘ └────────┘
```

### WebSocket протокол

**Подключение к AI ассистенту:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/{session_id}');

// Отправка сообщения
ws.send(JSON.stringify({
    type: "user_message",
    content: "Напиши функцию для сортировки массива"
}));

// Получение ответа
ws.onmessage = (event) => {
    const response = JSON.parse(event.data);
    console.log(response);
};
```

## 🛠 Разработка

### Команды для IDE (Flutter)

```bash
cd codelab_ide

# Запустить IDE
melos run:codelab_ide

# Запустить тесты
melos test

# Генерация кода (freezed, json_serializable)
melos generate

# Форматирование кода
melos format

# Анализ кода
melos analyze

# Очистить build артефакты
melos clean
```

### Команды для AI Service (Python)

```bash
cd codelab-ai-service

# Просмотр логов
docker compose logs -f

# Перезапуск сервиса
docker compose restart gateway

# Остановка всех сервисов
docker compose down

# Пересборка после изменений
docker compose up -d --build

# Загрузка локальной модели Ollama
./pull_model_docker.sh qwen3:0.6b
```

### Локальная разработка микросервисов

```bash
cd codelab-ai-service/gateway  # или agent-runtime, llm-proxy

# Создать виртуальное окружение
python -m venv .venv
source .venv/bin/activate

# Установить зависимости
uv pip install -e '.[dev]'

# Запустить тесты
pytest tests/

# Проверить код
ruff check app/
ruff check app/ --fix

# Запустить сервис локально
python app/main.py
```

## 📚 Документация

### 🌐 Полная документация (Docusaurus)
Вся актуальная документация доступна в [`website/docs/`](website/docs/):

**Начало работы:**
- [Установка](website/docs/getting-started/installation.md)
- [Быстрый старт](website/docs/getting-started/quick-start.md)
- [Системные требования](website/docs/getting-started/system-requirements.md)

**Архитектура:**
- [Обзор архитектуры](website/docs/architecture/overview.md)
- [Архитектура IDE](website/docs/architecture/ide-architecture.md)
- [Архитектура AI Service](website/docs/architecture/ai-service-architecture.md)
- [Интеграция компонентов](website/docs/architecture/integration.md)

**API документация:**
- [WebSocket Protocol](website/docs/api/websocket-protocol.md)
- [Agent Protocol](website/docs/api/agent-protocol.md)
- [Мультиагентная система](website/docs/api/multi-agent-system.md) ⭐ NEW
- [Tools Specification](website/docs/api/tools-specification.md)
- [Gateway API](website/docs/api/gateway.md)
- [Agent Runtime API](website/docs/api/agent-runtime.md)
- [LLM Proxy API](website/docs/api/llm-proxy.md)
- [Auth Service API](website/docs/api/auth-service.md) ⭐ NEW

**Руководства по интеграции:** ⭐ NEW
- [Интеграция с Auth Service](website/docs/guides/auth-integration.md)
- [Интеграция с мультиагентной системой](website/docs/guides/multi-agent-integration.md)

**Разработка:**
- [Разработка IDE](website/docs/development/ide.md)
- [Разработка AI Service](website/docs/development/ai-service.md)
- [Тестирование](website/docs/development/testing.md)
- [Contributing](website/docs/development/contributing.md)

### 📋 Техническая документация

**Основные документы** ([`doc/`](doc/)):
- **[Design Document](doc/design_doc.md)** - Полный дизайн-документ проекта
- **[Product Description](doc/product_description.md)** - Описание продукта и бизнес-модель
- **[Competitive Analysis](doc/competitive_analysis.md)** - Анализ конкурентов
- **[Project Roadmap 2026](doc/PROJECT_ROADMAP_2026.md)** - План развития на 2026 год
- **[Documentation Audit](doc/DOCUMENTATION_AUDIT_REPORT.md)** - Аудит документации

**Компонентная документация:**
- **[IDE Documentation](codelab_ide/README.md)** - Полное руководство по Flutter IDE
- **[AI Service Documentation](codelab-ai-service/README.md)** - Документация по микросервисам
- **[Deployment Guide](codelab-chart/README.md)** - Kubernetes развертывание

**Специализированная документация:**
- **[Multi-Agent System](codelab-ai-service/doc/MULTI_AGENT_README.md)** - Мультиагентная система
- **[HITL Implementation](codelab-ai-service/doc/HITL_IMPLEMENTATION.md)** - Human-in-the-Loop
- **[Session Persistence](codelab-ai-service/agent-runtime/SESSION_PERSISTENCE_GUIDE.md)** - Персистентность сессий

**Архивная документация:**
- **[POC Documentation](doc/poc/README.md)** - Документация Proof of Concept (частично устаревшая)
- **[Historical Reports](doc/reports/archive/)** - Архив отчетов о разработке

## 🧪 Тестирование

### Тестирование IDE

```bash
cd codelab_ide

# Запустить все тесты
melos test

# Тесты конкретного пакета
melos test --scope=codelab_core
melos test --scope=codelab_ai_assistant
```

### Тестирование AI Service

```bash
cd codelab-ai-service

# Тесты всех сервисов
cd gateway && uv run pytest tests
cd ../agent-runtime && uv run pytest tests
cd ../llm-proxy && uv run pytest tests

# Интеграционные тесты (требуется запущенный docker compose)
docker compose up -d
pytest tests/integration/
```

## 🤝 Участие в разработке

Мы приветствуем вклад в развитие проекта! Вот как вы можете помочь:

1. **Fork** репозитория
2. Создайте **ветку** для ваших изменений (`git checkout -b feature/amazing-feature`)
3. **Commit** изменения (`git commit -m 'Add amazing feature'`)
4. **Push** в ветку (`git push origin feature/amazing-feature`)
5. Откройте **Pull Request**

### Стандарты кода

- **Flutter/Dart**: Следуйте [Effective Dart](https://dart.dev/guides/language/effective-dart)
- **Python**: Используйте Ruff для форматирования и линтинга
- **Commits**: Используйте [Conventional Commits](https://www.conventionalcommits.org/)

## 📝 Лицензия

Этот проект распространяется под лицензией MIT. Подробности в файле [LICENSE](LICENSE).

```
MIT License

Copyright (c) 2025 CodeLab IDE

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## 🔗 Полезные ссылки

- **Flutter**: https://flutter.dev
- **Dart**: https://dart.dev
- **Melos**: https://melos.invertase.dev
- **FastAPI**: https://fastapi.tiangolo.com
- **Ollama**: https://ollama.com
- **OpenAI API**: https://platform.openai.com/docs
- **Anthropic API**: https://docs.anthropic.com

## 📧 Контакты

Если у вас есть вопросы или предложения, создайте [Issue](https://github.com/pese-git/codelab-workspace/issues) в репозитории.

---

**Сделано с ❤️ командой CodeLab**