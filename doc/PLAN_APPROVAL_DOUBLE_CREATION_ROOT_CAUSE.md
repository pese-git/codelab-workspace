# Plan Approval Double Creation - Root Cause Analysis

## 🔍 Проблема

При работе с Plan Approval возникали две критические проблемы:

1. **ApprovalManager не инициализирован** - `approval_manager` был `None` в `OrchestratorAgent`
2. **План создавался дважды** - после approval request создавался еще один план

## 🎯 Root Cause Analysis

### Проблема 1: ApprovalManager = None

**Причина:**
```python
# orchestrator_agent.py - set_planning_dependencies()
def set_planning_dependencies(
    self,
    task_classifier: TaskClassifier,
    planner: PlannerAgent,
    subtask_executor: SubtaskExecutor
):
    # approval_manager НЕ передавался!
    self.task_classifier = task_classifier
    self.planner = planner
    self.subtask_executor = subtask_executor
```

**Последствия:**
- `self.approval_manager` оставался `None`
- Невозможно создать approval request
- FSM не переходил в `PLAN_REVIEW`

### Проблема 2: Двойное создание плана

**Причина:**
```python
# orchestrator_agent.py - process()
async for chunk in self._handle_plan_required(session_id, user_message):
    yield chunk  # ❌ is_final не установлен!

# MessageProcessor продолжал обработку:
if not chunk.is_final:
    # Вызывал orchestrator.process() снова!
    async for response_chunk in orchestrator.process(...):
        yield response_chunk
```

**Последствия:**
- После `plan_approval_required` chunk MessageProcessor продолжал работу
- Вызывался `orchestrator.process()` второй раз
- План создавался дважды

## ✅ Решение

### Fix 1: Инжекция ApprovalManager

```python
# orchestrator_agent.py
def set_planning_dependencies(
    self,
    task_classifier: TaskClassifier,
    planner: PlannerAgent,
    subtask_executor: SubtaskExecutor,
    approval_manager: Optional[ApprovalManager] = None  # ✅ Добавлен параметр
):
    self.task_classifier = task_classifier
    self.planner = planner
    self.subtask_executor = subtask_executor
    if approval_manager:
        self.approval_manager = approval_manager  # ✅ Инжектируем

# dependencies.py
def ensure_orchestrator_option2_initialized(...):
    orchestrator.set_planning_dependencies(
        task_classifier=task_classifier,
        planner=planner,
        subtask_executor=subtask_executor,
        approval_manager=approval_manager  # ✅ Передаем
    )
```

### Fix 2: Флаг is_final

```python
# orchestrator_agent.py - _handle_plan_required()
yield StreamChunk(
    type="plan_approval_required",
    content=json.dumps(approval_data),
    is_final=True  # ✅ Устанавливаем флаг завершения
)

# message_processor.py
async for chunk in agent.process(...):
    yield chunk
    
    if chunk.is_final:  # ✅ Проверяем флаг
        logger.info("Agent signaled final chunk, terminating processing")
        return  # ✅ Завершаем обработку
```

## 📊 Результаты

### До исправления:
```
❌ approval_manager = None
❌ План создается 2 раза
❌ Approval request не создается
❌ FSM не переходит в PLAN_REVIEW
```

### После исправления:
```
✅ approval_manager инжектирован через DI
✅ План создается 1 раз
✅ Approval request создается корректно
✅ FSM переходит в PLAN_REVIEW
✅ Ожидает решения пользователя
```

## 🧪 Тестирование

Все тесты прошли успешно:

```bash
# Plan Approval Integration Tests
✅ 11/11 tests passed

# FSM Orchestrator Tests  
✅ 37/37 tests passed

# Message Orchestration Tests
✅ 12/12 tests passed

Total: ✅ 60/60 tests passed
```

## 📝 Измененные файлы

1. [`orchestrator_agent.py`](../codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py:1)
   - Расширен `set_planning_dependencies()` для приема `approval_manager`
   - Добавлен `is_final=True` в `plan_approval_required` chunk

2. [`dependencies.py`](../codelab-ai-service/agent-runtime/app/core/dependencies.py:1)
   - Обновлен `ensure_orchestrator_option2_initialized()` для передачи `approval_manager`

3. [`message_processor.py`](../codelab-ai-service/agent-runtime/app/services/message_processor.py:1)
   - Добавлена проверка `is_final` для завершения обработки

## 🎓 Lessons Learned

1. **Dependency Injection** - все зависимости должны явно передаваться через конструктор или setter
2. **Stream Control** - для управления потоком нужны явные флаги завершения (`is_final`)
3. **Testing** - интеграционные тесты помогают выявить проблемы с DI и потоком данных

## 🔗 Связанные документы

- [`PLAN_APPROVAL_DOUBLE_CREATION_BUG.md`](PLAN_APPROVAL_DOUBLE_CREATION_BUG.md) - описание бага
- [`PLAN_APPROVAL_FIXES_COMPLETE.md`](PLAN_APPROVAL_FIXES_COMPLETE.md) - детали исправлений
- [`PLAN_APPROVAL_COMPLETE.md`](PLAN_APPROVAL_COMPLETE.md) - общая документация

---

**Статус:** ✅ Исправлено и протестировано  
**Дата:** 2026-02-02  
**Коммит:** `945efa3`
