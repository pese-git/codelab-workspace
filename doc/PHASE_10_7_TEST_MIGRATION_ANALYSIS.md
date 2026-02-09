# Phase 10.7: Анализ миграции тестов

**Дата:** 2026-02-09  
**Статус:** В процессе  
**Цель:** Исправить 131 упавший тест после рефакторинга Phase 10.5 & 10.6

## 📊 Текущая ситуация

### Результаты тестирования
```
131 failed, 729 passed, 5 skipped, 399 warnings in 53.76s
```

- ✅ **84.3% тестов работают** (729/865)
- ❌ **15.1% тестов упали** (131/865)
- ⚠️ **399 Pydantic warnings** (deprecated Config)

## 🔍 Анализ проблем

### Проблема #1: Value Objects API изменился

**Старый API (позиционные аргументы):**
```python
agent_id = AgentId("coder")
subtask_id = SubtaskId("subtask-1")
plan_id = PlanId("plan-1")
conversation_id = ConversationId("test-session")
```

**Новый API (именованные параметры):**
```python
agent_id = AgentId(value="coder")
subtask_id = SubtaskId(value="subtask-1")
plan_id = PlanId(value="plan-1")
conversation_id = ConversationId(value="test-session")
```

**Причина:** Value Objects теперь наследуются от Pydantic BaseModel, который требует именованные параметры.

### Проблема #2: Pydantic Config deprecated

**Старый стиль:**
```python
class Entity(BaseModel):
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {...}
```

**Новый стиль:**
```python
from pydantic import ConfigDict

class Entity(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        ser_json_timedelta='float'
    )
```

## 📋 Категории упавших тестов

### 1. Execution Context (19 тестов)
- `test_entities.py`: 3 failed
  - `test_plan_with_multiple_subtasks`
  - `test_domain_events_are_collected`
  - `test_clear_domain_events`
  - `test_complete_plan_lifecycle`
  - `test_plan_lifecycle_with_subtask_failure`

- `test_services.py`: 11 failed
  - Все тесты `DependencyResolver`

- `test_value_objects.py`: 1 failed
  - `test_all_subtask_statuses_exist`

### 2. Session Context (7 тестов)
- `test_conversation.py`: 4 failed
  - `test_create_conversation`
  - `test_create_generates_event`
  - `test_add_message_generates_event`
  - `test_deactivate_generates_event`
  - `test_clear_messages_generates_event`

- `test_conversation_id.py`: 5 failed
  - `test_empty_id_raises_error`
  - `test_too_long_id_raises_error`
  - `test_invalid_characters_raise_error`
  - `test_equality`
  - `test_inequality`
  - `test_can_use_in_set`

### 3. Infrastructure (20 тестов)
- `test_execution_plan_mapper.py`: 1 failed
  - `test_roundtrip_conversion`

- `test_unit_of_work.py`: 19 failed
  - Все тесты SSEUnitOfWork

### 4. Остальные тесты (~84 теста)
- Integration tests
- Application layer tests
- FSM tests
- Event-driven tests
- И другие

## 🎯 План исправления

### Этап 1: Массовая замена Value Objects (приоритет: HIGH)
Использовать regex для замены во всех тестах:

```bash
# AgentId
AgentId\("([^"]+)"\) → AgentId(value="$1")

# SubtaskId
SubtaskId\("([^"]+)"\) → SubtaskId(value="$1")

# PlanId
PlanId\("([^"]+)"\) → PlanId(value="$1")

# ConversationId
ConversationId\("([^"]+)"\) → ConversationId(value="$1")

# ToolName
ToolName\("([^"]+)"\) → ToolName(value="$1")
```

### Этап 2: Исправить Pydantic warnings (приоритет: MEDIUM)
Заменить `class Config` на `model_config = ConfigDict(...)` в:
- `app/domain/shared/base_entity.py`
- `app/domain/events/base.py`
- `app/domain/entities/base.py`
- `app/domain/entities/hitl.py`
- `app/domain/entities/approval.py`
- `app/events/base_event.py`
- `app/api/v1/schemas/*.py`

### Этап 3: Проверить специфичные тесты (приоритет: LOW)
- Тесты, которые могут требовать дополнительных изменений
- Integration tests с реальными зависимостями

## 📈 Ожидаемые результаты

После исправления:
- ✅ **100% тестов работают** (865/865)
- ✅ **0 Pydantic warnings**
- ✅ **Все тесты используют новый API**

## 🚀 Следующие шаги

1. ✅ Создать анализ проблем
2. ⏳ Выполнить массовую замену Value Objects
3. ⏳ Исправить Pydantic warnings
4. ⏳ Запустить полное тестирование
5. ⏳ Создать финальный отчет
