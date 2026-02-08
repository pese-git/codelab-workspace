# 📋 Анализ зависимостей Legacy кода - Фаза 10.4

**Дата:** 6 февраля 2026  
**Статус:** ✅ Завершен

---

## 🎯 Цель

Найти все места использования legacy кода перед удалением.

---

## 📊 Результаты анализа

### 1. Legacy Entities

#### `app/domain/entities/session.py`

**Использование:**
- `app/agents/universal_agent.py` - импорт `Session`
- `app/agents/base_agent.py` - импорт `Session`
- `app/agents/architect_agent.py` - импорт `Session`
- `app/agents/ask_agent.py` - импорт `Session`
- `app/agents/coder_agent.py` - импорт `Session`
- `app/agents/debug_agent.py` - импорт `Session`
- `app/agents/orchestrator_agent.py` - импорт `Session`
- Backup файлы: `orchestrator_agent.py.bak`, `orchestrator_agent.py.bak2`, `orchestrator_agent.py.backup`

**Статус:** ⚠️ Используется в agents (но agents используют адаптеры)

#### `app/domain/entities/agent_context.py`

**Использование:**
- `app/infrastructure/persistence/mappers/plan_mapper.py` - импорт `AgentType`
- `app/domain/execution_context/services/subtask_executor.py` - импорт `AgentType`
- `app/domain/services/subtask_executor.py` - импорт `AgentType`

**Статус:** ⚠️ Используется `AgentType` enum

**Замена:** `app/domain/agent_context/value_objects/agent_capabilities.py` содержит новый `AgentType`

#### `app/domain/entities/execution_plan.py`

**Использование:** Не найдено прямых импортов

**Статус:** ✅ Можно удалить

---

### 2. Legacy Repositories

#### `app/domain/repositories/session_repository.py`

**Использование:** Не найдено

**Статус:** ✅ Можно удалить

#### `app/domain/repositories/agent_context_repository.py`

**Использование:** Не найдено

**Статус:** ✅ Можно удалить

#### `app/domain/repositories/plan_repository.py`

**Использование:**
- `app/agents/architect_agent.py` - импорт `PlanRepository`
- `app/application/coordinators/execution_coordinator.py` - импорт `PlanRepository`
- `app/infrastructure/persistence/repositories/plan_repository_impl.py` - импорт `PlanRepository`
- `app/domain/services/execution_engine.py` - импорт `PlanRepository`
- `app/domain/services/subtask_executor.py` - импорт `PlanRepository`

**Статус:** ⚠️ Используется в 5 местах

**Замена:** `app/domain/execution_context/repositories/execution_plan_repository.py`

---

### 3. Legacy Services

#### `app/domain/services/session_management.py`

**Использование:** Не найдено

**Статус:** ✅ Можно удалить

#### `app/domain/services/agent_orchestration.py`

**Использование:** Не найдено

**Статус:** ✅ Можно удалить

#### `app/domain/services/execution_engine.py`

**Использование:**
- `app/agents/orchestrator_agent.py` - импорт `ExecutionResult`
- `app/application/coordinators/execution_coordinator.py` - импорт `ExecutionEngine`, `ExecutionResult`

**Статус:** ⚠️ Используется `ExecutionResult` класс

**Замена:** Нужно проверить, есть ли `ExecutionResult` в новой архитектуре

---

## 🔍 Детальный анализ проблемных мест

### Проблема 1: AgentType enum дублируется

**Места определения:**
1. `app/domain/entities/agent_context.py` - legacy
2. `app/domain/agent_context/value_objects/agent_capabilities.py` - новый
3. `app/agents/base_agent.py` - используется в agents

**Решение:**
- Использовать новый `AgentType` из `agent_capabilities.py`
- Обновить импорты в:
  - `app/infrastructure/persistence/mappers/plan_mapper.py`
  - `app/domain/execution_context/services/subtask_executor.py`
  - `app/domain/services/subtask_executor.py`

---

### Проблема 2: PlanRepository используется

**Места использования:**
1. `app/agents/architect_agent.py` - TYPE_CHECKING импорт
2. `app/application/coordinators/execution_coordinator.py` - TYPE_CHECKING импорт
3. `app/infrastructure/persistence/repositories/plan_repository_impl.py` - наследование
4. `app/domain/services/execution_engine.py` - TYPE_CHECKING импорт
5. `app/domain/services/subtask_executor.py` - использование

**Решение:**
- Заменить на `ExecutionPlanRepository` из `app/domain/execution_context/repositories/`
- Обновить `plan_repository_impl.py` для наследования от нового интерфейса

---

### Проблема 3: ExecutionResult используется

**Места использования:**
1. `app/agents/orchestrator_agent.py` - импорт
2. `app/application/coordinators/execution_coordinator.py` - импорт

**Решение:**
- Проверить, есть ли `ExecutionResult` в новой архитектуре
- Если нет - создать или использовать альтернативу
- Обновить импорты

---

### Проблема 4: Session используется в agents

**Места использования:**
- Все agent файлы импортируют `Session`

**Анализ:**
- Agents используют адаптеры через DI
- Импорты `Session` могут быть для TYPE_CHECKING
- Нужно проверить, действительно ли используется

**Решение:**
- Проверить каждый agent файл
- Заменить на `Conversation` если используется
- Удалить импорт если только TYPE_CHECKING

---

## 📋 План действий

### Шаг 1: Обновить импорты AgentType (3 файла)

```bash
# Заменить импорты
app/infrastructure/persistence/mappers/plan_mapper.py
app/domain/execution_context/services/subtask_executor.py
app/domain/services/subtask_executor.py
```

**Замена:**
```python
# Было:
from app.domain.entities.agent_context import AgentType

# Стало:
from app.domain.agent_context.value_objects.agent_capabilities import AgentType
```

---

### Шаг 2: Обновить импорты PlanRepository (5 файлов)

```bash
# Заменить импорты
app/agents/architect_agent.py
app/application/coordinators/execution_coordinator.py
app/infrastructure/persistence/repositories/plan_repository_impl.py
app/domain/services/execution_engine.py
app/domain/services/subtask_executor.py
```

**Замена:**
```python
# Было:
from app.domain.repositories.plan_repository import PlanRepository

# Стало:
from app.domain.execution_context.repositories.execution_plan_repository import ExecutionPlanRepository
```

---

### Шаг 3: Обновить импорты ExecutionResult (2 файла)

```bash
# Проверить и заменить
app/agents/orchestrator_agent.py
app/application/coordinators/execution_coordinator.py
```

**Действие:** Найти новый `ExecutionResult` или создать

---

### Шаг 4: Обновить импорты Session в agents (7 файлов)

```bash
# Проверить использование
app/agents/universal_agent.py
app/agents/base_agent.py
app/agents/architect_agent.py
app/agents/ask_agent.py
app/agents/coder_agent.py
app/agents/debug_agent.py
app/agents/orchestrator_agent.py
```

**Действие:** Заменить на `Conversation` или удалить

---

### Шаг 5: Удалить backup файлы

```bash
rm app/agents/orchestrator_agent.py.bak
rm app/agents/orchestrator_agent.py.bak2
rm app/agents/orchestrator_agent.py.backup
```

---

### Шаг 6: Удалить legacy entities

```bash
rm app/domain/entities/session.py
rm app/domain/entities/agent_context.py
# execution_plan.py - проверить, не используется ли Plan entity
```

---

### Шаг 7: Удалить legacy repositories

```bash
rm app/domain/repositories/session_repository.py
rm app/domain/repositories/agent_context_repository.py
rm app/domain/repositories/plan_repository.py
```

---

### Шаг 8: Удалить legacy services

```bash
# Проверить, что не используются
rm app/domain/services/session_management.py  # если существует
rm app/domain/services/agent_orchestration.py  # если существует
# execution_engine.py - оставить, используется
```

---

## ⚠️ Риски

### Риск 1: ExecutionResult может не существовать в новой архитектуре

**Митигация:** Проверить перед удалением, создать если нужно

### Риск 2: plan_repository_impl.py наследуется от legacy

**Митигация:** Обновить наследование на новый интерфейс

### Риск 3: Agents могут использовать Session напрямую

**Митигация:** Проверить каждый файл перед удалением

---

## 📊 Статистика

| Категория | Файлов для обновления | Файлов для удаления |
|-----------|----------------------|---------------------|
| Entities | 3 (AgentType) | 2-3 |
| Repositories | 5 (PlanRepository) | 3 |
| Services | 2 (ExecutionResult) | 2-3 |
| Agents | 7 (Session) | 3 (backup) |
| **Итого** | **17** | **10-12** |

---

## ✅ Следующие шаги

1. ✅ Анализ завершен
2. ⏳ Начать обновление импортов
3. ⏳ Удалить legacy код
4. ⏳ Тестирование

---

**Время анализа:** 15 минут  
**Готовность к удалению:** 80% (нужны небольшие правки)
