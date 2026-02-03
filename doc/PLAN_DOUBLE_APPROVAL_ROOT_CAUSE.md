# Plan Double Approval - Root Cause Found!

## 🐛 Проблема

После одобрения плана и начала выполнения:
1. ✅ Пользователь одобряет план → выполнение начинается
2. ⚠️ Tool требует approval (HITL)
3. ✅ Пользователь одобряет tool
4. ❌ **План СНОВА запрашивается на подтверждение!**

## 🔍 Корневая причина

### Проблемный код: [`hitl_decision_handler.py:163`](../codelab-ai-service/agent-runtime/app/domain/services/hitl_decision_handler.py:163)

```python
# Продолжить обработку с текущим агентом (пустое сообщение)
async for chunk in self._message_processor.process(
    session_id=session_id,
    message=""  # ❌ ПРОБЛЕМА: пустое сообщение!
):
    yield chunk
```

### Что происходит:

1. **Tool approval обработан** → результат добавлен в историю
2. **Вызывается `message_processor.process("")`** с пустым сообщением
3. MessageProcessor вызывает **OrchestratorAgent**
4. Orchestrator видит:
   - Пустое сообщение (`message=""`)
   - FSM в состоянии `PLAN_EXECUTION`
5. **Orchestrator сбрасывает FSM** (строка 189 в orchestrator_agent.py):
   ```python
   if current_state in [FSMState.COMPLETED, FSMState.ERROR_HANDLING, 
                        FSMState.EXECUTION, FSMState.PLAN_REVIEW, FSMState.PLAN_EXECUTION]:
       # Reset FSM
       await self.fsm_orchestrator.reset(session_id)
   ```
6. **Orchestrator заново классифицирует задачу**
7. **Orchestrator заново создает план**
8. **План СНОВА запрашивается на подтверждение!**

## ❌ Почему это неправильно

**Tool approval во время выполнения подзадачи НЕ должен:**
- Сбрасывать FSM
- Перезапускать Orchestrator
- Заново создавать план
- Запрашивать повторное подтверждение

**Tool approval должен:**
- Продолжить выполнение текущей подзадачи
- Остаться в том же состоянии FSM (`PLAN_EXECUTION`)
- Вернуть управление агенту, который выполняет подзадачу

## ✅ Правильное решение

### Вариант 1: НЕ вызывать MessageProcessor после tool approval

Tool approval должен **возвращать tool_result напрямую**, без вызова MessageProcessor:

```python
async def handle(
    self,
    session_id: str,
    call_id: str,
    decision: str,
    modified_arguments: Optional[dict] = None,
    feedback: Optional[str] = None
) -> AsyncGenerator[StreamChunk, None]:
    # ... existing code ...
    
    # Добавить результат в историю сессии
    result_str = json.dumps(result)
    await self._session_service.add_message(
        session_id=session_id,
        role="tool",
        content=result_str,
        name=tool_name,
        tool_call_id=call_id
    )
    
    # ❌ УДАЛИТЬ: НЕ вызывать MessageProcessor!
    # async for chunk in self._message_processor.process(
    #     session_id=session_id,
    #     message=""
    # ):
    #     yield chunk
    
    # ✅ ДОБАВИТЬ: Вернуть tool_result chunk
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
```

### Вариант 2: Проверять контекст перед сбросом FSM в Orchestrator

Добавить проверку в [`orchestrator_agent.py:189`](../codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py:189):

```python
# НЕ сбрасывать FSM если это продолжение после tool_result
if message == "" and current_state == FSMState.PLAN_EXECUTION:
    # Это продолжение выполнения после tool approval
    # НЕ сбрасывать FSM, НЕ перезапускать планирование
    logger.info(
        f"Continuing plan execution after tool approval "
        f"for session {session_id}"
    )
    # Просто вернуть пустой chunk - выполнение продолжится
    return
```

## 🎯 Рекомендуемое решение

**Вариант 1** - более правильный, потому что:

1. Tool approval - это **внутренняя часть выполнения подзадачи**
2. Не должен перезапускать весь flow через Orchestrator
3. Должен просто вернуть tool_result и продолжить выполнение
4. Агент, который выполняет подзадачу, сам обработает tool_result

## 📝 Детальный план исправления

### Шаг 1: Изменить HITLDecisionHandler

**Файл**: `codelab-ai-service/agent-runtime/app/domain/services/hitl_decision_handler.py`

**Строка**: 161-167

**Было**:
```python
# Продолжить обработку с текущим агентом (пустое сообщение)
async for chunk in self._message_processor.process(
    session_id=session_id,
    message=""
):
    yield chunk
```

**Стало**:
```python
# Вернуть tool_result chunk для продолжения выполнения
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

### Шаг 2: Убедиться, что агенты обрабатывают tool_result

Агенты (Coder, Debug, etc.) уже обрабатывают tool_result через свой process() метод.
Когда они получают tool_result, они продолжают выполнение с LLM.

### Шаг 3: Тестирование

```python
async def test_tool_approval_during_plan_execution():
    # 1. Создать и одобрить план
    plan_id = await create_and_approve_plan(session_id)
    
    # 2. Начать выполнение плана
    # Subtask вызывает tool, который требует approval
    
    # 3. Одобрить tool
    chunks = []
    async for chunk in hitl_handler.handle(
        session_id=session_id,
        call_id="tool-call-123",
        decision="approve"
    ):
        chunks.append(chunk)
    
    # 4. Проверить, что:
    # - Вернулся tool_result chunk
    assert chunks[-1].type == "tool_result"
    
    # - FSM остался в PLAN_EXECUTION
    state = await fsm.get_current_state(session_id)
    assert state == FSMState.PLAN_EXECUTION
    
    # - План НЕ запрашивается повторно
    plan_approval_chunks = [c for c in chunks if c.type == "plan_approval_required"]
    assert len(plan_approval_chunks) == 0
```

## 🔄 Flow после исправления

### Правильный flow:

```
1. План создан и одобрен → FSM: PLAN_EXECUTION
2. Subtask выполняется → Coder agent
3. Coder вызывает tool → требует approval
4. SSE разрывается (HITL)
5. Пользователь одобряет tool → POST /agent/message/stream (hitl_decision)
6. HITLDecisionHandler:
   - Обрабатывает решение
   - Добавляет tool_result в историю
   - ✅ Возвращает tool_result chunk (НЕ вызывает MessageProcessor!)
7. Клиент получает tool_result
8. Клиент переоткрывает SSE stream → POST /agent/message/stream (tool_result)
9. MessageProcessor обрабатывает tool_result
10. Coder agent продолжает выполнение с tool_result
11. FSM остается в PLAN_EXECUTION
12. ✅ План НЕ запрашивается повторно!
```

## ✅ Результат

После исправления:
- ✅ Tool approval обрабатывается правильно
- ✅ FSM остается в PLAN_EXECUTION
- ✅ План НЕ запрашивается повторно
- ✅ Выполнение продолжается с текущей подзадачи
- ✅ Нет перезапуска Orchestrator
- ✅ Нет повторного создания плана
