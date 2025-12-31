# Архитектура Agent Runtime Service

## 📋 Обзор

**Agent Runtime** — это микросервис на базе FastAPI, который управляет AI-агентами для взаимодействия с языковыми моделями (LLM). Сервис реализует мультиагентную систему с 5 специализированными агентами и обеспечивает стриминговую обработку сообщений между пользователем и LLM.

## 🏗️ Архитектурные принципы

### 1. Многоуровневая архитектура
```
┌─────────────────────────────────────────┐
│         API Layer (endpoints.py)        │  ← HTTP/SSE интерфейс
├─────────────────────────────────────────┤
│      Services Layer (services/)         │  ← Бизнес-логика
├─────────────────────────────────────────┤
│       Agents Layer (agents/)            │  ← Специализированные агенты
├─────────────────────────────────────────┤
│       Models Layer (models/)            │  ← Pydantic схемы
├─────────────────────────────────────────┤
│    Core Layer (config, dependencies)    │  ← Конфигурация и DI
└─────────────────────────────────────────┘
```

### 2. Dependency Injection (DI)
Все зависимости управляются через [`app/core/dependencies.py`](codelab-ai-service/agent-runtime/app/core/dependencies.py):
- Singleton-инстансы сервисов
- Централизованное управление зависимостями
- Легкое тестирование через моки

### 3. Строгая типизация
- Все модели данных определены через Pydantic в [`app/models/schemas.py`](codelab-ai-service/agent-runtime/app/models/schemas.py)
- Type hints во всех функциях
- Валидация данных на уровне моделей

## 🎯 Основные компоненты

### 1. API Layer (`app/api/v1/endpoints.py`)

**Endpoints:**
- `GET /health` — проверка статуса сервиса
- `POST /agent/message/stream` — стриминговая обработка сообщений (SSE)
- `GET /agents` — список всех зарегистрированных агентов
- `GET /agents/{session_id}/current` — текущий активный агент сессии

**Типы сообщений:**
- `user_message` — обычное сообщение пользователя
- `tool_result` — результат выполнения инструмента из Gateway
- `switch_agent` — явный запрос на переключение агента

### 2. Multi-Agent System

#### Архитектура агентов

```
                    ┌──────────────────┐
                    │  Orchestrator    │
                    │  (Маршрутизатор) │
                    └────────┬─────────┘
                             │
            ┌────────────────┼────────────────┐
            │                │                │
    ┌───────▼──────┐  ┌─────▼─────┐  ┌──────▼──────┐
    │    Coder     │  │ Architect │  │    Debug    │
    │ (Полный      │  │ (Только   │  │ (Read-only  │
    │  доступ)     │  │  .md)     │  │  + execute) │
    └──────────────┘  └───────────┘  └─────────────┘
                             │
                      ┌──────▼──────┐
                      │     Ask     │
                      │  (Только    │
                      │   чтение)   │
                      └─────────────┘
```

#### Специализированные агенты

| Агент | Файл | Роль | Инструменты | Ограничения |
|-------|------|------|-------------|-------------|
| **Orchestrator** | [`orchestrator_agent.py`](codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py) | Анализ и маршрутизация запросов | read_file, list_files, search_in_code | Только анализ, без модификации |
| **Coder** | [`coder_agent.py`](codelab-ai-service/agent-runtime/app/agents/coder_agent.py) | Написание и модификация кода | Все инструменты | Нет ограничений |
| **Architect** | [`architect_agent.py`](codelab-ai-service/agent-runtime/app/agents/architect_agent.py) | Проектирование и планирование | read_file, write_file, list_files, search_in_code | Только `.md` файлы |
| **Debug** | [`debug_agent.py`](codelab-ai-service/agent-runtime/app/agents/debug_agent.py) | Отладка и диагностика | read_file, list_files, search_in_code, execute_command | Без write_file |
| **Ask** | [`ask_agent.py`](codelab-ai-service/agent-runtime/app/agents/ask_agent.py) | Ответы на вопросы | read_file, search_in_code, list_files | Только чтение |

#### Базовый класс агента ([`base_agent.py`](codelab-ai-service/agent-runtime/app/agents/base_agent.py))

```python
class BaseAgent(ABC):
    - agent_type: AgentType          # Тип агента
    - system_prompt: str             # Системный промпт
    - allowed_tools: List[str]       # Разрешенные инструменты
    - file_restrictions: List[str]   # Ограничения на файлы (regex)
    
    @abstractmethod
    async def process(session_id, message, context) -> AsyncGenerator
    
    def can_use_tool(tool_name: str) -> bool
    def can_edit_file(file_path: str) -> bool
```

### 3. Services Layer

#### [`multi_agent_orchestrator.py`](codelab-ai-service/agent-runtime/app/services/multi_agent_orchestrator.py)
**Координатор мультиагентной системы:**
- Маршрутизация сообщений к соответствующим агентам
- Управление переключением агентов
- Сохранение контекста между переключениями
- Обработка явных и автоматических переключений

**Поток работы:**
```
User Message → Orchestrator (анализ) → Specialist Agent → LLM → Tool Call → Gateway
                                                                              ↓
Tool Result ← Agent Runtime ← LLM Response ← Continue with current agent ←────┘
```

#### [`session_manager.py`](codelab-ai-service/agent-runtime/app/services/session_manager.py)
**Управление сессиями:**
- In-memory хранилище состояний сессий
- Thread-safe операции (RLock)
- История сообщений (user, assistant, system, tool)
- Поддержка tool_result с tool_call_id для OpenAI API

**Основные методы:**
```python
- get_or_create(session_id, system_prompt) -> SessionState
- append_message(session_id, role, content, name)
- append_tool_result(session_id, call_id, tool_name, result)
- get_history(session_id) -> List[dict]
```

#### [`llm_stream_service.py`](codelab-ai-service/agent-runtime/app/services/llm_stream_service.py)
**Стриминг от LLM:**
- Обработка ответов от LLM Proxy
- Парсинг tool_calls из ответа
- Определение необходимости подтверждения (HITL)
- Генерация StreamChunk для SSE

**HITL (Human-in-the-Loop):**
- Опасные команды требуют подтверждения
- Инструменты write_file, delete_file, move_file всегда требуют подтверждения
- Паттерны: `rm -rf`, `sudo`, `chmod`, `curl`, `wget`

#### [`agent_router.py`](codelab-ai-service/agent-runtime/app/services/agent_router.py)
**Реестр агентов:**
- Регистрация и получение агентов по типу
- Singleton паттерн
- Валидация существования агентов

#### [`agent_context.py`](codelab-ai-service/agent-runtime/app/services/agent_context.py)
**Контекст агента:**
- Отслеживание текущего активного агента
- История переключений агентов
- Метаданные сессии

#### [`tool_registry.py`](codelab-ai-service/agent-runtime/app/services/tool_registry.py)
**Реестр инструментов:**

**Локальные инструменты** (выполняются в agent-runtime):
- `echo` — эхо текста
- `calculator` — вычисление математических выражений

**IDE-side инструменты** (выполняются в Gateway/IDE):
- `read_file` — чтение файла
- `write_file` — запись в файл (требует подтверждения)
- `list_files` — список файлов
- `create_directory` — создание директории
- `execute_command` — выполнение команды (опасные требуют подтверждения)
- `search_in_code` — поиск в коде

**Спецификации инструментов:**
- OpenAI-совместимый формат
- JSON Schema для параметров
- Описания и примеры использования

#### [`llm_proxy_client.py`](codelab-ai-service/agent-runtime/app/services/llm_proxy_client.py)
**HTTP клиент для LLM Proxy:**
- Асинхронные запросы через httpx
- Поддержка стриминга и non-streaming режимов
- Обработка ошибок и таймаутов

#### [`tool_parser.py`](codelab-ai-service/agent-runtime/app/services/tool_parser.py)
**Парсинг tool calls:**
- Извлечение tool_calls из ответа LLM
- Поддержка различных форматов (OpenAI, Anthropic)
- Очистка контента от tool_calls

### 4. Models Layer

#### [`schemas.py`](codelab-ai-service/agent-runtime/app/models/schemas.py)
**Основные модели:**

```python
# Сообщения
Message(role, content, name)
SessionState(session_id, messages, pending_tool_calls, metadata)

# Стриминг
StreamChunk(type, content, token, is_final, call_id, tool_name, arguments)
AgentStreamRequest(session_id, message)

# Инструменты
ToolCall(id, tool_name, arguments, status)
ToolResult(call_id, result, error, execution_time_ms)

# Мультиагентная система
AgentSwitchRequest(type, agent_type, content, reason)
AgentInfo(type, name, description, allowed_tools, has_file_restrictions)
```

#### [`hitl_models.py`](codelab-ai-service/agent-runtime/app/models/hitl_models.py)
**Модели для Human-in-the-Loop:**
- Модели для запросов подтверждения
- Статусы выполнения инструментов

### 5. Core Layer

#### [`config.py`](codelab-ai-service/agent-runtime/app/core/config.py)
**Конфигурация через переменные окружения:**
```python
AppConfig:
    LLM_PROXY_URL: str          # URL LLM Proxy сервиса
    GATEWAY_URL: str            # URL Gateway сервиса
    LLM_MODEL: str              # Модель LLM
    INTERNAL_API_KEY: str       # Ключ для внутренней аутентификации
    LOG_LEVEL: str              # Уровень логирования
    VERSION: str                # Версия сервиса
```

#### [`dependencies.py`](codelab-ai-service/agent-runtime/app/core/dependencies.py)
**Провайдеры зависимостей:**
```python
get_config() -> AppConfig
get_logger() -> Logger
get_session_manager() -> SessionManager
get_llm_proxy_client() -> LLMProxyClient
get_tool_registry() -> Dict[str, Callable]
```

### 6. Middleware

#### [`internal_auth.py`](codelab-ai-service/agent-runtime/app/middleware/internal_auth.py)
**Внутренняя аутентификация:**
- Проверка заголовка `X-Internal-Auth`
- Исключения для `/health` и `/docs`
- Возврат 401 при неверном ключе

## 🔄 Поток обработки запроса

### 1. Обычное сообщение пользователя

```
1. POST /agent/message/stream
   ├─ message: {type: "user_message", content: "Create widget"}
   └─ session_id: "session_123"

2. SessionManager.get_or_create(session_id)
   └─ Создание или получение сессии

3. SessionManager.append_message(session_id, "user", content)
   └─ Добавление сообщения в историю

4. MultiAgentOrchestrator.process_message(session_id, message)
   ├─ AgentContext.get_or_create(session_id)
   │  └─ Текущий агент: Orchestrator (по умолчанию)
   │
   ├─ Orchestrator.process(session_id, message, context)
   │  ├─ LLM анализирует запрос
   │  └─ Возвращает: StreamChunk(type="switch_agent", target_agent="coder")
   │
   ├─ AgentContext.switch_agent(AgentType.CODER, reason)
   │  └─ Переключение на Coder агента
   │
   └─ Coder.process(session_id, message, context)
      ├─ LLMStreamService.stream_response(session_id, history)
      │  ├─ LLMProxyClient.chat_completion(model, messages, tools)
      │  ├─ Парсинг tool_calls
      │  └─ Возврат: StreamChunk(type="tool_call", tool_name="write_file", ...)
      │
      └─ SessionManager.append(assistant message with tool_call)

5. SSE Response → Gateway → IDE
   ├─ event: message, data: {type: "agent_switched", ...}
   └─ event: message, data: {type: "tool_call", call_id: "call_123", ...}
```

### 2. Результат выполнения инструмента

```
1. POST /agent/message/stream
   ├─ message: {type: "tool_result", call_id: "call_123", result: {...}}
   └─ session_id: "session_123"

2. SessionManager.append_tool_result(session_id, call_id, tool_name, result)
   └─ Добавление tool message с tool_call_id

3. MultiAgentOrchestrator.process_message(session_id, message="")
   └─ Продолжение с текущим агентом (Coder)

4. Coder.process(session_id, "", context)
   ├─ LLMStreamService.stream_response(session_id, history)
   │  └─ История теперь содержит: [user, assistant+tool_call, tool]
   │
   └─ LLM генерирует финальный ответ
      └─ StreamChunk(type="assistant_message", content="Created widget", is_final=true)

5. SSE Response → Gateway → IDE
   └─ event: message, data: {type: "assistant_message", content: "...", is_final: true}
```

### 3. Явное переключение агента

```
1. POST /agent/message/stream
   ├─ message: {type: "switch_agent", agent_type: "architect", content: "Design system"}
   └─ session_id: "session_123"

2. AgentContext.switch_agent(AgentType.ARCHITECT, "User requested")
   └─ Переключение на Architect агента

3. Architect.process(session_id, message, context)
   └─ Обработка с ограничениями (только .md файлы)

4. SSE Response
   ├─ event: message, data: {type: "agent_switched", to_agent: "architect"}
   └─ event: message, data: {type: "tool_call", tool_name: "write_file", path: "design.md"}
```

## 🔐 Безопасность

### 1. Внутренняя аутентификация
- Все endpoints защищены middleware
- Требуется заголовок `X-Internal-Auth`
- Конфигурируется через `AGENT_RUNTIME__INTERNAL_API_KEY`

### 2. Ограничения агентов
- **File restrictions**: regex паттерны для контроля доступа к файлам
- **Tool restrictions**: каждый агент имеет список разрешенных инструментов
- **Валидация**: проверка перед выполнением

### 3. Human-in-the-Loop (HITL)
- Опасные операции требуют подтверждения пользователя
- `requires_approval` флаг в tool_call
- Gateway отправляет запрос подтверждения в IDE

## 📊 Структура данных

### SessionState
```python
{
    "session_id": "session_123",
    "messages": [
        {"role": "system", "content": "You are..."},
        {"role": "user", "content": "Create widget"},
        {"role": "assistant", "content": null, "tool_calls": [...]},
        {"role": "tool", "content": "{...}", "tool_call_id": "call_123", "name": "write_file"}
    ],
    "last_activity": "2025-12-31T05:00:00"
}
```

**Примечание:** Для хранения метаданных используется `AgentContext.metadata`, а не `SessionState.metadata`.

### AgentContext
```python
{
    "session_id": "session_123",
    "current_agent": "coder",
    "agent_history": [
        {"agent": "orchestrator", "timestamp": "...", "reason": "Initial"},
        {"agent": "coder", "timestamp": "...", "reason": "Orchestrator routing"}
    ],
    "metadata": {}
}
```

## 🧪 Тестирование

### Структура тестов
```
tests/
├── conftest.py                      # Фикстуры и настройки
├── test_main.py                     # Тесты API endpoints
├── test_models.py                   # Тесты Pydantic моделей
├── test_session_manager.py          # Тесты управления сессиями
├── test_tool_parser.py              # Тесты парсинга инструментов
├── test_llm_stream_service.py       # Тесты стриминга LLM
├── test_internal_auth_middleware.py # Тесты аутентификации
└── test_multi_agent_system.py       # Тесты мультиагентной системы (26 тестов)
```

### Запуск тестов
```bash
cd codelab-ai-service/agent-runtime
uv run pytest tests/ -v
```

## 🚀 Развертывание

### Docker
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install uv && uv sync
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

### Docker Compose
```yaml
agent-runtime:
  build: ./agent-runtime
  ports:
    - "8001:8001"
  environment:
    - AGENT_RUNTIME__LLM_PROXY_URL=http://llm-proxy:8002
    - AGENT_RUNTIME__INTERNAL_API_KEY=${INTERNAL_API_KEY}
  depends_on:
    - llm-proxy
```

## 📈 Метрики и мониторинг

### Логирование
- Структурированное логирование через Python logging
- Уровни: DEBUG, INFO, WARNING, ERROR
- Логирование всех операций агентов
- Трассировка переключений агентов

### Потенциальные метрики
- Количество запросов к каждому агенту
- Время обработки по агентам
- Точность классификации Orchestrator
- Количество переключений агентов
- Использование инструментов
- Частота HITL подтверждений

## 🔧 Расширение системы

### Добавление нового агента

1. **Создать класс агента:**
```python
# app/agents/new_agent.py
from app.agents.base_agent import BaseAgent, AgentType

class NewAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_type=AgentType.NEW,
            system_prompt=NEW_AGENT_PROMPT,
            allowed_tools=["read_file", "search_in_code"],
            file_restrictions=[r".*\.txt$"]  # Только .txt файлы
        )
    
    async def process(self, session_id, message, context):
        # Реализация логики агента
        pass
```

2. **Создать промпт:**
```python
# app/agents/prompts/new_agent.py
NEW_AGENT_PROMPT = """
You are a specialized agent for...
"""
```

3. **Зарегистрировать агента:**
```python
# app/agents/__init__.py
from app.agents.new_agent import NewAgent
from app.services.agent_router import agent_router

agent_router.register_agent(NewAgent())
```

### Добавление нового инструмента

1. **Добавить спецификацию:**
```python
# app/services/tool_registry.py
TOOLS_SPEC.append({
    "type": "function",
    "function": {
        "name": "new_tool",
        "description": "Description of the tool",
        "parameters": {
            "type": "object",
            "properties": {
                "param1": {"type": "string", "description": "..."}
            },
            "required": ["param1"]
        }
    }
})
```

2. **Для локального инструмента:**
```python
def new_tool_impl(param1: str) -> str:
    # Реализация
    return result

LOCAL_TOOLS["new_tool"] = new_tool_impl
```

## 📚 Зависимости

```toml
[project.dependencies]
fastapi = "0.104.1"           # Web framework
uvicorn = "0.24.0"            # ASGI server
python-dotenv = "1.0.0"       # Env variables
httpx = "0.25.1"              # HTTP client
pydantic = "2.5.1"            # Data validation
sse-starlette = "1.6.5"       # SSE support
langchain = ">=0.2.5"         # LLM framework
smolagents = ">=1.23.0"       # Agent framework
```

## 🎯 Ключевые особенности

1. **Мультиагентная система** — 5 специализированных агентов с четкими ролями
2. **LLM-based маршрутизация** — Orchestrator использует LLM для точной классификации
3. **Строгие ограничения** — контроль доступа к инструментам и файлам
4. **SSE стриминг** — реал-тайм передача ответов
5. **HITL поддержка** — подтверждение опасных операций
6. **Thread-safe** — безопасная работа с сессиями
7. **Расширяемость** — легко добавлять новых агентов и инструменты
8. **Типизация** — полная типизация через Pydantic и type hints
9. **Тестируемость** — DI и моки для легкого тестирования
10. **Документация** — OpenAPI/Swagger автогенерация

## 🔗 Интеграция с другими сервисами

### Gateway
- Получает SSE события от Agent Runtime
- Пересылает их через WebSocket в IDE
- Отправляет tool_result обратно в Agent Runtime

### LLM Proxy
- Предоставляет унифицированный API для различных LLM провайдеров
- Обрабатывает запросы от Agent Runtime
- Возвращает ответы с tool_calls

### IDE (Flutter)
- Отображает сообщения агентов
- Выполняет инструменты (file operations, commands)
- Запрашивает подтверждения для HITL
- Отправляет результаты обратно через Gateway

## 📝 Выводы

Agent Runtime Service — это хорошо спроектированный микросервис с:
- ✅ Четкой архитектурой и разделением ответственности
- ✅ Мультиагентной системой с специализацией
- ✅ Строгой типизацией и валидацией
- ✅ Безопасностью и контролем доступа
- ✅ Расширяемостью и тестируемостью
- ✅ Полной документацией и примерами

Система готова к production использованию и дальнейшему развитию.
