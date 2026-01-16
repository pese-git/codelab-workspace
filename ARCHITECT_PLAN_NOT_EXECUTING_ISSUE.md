# Проблема: План не выполняется после подтверждения

## Симптомы

На скриншоте видно:
1. Пользователь нажал "да" для подтверждения плана
2. Сразу показывается "Plan Execution Complete" с:
   - Total subtasks: 8
   - Completed: 0
   - Failed: 0

**План завершается мгновенно без выполнения ни одной подзадачи.**

## Корневая причина

Проблема в методе [`_execute_plan`](codelab-ai-service/agent-runtime/app/services/multi_agent_orchestrator.py:220-384) в `multi_agent_orchestrator.py`.

### Анализ кода

```python
# multi_agent_orchestrator.py:254-260
while not plan.is_complete:
    # Get next subtask
    subtask = session_mgr.get_next_subtask(session_id)
    
    if not subtask:
        # No more subtasks or all complete
        break
```

Метод `get_next_subtask` возвращает `None` сразу же, что приводит к немедленному выходу из цикла.

### Почему `get_next_subtask` возвращает `None`?

Смотрим [`session_manager_async.py:520-570`](codelab-ai-service/agent-runtime/app/services/session_manager_async.py:520-570):

```python
def get_next_subtask(self, session_id: str) -> Optional["Subtask"]:
    plan = self.get_plan(session_id)
    if not plan:
        return None  # ← ПРОБЛЕМА: план не найден!
    
    # ... остальной код
```

**План не найден в `session_mgr._plans`!**

## Почему план не найден?

### Проблема в `endpoints.py`

Смотрим обработку `plan_decision` в [`endpoints.py:137-157`](codelab-ai-service/agent-runtime/app/api/v1/endpoints.py:137-157):

```python
if decision == PlanDecision.APPROVE:
    logger.info(f"Plan APPROVED: executing {len(plan.subtasks)} subtasks")
    
    # Mark plan as approved
    plan.is_approved = True  # ← Изменяем локальную переменную
    
    # Continue with plan execution (orchestrator will handle it)
    async for chunk in multi_agent_orchestrator.process_message(
        session_id=request.session_id,
        message=""  # Empty message to trigger plan execution
    ):
        # ...
```

**Проблема:** Мы получаем план через `async_session_mgr.get_plan()`, изменяем его `is_approved = True`, но это изменение **НЕ сохраняется** обратно в `session_mgr._plans`!

### Почему изменение не сохраняется?

В Python, когда мы делаем:
```python
plan = async_session_mgr.get_plan(request.session_id)  # Получаем ссылку на объект
plan.is_approved = True  # Изменяем объект
```

Это **ДОЛЖНО** работать, потому что `plan` - это ссылка на объект в словаре `_plans`.

**НО!** Проблема может быть в том, что:

1. **План создается в Architect agent**, но не сохраняется в `session_mgr`
2. **План удаляется** где-то между созданием и подтверждением
3. **Используются разные экземпляры** `session_mgr`

## Диагностика

Давайте проверим, где план сохраняется в Architect agent:

```python
# architect_agent.py:133
session_mgr.set_plan(session_id, plan)
```

Это выглядит правильно. Но давайте проверим, что происходит дальше.

### Проверка в `multi_agent_orchestrator.py`

```python
# multi_agent_orchestrator.py:66-78
if async_session_mgr.has_plan(session_id):
    plan = async_session_mgr.get_plan(session_id)
    
    # If plan requires approval but not yet approved, wait for plan_decision
    if plan.requires_approval and not plan.is_approved:
        logger.info(f"Session {session_id} has plan waiting for approval")
        yield StreamChunk(
            type="assistant_message",
            content="Ожидаю подтверждения плана...",
            is_final=True
        )
        return
```

Это тоже выглядит правильно.

## Реальная проблема

Я нашел её! Смотрите на строку 146 в `endpoints.py`:

```python
async for chunk in multi_agent_orchestrator.process_message(
    session_id=request.session_id,
    message=""  # Empty message to trigger plan execution
):
```

Когда мы вызываем `process_message` с пустым сообщением, orchestrator проверяет:

```python
# multi_agent_orchestrator.py:81-85
# Plan is approved, execute it
if plan.is_approved and not plan.is_complete:
    logger.info(f"Session {session_id} has approved plan, continuing execution")
    async for chunk in self._execute_plan(session_id, async_session_mgr, context):
        yield chunk
    return
```

Но к этому моменту `plan.is_approved` может быть **False**, потому что мы изменили локальную переменную в `endpoints.py`, но не обновили план в `session_mgr`!

## Решение

### Вариант 1: Обновить план в session_mgr после изменения

В [`endpoints.py:141`](codelab-ai-service/agent-runtime/app/api/v1/endpoints.py:141):

```python
if decision == PlanDecision.APPROVE:
    logger.info(f"Plan APPROVED: executing {len(plan.subtasks)} subtasks")
    
    # Mark plan as approved
    plan.is_approved = True
    
    # ДОБАВИТЬ: Обновить план в session_mgr
    async_session_mgr.set_plan(request.session_id, plan)
    
    # Continue with plan execution
    async for chunk in multi_agent_orchestrator.process_message(
        session_id=request.session_id,
        message=""
    ):
        # ...
```

### Вариант 2: Использовать метод для обновления статуса

Добавить метод в `AsyncSessionManager`:

```python
def approve_plan(self, session_id: str) -> bool:
    """
    Approve execution plan for a session.
    
    Args:
        session_id: Session identifier
        
    Returns:
        True if plan was found and approved, False otherwise
    """
    plan = self.get_plan(session_id)
    if not plan:
        logger.warning(f"No plan found for session {session_id}")
        return False
    
    plan.is_approved = True
    logger.info(f"Approved execution plan for session {session_id}")
    return True
```

Затем в `endpoints.py`:

```python
if decision == PlanDecision.APPROVE:
    logger.info(f"Plan APPROVED: executing {len(plan.subtasks)} subtasks")
    
    # Approve plan in session manager
    if not async_session_mgr.approve_plan(request.session_id):
        yield {
            "event": "error",
            "data": json.dumps({
                "type": "error",
                "error": "Plan not found",
                "is_final": True
            })
        }
        return
    
    # Continue with plan execution
    async for chunk in multi_agent_orchestrator.process_message(
        session_id=request.session_id,
        message=""
    ):
        # ...
```

## Рекомендуемое решение

**Вариант 1** - самый простой и быстрый. Просто добавить одну строку:

```python
async_session_mgr.set_plan(request.session_id, plan)
```

после установки `plan.is_approved = True`.

## Дополнительная проблема

Также нужно сделать то же самое для `PlanDecision.EDIT`:

```python
elif decision == PlanDecision.EDIT:
    logger.info(f"Plan EDITED: updating subtasks")
    
    if modified_subtasks:
        # Update plan with modified subtasks
        from app.models.schemas import Subtask, SubtaskStatus
        plan.subtasks = [
            Subtask(
                id=st.get("id", f"subtask_{i+1}"),
                description=st["description"],
                agent=st["agent"],
                estimated_time=st.get("estimated_time"),
                status=SubtaskStatus.PENDING,
                dependencies=st.get("dependencies", [])
            )
            for i, st in enumerate(modified_subtasks)
        ]
        plan.is_approved = True
        
        # ДОБАВИТЬ: Обновить план в session_mgr
        async_session_mgr.set_plan(request.session_id, plan)
        
        # Continue with modified plan execution
        async for chunk in multi_agent_orchestrator.process_message(
            session_id=request.session_id,
            message=""
        ):
            # ...
```

## Итоговые изменения

### Файл: `codelab-ai-service/agent-runtime/app/api/v1/endpoints.py`

**Строка 141** - после `plan.is_approved = True`:
```python
# Mark plan as approved
plan.is_approved = True

# Update plan in session manager
async_session_mgr.set_plan(request.session_id, plan)
```

**Строка 176** - после `plan.is_approved = True`:
```python
plan.is_approved = True

# Update plan in session manager
async_session_mgr.set_plan(request.session_id, plan)
```

## Тестирование

После внесения изменений:

1. Создать план через Architect
2. Подтвердить план
3. План должен начать выполняться, показывая прогресс каждой подзадачи
4. В конце должно быть "Completed: 8" вместо "Completed: 0"

## Почему это не было замечено раньше?

Это классическая ошибка работы с изменяемыми объектами в Python. Обычно изменение объекта, полученного из словаря, работает:

```python
plan = dict[key]  # Получаем ссылку
plan.field = value  # Изменяем объект - изменение видно в словаре
```

Но в данном случае проблема в том, что между получением плана и его использованием происходит вызов другого метода (`process_message`), который снова получает план из словаря. Если мы не сохранили изменения обратно, новый вызов получит старую версию.

## Альтернативное объяснение

Возможно, проблема в том, что `get_plan` возвращает **копию** объекта, а не ссылку. Давайте проверим:

```python
# session_manager_async.py:413-429
def get_plan(self, session_id: str) -> Optional["ExecutionPlan"]:
    plan = self._plans.get(session_id)
    if plan:
        logger.debug(...)
    return plan  # ← Возвращает ссылку, не копию
```

Нет, возвращается ссылка. Значит, проблема действительно в том, что мы не вызываем `set_plan` после изменения.

## Заключение

**Проблема:** После подтверждения плана изменение `plan.is_approved = True` не сохраняется в `session_mgr._plans`, поэтому при следующем вызове `get_plan` возвращается план с `is_approved = False`.

**Решение:** Добавить `async_session_mgr.set_plan(request.session_id, plan)` после изменения плана в обработчике `plan_decision`.
