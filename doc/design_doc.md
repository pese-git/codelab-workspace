# Design-Doc: CodeLab AI-Powered IDE

*основан на шаблоне команды [Reliable ML](https://github.com/IrinaGoloshchapova/ml_system_design_doc_ru/blob/main/ML_System_Design_Doc_Template.md)*

---

## 1. Контекст проекта

### 1.1 Бизнес-задача

CodeLab решает проблему низкой производительности разработчиков при выполнении рутинных задач программирования. Современные разработчики тратят значительное время на:

- **Написание шаблонного кода** - повторяющиеся паттерны, boilerplate код
- **Поиск информации** - документация, примеры использования API, решение типовых проблем
- **Рефакторинг** - улучшение структуры кода, оптимизация производительности
- **Отладка** - поиск и исправление ошибок, анализ логов
- **Архитектурное проектирование** - выбор паттернов, структурирование проекта

**Цель проекта**: создать AI-powered IDE, которая автоматизирует рутинные задачи разработки и предоставляет интеллектуальную помощь через специализированную мульти-агентную систему, повышая производительность разработчиков на 30-50%.

**Ключевые преимущества**:
- Контекстно-зависимая помощь с учетом всей кодовой базы проекта
- Специализированные AI-агенты для разных типов задач
- Human-in-the-Loop (HITL) для контроля опасных операций
- Поддержка множества LLM провайдеров (коммерческих и локальных)

### 1.2 Целевая аудитория и пользователи

**Основные сегменты пользователей**:

1. **Профессиональные разработчики** (primary)
   - Fullstack, Backend, Frontend разработчики
   - Потребность: ускорение разработки, автоматизация рутины
   - Сценарии: рефакторинг legacy кода, написание тестов, документирование

2. **Студенты и начинающие разработчики** (secondary)
   - Изучающие программирование
   - Потребность: обучение, понимание best practices
   - Сценарии: объяснение кода, помощь в решении задач, изучение паттернов

3. **Технические лидеры и архитекторы** (tertiary)
   - Team leads, Solution architects
   - Потребность: проектирование архитектуры, code review
   - Сценарии: архитектурные решения, анализ качества кода, планирование рефакторинга

**Типовые сценарии использования**:

| Сценарий | Агент | Описание |
|----------|-------|----------|
| Написание нового функционала | Coder | Генерация кода на основе требований |
| Рефакторинг существующего кода | Coder | Улучшение структуры, оптимизация |
| Отладка и исправление ошибок | Debug | Анализ ошибок, предложение исправлений |
| Проектирование архитектуры | Architect | Выбор паттернов, структурирование проекта |
| Ответы на вопросы | Ask | Объяснение кода, документации, концепций |
| Комплексные задачи | Orchestrator | Координация работы нескольких агентов |

### 1.3 Ограничения и допущения

**Функциональные ограничения**:
- Система **не выполняет** автоматическую компиляцию и запуск кода (только генерация)
- Система **не заменяет** полноценную систему контроля версий (Git)
- Система **не предоставляет** встроенный debugger (только анализ и рекомендации)
- Система **не поддерживает** collaborative editing в реальном времени

**Технические допущения**:
- Пользователь имеет доступ к интернету для работы с облачными LLM
- Файловая система проекта доступна для чтения/записи
- Проект имеет стандартную структуру (не обфусцированный код)
- Размер файлов проекта не превышает разумных пределов (< 10MB на файл)

**Допущения о данных**:
- Код написан на популярных языках программирования
- Проект содержит читаемый исходный код (не бинарные файлы)
- Структура проекта следует общепринятым конвенциям

**Инфраструктурные ограничения**:
- Требуется Docker для развертывания backend
- PostgreSQL и Redis для персистентности данных
- Минимум 4GB RAM для работы локальных LLM (Ollama)

---

## 2. Архитектура решения

### 2.1 Общая схема

CodeLab построен на микросервисной архитектуре с четким разделением ответственности:

```
┌─────────────────────────────────────────────────────────────────┐
│                     CodeLab IDE (Flutter/Dart)                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────────┐ │
│  │ Explorer │  │  Editor  │  │ Terminal │  │ AI Assistant    │ │
│  │          │  │          │  │          │  │ Panel           │ │
│  └──────────┘  └──────────┘  └──────────┘  └─────────────────┘ │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              BLoC State Management                        │  │
│  │  • SessionBloc  • ToolApprovalBloc  • FileSystemBloc     │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │ WebSocket (wss://)
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Nginx (Reverse Proxy)                   │
│                    • SSL Termination                            │
│                    • Load Balancing                             │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Auth Service (FastAPI)                     │
│                    • OAuth2 + JWT                               │
│                    • User Management                            │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Gateway (FastAPI)                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  • WebSocket Handler                                      │  │
│  │  • Session Management                                     │  │
│  │  • Token Buffer Manager (streaming optimization)         │  │
│  │  • JWT Validation                                         │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP/WebSocket
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Agent Runtime (FastAPI)                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │           Multi-Agent Orchestrator                        │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐         │  │
│  │  │Orchestrator│  │   Coder    │  │ Architect  │         │  │
│  │  │   Agent    │  │   Agent    │  │   Agent    │         │  │
│  │  └────────────┘  └────────────┘  └────────────┘         │  │
│  │  ┌────────────┐  ┌────────────┐                         │  │
│  │  │   Debug    │  │    Ask     │                         │  │
│  │  │   Agent    │  │   Agent    │                         │  │
│  │  └────────────┘  └────────────┘                         │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  • HITL Manager (Human-in-the-Loop)                      │  │
│  │  • Tool Registry (read_file, write_file, execute, etc.)  │  │
│  │  • Session Manager (async, PostgreSQL persistence)       │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      LLM Proxy (FastAPI)                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              LiteLLM Integration                          │  │
│  │  • Unified API для множества провайдеров                 │  │
│  │  • Rate limiting, retry logic                            │  │
│  │  • Cost tracking                                          │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│   OpenAI    │  │  Anthropic  │  │   Ollama    │
│   GPT-4     │  │  Claude 3.x │  │  (Local)    │
└─────────────┘  └─────────────┘  └─────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    Data Layer                                   │
│  ┌──────────────────────┐  ┌──────────────────────┐            │
│  │   PostgreSQL         │  │      Redis           │            │
│  │  • Sessions          │  │  • Cache             │            │
│  │  • HITL Requests     │  │  • Session State     │            │
│  │  • User Data         │  │  • Rate Limiting     │            │
│  └──────────────────────┘  └──────────────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

**Ключевые компоненты**:

1. **Frontend (codelab_ide)**: Flutter-приложение с BLoC паттерном
2. **Gateway**: WebSocket сервер, управление сессиями, буферизация токенов
3. **Agent Runtime**: Мульти-агентная система, HITL, инструменты работы с кодом
4. **LLM Proxy**: Унифицированный доступ к LLM провайдерам через LiteLLM
5. **Auth Service**: OAuth2 + JWT аутентификация
6. **Data Layer**: PostgreSQL (персистентность) + Redis (кеш, состояние)

### 2.2 Хранилище знаний / документооборот

**Источники знаний**:

1. **Файловая система проекта**
   - Исходный код (все языки программирования)
   - Конфигурационные файлы (JSON, YAML, TOML, etc.)
   - Документация (Markdown, README, docs/)
   - Зависимости (package.json, requirements.txt, pubspec.yaml)

2. **Контекст сессии**
   - История диалога (сохраняется в PostgreSQL)
   - Открытые файлы и их содержимое
   - Текущее состояние workspace
   - Предыдущие действия агентов

3. **Метаданные проекта**
   - Структура директорий
   - Список файлов и их типы
   - Git история (планируется)

**Инструменты доступа к знаниям**:

```python
# Tool Registry в Agent Runtime
AVAILABLE_TOOLS = {
    "read_file": {
        "description": "Чтение содержимого файла",
        "parameters": {"path": "string"},
        "hitl_required": False
    },
    "write_file": {
        "description": "Запись/изменение файла",
        "parameters": {"path": "string", "content": "string"},
        "hitl_required": True  # Требует подтверждения
    },
    "list_files": {
        "description": "Список файлов в директории",
        "parameters": {"path": "string", "recursive": "boolean"},
        "hitl_required": False
    },
    "search_files": {
        "description": "Поиск по содержимому файлов (regex)",
        "parameters": {"pattern": "string", "path": "string"},
        "hitl_required": False
    },
    "execute_command": {
        "description": "Выполнение shell команды",
        "parameters": {"command": "string"},
        "hitl_required": True  # Опасная операция
    }
}
```

**Стратегия индексирования** (текущая реализация):
- Файлы читаются по требованию (on-demand)
- Кеширование содержимого в Redis (TTL: 5 минут)
- Инкрементальное обновление при изменениях

**Планируется**:
- Векторная база данных (Qdrant/Chroma) для семантического поиска
- Автоматическая индексация при открытии проекта
- Embeddings для кода и документации

### 2.3 Retrieval + Generation

**Retrieval (извлечение контекста)**:

1. **Явный retrieval** - агент запрашивает конкретные файлы:
   ```
   User: "Добавь валидацию в функцию login"
   Agent: [использует read_file("auth/login.py")]
   Agent: [анализирует код, генерирует решение]
   ```

2. **Контекстный retrieval** - использование истории сессии:
   ```
   User: "Теперь добавь тесты для этой функции"
   Agent: [использует контекст предыдущего сообщения]
   Agent: [знает, что речь о login.py]
   ```

3. **Проактивный retrieval** - агент самостоятельно ищет связанные файлы:
   ```
   Agent: [читает login.py]
   Agent: [видит import from models.user]
   Agent: [автоматически читает models/user.py для полного контекста]
   ```

**Generation (генерация ответов)**:

Каждый агент имеет специализированный system prompt:

```python
# Пример: Coder Agent
CODER_SYSTEM_PROMPT = """
Ты - специализированный агент для написания и модификации кода.

Твои обязанности:
- Написание нового кода на основе требований
- Рефакторинг существующего кода
- Оптимизация производительности
- Следование best practices и code style проекта

Правила:
1. Всегда читай существующий код перед изменениями
2. Сохраняй стиль кодирования проекта
3. Добавляй комментарии для сложной логики
4. Используй write_file только после анализа
5. Предлагай несколько вариантов решения при необходимости

Доступные инструменты: read_file, write_file, list_files, search_files
"""
```

**Pipeline генерации**:

```
1. Получение запроса пользователя
   ↓
2. Определение типа задачи → выбор агента (Orchestrator)
   ↓
3. Retrieval: сбор необходимого контекста
   ↓
4. Формирование промпта: system + context + user query
   ↓
5. LLM генерация (streaming)
   ↓
6. Парсинг tool calls (если есть)
   ↓
7. HITL проверка (для опасных операций)
   ↓
8. Выполнение инструментов
   ↓
9. Повторная генерация с результатами (если нужно)
   ↓
10. Отправка финального ответа пользователю
```

**Оптимизации**:
- Token Buffer Manager в Gateway для плавного streaming
- Кеширование промптов в Redis
- Параллельное выполнение независимых tool calls
- Fallback на более простые модели при ошибках

### 2.4 Интеграции и интерфейсы

**Внешние интеграции**:

1. **LLM Провайдеры** (через LiteLLM):
   ```yaml
   # litellm_config.yaml
   model_list:
     - model_name: gpt-4
       litellm_params:
         model: gpt-4-turbo-preview
         api_key: os.environ/OPENAI_API_KEY
     
     - model_name: claude-3-opus
       litellm_params:
         model: claude-3-opus-20240229
         api_key: os.environ/ANTHROPIC_API_KEY
     
     - model_name: ollama/codellama
       litellm_params:
         model: ollama/codellama
         api_base: http://ollama:11434
   ```

2. **OAuth2 провайдеры** (планируется):
   - GitHub OAuth
   - Google OAuth
   - Microsoft Azure AD

**Внутренние интерфейсы**:

1. **WebSocket Protocol** (Gateway ↔ IDE):
   ```typescript
   // Клиент → Сервер
   interface ClientMessage {
     type: "chat" | "tool_approval" | "cancel";
     session_id: string;
     data: {
       message?: string;
       approval_id?: string;
       approved?: boolean;
     };
   }

   // Сервер → Клиент
   interface ServerMessage {
     type: "token" | "tool_call" | "tool_result" | "error" | "done";
     session_id: string;
     data: any;
   }
   ```

2. **Internal Service Communication** (HTTP):
   ```python
   # Gateway → Agent Runtime
   POST /api/v1/agent/chat
   Headers:
     X-Internal-Secret: <shared_secret>
     Authorization: Bearer <jwt_token>
   Body:
     {
       "session_id": "uuid",
       "message": "user query",
       "context": {...}
     }

   # Agent Runtime → LLM Proxy
   POST /api/v1/llm/chat/completions
   Headers:
     X-Internal-Secret: <shared_secret>
   Body:
     {
       "model": "gpt-4",
       "messages": [...],
       "stream": true,
       "tools": [...]
     }
   ```

3. **Database Interfaces**:
   ```python
   # PostgreSQL (SQLAlchemy async)
   class SessionRepository:
       async def create_session(user_id: str) -> Session
       async def get_session(session_id: str) -> Session
       async def save_message(session_id: str, message: Message)
   
   class HITLRepository:
       async def create_request(session_id: str, tool_call: dict) -> HITLRequest
       async def update_status(request_id: str, approved: bool)
   
   # Redis (aioredis)
   class CacheService:
       async def get_session_state(session_id: str) -> dict
       async def set_session_state(session_id: str, state: dict, ttl: int)
   ```

**API Спецификации**:
- OpenAPI 3.0 для всех REST endpoints
- AsyncAPI для WebSocket протокола
- Swagger UI доступен на `/docs` каждого сервиса

### 2.5 Инфраструктура и развертывание

**Контейнеризация** (Docker Compose):

```yaml
# docker-compose.yml (упрощенная версия)
services:
  nginx:
    image: nginx:alpine
    ports: ["80:80", "443:443"]
    depends_on: [gateway, auth-service]
  
  auth-service:
    build: ./auth-service
    environment:
      DATABASE_URL: postgresql://...
      JWT_SECRET: ${JWT_SECRET}
  
  gateway:
    build: ./gateway
    environment:
      AGENT_RUNTIME_URL: http://agent-runtime:8000
      REDIS_URL: redis://redis:6379
  
  agent-runtime:
    build: ./agent-runtime
    environment:
      LLM_PROXY_URL: http://llm-proxy:8000
      DATABASE_URL: postgresql://...
      REDIS_URL: redis://redis:6379
  
  llm-proxy:
    build: ./llm-proxy
    environment:
      LITELLM_CONFIG: /app/litellm_config.yaml
  
  ollama:
    image: ollama/ollama
    volumes: ["ollama-data:/root/.ollama"]
  
  postgres:
    image: postgres:15-alpine
    volumes: ["postgres-data:/var/lib/postgresql/data"]
  
  redis:
    image: redis:7-alpine
    volumes: ["redis-data:/data"]
```

**Масштабирование**:

1. **Горизонтальное масштабирование**:
   - Gateway: несколько реплик за Nginx (sticky sessions через Redis)
   - Agent Runtime: stateless, легко масштабируется
   - LLM Proxy: кеширование в Redis, rate limiting

2. **Вертикальное масштабирование**:
   - Ollama: требует GPU для производительности
   - PostgreSQL: увеличение connection pool
   - Redis: увеличение памяти для кеша

**Мониторинг и логирование**:

```python
# Структурированное логирование
import structlog

logger = structlog.get_logger()
logger.info(
    "agent_execution",
    agent="coder",
    session_id=session_id,
    tool="write_file",
    duration_ms=duration
)
```

**Планируется**:
- Prometheus + Grafana для метрик
- ELK Stack для централизованного логирования
- Jaeger для distributed tracing
- Health checks и auto-restart

**Требования к ресурсам**:

| Компонент | CPU | RAM | Storage |
|-----------|-----|-----|---------|
| Gateway | 1 core | 512MB | - |
| Agent Runtime | 2 cores | 1GB | - |
| LLM Proxy | 1 core | 512MB | - |
| Ollama (CPU) | 4 cores | 8GB | 10GB |
| Ollama (GPU) | - | 16GB VRAM | 10GB |
| PostgreSQL | 2 cores | 2GB | 20GB |
| Redis | 1 core | 1GB | 5GB |

---

## 3. Данные и качество знаний

### 3.1 Сбор и предобработка данных

**Источники данных**:

1. **Файлы проекта пользователя**:
   - Исходный код (Python, JavaScript, Dart, Java, C++, etc.)
   - Конфигурационные файлы (JSON, YAML, TOML, XML)
   - Документация (Markdown, RST, TXT)
   - Зависимости (package.json, requirements.txt, pubspec.yaml, pom.xml)

2. **Метаданные проекта**:
   - Структура директорий
   - Размеры файлов
   - Даты модификации
   - Git информация (ветки, коммиты) - планируется

**Предобработка**:

```python
# Фильтрация файлов
EXCLUDED_PATTERNS = [
    "node_modules/", ".git/", "build/", "dist/",
    "*.pyc", "*.class", "*.o", "*.so",
    ".DS_Store", "Thumbs.db"
]

# Ограничения размера
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_CONTEXT_TOKENS = 100_000  # для GPT-4 Turbo

# Нормализация кода
def preprocess_code(content: str, language: str) -> str:
    """
    - Удаление лишних пробелов
    - Нормализация переносов строк
    - Удаление комментариев (опционально)
    """
    pass
```

**Обработка больших файлов**:
- Chunking: разбиение на логические блоки (функции, классы)
- Summarization: краткое описание содержимого
- Selective reading: чтение только релевантных частей

### 3.2 Векторизация и индексирование

**Текущее состояние**: 
- Простой поиск по имени файла и regex по содержимому
- Кеширование прочитанных файлов в Redis

**Планируется** (Phase 2):

1. **Векторная база данных**:
   ```python
   # Интеграция с Qdrant
   from qdrant_client import QdrantClient
   
   class VectorStore:
       def __init__(self):
           self.client = QdrantClient(host="qdrant", port=6333)
       
       async def index_codebase(self, project_path: str):
           """Индексация всей кодовой базы"""
           for file in get_code_files(project_path):
               chunks = chunk_code(file.content, file.language)
               embeddings = await get_embeddings(chunks)
               await self.client.upsert(
                   collection_name=f"project_{project_id}",
                   points=[
                       {
                           "id": chunk_id,
                           "vector": embedding,
                           "payload": {
                               "file_path": file.path,
                               "chunk_text": chunk.text,
                               "language": file.language
                           }
                       }
                       for chunk, embedding in zip(chunks, embeddings)
                   ]
               )
       
       async def semantic_search(self, query: str, top_k: int = 5):
           """Семантический поиск по кодовой базе"""
           query_embedding = await get_embeddings([query])
           results = await self.client.search(
               collection_name=f"project_{project_id}",
               query_vector=query_embedding[0],
               limit=top_k
           )
           return results
   ```

2. **Embedding модели**:
   - OpenAI text-embedding-3-small (1536 dim)
   - Sentence-Transformers (локально, 384-768 dim)
   - CodeBERT для специализированных code embeddings

3. **Стратегия индексирования**:
   - Полная индексация при открытии проекта (background task)
   - Инкрементальное обновление при изменении файлов
   - Переиндексация раз в 24 часа

4. **Chunking стратегии**:
   ```python
   def chunk_code_by_ast(code: str, language: str) -> List[Chunk]:
       """
       Разбиение кода на логические блоки через AST:
       - Функции/методы
       - Классы
       - Модули
       """
       pass
   
   def chunk_with_overlap(text: str, chunk_size: int = 512, overlap: int = 50):
       """
       Разбиение с перекрытием для сохранения контекста
       """
       pass
   ```

### 3.3 Метрики качества знаний

**Метрики покрытия**:

1. **Code Coverage**:
   - % проиндексированных файлов от общего числа
   - % строк кода в векторной БД
   - Распределение по языкам программирования

2. **Context Relevance**:
   ```python
   def calculate_relevance_score(retrieved_chunks, user_query):
       """
       Оценка релевантности извлеченного контекста:
       - Cosine similarity с запросом
       - Наличие ключевых слов
       - Свежесть данных (timestamp)
       """
       pass
   ```

3. **Retrieval Metrics**:
   - Precision@K: доля релевантных результатов в топ-K
   - Recall@K: доля найденных релевантных документов
   - MRR (Mean Reciprocal Rank): позиция первого релевантного результата

**Метрики актуальности**:

```python
# Отслеживание изменений
class FreshnessTracker:
    async def check_staleness(self, file_path: str) -> bool:
        """Проверка, устарел ли индекс файла"""
        indexed_mtime = await get_indexed_mtime(file_path)
        current_mtime = os.path.getmtime(file_path)
        return current_mtime > indexed_mtime
    
    async def get_stale_files_percentage(self) -> float:
        """% устаревших файлов в индексе"""
        pass
```

**Метрики консистентности**:

- Проверка целостности ссылок между файлами (imports, includes)
- Валидация синтаксиса проиндексированного кода
- Обнаружение дубликатов и конфликтов

**Мониторинг качества** (планируется):

```python
# Логирование метрик
await metrics_service.log({
    "retrieval_latency_ms": 45,
    "chunks_retrieved": 5,
    "avg_relevance_score": 0.87,
    "cache_hit_rate": 0.65,
    "index_freshness": 0.95
})
```

---

## 4. Модель и генерация

### 4.1 Выбор LLM и промптинг

**Поддерживаемые модели**:

| Провайдер | Модель | Контекст | Использование |
|-----------|--------|----------|---------------|
| OpenAI | GPT-4 Turbo | 128K | Production, сложные задачи |
| OpenAI | GPT-3.5 Turbo | 16K | Быстрые ответы, простые задачи |
| Anthropic | Claude 3 Opus | 200K | Длинный контекст, анализ |
| Anthropic | Claude 3 Sonnet | 200K | Баланс скорость/качество |
| Anthropic | Claude 3 Haiku | 200K | Быстрые ответы |
| Ollama | CodeLlama 34B | 16K | Локальная разработка |
| Ollama | Mistral 7B | 8K | Легковесные задачи |

**Выбор модели по задаче**:

```python
MODEL_SELECTION_STRATEGY = {
    "orchestrator": "gpt-4-turbo",      # Требует reasoning
    "coder": "claude-3-opus",           # Лучше для кода
    "architect": "gpt-4-turbo",         # Архитектурные решения
    "debug": "claude-3-sonnet",         # Баланс скорость/качество
    "ask": "gpt-3.5-turbo",             # Быстрые ответы
}

# Fallback стратегия
FALLBACK_CHAIN = [
    "gpt-4-turbo",
    "claude-3-opus",
    "gpt-3.5-turbo",
    "ollama/codellama"  # Локальный fallback
]
```

**Специализированные промпты**:

```python
# Orchestrator Agent
ORCHESTRATOR_PROMPT = """
Ты - Orchestrator Agent, координирующий работу специализированных агентов.

Доступные агенты:
- Coder: написание и модификация кода
- Architect: проектирование архитектуры, выбор паттернов
- Debug: отладка, поиск ошибок, анализ логов
- Ask: ответы на вопросы, объяснение кода

Твоя задача:
1. Проанализировать запрос пользователя
2. Определить, какой агент (или агенты) нужны
3. Разбить сложную задачу на подзадачи
4. Координировать выполнение
5. Агрегировать результаты

Правила:
- Для простых задач делегируй напрямую одному агенту
- Для сложных задач создавай план с несколькими шагами
- Всегда объясняй свой выбор агента
- Если задача неясна, задавай уточняющие вопросы
"""

# Coder Agent
CODER_PROMPT = """
Ты - Coder Agent, специализирующийся на написании и модификации кода.

Твои принципы:
1. Clean Code: читаемость, простота, понятность
2. DRY (Don't Repeat Yourself): избегай дублирования
3. SOLID: следуй принципам объектно-ориентированного дизайна
4. Best Practices: используй идиомы и паттерны языка

Workflow:
1. Прочитай существующий код (read_file)
2. Проанализируй структуру и стиль
3. Предложи решение с объяснением
4. Запроси подтверждение для изменений (write_file)
5. Проверь результат

Доступные инструменты:
- read_file: чтение файла
- write_file: запись/изменение файла (требует HITL)
- list_files: список файлов
- search_files: поиск по содержимому

Всегда:
- Сохраняй стиль кодирования проекта
- Добавляй комментарии для сложной логики
- Предлагай тесты для нового кода
- Учитывай производительность и безопасность
"""

# Debug Agent
DEBUG_PROMPT = """
Ты - Debug Agent, специалист по отладке и поиску ошибок.

Твой подход:
1. Systematic Analysis: методичный анализ проблемы
2. Root Cause: поиск первопричины, а не симптомов
3. Hypothesis Testing: формулирование и проверка гипотез
4. Minimal Reproduction: создание минимального примера

Workflow:
1. Собери информацию: код, ошибки, логи
2. Проанализируй stack trace
3. Сформулируй гипотезы о причине
4. Проверь гипотезы через чтение кода
5. Предложи исправление с объяснением

Инструменты:
- read_file: чтение кода
- search_files: поиск паттернов ошибок
- execute_command: запуск тестов (с осторожностью)

Помни:
- Ошибка может быть не там, где проявляется
- Проверяй граничные случаи
- Учитывай race conditions и async проблемы
- Предлагай способы предотвращения в будущем
"""
```

**Prompt Engineering техники**:

1. **Few-shot learning**:
   ```python
   EXAMPLES = """
   Пример 1:
   User: "Добавь валидацию email в форму регистрации"
   Agent: [читает forms/register.py]
   Agent: [предлагает regex валидацию + библиотеку email-validator]
   
   Пример 2:
   User: "Оптимизируй этот SQL запрос"
   Agent: [анализирует запрос]
   Agent: [предлагает добавить индексы + переписать JOIN]
   """
   ```

2. **Chain-of-Thought**:
   ```
   "Давай решим эту задачу пошагово:
   1. Сначала проанализируем текущую структуру...
   2. Затем определим, что нужно изменить...
   3. Наконец, реализуем решение..."
   ```

3. **Self-Consistency**:
   - Генерация нескольких вариантов решения
   - Выбор наиболее консистентного

### 4.2 Контроль качества ответов

**HITL (Human-in-the-Loop) система**:

```python
# Политика HITL
HITL_POLICY = {
    "write_file": {
        "required": True,
        "reason": "Изменение файлов требует подтверждения"
    },
    "execute_command": {
        "required": True,
        "reason": "Выполнение команд может быть опасным"
    },
    "delete_file": {
        "required": True,
        "reason": "Удаление необратимо"
    },
    "read_file": {
        "required": False,
        "reason": "Чтение безопасно"
    }
}

# Workflow HITL
class HITLManager:
    async def request_approval(
        self,
        session_id: str,
        tool_name: str,
        parameters: dict
    ) -> HITLRequest:
        """
        1. Создать запрос в БД
        2. Отправить в UI через WebSocket
        3. Ждать ответа пользователя
        4. Обновить статус в БД
        """
        request = await self.db.create_hitl_request(
            session_id=session_id,
            tool_name=tool_name,
            parameters=parameters,
            status="pending"
        )
        
        await self.ws.send_tool_approval_request(
            session_id=session_id,
            request_id=request.id,
            tool_name=tool_name,
            parameters=parameters
        )
        
        # Ждем ответа (с timeout)
        approved = await self.wait_for_approval(
            request.id,
            timeout=300  # 5 минут
        )
        
        return approved
```

**Валидация параметров**:

```python
class ToolValidator:
    def validate_write_file(self, params: dict) -> ValidationResult:
        """
        Проверки:
        - Путь не выходит за пределы проекта
        - Файл не является системным
        - Размер контента разумный (< 1MB)
        - Валидный синтаксис (если код)
        """
        path = params.get("path")
        content = params.get("content")
        
        if ".." in path or path.startswith("/"):
            return ValidationResult(
                valid=False,
                error="Недопустимый путь"
            )
        
        if len(content) > 1_000_000:
            return ValidationResult(
                valid=False,
                error="Контент слишком большой"
            )
        
        # Проверка синтаксиса
        if path.endswith(".py"):
            try:
                ast.parse(content)
            except SyntaxError as e:
                return ValidationResult(
                    valid=False,
                    error=f"Синтаксическая ошибка: {e}"
                )
        
        return ValidationResult(valid=True)
```

**Fallback стратегии**:

```python
class LLMFallbackHandler:
    async def call_with_fallback(
        self,
        messages: List[dict],
        tools: List[dict]
    ) -> str:
        """
        Попытка вызова с fallback на другие модели
        """
        for model in FALLBACK_CHAIN:
            try:
                response = await self.llm_client.chat(
                    model=model,
                    messages=messages,
                    tools=tools,
                    timeout=30
                )
                return response
            except Exception as e:
                logger.warning(
                    "llm_call_failed",
                    model=model,
                    error=str(e)
                )
                continue
        
        # Все модели недоступны
        raise LLMUnavailableError("Все LLM провайдеры недоступны")
```

**Метрики качества**:

```python
# Отслеживание качества ответов
class QualityMetrics:
    async def track_response(
        self,
        session_id: str,
        response: str,
        user_feedback: Optional[str] = None
    ):
        """
        Метрики:
        - Время генерации
        - Количество токенов
        - Использованные инструменты
        - Feedback пользователя (thumbs up/down)
        - Процент одобренных HITL запросов
        """
        await self.metrics_db.insert({
            "session_id": session_id,
            "response_length": len(response),
            "generation_time_ms": ...,
            "tools_used": [...],
            "user_feedback": user_feedback,
            "timestamp": datetime.utcnow()
        })
```

### 4.3 Обучение/дообучение

**Текущее состояние**: 
- Используются pre-trained модели без дообучения
- Промпт-инжиниринг для адаптации под задачи

**Планируется** (Phase 3):

1. **Сбор данных для fine-tuning**:
   ```python
   class TrainingDataCollector:
       async def collect_interaction(
           self,
           user_query: str,
           agent_response: str,
           tools_used: List[dict],
           user_approved: bool,
           user_feedback: Optional[str]
       ):
           """
           Сохранение успешных взаимодействий для обучения:
           - Запрос пользователя
           - Ответ агента
           - Использованные инструменты
           - Одобрение пользователя
           - Feedback
           """
           if user_approved and user_feedback in ["positive", None]:
               await self.training_db.insert({
                   "query": user_query,
                   "response": agent_response,
                   "tools": tools_used,
                   "quality_score": self.calculate_quality(...)
               })
   ```

2. **Fine-tuning стратегия**:
   - **LoRA (Low-Rank Adaptation)** для эффективного дообучения
   - Специализация моделей по агентам (Coder, Debug, etc.)
   - Периодическое переобучение (раз в месяц)

3. **Reinforcement Learning from Human Feedback (RLHF)**:
   ```python
   # Reward model на основе пользовательского feedback
   class RewardModel:
       def calculate_reward(
           self,
           response: str,
           user_approved: bool,
           execution_success: bool,
           code_quality_score: float
       ) -> float:
           """
           Reward = w1 * approval + w2 * success + w3 * quality
           """
           reward = (
               0.5 * float(user_approved) +
               0.3 * float(execution_success) +
               0.2 * code_quality_score
           )
           return reward
   ```

4. **Continuous Learning**:
   - A/B тестирование новых версий моделей
   - Мониторинг метрик качества
   - Автоматический rollback при деградации

---

## 5. UX / пользовательский опыт

### 5.1 Сценарии взаимодействия

**Сценарий 1: Написание нового функционала**

```
User: "Создай REST API endpoint для получения списка пользователей"

Orchestrator: [анализирует задачу]
Orchestrator: "Это задача для Coder Agent. Передаю..."

Coder: [читает структуру проекта]
Coder: "Я вижу, что проект использует FastAPI. Создам endpoint в api/users.py"

Coder: [генерирует код]
Coder: "Предлагаю следующую реализацию:
```python
@router.get("/users", response_model=List[UserResponse])
async def get_users(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100
):
    users = await db.query(User).offset(skip).limit(limit).all()
    return users
```

Также нужно:
1. Добавить модель UserResponse в schemas.py
2. Зарегистрировать router в main.py

Создать эти файлы?"

User: [одобряет через UI]

Coder: [создает файлы]
Coder: "✅ Endpoint создан. Также добавил базовые тесты в tests/test_users.py"
```

**Сценарий 2: Отладка ошибки**

```
User: "У меня ошибка: KeyError: 'user_id' в функции process_order"

Debug: [читает код функции]
Debug: "Анализирую функцию process_order()..."

Debug: [находит проблему]
Debug: "Нашел проблему! В строке 45 вы обращаетесь к request['user_id'], 
но это поле опциональное и может отсутствовать.

Рекомендую:
1. Использовать request.get('user_id') вместо request['user_id']
2. Добавить валидацию на входе функции
3. Добавить тест для случая без user_id

Вот исправленный код:
```python
def process_order(request: dict):
    user_id = request.get('user_id')
    if not user_id:
        raise ValueError("user_id is required")
    ...
```

Применить исправление?"

User: [одобряет]

Debug: "✅ Исправление применено. Также добавил unit test для этого случая."
```

**Сценарий 3: Архитектурное проектирование**

```
User: "Как лучше организовать микросервисную архитектуру для e-commerce?"

Orchestrator: "Это архитектурный вопрос. Передаю Architect Agent..."

Architect: "Для e-commerce рекомендую следующую архитектуру:

**Микросервисы:**
1. User Service - управление пользователями, аутентификация
2. Product Service - каталог товаров, поиск
3. Order Service - обработка заказов
4. Payment Service - платежи (изолированный)
5. Notification Service - email/SMS уведомления

**Коммуникация:**
- Синхронная: REST/gRPC для запросов
- Асинхронная: RabbitMQ/Kafka для событий

**Паттерны:**
- API Gateway для единой точки входа
- Service Discovery (Consul/Eureka)
- Circuit Breaker для отказоустойчивости
- Saga Pattern для распределенных транзакций

**Хранилище:**
- PostgreSQL для User/Order (ACID)
- MongoDB для Product (гибкая схема)
- Redis для кеша и сессий

Создать диаграмму и базовую структуру проекта?"

User: "Да, создай структуру для Order Service"

Architect: [создает структуру директорий и базовые файлы]
Architect: "✅ Создана структура Order Service с базовыми компонентами"
```

**Сценарий 4: Комплексная задача**

```
User: "Добавь систему логирования во все сервисы с отправкой в ELK"

Orchestrator: "Это комплексная задача. План:
1. Architect: спроектирует структуру логирования
2. Coder: реализует логгеры для каждого сервиса
3. Coder: настроит интеграцию с ELK

Начинаем?"

User: "Да"

Architect: "Предлагаю структурированное логирование с structlog:
- Единый формат JSON для всех сервисов
- Контекстные поля (service_name, request_id, user_id)
- Уровни: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Ротация логов по размеру/времени"

Coder: [создает базовый logger module]
Coder: "Создал app/core/logging.py с настроенным structlog"

Coder: [обновляет каждый сервис]
Coder: "Добавил логирование в Gateway, Agent Runtime, LLM Proxy"

Coder: [создает docker-compose для ELK]
Coder: "Настроил Logstash для сбора логов из всех контейнеров"

Orchestrator: "✅ Задача выполнена. Логи доступны в Kibana на localhost:5601"
```

### 5.2 Диалоговая логика

**Multi-turn диалоги**:

```python
class ConversationManager:
    async def handle_message(
        self,
        session_id: str,
        message: str
    ) -> AsyncIterator[str]:
        """
        Управление контекстом диалога:
        1. Загрузка истории сессии
        2. Добавление нового сообщения
        3. Формирование контекста для LLM
        4. Генерация ответа
        5. Сохранение в историю
        """
        # Загрузка истории (последние 10 сообщений)
        history = await self.session_manager.get_history(
            session_id,
            limit=10
        )
        
        # Формирование контекста
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *[
                {"role": msg.role, "content": msg.content}
                for msg in history
            ],
            {"role": "user", "content": message}
        ]
        
        # Генерация с streaming
        async for token in self.llm_client.stream(messages):
            yield token
        
        # Сохранение в историю
        await self.session_manager.add_message(
            session_id,
            role="user",
            content=message
        )
        await self.session_manager.add_message(
            session_id,
            role="assistant",
            content=full_response
        )
```

**Контекст сессии**:

```python
class SessionContext:
    """
    Контекст сессии включает:
    - История сообщений
    - Текущий агент
    - Открытые файлы
    - Выполненные инструменты
    - Pending HITL запросы
    """
    session_id: str
    user_id: str
    current_agent: str
    message_history: List[Message]
    open_files: List[str]
    tool_history: List[ToolCall]
    pending_hitl: List[HITLRequest]
    created_at: datetime
    last_activity: datetime
```

**Переключение между агентами**:

```python
class AgentRouter:
    async def route_message(
        self,
        message: str,
        context: SessionContext
    ) -> str:
        """
        Определение нужного агента:
        1. Анализ intent сообщения
        2. Учет текущего контекста
        3. Выбор агента или Orchestrator
        """
        # Простые правила (можно заменить на ML classifier)
        if any(kw in message.lower() for kw in ["напиши", "создай", "добавь"]):
            return "coder"
        elif any(kw in message.lower() for kw in ["ошибка", "не работает", "баг"]):
            return "debug"
        elif any(kw in message.lower() for kw in ["архитектура", "структура", "паттерн"]):
            return "architect"
        elif any(kw in message.lower() for kw in ["что", "как", "почему", "объясни"]):
            return "ask"
        else:
            # Сложная задача - отправляем Orchestrator
            return "orchestrator"
```

**Управление состоянием диалога**:

```python
class DialogueState(Enum):
    IDLE = "idle"                    # Ожидание ввода
    PROCESSING = "processing"        # Обработка запроса
    WAITING_APPROVAL = "waiting"     # Ожидание HITL
    EXECUTING_TOOL = "executing"     # Выполнение инструмента
    ERROR = "error"                  # Ошибка

class DialogueManager:
    async def transition_state(
        self,
        session_id: str,
        new_state: DialogueState
    ):
        """Переход между состояниями с уведомлением UI"""
        await self.session_manager.update_state(session_id, new_state)
        await self.ws.send_state_update(session_id, new_state)
```

### 5.3 Метрики UX

**Производительность**:

```python
class PerformanceMetrics:
    # Время до первого токена (TTFT)
    time_to_first_token: float  # Target: < 500ms
    
    # Время полного ответа
    total_response_time: float  # Target: < 5s для простых задач
    
    # Скорость streaming
    tokens_per_second: float    # Target: > 20 tokens/s
    
    # Latency инструментов
    tool_execution_time: Dict[str, float]  # read_file: <100ms
```

**Качество**:

```python
class QualityMetrics:
    # User satisfaction
    thumbs_up_rate: float       # Target: > 80%
    thumbs_down_rate: float     # Target: < 10%
    
    # HITL approval rate
    hitl_approval_rate: float   # Target: > 90%
    
    # Task completion
    task_completion_rate: float # Target: > 85%
    
    # Error rate
    error_rate: float           # Target: < 5%
```

**Engagement**:

```python
class EngagementMetrics:
    # Активность
    daily_active_users: int
    messages_per_session: float     # Target: > 5
    session_duration: float         # Target: > 10 min
    
    # Retention
    day_1_retention: float          # Target: > 40%
    day_7_retention: float          # Target: > 20%
    day_30_retention: float         # Target: > 10%
    
    # Feature usage
    agent_usage_distribution: Dict[str, float]
    tool_usage_frequency: Dict[str, int]
```

**NPS (Net Promoter Score)**:

```python
class NPSTracker:
    async def collect_nps(self, user_id: str):
        """
        Вопрос: "Насколько вероятно, что вы порекомендуете
        CodeLab коллеге? (0-10)"
        
        Promoters (9-10): довольные пользователи
        Passives (7-8): нейтральные
        Detractors (0-6): недовольные
        
        NPS = % Promoters - % Detractors
        Target: NPS > 50
        """
        pass
```

---

## 6. Безопасность, соответствие и этика

### 6.1 Аутентификация и авторизация

**OAuth2 + JWT**:

```python
# Auth Service
class AuthService:
    async def authenticate(self, username: str, password: str) -> TokenPair:
        """
        1. Проверка credentials
        2. Генерация access token (JWT, TTL: 15 min)
        3. Генерация refresh token (TTL: 7 days)
        """
        user = await self.user_repo.get_by_username(username)
        if not user or not verify_password(password, user.password_hash):
            raise AuthenticationError("Invalid credentials")
        
        access_token = create_jwt(
            user_id=user.id,
            expires_in=timedelta(minutes=15)
        )
        refresh_token = create_jwt(
            user_id=user.id,
            expires_in=timedelta(days=7),
            token_type="refresh"
        )
        
        return TokenPair(access_token, refresh_token)
```

**Internal Service Authentication**:

```python
# Middleware для внутренней коммуникации
class InternalAuthMiddleware:
    def __init__(self, shared_secret: str):
        self.shared_secret = shared_secret
    
    async def __call__(self, request: Request):
        internal_secret = request.headers.get("X-Internal-Secret")
        if internal_secret != self.shared_secret:
            raise HTTPException(status_code=403, detail="Forbidden")
```

### 6.2 HITL (Human-in-the-Loop) для опасных операций

**Категории опасности**:

| Операция | Уровень риска | HITL требуется | Причина |
|----------|---------------|----------------|---------|
| read_file | Низкий | ❌ | Только чтение |
| list_files | Низкий | ❌ | Только чтение |
| search_files | Низкий | ❌ | Только чтение |
| write_file | Высокий | ✅ | Изменение кода |
| delete_file | Критический | ✅ | Необратимо |
| execute_command | Критический | ✅ | Выполнение кода |
| git_commit | Средний | ✅ | Изменение истории |

**Персистентность HITL запросов**:

```sql
-- PostgreSQL schema
CREATE TABLE hitl_requests (
    id UUID PRIMARY KEY,
    session_id UUID NOT NULL,
    tool_name VARCHAR(100) NOT NULL,
    parameters JSONB NOT NULL,
    status VARCHAR(20) NOT NULL, -- pending, approved, rejected, timeout
    created_at TIMESTAMP NOT NULL,
    responded_at TIMESTAMP,
    user_response JSONB,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE INDEX idx_hitl_session ON hitl_requests(session_id);
CREATE INDEX idx_hitl_status ON hitl_requests(status);
```

### 6.3 Изоляция и песочница

**Docker изоляция**:
- Каждый сервис в отдельном контейнере
- Ограничение ресурсов (CPU, RAM)
- Сетевая изоляция (internal networks)
- Read-only файловые системы где возможно

**Валидация путей**:

```python
class PathValidator:
    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root).resolve()
    
    def validate_path(self, path: str) -> Path:
        """
        Проверка, что путь находится внутри workspace
        """
        full_path = (self.workspace_root / path).resolve()
        
        # Проверка на path traversal
        if not str(full_path).startswith(str(self.workspace_root)):
            raise SecurityError("Path outside workspace")
        
        # Проверка на системные файлы
        if any(part.startswith('.') for part in full_path.parts):
            raise SecurityError("Access to hidden files denied")
        
        return full_path
```

### 6.4 Аудит и логирование

**Структурированное логирование**:

```python
# Логирование всех действий агентов
logger.info(
    "agent_action",
    agent="coder",
    action="write_file",
    session_id=session_id,
    user_id=user_id,
    file_path=file_path,
    approved=True,
    timestamp=datetime.utcnow()
)

# Логирование HITL решений
logger.info(
    "hitl_decision",
    request_id=request_id,
    tool_name=tool_name,
    approved=approved,
    response_time_ms=response_time,
    user_id=user_id
)
```

**Audit Trail**:

```sql
CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    user_id UUID NOT NULL,
    session_id UUID,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id VARCHAR(255),
    details JSONB,
    ip_address INET,
    user_agent TEXT
);

CREATE INDEX idx_audit_user ON audit_log(user_id);
CREATE INDEX idx_audit_timestamp ON audit_log(timestamp);
```

### 6.5 Защита данных

**Шифрование**:
- TLS/SSL для всех внешних соединений
- Шифрование паролей (bcrypt, cost factor: 12)
- Шифрование sensitive данных в БД (AES-256)

**Ограничение доступа к данным**:

```python
class DataAccessPolicy:
    async def can_access_session(self, user_id: str, session_id: str) -> bool:
        """Пользователь может видеть только свои сессии"""
        session = await self.session_repo.get(session_id)
        return session.user_id == user_id
    
    async def can_access_project(self, user_id: str, project_id: str) -> bool:
        """Проверка прав доступа к проекту"""
        # Планируется: team-based access control
        pass
```

### 6.6 Rate Limiting

```python
# Redis-based rate limiting
class RateLimiter:
    async def check_rate_limit(
        self,
        user_id: str,
        action: str,
        limit: int,
        window: int
    ) -> bool:
        """
        Ограничения:
        - LLM requests: 100/hour per user
        - File operations: 1000/hour per user
        - HITL requests: 50/hour per user
        """
        key = f"rate_limit:{user_id}:{action}"
        count = await self.redis.incr(key)
        
        if count == 1:
            await self.redis.expire(key, window)
        
        if count > limit:
            raise RateLimitExceeded(f"Rate limit exceeded for {action}")
        
        return True
```

### 6.7 Этические соображения

**Прозрачность**:
- Пользователь всегда видит, какой агент работает
- Все изменения файлов требуют явного подтверждения
- История всех действий доступна пользователю

**Контроль**:
- Пользователь может отменить любую операцию
- Возможность отката изменений (через Git интеграцию)
- Экспорт всех данных по запросу

**Ответственное использование AI**:
- Предупреждения о потенциальных проблемах в сгенерированном коде
- Рекомендации по security best practices
- Отказ от генерации вредоносного кода

---

## 7. План внедрения и эксплуатации

### 7.1 Этапы проекта

**Phase 1: MVP (Завершено)** ✅

- [x] Базовая IDE на Flutter (Explorer, Editor, Terminal)
- [x] WebSocket коммуникация с backend
- [x] Мульти-агентная система (5 агентов)
- [x] HITL система с персистентностью
- [x] Интеграция с LLM провайдерами (OpenAI, Anthropic, Ollama)
- [x] PostgreSQL для хранения сессий
- [x] Redis для кеширования
- [x] Docker Compose развертывание

**Phase 2: Enhanced RAG (В разработке)** 🚧

- [ ] Векторная база данных (Qdrant)
- [ ] Семантический поиск по кодовой базе
- [ ] Автоматическая индексация проектов
- [ ] Улучшенный контекстный retrieval
- [ ] Code embeddings (CodeBERT)
- [ ] Инкрементальное обновление индекса

**Phase 3: Advanced Features (Планируется)** 📋

- [ ] Git интеграция (commit, push, pull, merge)
- [ ] Collaborative editing (real-time)
- [ ] Code review агент
- [ ] Test generation агент
- [ ] Performance profiling агент
- [ ] Security scanning агент

**Phase 4: Enterprise Features (Будущее)** 🔮

- [ ] Team workspaces
- [ ] Role-based access control (RBAC)
- [ ] SSO интеграция (SAML, LDAP)
- [ ] On-premise deployment
- [ ] Custom model fine-tuning
- [ ] Advanced analytics dashboard

### 7.2 Roadmap

```
Q1 2026:
├── ✅ MVP Release
├── 🚧 Векторный поиск (Qdrant)
└── 📋 Git интеграция (базовая)

Q2 2026:
├── Code review агент
├── Test generation
└── Performance оптимизации

Q3 2026:
├── Collaborative editing
├── Team workspaces
└── RBAC

Q4 2026:
├── Enterprise features
├── On-premise deployment
└── Custom fine-tuning
```

### 7.3 Поддержка и эксплуатация

**Мониторинг**:

```python
# Health checks
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "dependencies": {
            "postgres": await check_postgres(),
            "redis": await check_redis(),
            "llm_proxy": await check_llm_proxy()
        }
    }

# Metrics endpoint (Prometheus format)
@app.get("/metrics")
async def metrics():
    return generate_prometheus_metrics()
```

**Метрики производительности**:

- Response time (p50, p95, p99)
- Throughput (requests/second)
- Error rate
- LLM latency
- Database query time
- Cache hit rate

**Алерты**:

```yaml
# Prometheus alerts
groups:
  - name: codelab_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        annotations:
          summary: "High error rate detected"
      
      - alert: SlowLLMResponse
        expr: histogram_quantile(0.95, llm_response_time_seconds) > 10
        for: 5m
        annotations:
          summary: "LLM response time is too slow"
      
      - alert: DatabaseConnectionPoolExhausted
        expr: db_connection_pool_usage > 0.9
        for: 2m
        annotations:
          summary: "Database connection pool almost exhausted"
```

**Backup стратегия**:

```bash
# PostgreSQL backup (ежедневно)
pg_dump -h postgres -U codelab -d codelab_db | gzip > backup_$(date +%Y%m%d).sql.gz

# Retention: 7 daily, 4 weekly, 12 monthly
```

**Disaster Recovery**:

- RTO (Recovery Time Objective): < 1 hour
- RPO (Recovery Point Objective): < 15 minutes
- Автоматический failover для критических сервисов
- Geo-redundant backups

---

## 8. Риски и допущения

### 8.1 Технические риски

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| **Качество ответов LLM** | Высокая | Высокое | • HITL для критических операций<br>• Валидация сгенерированного кода<br>• Fallback на другие модели |
| **Стоимость API** | Средняя | Высокое | • Кеширование ответов<br>• Использование локальных моделей (Ollama)<br>• Rate limiting |
| **Производительность** | Средняя | Среднее | • Оптимизация промптов<br>• Параллельное выполнение<br>• Масштабирование инфраструктуры |
| **Безопасность** | Низкая | Критическое | • HITL для опасных операций<br>• Песочница для выполнения кода<br>• Аудит логирование |
| **Доступность LLM** | Средняя | Высокое | • Fallback chain<br>• Локальные модели<br>• Graceful degradation |

### 8.2 Бизнес-риски

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| **Низкая adoption** | Средняя | Высокое | • Бесплатный tier<br>• Активный маркетинг<br>• Community building |
| **Конкуренция** | Высокая | Среднее | • Уникальные features (мульти-агенты)<br>• Лучший UX<br>• Локальные модели |
| **Изменение LLM API** | Средняя | Среднее | • Абстракция через LiteLLM<br>• Поддержка множества провайдеров |

### 8.3 Допущения

**Технические**:
- LLM модели продолжат улучшаться
- Стоимость API будет снижаться
- Локальные модели станут более производительными
- WebSocket поддерживается всеми браузерами

**Бизнес**:
- Разработчики готовы использовать AI-инструменты
- Рынок AI-powered IDE будет расти
- Пользователи готовы платить за premium features

---

## 9. Бюджет и ресурсы

### 9.1 Человеческие ресурсы

**Команда разработки**:

| Роль | FTE | Обязанности |
|------|-----|-------------|
| **Tech Lead** | 1.0 | Архитектура, code review, технические решения |
| **Backend Engineer** | 2.0 | Agent Runtime, Gateway, LLM Proxy |
| **Frontend Engineer** | 1.5 | Flutter IDE, UI/UX |
| **ML Engineer** | 1.0 | Промпт-инжиниринг, RAG, fine-tuning |
| **DevOps Engineer** | 0.5 | Инфраструктура, CI/CD, мониторинг |
| **QA Engineer** | 0.5 | Тестирование, автоматизация |
| **Product Manager** | 0.5 | Roadmap, приоритизация, feedback |

**Итого**: 7 FTE

### 9.2 Технологические ресурсы

**Облачная инфраструктура** (AWS/GCP):

| Ресурс | Спецификация | Стоимость/месяц |
|--------|--------------|-----------------|
| **Compute** | 4x t3.medium (Gateway, Agent Runtime) | $120 |
| **Database** | RDS PostgreSQL (db.t3.medium) | $80 |
| **Cache** | ElastiCache Redis (cache.t3.small) | $40 |
| **Storage** | 100GB SSD | $10 |
| **Load Balancer** | Application LB | $20 |
| **Monitoring** | CloudWatch, Prometheus | $30 |

**Итого инфраструктура**: ~$300/месяц (для 100 пользователей)

**LLM API** (переменные затраты):

| Провайдер | Модель | Стоимость | Использование |
|-----------|--------|-----------|---------------|
| OpenAI | GPT-4 Turbo | $10/1M input tokens | 30% запросов |
| OpenAI | GPT-3.5 Turbo | $0.5/1M input tokens | 40% запросов |
| Anthropic | Claude 3 Opus | $15/1M input tokens | 20% запросов |
| Ollama | Local | $0 (только GPU) | 10% запросов |

**Средняя стоимость на пользователя**: $5-10/месяц (при активном использовании)

**GPU для Ollama** (опционально):

- NVIDIA A100 (40GB): $1000-1500/месяц (облако)
- Или локальный сервер: $10,000 единоразово

### 9.3 Общий бюджет (годовой)

| Категория | Стоимость |
|-----------|-----------|
| **Зарплаты** (7 FTE × $100k) | $700,000 |
| **Инфраструктура** ($300 × 12) | $3,600 |
| **LLM API** (1000 пользователей × $7 × 12) | $84,000 |
| **Инструменты и лицензии** | $20,000 |
| **Маркетинг** | $50,000 |
| **Прочее** (10% buffer) | $85,760 |

**Итого**: ~$943,360/год

### 9.4 Модель монетизации

**Free Tier**:
- 100 запросов/месяц
- Базовые агенты (Coder, Ask)
- Только облачные модели

**Pro Tier** ($20/месяц):
- Unlimited запросы
- Все агенты
- Локальные модели (Ollama)
- Priority support

**Team Tier** ($50/пользователь/месяц):
- Все из Pro
- Team workspaces
- Collaborative editing
- Advanced analytics
- SSO

**Enterprise** (Custom pricing):
- On-premise deployment
- Custom fine-tuning
- SLA guarantees
- Dedicated support

---

## 10. Приложения

### 10.1 Ссылки на документацию

**Техническая документация**:

- [Multi-Agent Architecture](../codelab-ai-service/doc/multi-agent-architecture-plan.md)
- [HITL Implementation](../codelab-ai-service/doc/HITL_IMPLEMENTATION.md)
- [WebSocket Protocol](../codelab-ai-service/doc/websocket-protocol.md)
- [Agent Runtime Tech Req](../codelab-ai-service/doc/tech-req-agent-runtime-service.md)
- [Gateway Tech Req](../codelab-ai-service/doc/tech-req-gateway.md)
- [LLM Proxy Tech Req](../codelab-ai-service/doc/tech-req-llm-proxy-service.md)

**Руководства**:

- [Multi-Agent Quick Start](../codelab-ai-service/doc/multi-agent-quick-start.md)
- [Database Configuration](../codelab-ai-service/DATABASE_CONFIGURATION.md)
- [PostgreSQL Migration](../codelab-ai-service/POSTGRES_MIGRATION_SUMMARY.md)

**Отчеты**:

- [Multi-Agent Final Report](../codelab-ai-service/MULTI_AGENT_FINAL_REPORT.md)
- [Test Coverage Report](../codelab-ai-service/agent-runtime/TEST_COVERAGE_REPORT.md)

### 10.2 Архитектурные диаграммы

**Компонентная диаграмма**:

```
┌─────────────────────────────────────────────────────────────┐
│                        CodeLab IDE                          │
│                      (Flutter/Dart)                         │
└────────────────────────┬────────────────────────────────────┘
                         │ WebSocket
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                         Gateway                             │
│              (Session Management, Streaming)                │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                     Agent Runtime                           │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Multi-Agent System                       │  │
│  │  Orchestrator → Coder / Architect / Debug / Ask      │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  HITL Manager │ Tool Registry │ Session Manager      │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                       LLM Proxy                             │
│                  (LiteLLM Integration)                      │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
    [OpenAI]      [Anthropic]       [Ollama]
```

**Диаграмма последовательности (HITL)**:

```
User → IDE → Gateway → Agent Runtime → LLM → Agent Runtime
                                        ↓
                                   [Tool Call]
                                        ↓
                                   HITL Manager
                                        ↓
                                   PostgreSQL
                                        ↓
IDE ← Gateway ← Agent Runtime ← [Approval Request]
                                        ↓
User [Approve/Reject] → IDE → Gateway → Agent Runtime
                                        ↓
                                   HITL Manager
                                        ↓
                                   [Execute Tool]
                                        ↓
IDE ← Gateway ← Agent Runtime ← [Tool Result]
```

### 10.3 API Спецификации

**WebSocket Messages**:

```typescript
// Client → Server
type ClientMessage =
  | { type: "chat", session_id: string, message: string }
  | { type: "tool_approval", approval_id: string, approved: boolean }
  | { type: "cancel", session_id: string };

// Server → Client
type ServerMessage =
  | { type: "token", data: string }
  | { type: "tool_call", data: ToolCall }
  | { type: "tool_result", data: ToolResult }
  | { type: "error", error: string }
  | { type: "done" };
```

**REST API Endpoints**:

```
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh
POST   /api/v1/sessions
GET    /api/v1/sessions/:id
DELETE /api/v1/sessions/:id
GET    /api/v1/sessions/:id/history
POST   /api/v1/agent/chat
GET    /api/v1/hitl/requests/:id
PUT    /api/v1/hitl/requests/:id/approve
PUT    /api/v1/hitl/requests/:id/reject
```

### 10.4 Глоссарий

- **Agent**: Специализированный AI-компонент для выполнения определенного типа задач
- **HITL**: Human-in-the-Loop - механизм подтверждения опасных операций пользователем
- **LLM**: Large Language Model - большая языковая модель
- **RAG**: Retrieval-Augmented Generation - генерация с дополнением контекстом
- **Tool Call**: Вызов инструмента агентом (read_file, write_file, etc.)
- **Session**: Контекст диалога пользователя с системой
- **Orchestrator**: Агент-координатор, управляющий другими агентами
- **Streaming**: Потоковая передача ответа токен за токеном
- **Fallback**: Резервный вариант при недоступности основного сервиса

### 10.5 Контакты и ресурсы

**Репозитории**:
- Backend: `codelab-ai-service/`
- Frontend: `codelab_ide/`
- Documentation: `doc/`

**Команда**:
- Tech Lead: [contact]
- Product Manager: [contact]

**Ссылки**:
- Website: [планируется]
- Documentation: [планируется]
- Community: [планируется]

---

**Версия документа**: 1.0
**Дата создания**: 2026-01-09
**Последнее обновление**: 2026-01-09
**Статус**: Draft → Review → Approved

---

*Этот дизайн-документ является живым документом и будет обновляться по мере развития проекта CodeLab.*