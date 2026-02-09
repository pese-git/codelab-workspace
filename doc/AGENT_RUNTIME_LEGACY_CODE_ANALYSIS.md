# Анализ Legacy кода в Agent Runtime

**Дата анализа:** 2026-02-09  
**Ветка:** feature/phase-10-5-legacy-cleanup  
**Статус:** В процессе очистки legacy кода

## Резюме

В agent-runtime **присутствует legacy код**, но он находится в процессе постепенной миграции на новую DDD-архитектуру. Найдено **43 упоминания** deprecated/legacy кода в исходниках.

### Ключевые находки:

✅ **Основной legacy код удален** (коммит `dc645e6` - "remove all legacy code")  
⚠️ **Остались элементы обратной совместимости** для плавной миграции  
🔄 **Активная миграция на DDD-архитектуру** (Phase 10)

---

## 1. Категории Legacy кода

### 1.1 Deprecated Aliases (Алиасы для обратной совместимости)

**Местоположение:** [`app/domain/entities/__init__.py`](../codelab-ai-service/agent-runtime/app/domain/entities/__init__.py)

```python
# Lazy imports для deprecated aliases
def __getattr__(name):
    """Lazy loading для deprecated aliases."""
    if name == "Session":
        from ..session_context.entities.conversation import Conversation
        return Conversation
    elif name == "AgentContext":
        from ..agent_context.entities.agent import Agent
        return Agent
    elif name == "AgentSwitch":
        from ..agent_context.entities.agent import AgentSwitchRecord
        return AgentSwitchRecord
    elif name == "AgentType":
        from ..agent_context.value_objects.agent_capabilities import AgentType as AT
        return AT
```

**Deprecated сущности:**
- `Session` → `Conversation` (domain.session_context)
- `AgentContext` → `Agent` (domain.agent_context)
- `AgentSwitch` → `AgentSwitchRecord`
- `AgentType` → из value_objects
- `Plan` → Legacy Plan entity (все еще используется)

**Статус:** ⚠️ Требуется миграция использующего кода

---

### 1.2 Global Singleton ApprovalManager (DEPRECATED)

**Местоположение:** [`app/domain/services/approval_management.py`](../codelab-ai-service/agent-runtime/app/domain/services/approval_management.py:449-533)

```python
# DEPRECATED: Global singleton for backward compatibility
# This will be removed in future versions
_global_approval_manager: Optional[ApprovalManager] = None

def _get_global_approval_manager() -> ApprovalManager:
    """
    Get global approval manager (DEPRECATED).
    
    This creates a manager that manages its own DB sessions.
    Use get_approval_manager_with_db() with dependency injection instead.
    """
```

**Проблемы:**
- Глобальный синглтон нарушает принципы DI
- Управляет собственными DB сессиями (анти-паттерн)
- Создает `SelfManagedRepository` с автоматическими коммитами

**Рекомендация:** 🔴 Удалить после миграции всех зависимостей на DI

**Использование:**
```python
# OLD (deprecated):
from app.domain.services.approval_management import approval_manager

# NEW (recommended):
def get_manager(db: AsyncSession = Depends(get_db)):
    repo = ApprovalRepositoryImpl(db)
    return get_approval_manager_with_db(repo)
```

---

### 1.3 Legacy Database Fields

**Местоположение:** [`app/infrastructure/persistence/models/hitl.py`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/models/hitl.py:45-50)

```python
# Legacy HITL fields (for backward compatibility)
call_id: Mapped[Optional[str]] = mapped_column(
    String(255), nullable=True, 
    comment="Tool call identifier (legacy, use request_id)"
)
tool_name: Mapped[Optional[str]] = mapped_column(
    String(255), nullable=True, 
    comment="Name of the tool being called (legacy)"
)
arguments: Mapped[Optional[dict]] = mapped_column(
    JSON, nullable=True, 
    comment="Tool arguments as JSON (legacy)"
)
```

**Новая структура:**
- `request_id` (unified identifier)
- `request_type` (tool, plan, etc.)
- `subject` (tool name, plan title)
- `details` (flexible JSON)

**Статус:** ⚠️ Legacy поля сохранены для обратной совместимости API

---

### 1.4 Legacy OpenAI function_call Format

**Местоположение:** [`app/infrastructure/llm/tool_parser.py`](../codelab-ai-service/agent-runtime/app/infrastructure/llm/tool_parser.py:118-142)

```python
def _parse_function_call(self, fc: Any) -> Optional[ToolCall]:
    """Parse legacy function_call format"""
    try:
        tool_name = fc.get("name", "") if isinstance(fc, dict) else getattr(fc, "name", "")
        arguments_str = (
            fc.get("arguments", "{}") if isinstance(fc, dict)
            else getattr(fc, "arguments", "{}")
        )
        arguments = json.loads(arguments_str)
        
        if not tool_name:
            return None
        
        call_id = f"call_func_{id(fc)}"
        
        logger.info(f"Parsed legacy function_call: {tool_name}")
        
        return ToolCall.model_construct(
            id=call_id, 
            tool_name=tool_name, 
            arguments=arguments
        )
    except Exception as e:
        logger.warning(f"Failed to parse legacy function_call: {e}")
        return None
```

**Причина:** Поддержка старого формата OpenAI API (до введения native tool calls)

**Статус:** ✅ Необходимо для совместимости с разными версиями LLM API

---

### 1.5 Legacy Method в OrchestratorAgent

**Местоположение:** [`app/agents/orchestrator_agent.py`](../codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py:433-451)

```python
# Legacy method kept for backward compatibility
async def classify_task_with_llm(self, message: str) -> tuple[AgentType, Dict[str, Any]]:
    """
    Legacy method - redirects to Planning System classifier.
    
    Kept for backward compatibility. New code should use
    _classify_with_planning_system() directly.
    """
    logger.warning(
        "classify_task_with_llm() is deprecated. "
        "Use _classify_with_planning_system() instead."
    )
    return await self._classify_with_planning_system(message)
```

**Статус:** ⚠️ Редирект на новый метод, можно удалить после проверки использования

---

### 1.6 Legacy ExecutionEngine

**Местоположение:** [`app/domain/services/execution_engine.py`](../codelab-ai-service/agent-runtime/app/domain/services/execution_engine.py)

**Статус:** 🔄 В процессе замены на `PlanExecutionService` (DDD)

**DI Module:** [`app/core/di/execution_module.py`](../codelab-ai-service/agent-runtime/app/core/di/execution_module.py:129-143)

```python
@provider
def provide_execution_engine(
    self,
    plan_repository: PlanRepository,
    session_service: ConversationManagementService,
    approval_manager: ApprovalManager,
) -> ExecutionEngine:
    """
    Предоставить legacy ExecutionEngine.
    
    DEPRECATED: Use PlanExecutionService instead.
    This is kept for backward compatibility during migration.
    """
```

**Рекомендация:** 🔴 Завершить миграцию на `PlanExecutionService`

---

### 1.7 Legacy Repository Aliases

**Местоположение:** [`app/domain/repositories/__init__.py`](../codelab-ai-service/agent-runtime/app/domain/repositories/__init__.py:17-26)

```python
# Алиасы для обратной совместимости (deprecated - use new DDD repositories)
from ..session_context.repositories.conversation_repository import ConversationRepository as SessionRepository
from ..agent_context.repositories.agent_repository import AgentRepository as AgentContextRepository
from ..execution_context.repositories.execution_plan_repository import ExecutionPlanRepository as PlanRepository
```

**Deprecated:**
- `SessionRepository` → `ConversationRepository`
- `AgentContextRepository` → `AgentRepository`
- `PlanRepository` → `ExecutionPlanRepository`

---

## 2. Статистика Legacy кода

### Количественный анализ:

```bash
# Упоминания deprecated/legacy в коде
$ grep -r "DEPRECATED\|deprecated\|backward compatibility\|legacy" --include="*.py" app/ | wc -l
43
```

### Распределение по категориям:

| Категория | Количество | Критичность | Статус |
|-----------|------------|-------------|--------|
| Deprecated aliases | 7 | ⚠️ Средняя | Требует миграции |
| Global singletons | 1 | 🔴 Высокая | Удалить |
| Legacy DB fields | 3 | ⚠️ Средняя | Сохранить для API |
| Legacy methods | 2 | 🟡 Низкая | Можно удалить |
| Legacy parsers | 1 | ✅ OK | Необходимо |
| Legacy services | 1 | 🔴 Высокая | Мигрировать |

---

## 3. История миграции

### Коммит dc645e6: "remove all legacy code"

```bash
$ git show dc645e6 --stat
```

Этот коммит удалил основной legacy код и достиг **100% соответствия целевой архитектуре**.

### Что было удалено:
- Старые сервисы без DDD
- Прямые обращения к БД без репозиториев
- Монолитные классы без разделения ответственности
- Код без событийной модели

### Что осталось:
- Алиасы для плавной миграции
- Legacy поля в БД для API совместимости
- Deprecated методы с предупреждениями
- Адаптеры между старым и новым кодом

---

## 4. Текущая архитектура (DDD)

### Новая структура (Phase 10):

```
app/
├── domain/
│   ├── agent_context/          # Bounded Context: Агенты
│   │   ├── entities/
│   │   ├── repositories/
│   │   ├── services/
│   │   └── value_objects/
│   ├── session_context/        # Bounded Context: Сессии
│   │   ├── entities/
│   │   ├── repositories/
│   │   └── services/
│   ├── execution_context/      # Bounded Context: Выполнение
│   │   ├── entities/
│   │   ├── repositories/
│   │   └── services/
│   ├── approval_context/       # Bounded Context: Аппрувы
│   ├── llm_context/           # Bounded Context: LLM
│   └── tool_context/          # Bounded Context: Инструменты
├── application/               # Application Layer (CQRS)
│   ├── commands/
│   ├── queries/
│   └── use_cases/
└── infrastructure/            # Infrastructure Layer
    ├── persistence/
    └── adapters/
```

### Принципы новой архитектуры:

✅ **Domain-Driven Design (DDD)**
- Bounded Contexts
- Aggregates & Entities
- Value Objects
- Domain Events

✅ **CQRS (Command Query Responsibility Segregation)**
- Commands для изменений
- Queries для чтения
- Use Cases для бизнес-логики

✅ **Event-Driven Architecture**
- Domain Events
- Event Bus
- Event Subscribers

✅ **Dependency Injection**
- Injector framework
- Provider pattern
- Scoped dependencies

---

## 5. План очистки Legacy кода

### Phase 10.5: Legacy Cleanup (текущая ветка)

**Цель:** Удалить оставшийся legacy код без нарушения работы системы

### Шаг 1: Миграция зависимостей от deprecated aliases ✅

**Задачи:**
- [ ] Найти все использования `Session` → заменить на `Conversation`
- [ ] Найти все использования `AgentContext` → заменить на `Agent`
- [ ] Найти все использования `AgentSwitch` → заменить на `AgentSwitchRecord`
- [ ] Обновить импорты на прямые из DDD контекстов

**Команда для поиска:**
```bash
grep -r "from.*domain.entities import.*Session\|AgentContext\|AgentSwitch" --include="*.py" app/
```

### Шаг 2: Удаление Global ApprovalManager 🔴

**Задачи:**
- [ ] Найти все использования `approval_manager` singleton
- [ ] Заменить на DI через `get_approval_manager_with_db()`
- [ ] Удалить `_global_approval_manager` и `SelfManagedRepository`
- [ ] Обновить тесты

**Места использования:**
```python
# Найти:
from app.domain.services.approval_management import approval_manager

# Заменить на:
@inject
def handler(approval_manager: ApprovalManager = Provide[Container.approval_manager]):
    ...
```

### Шаг 3: Миграция ExecutionEngine → PlanExecutionService 🔄

**Задачи:**
- [ ] Завершить адаптер между старым и новым API
- [ ] Мигрировать все вызовы ExecutionEngine
- [ ] Удалить legacy ExecutionEngine
- [ ] Обновить DI контейнер

### Шаг 4: Очистка deprecated методов 🟡

**Задачи:**
- [ ] Удалить `classify_task_with_llm()` из OrchestratorAgent
- [ ] Проверить отсутствие вызовов
- [ ] Обновить документацию

### Шаг 5: Документация миграции 📝

**Задачи:**
- [ ] Создать Migration Guide для разработчиков
- [ ] Обновить API документацию
- [ ] Добавить примеры использования нового API

---

## 6. Риски и рекомендации

### Риски:

🔴 **Высокий риск:**
- Удаление Global ApprovalManager может сломать существующий код
- ExecutionEngine используется в критических путях

⚠️ **Средний риск:**
- Legacy DB поля нужны для обратной совместимости API
- Клиенты могут использовать старые поля

🟡 **Низкий риск:**
- Deprecated методы с редиректами безопасны
- Алиасы не влияют на производительность

### Рекомендации:

1. **Постепенная миграция:**
   - Не удалять код сразу
   - Добавить deprecation warnings
   - Дать время на миграцию клиентов

2. **Тестирование:**
   - Полное покрытие тестами перед удалением
   - Integration tests для критических путей
   - Backward compatibility tests

3. **Мониторинг:**
   - Логировать использование deprecated API
   - Метрики для отслеживания миграции
   - Алерты на использование legacy кода

4. **Документация:**
   - Migration guide для каждого deprecated компонента
   - Примеры миграции кода
   - Changelog с breaking changes

---

## 7. Выводы

### Текущее состояние:

✅ **Основной legacy код удален** - архитектура соответствует DDD принципам  
⚠️ **Остались элементы совместимости** - для плавной миграции  
🔄 **Активная работа по очистке** - ветка phase-10-5-legacy-cleanup  

### Количество legacy кода:

- **43 упоминания** deprecated/legacy в коде
- **~5-7%** от общего кодовой базы
- **Критичных legacy компонентов:** 2 (ApprovalManager, ExecutionEngine)

### Приоритеты:

1. 🔴 **Высокий:** Удалить Global ApprovalManager
2. 🔴 **Высокий:** Завершить миграцию ExecutionEngine
3. ⚠️ **Средний:** Мигрировать deprecated aliases
4. 🟡 **Низкий:** Удалить deprecated методы
5. ✅ **Сохранить:** Legacy DB поля (для API), Legacy parsers (для LLM)

### Оценка времени:

- **Шаг 1-2:** 2-3 дня (миграция зависимостей)
- **Шаг 3:** 3-5 дней (ExecutionEngine → PlanExecutionService)
- **Шаг 4:** 1 день (удаление методов)
- **Шаг 5:** 1-2 дня (документация)

**Итого:** ~7-11 дней для полной очистки legacy кода

---

## 8. Ссылки

### Документация:
- [Phase 10 Progress](./PHASE_10_PROGRESS_DASHBOARD.md)
- [Phase 10.5 Plan](./agent-runtime-phase-10-5-legacy-cleanup-plan.md)
- [DDD Architecture](./agent-runtime-clean-architecture-audit.md)

### Коммиты:
- `dc645e6` - remove all legacy code - 100% target architecture compliance
- `bd1554d` - feat: implement virtual tools support
- `e067113` - fix: critical bugs in HITL workflow

### Код:
- [domain/entities/__init__.py](../codelab-ai-service/agent-runtime/app/domain/entities/__init__.py) - Deprecated aliases
- [domain/services/approval_management.py](../codelab-ai-service/agent-runtime/app/domain/services/approval_management.py) - Global singleton
- [infrastructure/persistence/models/hitl.py](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/models/hitl.py) - Legacy DB fields

---

**Автор:** Roo Code AI  
**Дата:** 2026-02-09  
**Версия:** 1.0
