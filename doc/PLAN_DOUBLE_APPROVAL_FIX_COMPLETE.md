# ✅ Plan Double Approval Fix Complete

## 🐛 Проблема

После одобрения плана и начала выполнения:
1. ✅ Пользователь одобряет план → выполнение начинается
2. ⚠️ Tool требует approval (HITL)
3. ✅ Пользователь одобряет tool
4. ❌ **План СНОВА запрашивается на подтверждение!**

## 🔍 Корневая причина

### Проблемный код: [`hitl_decision_handler.py:163`](../codelab-ai-service/agent-runtime/app/domain/services/hitl_decision_handler.py:163)

**Было:**
```python
# Продолжить обработку с текущим агентом (пустое сообщение)
async for chunk in self._message_processor.process(
    session_id=session_id,
    message=""  # ❌ ПРОБЛЕМА: пустое сообщение!
):
    yield chunk
```

### Что происходило:

1. Tool approval обработан → результат добавлен в историю
2. **Вызывался `message_processor.process("")`** с пустым сообщением
3. MessageProcessor вызывал **OrchestratorAgent**
4. Orchestrator видел пустое сообщение и FSM в состоянии `PLAN_EXECUTION`
5. **Orchestrator сбрасывал FSM** (строка 189 в orchestrator_agent.py)
6. **Orchestrator заново классифицировал задачу**
7. **Orchestrator заново создавал план**
8. **План СНОВА запрашивался на подтверждение!**

## 🔧 Решение

### Изменение в [`hitl_decision_handler.py`](../codelab-ai-service/agent-runtime/app/domain/services/hitl_decision_handler.py)

**Строка**: 161-167

**Было:**
```python
logger.info(
    f"HITL результат добавлен в сессию {session_id}, "
    f"продолжаем обработку с текущим агентом"
)

# Продолжить обработку с текущим агентом (пустое сообщение)
# Используем MessageProcessor для продолжения после tool_result
async for chunk in self._message_processor.process(
    session_id=session_id,
    message=""  # Пустое сообщение = продолжить после tool_result
):
    yield chunk
```

**Стало:**
```python
logger.info(
    f"HITL результат добавлен в сессию {session_id}, "
    f"возвращаем tool_result для продолжения выполнения"
)

# ИСПРАВЛЕНИЕ: Вернуть tool_result chunk вместо вызова MessageProcessor
# Tool approval - это внутренняя часть выполнения подзадачи.
# НЕ должен перезапускать весь flow через Orchestrator.
# Клиент получит tool_result и сам решит, как продолжить.
yield StreamChunk(
    type="tool_result",
    content=result_str,
    metadata={
        "call_id": call_id,
        "tool_name": tool_name,
        "decision": decision,
        "status": result.get("status")
    },
    is_final=True
)

logger.info(
    f"HITL decision processed for session {session_id}, "
    f"tool_result returned for continuation"
)
```

## 📊 Flow после исправления

### До исправления (неправильно):
```
1. План одобрен → FSM: PLAN_EXECUTION
2. Subtask выполняется → Coder agent
3. Tool требует approval → SSE разрывается
4. Пользователь одобряет tool
5. HITLDecisionHandler вызывает MessageProcessor("")
6. MessageProcessor → OrchestratorAgent
7. Orchestrator сбрасывает FSM
8. Orchestrator заново создает план
9. ❌ План СНОВА запрашивается на подтверждение!
```

### После исправления (правильно):
```
1. План одобрен → FSM: PLAN_EXECUTION
2. Subtask выполняется → Coder agent
3. Tool требует approval → SSE разрывается
4. Пользователь одобряет tool
5. HITLDecisionHandler возвращает tool_result chunk
6. Клиент получает tool_result
7. Клиент переоткрывает SSE с tool_result
8. MessageProcessor обрабатывает tool_result
9. Coder agent продолжает выполнение
10. FSM остается в PLAN_EXECUTION
11. ✅ План НЕ запрашивается повторно!
```

## ✅ Результаты

### До исправления:
```
❌ Tool approval вызывал MessageProcessor с пустым сообщением
❌ Orchestrator сбрасывал FSM
❌ Orchestrator заново создавал план
❌ План запрашивался на подтверждение дважды
❌ Пользователь видел повторный запрос approval
❌ Выполнение прерывалось
```

### После исправления:
```
✅ Tool approval возвращает tool_result chunk
✅ FSM остается в PLAN_EXECUTION
✅ Orchestrator НЕ вызывается
✅ План НЕ создается заново
✅ План запрашивается на подтверждение только один раз
✅ Выполнение продолжается без прерываний
✅ Пользователь не видит повторных запросов
```

## 🧪 Тестирование

### Тест 1: Tool approval во время выполнения плана
```python
async def test_tool_approval_during_plan_execution():
    # 1. Создать и одобрить план
    plan_id = await create_and_approve_plan(session_id, "Create login form")
    
    # 2. Начать выполнение плана
    # Subtask вызывает write_file, который требует approval
    
    # 3. Одобрить tool
    chunks = []
    async for chunk in hitl_handler.handle(
        session_id=session_id,
        call_id="write-file-123",
        decision="approve"
    ):
        chunks.append(chunk)
    
    # 4. Проверить результаты
    # - Вернулся tool_result chunk
    assert chunks[-1].type == "tool_result"
    assert chunks[-1].metadata["call_id"] == "write-file-123"
    assert chunks[-1].metadata["status"] == "approved"
    
    # - FSM остался в PLAN_EXECUTION
    state = await fsm.get_current_state(session_id)
    assert state == FSMState.PLAN_EXECUTION
    
    # - План НЕ запрашивается повторно
    plan_approval_chunks = [c for c in chunks if c.type == "plan_approval_required"]
    assert len(plan_approval_chunks) == 0
    
    # - Нет switch_agent chunks (Orchestrator не вызывался)
    switch_chunks = [c for c in chunks if c.type == "switch_agent"]
    assert len(switch_chunks) == 0
```

### Тест 2: Множественные tool approvals в одном плане
```python
async def test_multiple_tool_approvals_in_plan():
    # 1. Создать план с несколькими subtasks
    plan_id = await create_and_approve_plan(
        session_id,
        "Create login form with validation"
    )
    
    # 2. Первая subtask требует tool approval
    await hitl_handler.handle(
        session_id=session_id,
        call_id="write-file-1",
        decision="approve"
    )
    
    # 3. Вторая subtask требует tool approval
    await hitl_handler.handle(
        session_id=session_id,
        call_id="write-file-2",
        decision="approve"
    )
    
    # 4. Проверить, что план запрашивался только один раз
    approval_requests = await approval_manager.get_all_by_session(session_id)
    plan_approvals = [r for r in approval_requests if r.request_type == "plan"]
    assert len(plan_approvals) == 1  # Только один plan approval
```

## 📝 Изменённые файлы

1. ✅ [`hitl_decision_handler.py`](../codelab-ai-service/agent-runtime/app/domain/services/hitl_decision_handler.py) - исправлен метод `handle()`
   - Удален вызов `message_processor.process("")`
   - Добавлен возврат `tool_result` chunk

## 🔗 Связанные исправления

Эта проблема связана с другими исправлениями:

1. **Транзакционная изоляция** ([`PLAN_TRANSACTION_ISOLATION_FIX.md`](PLAN_TRANSACTION_ISOLATION_FIX.md))
   - План не коммитился → не был виден в других транзакциях
   - Исправлено добавлением `commit=True`

2. **FSM валидация** ([`FSM_PLAN_APPROVAL_FIX_COMPLETE.md`](FSM_PLAN_APPROVAL_FIX_COMPLETE.md))
   - Отсутствие проверки состояния FSM перед approval
   - Исправлено добавлением валидации в `plan_approval_handler.py`

3. **Double approval** (этот документ)
   - Tool approval перезапускал Orchestrator
   - Исправлено возвратом `tool_result` вместо вызова MessageProcessor

## 🎯 Итог

**Проблема полностью решена:**

1. ✅ Tool approval возвращает `tool_result` chunk
2. ✅ MessageProcessor НЕ вызывается с пустым сообщением
3. ✅ Orchestrator НЕ перезапускается
4. ✅ FSM остается в правильном состоянии
5. ✅ План НЕ создается заново
6. ✅ План запрашивается на подтверждение только один раз
7. ✅ Выполнение продолжается без прерываний

**План больше НЕ запрашивается на подтверждение дважды!**
