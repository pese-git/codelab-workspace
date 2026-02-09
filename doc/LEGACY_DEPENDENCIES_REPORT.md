# Отчет о зависимостях Legacy кода

**Дата анализа:** 2026-02-09
**Ветка:** feature/phase-10-5-legacy-cleanup
**Базовый документ:** [AGENT_RUNTIME_LEGACY_CODE_ANALYSIS.md](./AGENT_RUNTIME_LEGACY_CODE_ANALYSIS.md)

## Резюме

Проведен детальный анализ использования legacy компонентов в кодовой базе agent-runtime. Найдены конкретные места использования deprecated aliases, global singleton, legacy сервисов и **legacy Plan entity**.

### ⚠️ ВАЖНО: Legacy Plan Entity

Обнаружена **критическая legacy сущность**:
- **Legacy:** [`app/domain/entities/plan.py`](../codelab-ai-service/agent-runtime/app/domain/entities/plan.py) - 483 строки
- **New DDD:** [`app/domain/execution_context/entities/execution_plan.py`](../codelab-ai-service/agent-runtime/app/domain/execution_context/entities/execution_plan.py) - 391 строка

**Использование legacy Plan:**
- 7 файлов импортируют `from app.domain.entities.plan import Plan`
- Включая `execution_engine.py` (который тоже legacy)
- Требуется полная миграция на `ExecutionPlan`

---

## 1. Deprecated Aliases

### 1.1 SessionRepository / AgentContextRepositoryImpl

**Статус:** ⚠️ Используются алиасы в infrastructure layer

**Найденные использования:**

#### Файл: [`app/main.py:91`](../codelab-ai-service/agent-runtime/app/main.py:91)
```python
AgentContextRepositoryImpl
```
**Контекст:** Импорт в main.py  
**Сложность миграции:** Низкая  
**Действие:** Заменить на `AgentRepositoryImpl`

#### Файл: [`app/infrastructure/persistence/repositories/__init__.py`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/repositories/__init__.py)
```python
# Строки 21-22:
SessionRepositoryImpl = ConversationRepositoryImpl
AgentContextRepositoryImpl = AgentRepositoryImpl

# Строки 31-32 в __all__:
"SessionRepositoryImpl",
"AgentContextRepositoryImpl",
```
**Контекст:** Алиасы для обратной совместимости  
**Сложность миграции:** Низкая  
**Действие:** Удалить алиасы после миграции main.py

#### Файл: [`app/domain/repositories/__init__.py`](../codelab-ai-service/agent-runtime/app/domain/repositories/__init__.py)
```python
# Строки 18-19:
from ..session_context.repositories.conversation_repository import ConversationRepository as SessionRepository
from ..agent_context.repositories.agent_repository import AgentRepository as AgentContextRepository

# Строки 26-27 в __all__:
"SessionRepository",  # Use ConversationRepository from domain.session_context
"AgentContextRepository",  # Use AgentRepository from domain.agent_context
```
**Контекст:** Алиасы в domain layer  
**Сложность миграции:** Низкая  
**Действие:** Удалить алиасы

### 1.2 Session / AgentContext в комментариях

**Статус:** 🟡 Только в docstrings и комментариях

**Найденные использования:**

Файлы с упоминаниями в docstrings (не требуют изменения кода, только документации):
- [`app/agents/universal_agent.py:57,65,69`](../codelab-ai-service/agent-runtime/app/agents/universal_agent.py)
- [`app/agents/base_agent.py:83,87`](../codelab-ai-service/agent-runtime/app/agents/base_agent.py)
- [`app/agents/architect_agent.py:70,78,82,154,269`](../codelab-ai-service/agent-runtime/app/agents/architect_agent.py)
- [`app/agents/ask_agent.py:59,67,71`](../codelab-ai-service/agent-runtime/app/agents/ask_agent.py)
- [`app/agents/coder_agent.py:56,64,68`](../codelab-ai-service/agent-runtime/app/agents/coder_agent.py)
- [`app/agents/debug_agent.py:59,67,71`](../codelab-ai-service/agent-runtime/app/agents/debug_agent.py)
- [`app/agents/orchestrator_agent.py:167`](../codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py)

**Действие:** Обновить docstrings: `Session` → `Conversation`

### 1.3 AgentContext в типах

**Статус:** ⚠️ Используется в DTO и mappers

**Найденные использования:**

#### Файл: [`app/api/v1/schemas/agent_schemas.py:43`](../codelab-ai-service/agent-runtime/app/api/v1/schemas/agent_schemas.py:43)
```python
context: AgentContextDTO = Field(description="Данные контекста агента")
```
**Контекст:** API schema  
**Сложность миграции:** Низкая  
**Действие:** Проверить что `AgentContextDTO` не использует deprecated типы

#### Файл: [`app/application/dto/agent_context_dto.py:108`](../codelab-ai-service/agent-runtime/app/application/dto/agent_context_dto.py:108)
```python
context: AgentContext,
```
**Контекст:** DTO mapper  
**Сложность миграции:** Средняя  
**Действие:** Проверить импорты и заменить на `Agent` если используется deprecated alias

#### Файлы: mappers
- [`app/infrastructure/persistence/mappers/agent_mapper.py:38`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/mappers/agent_mapper.py:38)
- [`app/infrastructure/persistence/mappers/agent_context_mapper.py:37,152`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/mappers/agent_context_mapper.py)

**Контекст:** Persistence mappers  
**Сложность миграции:** Средняя  
**Действие:** Проверить что используются правильные типы из DDD контекстов

---

## 2. Global ApprovalManager Singleton

**Статус:** 🔴 Активно используется в критических компонентах

### 2.1 Использование через self._approval_manager

**Найденные использования:**

#### Файл: [`app/application/handlers/stream_llm_response_handler.py:308`](../codelab-ai-service/agent-runtime/app/application/handlers/stream_llm_response_handler.py:308)
```python
await self._approval_manager.add_pending(
```
**Контекст:** Stream handler для LLM ответов  
**Сложность миграции:** Высокая  
**Действие:** Инжектировать ApprovalManager через конструктор

#### Файл: [`app/domain/services/tool_result_handler.py`](../codelab-ai-service/agent-runtime/app/domain/services/tool_result_handler.py)
```python
# Строка 116:
pending = await self._approval_manager.get_pending(call_id)

# Строка 121:
await self._approval_manager.reject(call_id, reason=f"Tool execution failed: {error}")

# Строка 127:
await self._approval_manager.approve(call_id)
```
**Контекст:** Tool result handler  
**Сложность миграции:** Высокая  
**Действие:** Инжектировать ApprovalManager через конструктор

#### Файл: [`app/domain/services/plan_approval_handler.py`](../codelab-ai-service/agent-runtime/app/domain/services/plan_approval_handler.py)
```python
# Строка 127:
pending_approval = await self._approval_manager.get_pending(approval_request_id)

# Строка 182:
await self._approval_manager.approve(approval_request_id)

# Строка 271:
await self._approval_manager.reject(approval_request_id, reason=feedback)

# Строка 319:
await self._approval_manager.reject(
```
**Контекст:** Plan approval handler  
**Сложность миграции:** Высокая  
**Действие:** Инжектировать ApprovalManager через конструктор

#### Файл: [`app/domain/services/hitl_decision_handler.py`](../codelab-ai-service/agent-runtime/app/domain/services/hitl_decision_handler.py)
```python
# Строка 112:
pending_approval = await self._approval_manager.get_pending(call_id)

# Строки 140-146:
logger.info(f"[DEBUG] Calling approval_manager.reject() for call_id={call_id}")
await self._approval_manager.reject(call_id, reason=feedback)
logger.info(f"[DEBUG] approval_manager.reject() completed for call_id={call_id}")

logger.info(f"[DEBUG] Calling approval_manager.approve() for call_id={call_id}")
await self._approval_manager.approve(call_id)
logger.info(f"[DEBUG] approval_manager.approve() completed for call_id={call_id}")
```
**Контекст:** HITL decision handler  
**Сложность миграции:** Высокая  
**Действие:** Инжектировать ApprovalManager через конструктор

#### Файл: [`app/domain/services/execution_engine.py:383`](../codelab-ai-service/agent-runtime/app/domain/services/execution_engine.py:383)
```python
current_pending = await self.approval_manager.get_pending_by_session(session_id)
```
**Контекст:** Legacy ExecutionEngine  
**Сложность миграции:** Высокая (будет удален вместе с ExecutionEngine)  
**Действие:** Удалить вместе с ExecutionEngine

### 2.2 Использование в API endpoints

#### Файл: [`app/api/v1/routers/sessions_router.py:447`](../codelab-ai-service/agent-runtime/app/api/v1/routers/sessions_router.py:447)
```python
pending_approvals = await approval_manager.get_all_pending(session_id)
```
**Контекст:** Sessions API endpoint  
**Сложность миграции:** Средняя  
**Действие:** Добавить dependency injection через `Depends(get_approval_manager)`

### 2.3 Использование в агентах

#### Файл: [`app/agents/orchestrator_agent.py:581`](../codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py:581)
```python
await approval_manager.add_pending(
```
**Контекст:** OrchestratorAgent  
**Сложность миграции:** Средняя  
**Действие:** Инжектировать ApprovalManager через конструктор

---

## 3. Legacy ExecutionEngine

**Статус:** 🔴 Используется в DI, но не в агентах напрямую

### 3.1 Использование в DI контейнере

#### Файл: [`app/core/di/execution_module.py`](../codelab-ai-service/agent-runtime/app/core/di/execution_module.py)
```python
# Строка 18:
from app.domain.services import ExecutionEngine

# Строка 32:
- ExecutionEngine (legacy)

# Строка 41:
self._execution_engine: Optional[ExecutionEngine] = None

# Строка 128:
) -> ExecutionEngine:

# Строка 130:
Предоставить legacy ExecutionEngine.

# Строка 142:
ExecutionEngine: Legacy engine

# Строка 162:
self._execution_engine = ExecutionEngine(
```
**Контекст:** DI module для execution  
**Сложность миграции:** Высокая  
**Действие:** Удалить provider для ExecutionEngine, оставить только PlanExecutionService

### 3.2 Использование в импортах

#### Файл: [`app/domain/services/__init__.py:16`](../codelab-ai-service/agent-runtime/app/domain/services/__init__.py:16)
```python
from .execution_engine import ExecutionEngine
```
**Контекст:** Экспорт из services  
**Сложность миграции:** Низкая  
**Действие:** Удалить импорт

#### Файл: [`app/agents/orchestrator_agent.py:25`](../codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py:25)
```python
from app.domain.services.execution_engine import ExecutionResult
```
**Контекст:** Импорт только типа ExecutionResult  
**Сложность миграции:** Средняя  
**Действие:** Переместить ExecutionResult в execution_context или использовать новый тип

---

## 4. Приоритеты миграции

### 🔴 Критический приоритет (блокирует удаление legacy кода)

1. **Global ApprovalManager в handlers** (4 файла)
   - `stream_llm_response_handler.py`
   - `tool_result_handler.py`
   - `plan_approval_handler.py`
   - `hitl_decision_handler.py`
   
   **Оценка:** 2-3 дня
   **Риск:** Высокий (критические компоненты HITL)

2. **ExecutionEngine в DI** (1 файл)
   - `execution_module.py`
   
   **Оценка:** 1-2 дня
   **Риск:** Средний (уже есть PlanExecutionService)

3. **Global ApprovalManager в API** (1 файл)
   - `sessions_router.py`
   
   **Оценка:** 0.5 дня
   **Риск:** Низкий (простая замена на Depends)

### ⚠️ Высокий приоритет (нужно для чистоты архитектуры)

4. **Repository aliases в infrastructure** (2 файла)
   - `infrastructure/persistence/repositories/__init__.py`
   - `domain/repositories/__init__.py`
   
   **Оценка:** 0.5 дня
   **Риск:** Низкий

5. **AgentContextRepositoryImpl в main.py** (1 файл)
   - `main.py`
   
   **Оценка:** 0.5 дня
   **Риск:** Низкий

### 🟡 Средний приоритет (улучшение документации)

6. **Session в docstrings** (7 файлов агентов)
   - Все файлы агентов
   
   **Оценка:** 1 день
   **Риск:** Минимальный (только документация)

7. **AgentContext в DTO/mappers** (4 файла)
   - `agent_schemas.py`
   - `agent_context_dto.py`
   - `agent_mapper.py`
   - `agent_context_mapper.py`
   
   **Оценка:** 1 день
   **Риск:** Низкий

---

## 5. План миграции по файлам

### Этап 1: Handlers (2-3 дня)

**Порядок миграции:**

1. `app/application/handlers/stream_llm_response_handler.py`
   - Добавить `approval_manager: ApprovalManager` в конструктор
   - Обновить все места создания handler

2. `app/domain/services/tool_result_handler.py`
   - Добавить `approval_manager: ApprovalManager` в конструктор
   - Обновить DI

3. `app/domain/services/plan_approval_handler.py`
   - Добавить `approval_manager: ApprovalManager` в конструктор
   - Обновить DI

4. `app/domain/services/hitl_decision_handler.py`
   - Добавить `approval_manager: ApprovalManager` в конструктор
   - Обновить DI

### Этап 2: API и агенты (1 день)

5. `app/api/v1/routers/sessions_router.py`
   - Добавить `approval_manager: ApprovalManager = Depends(get_approval_manager)`

6. `app/agents/orchestrator_agent.py`
   - Добавить `approval_manager: ApprovalManager` в конструктор

### Этап 3: ExecutionEngine (1-2 дня)

7. `app/core/di/execution_module.py`
   - Удалить `provide_execution_engine()`
   - Удалить `self._execution_engine`

8. `app/domain/services/__init__.py`
   - Удалить импорт `ExecutionEngine`

9. `app/agents/orchestrator_agent.py`
   - Заменить `ExecutionResult` на новый тип

10. `app/domain/services/execution_engine.py`
    - **УДАЛИТЬ ФАЙЛ**

### Этап 4: Aliases (1 день)

11. `app/main.py`
    - Заменить `AgentContextRepositoryImpl` → `AgentRepositoryImpl`

12. `app/infrastructure/persistence/repositories/__init__.py`
    - Удалить алиасы `SessionRepositoryImpl`, `AgentContextRepositoryImpl`

13. `app/domain/repositories/__init__.py`
    - Удалить алиасы `SessionRepository`, `AgentContextRepository`

14. `app/domain/entities/__init__.py`
    - Удалить `__getattr__` с lazy imports

### Этап 5: Документация (1 день)

15. Обновить docstrings во всех агентах
16. Проверить DTO и mappers
17. Обновить комментарии

---

## 6. Команды для проверки

```bash
# После каждого этапа проверять:

# 1. Нет импортов global singleton
! grep -r "from.*approval_management import approval_manager" --include="*.py" app/

# 2. Нет использования ExecutionEngine
! grep -r "from.*execution_engine import ExecutionEngine" --include="*.py" app/

# 3. Нет deprecated aliases
! grep -r "SessionRepository\|AgentContextRepository" --include="*.py" app/domain/
! grep -r "SessionRepositoryImpl\|AgentContextRepositoryImpl" --include="*.py" app/infrastructure/

# 4. Тесты проходят
pytest tests/ -v

# 5. Код компилируется
python -m py_compile app/**/*.py
```

---

## 7. Оценка времени

| Этап | Файлов | Дней | Риск |
|------|--------|------|------|
| 1. Handlers | 4 | 2-3 | 🔴 Высокий |
| 2. API и агенты | 2 | 1 | ⚠️ Средний |
| 3. ExecutionEngine | 4 | 1-2 | ⚠️ Средний |
| 4. Aliases | 4 | 1 | 🟡 Низкий |
| 5. Документация | 11 | 1 | 🟢 Минимальный |
| **ИТОГО** | **25** | **6-8** | - |

---

## 8. Критические зависимости

### Handlers зависят от:
- `ApprovalManager` (нужен DI)
- `ApprovalRepository` (уже есть)
- `AsyncSession` (уже есть)

### ExecutionEngine зависит от:
- `PlanExecutionService` (уже есть)
- `ExecutionResult` тип (нужно мигрировать)

### Aliases зависят от:
- Миграции всех импортов (нужно сначала заменить использования)

---

## 9. Следующие шаги

1. ✅ **Анализ завершен** - создан детальный отчет
2. 🔄 **Начать Этап 1** - миграция handlers на DI
3. ⏳ **Подготовить тесты** - для проверки после каждого изменения
4. ⏳ **Создать PR** - после завершения каждого этапа

---

**Автор:** Roo Code AI  
**Дата:** 2026-02-09  
**Версия:** 1.0  
**Статус:** ✅ Анализ завершен
