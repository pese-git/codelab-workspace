# Анализ Legacy кода agent-runtime

## 📋 Обзор

Детальный анализ использования legacy компонентов из [`services/`](codelab-ai-service/agent-runtime/app/services), [`models/`](codelab-ai-service/agent-runtime/app/models) и [`middleware/`](codelab-ai-service/agent-runtime/app/middleware) в текущей архитектуре.

---

## 1️⃣ Legacy Services (10 файлов)

### ✅ **АКТИВНО ИСПОЛЬЗУЮТСЯ** (7 файлов)

#### 1.1 [`agent_router.py`](codelab-ai-service/agent-runtime/app/services/agent_router.py) - **ИСПОЛЬЗУЕТСЯ**
**Назначение:** Реестр и маршрутизация агентов

**Где используется:**
- [`app/main.py`](codelab-ai-service/agent-runtime/app/main.py:109) - инициализация агентов
- [`app/agents/__init__.py`](codelab-ai-service/agent-runtime/app/agents/__init__.py:14) - регистрация агентов
- [`app/agents/orchestrator_agent.py`](codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py:118) - проверка доступных агентов
- [`app/services/multi_agent_orchestrator.py`](codelab-ai-service/agent-runtime/app/services/multi_agent_orchestrator.py:18) - получение агентов

**Аналог в новой архитектуре:** ❌ НЕТ
- Должен быть в [`domain/services/agent_registry.py`](codelab-ai-service/agent-runtime/app/domain/services) или [`infrastructure/agents/agent_registry.py`](codelab-ai-service/agent-runtime/app/infrastructure)

**Рекомендация:** 
- ⚠️ **ОСТАВИТЬ** - это доменный сервис, но переименовать в `AgentRegistry` и переместить в [`domain/services/`](codelab-ai-service/agent-runtime/app/domain/services)
- Функциональность уникальна и активно используется

---

#### 1.2 [`database.py`](codelab-ai-service/agent-runtime/app/services/database.py) - **ИСПОЛЬЗУЕТСЯ**
**Назначение:** Управление базой данных (SQLAlchemy модели + DatabaseService)

**Где используется:**
- [`app/main.py`](codelab-ai-service/agent-runtime/app/main.py:54-55) - инициализация БД
- [`app/main.py`](codelab-ai-service/agent-runtime/app/main.py:79) - получение сессии БД
- [`app/main.py`](codelab-ai-service/agent-runtime/app/main.py:194) - закрытие БД
- [`app/core/dependencies.py`](codelab-ai-service/agent-runtime/app/core/dependencies.py:14) - DI для БД
- [`app/services/hitl_manager.py`](codelab-ai-service/agent-runtime/app/services/hitl_manager.py:19,119) - работа с pending approvals

**Аналог в новой архитектуре:** ✅ **ЧАСТИЧНО**
- SQLAlchemy модели → [`infrastructure/persistence/models/`](codelab-ai-service/agent-runtime/app/infrastructure/persistence/models)
- DatabaseService → [`infrastructure/persistence/database.py`](codelab-ai-service/agent-runtime/app/infrastructure/persistence)
- Репозитории → [`infrastructure/persistence/repositories/`](codelab-ai-service/agent-runtime/app/infrastructure/persistence/repositories)

**Рекомендация:**
- ⚠️ **РЕФАКТОРИТЬ** - разделить на компоненты:
  1. Модели (SessionModel, MessageModel, etc.) → [`infrastructure/persistence/models/`](codelab-ai-service/agent-runtime/app/infrastructure/persistence/models)
  2. DatabaseService → [`infrastructure/persistence/database.py`](codelab-ai-service/agent-runtime/app/infrastructure/persistence)
  3. Функции init_database, get_db → [`infrastructure/persistence/database.py`](codelab-ai-service/agent-runtime/app/infrastructure/persistence)

---

#### 1.3 [`hitl_manager.py`](codelab-ai-service/agent-runtime/app/services/hitl_manager.py) - **ИСПОЛЬЗУЕТСЯ**
**Назначение:** Управление HITL (Human-in-the-Loop) состояниями

**Где используется:**
- [`app/services/llm_stream_service.py`](codelab-ai-service/agent-runtime/app/services/llm_stream_service.py:23) - проверка и добавление pending approvals

**Аналог в новой архитектуре:** ❌ НЕТ

**Рекомендация:**
- ⚠️ **ПЕРЕМЕСТИТЬ** в [`domain/services/hitl_management.py`](codelab-ai-service/agent-runtime/app/domain/services)
- Это доменный сервис, управляющий бизнес-логикой HITL

---

#### 1.4 [`hitl_policy_service.py`](codelab-ai-service/agent-runtime/app/services/hitl_policy_service.py) - **ИСПОЛЬЗУЕТСЯ**
**Назначение:** Политики HITL (какие инструменты требуют одобрения)

**Где используется:**
- [`app/services/llm_stream_service.py`](codelab-ai-service/agent-runtime/app/services/llm_stream_service.py:22) - проверка требований одобрения

**Аналог в новой архитектуре:** ❌ НЕТ

**Рекомендация:**
- ⚠️ **ПЕРЕМЕСТИТЬ** в [`domain/services/hitl_policy.py`](codelab-ai-service/agent-runtime/app/domain/services)
- Это доменный сервис, определяющий бизнес-правила

---

#### 1.5 [`llm_proxy_client.py`](codelab-ai-service/agent-runtime/app/services/llm_proxy_client.py) - **ИСПОЛЬЗУЕТСЯ**
**Назначение:** HTTP клиент для LLM Proxy

**Где используется:**
- [`app/services/llm_stream_service.py`](codelab-ai-service/agent-runtime/app/services/llm_stream_service.py:16) - вызов LLM
- [`app/agents/orchestrator_agent.py`](codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py:12) - вызов LLM

**Аналог в новой архитектуре:** ❌ НЕТ (должен быть в [`infrastructure/llm/`](codelab-ai-service/agent-runtime/app/infrastructure/llm))

**Рекомендация:**
- ✅ **ПЕРЕМЕСТИТЬ** в [`infrastructure/llm/client.py`](codelab-ai-service/agent-runtime/app/infrastructure/llm/client.py)
- Это инфраструктурный компонент (внешний HTTP клиент)

---

#### 1.6 [`llm_stream_service.py`](codelab-ai-service/agent-runtime/app/services/llm_stream_service.py) - **ИСПОЛЬЗУЕТСЯ**
**Назначение:** Обработка streaming ответов от LLM

**Где используется:**
- [`app/agents/architect_agent.py`](codelab-ai-service/agent-runtime/app/agents/architect_agent.py:12)
- [`app/agents/ask_agent.py`](codelab-ai-service/agent-runtime/app/agents/ask_agent.py:12)
- [`app/agents/coder_agent.py`](codelab-ai-service/agent-runtime/app/agents/coder_agent.py:11)
- [`app/agents/debug_agent.py`](codelab-ai-service/agent-runtime/app/agents/debug_agent.py:12)
- [`app/agents/universal_agent.py`](codelab-ai-service/agent-runtime/app/agents/universal_agent.py:10)

**Аналог в новой архитектуре:** ❌ НЕТ (должен быть в [`infrastructure/llm/`](codelab-ai-service/agent-runtime/app/infrastructure/llm))

**Рекомендация:**
- ✅ **ПЕРЕМЕСТИТЬ** в [`infrastructure/llm/streaming.py`](codelab-ai-service/agent-runtime/app/infrastructure/llm/streaming.py)
- Это инфраструктурный компонент (работа с LLM API)

---

#### 1.7 [`multi_agent_orchestrator.py`](codelab-ai-service/agent-runtime/app/services/multi_agent_orchestrator.py) - **ИСПОЛЬЗУЕТСЯ**
**Назначение:** Оркестрация мульти-агентной системы

**Где используется:**
- [`app/main.py`](codelab-ai-service/agent-runtime/app/main.py:108) - обработка сообщений

**Аналог в новой архитектуре:** ✅ **ЧАСТИЧНО**
- Есть [`domain/services/agent_orchestration.py`](codelab-ai-service/agent-runtime/app/domain/services/agent_orchestration.py)

**Рекомендация:**
- ⚠️ **ОБЪЕДИНИТЬ** с [`domain/services/agent_orchestration.py`](codelab-ai-service/agent-runtime/app/domain/services/agent_orchestration.py)
- Проверить дублирование функциональности
- Оставить в [`domain/services/`](codelab-ai-service/agent-runtime/app/domain/services) как доменный сервис

---

### ✅ **ИСПОЛЬЗУЮТСЯ ЧАСТИЧНО** (3 файла)

#### 1.8 [`retry_service.py`](codelab-ai-service/agent-runtime/app/services/retry_service.py) - **ИСПОЛЬЗУЕТСЯ**
**Назначение:** Retry логика с exponential backoff

**Где используется:**
- [`app/services/llm_proxy_client.py`](codelab-ai-service/agent-runtime/app/services/llm_proxy_client.py:14-18) - retry для LLM запросов

**Аналог в новой архитектуре:** ✅ **ДА**
- [`infrastructure/resilience/retry_handler.py`](codelab-ai-service/agent-runtime/app/infrastructure/resilience/retry_handler.py)

**Рекомендация:**
- ✅ **УДАЛИТЬ** - функциональность дублируется в [`infrastructure/resilience/retry_handler.py`](codelab-ai-service/agent-runtime/app/infrastructure/resilience/retry_handler.py)
- Обновить импорты в [`llm_proxy_client.py`](codelab-ai-service/agent-runtime/app/services/llm_proxy_client.py)

---

#### 1.9 [`tool_parser.py`](codelab-ai-service/agent-runtime/app/services/tool_parser.py) - **ИСПОЛЬЗУЕТСЯ**
**Назначение:** Парсинг tool calls из LLM ответов

**Где используется:**
- [`app/services/llm_stream_service.py`](codelab-ai-service/agent-runtime/app/services/llm_stream_service.py:17) - парсинг tool calls

**Аналог в новой архитектуре:** ❌ НЕТ

**Рекомендация:**
- ⚠️ **ПЕРЕМЕСТИТЬ** в [`infrastructure/llm/tool_parser.py`](codelab-ai-service/agent-runtime/app/infrastructure/llm/tool_parser.py)
- Это инфраструктурный компонент (парсинг LLM ответов)

---

#### 1.10 [`tool_registry.py`](codelab-ai-service/agent-runtime/app/services/tool_registry.py) - **ИСПОЛЬЗУЕТСЯ**
**Назначение:** Реестр доступных инструментов

**Где используется:**
- [`app/services/llm_stream_service.py`](codelab-ai-service/agent-runtime/app/services/llm_stream_service.py:21) - получение TOOLS_SPEC

**Аналог в новой архитектуре:** ❌ НЕТ

**Рекомендация:**
- ⚠️ **ПЕРЕМЕСТИТЬ** в [`domain/services/tool_registry.py`](codelab-ai-service/agent-runtime/app/domain/services/tool_registry.py) или [`infrastructure/tools/registry.py`](codelab-ai-service/agent-runtime/app/infrastructure/tools)
- Это может быть как доменный (определение доступных инструментов), так и инфраструктурный компонент

---

## 2️⃣ Legacy Models (2 файла)

### ✅ **АКТИВНО ИСПОЛЬЗУЮТСЯ**

#### 2.1 [`hitl_models.py`](codelab-ai-service/agent-runtime/app/models/hitl_models.py) - **ИСПОЛЬЗУЕТСЯ**
**Назначение:** Pydantic модели для HITL

**Где используется:**
- [`app/services/hitl_manager.py`](codelab-ai-service/agent-runtime/app/services/hitl_manager.py:13-17) - все HITL модели
- [`app/services/hitl_policy_service.py`](codelab-ai-service/agent-runtime/app/services/hitl_policy_service.py:13) - HITLPolicy, HITLPolicyRule

**Аналог в новой архитектуре:** ❌ НЕТ

**Рекомендация:**
- ⚠️ **ПЕРЕМЕСТИТЬ** в [`domain/entities/hitl.py`](codelab-ai-service/agent-runtime/app/domain/entities/hitl.py)
- Это доменные сущности (бизнес-модели HITL)

---

#### 2.2 [`schemas.py`](codelab-ai-service/agent-runtime/app/models/schemas.py) - **ИСПОЛЬЗУЕТСЯ**
**Назначение:** Общие Pydantic схемы (Message, ToolCall, StreamChunk, etc.)

**Где используется:**
- Везде в проекте (агенты, сервисы, API)

**Аналог в новой архитектуре:** ✅ **ЧАСТИЧНО**
- [`api/v1/schemas/`](codelab-ai-service/agent-runtime/app/api/v1/schemas) - API схемы
- [`application/dto/`](codelab-ai-service/agent-runtime/app/application/dto) - DTO
- [`domain/entities/`](codelab-ai-service/agent-runtime/app/domain/entities) - доменные сущности

**Рекомендация:**
- ⚠️ **РАЗДЕЛИТЬ** на компоненты:
  1. `Message`, `ToolCall` → [`domain/entities/message.py`](codelab-ai-service/agent-runtime/app/domain/entities/message.py) (уже есть, проверить дублирование)
  2. `StreamChunk` → [`api/v1/schemas/stream_schemas.py`](codelab-ai-service/agent-runtime/app/api/v1/schemas) (API response)
  3. `AgentStreamRequest` → [`api/v1/schemas/message_schemas.py`](codelab-ai-service/agent-runtime/app/api/v1/schemas/message_schemas.py) (уже есть)
  4. `AgentInfo` → [`api/v1/schemas/agent_schemas.py`](codelab-ai-service/agent-runtime/app/api/v1/schemas/agent_schemas.py) (уже есть)

---

## 3️⃣ Legacy Middleware (1 файл)

### ✅ **АКТИВНО ИСПОЛЬЗУЕТСЯ**

#### 3.1 [`internal_auth.py`](codelab-ai-service/agent-runtime/app/middleware/internal_auth.py) - **ИСПОЛЬЗУЕТСЯ**
**Назначение:** Middleware для внутренней аутентификации

**Где используется:**
- [`app/main.py`](codelab-ai-service/agent-runtime/app/main.py) - регистрация middleware (предположительно)

**Аналог в новой архитектуре:** ✅ **ДА**
- [`api/middleware/`](codelab-ai-service/agent-runtime/app/api/middleware) - уже есть структура

**Рекомендация:**
- ✅ **ПЕРЕМЕСТИТЬ** в [`api/middleware/internal_auth.py`](codelab-ai-service/agent-runtime/app/api/middleware/internal_auth.py)
- Обновить импорты в [`main.py`](codelab-ai-service/agent-runtime/app/main.py)

---

## 📊 Сводная таблица

| Файл | Используется | Аналог в новой архитектуре | Действие |
|------|--------------|----------------------------|----------|
| **services/agent_router.py** | ✅ Да | ❌ Нет | ⚠️ Переместить в `domain/services/` |
| **services/database.py** | ✅ Да | ✅ Частично | ⚠️ Разделить на компоненты |
| **services/hitl_manager.py** | ✅ Да | ❌ Нет | ⚠️ Переместить в `domain/services/` |
| **services/hitl_policy_service.py** | ✅ Да | ❌ Нет | ⚠️ Переместить в `domain/services/` |
| **services/llm_proxy_client.py** | ✅ Да | ❌ Нет | ✅ Переместить в `infrastructure/llm/` |
| **services/llm_stream_service.py** | ✅ Да | ❌ Нет | ✅ Переместить в `infrastructure/llm/` |
| **services/multi_agent_orchestrator.py** | ✅ Да | ✅ Частично | ⚠️ Объединить с `domain/services/agent_orchestration.py` |
| **services/retry_service.py** | ✅ Да | ✅ Да | ✅ Удалить (дублируется) |
| **services/tool_parser.py** | ✅ Да | ❌ Нет | ✅ Переместить в `infrastructure/llm/` |
| **services/tool_registry.py** | ✅ Да | ❌ Нет | ⚠️ Переместить в `domain/services/` или `infrastructure/tools/` |
| **models/hitl_models.py** | ✅ Да | ❌ Нет | ⚠️ Переместить в `domain/entities/` |
| **models/schemas.py** | ✅ Да | ✅ Частично | ⚠️ Разделить на компоненты |
| **middleware/internal_auth.py** | ✅ Да | ✅ Да | ✅ Переместить в `api/middleware/` |

---

## 🎯 План миграции (приоритеты)

### Высокий приоритет (простые переносы)

1. ✅ **Переместить middleware/internal_auth.py**
   ```
   middleware/internal_auth.py → api/middleware/internal_auth.py
   ```

2. ✅ **Переместить LLM компоненты в infrastructure/llm/**
   ```
   services/llm_proxy_client.py → infrastructure/llm/client.py
   services/llm_stream_service.py → infrastructure/llm/streaming.py
   services/tool_parser.py → infrastructure/llm/tool_parser.py
   ```

3. ✅ **Удалить дублирующийся retry_service.py**
   ```
   services/retry_service.py → УДАЛИТЬ
   Обновить импорты: infrastructure/resilience/retry_handler.py
   ```

### Средний приоритет (требуют анализа)

4. ⚠️ **Разделить database.py**
   ```
   services/database.py:
   - Модели → infrastructure/persistence/models/
   - DatabaseService → infrastructure/persistence/database.py
   - Функции init/get_db → infrastructure/persistence/database.py
   ```

5. ⚠️ **Переместить HITL компоненты**
   ```
   models/hitl_models.py → domain/entities/hitl.py
   services/hitl_manager.py → domain/services/hitl_management.py
   services/hitl_policy_service.py → domain/services/hitl_policy.py
   ```

6. ⚠️ **Разделить schemas.py**
   ```
   models/schemas.py:
   - Message, ToolCall → domain/entities/ (проверить дублирование)
   - StreamChunk → api/v1/schemas/stream_schemas.py
   - AgentStreamRequest → api/v1/schemas/ (уже есть)
   - AgentInfo → api/v1/schemas/ (уже есть)
   ```

### Низкий приоритет (требуют рефакторинга)

7. ⚠️ **Рефакторить agent_router.py**
   ```
   services/agent_router.py → domain/services/agent_registry.py
   Переименовать: AgentRouter → AgentRegistry
   ```

8. ⚠️ **Объединить orchestrator сервисы**
   ```
   services/multi_agent_orchestrator.py + domain/services/agent_orchestration.py
   → domain/services/agent_orchestration.py (единый сервис)
   ```

9. ⚠️ **Переместить tool_registry.py**
   ```
   services/tool_registry.py → domain/services/tool_registry.py
   или → infrastructure/tools/registry.py
   (требует решения: domain или infrastructure?)
   ```

---

## ✅ Заключение

**Все legacy компоненты активно используются** и требуют миграции, а не удаления.

**Статистика:**
- ✅ **Используются:** 13/13 файлов (100%)
- ❌ **Не используются:** 0 файлов
- ⚠️ **Требуют переноса:** 10 файлов
- ✅ **Можно удалить (дублируются):** 1 файл ([`retry_service.py`](codelab-ai-service/agent-runtime/app/services/retry_service.py))
- ⚠️ **Требуют разделения:** 2 файла ([`database.py`](codelab-ai-service/agent-runtime/app/services/database.py), [`schemas.py`](codelab-ai-service/agent-runtime/app/models/schemas.py))

**Рекомендация:** Выполнить миграцию поэтапно согласно приоритетам выше для достижения 100% соответствия целевой архитектуре.
