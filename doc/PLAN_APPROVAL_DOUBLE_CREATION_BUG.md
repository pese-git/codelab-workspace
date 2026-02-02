# 🐛 Bug: План создается дважды

## 📊 Симптомы

1. ✅ План создается успешно (Plan 04cb84b7)
2. ✅ FSM переходит в `plan_review`
3. ✅ Approval request создается
4. ❌ **Orchestrator вызывается ПОВТОРНО** (05:43:39,869)
5. ❌ FSM сбрасывается из `plan_review` в `idle`
6. ❌ Создается второй план (Plan 9760f62d)
7. ❌ Диалог подтверждения не отображается в IDE

## 🔍 Корневая причина

### Проблема в [`orchestrator_agent.py:189-212`](codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py:189)

```python
# Reset FSM if in terminal state or non-IDLE states that shouldn't process new messages
if current_state in [FSMState.COMPLETED, FSMState.ERROR_HANDLING, FSMState.EXECUTION, FSMState.PLAN_REVIEW, FSMState.PLAN_EXECUTION]:
    logger.info(
        f"Resetting FSM from {current_state.value} to IDLE for new message "
        f"in session {session_id}"
    )
    if current_state == FSMState.COMPLETED:
        await self.fsm_orchestrator.transition(
            session_id=session_id,
            event=FSMEvent.RESET,
            metadata={"reason": "new_message"}
        )
    elif current_state == FSMState.PLAN_REVIEW:
        # User sent new message instead of approving - treat as rejection
        await self.fsm_orchestrator.transition(
            session_id=session_id,
            event=FSMEvent.PLAN_REJECTED,
            metadata={"reason": "new_message_received"}
        )
        self.fsm_orchestrator.reset(session_id)
```

**Проблема:** Код предполагает, что если FSM в `PLAN_REVIEW`, то пришло НОВОЕ сообщение от пользователя. Но на самом деле `process()` вызывается повторно с ТЕМ ЖЕ сообщением!

## 📝 Логи подтверждают

```
05:43:39,862 - Plan 04cb84b7 created by Architect
05:43:39,862 - FSM transition: architect_planning -> plan_review
05:43:39,869 - Plan approval request created: plan-approval-04cb84b7
05:43:39,869 - Orchestrator processing request for session a8f85aa2  ⬅️ ПОВТОРНЫЙ ВЫЗОВ!
05:43:39,869 - Current FSM state: plan_review
05:43:39,869 - Resetting FSM from plan_review to IDLE  ⬅️ ОШИБКА!
05:43:39,869 - FSM transition: plan_review -> idle (event: plan_rejected)
05:43:41,351 - FSM transition: classify -> plan_required
05:43:46,336 - Plan 9760f62d created by Architect  ⬅️ ВТОРОЙ ПЛАН!
```

## 🎯 Почему `process()` вызывается дважды?

Возможные причины:

1. **WebSocket отправляет chunks асинхронно**, и после `return` в `_coordinate_plan_execution()` (строка 598), где-то в коде происходит повторный вызов `process()`

2. **MessageProcessor или другой компонент** может вызывать `process()` повторно после получения chunks

3. **Проблема в стриминге** - после yield chunks система думает, что нужно продолжить обработку

## 💡 Решение

### Вариант 1: Не сбрасывать FSM из PLAN_REVIEW

Изменить логику в `orchestrator_agent.py:189-212`:

```python
# Reset FSM if in terminal state or non-IDLE states that shouldn't process new messages
# BUT: Do NOT reset from PLAN_REVIEW - we're waiting for user approval!
if current_state in [FSMState.COMPLETED, FSMState.ERROR_HANDLING, FSMState.EXECUTION, FSMState.PLAN_EXECUTION]:
    logger.info(
        f"Resetting FSM from {current_state.value} to IDLE for new message "
        f"in session {session_id}"
    )
    if current_state == FSMState.COMPLETED:
        await self.fsm_orchestrator.transition(
            session_id=session_id,
            event=FSMEvent.RESET,
            metadata={"reason": "new_message"}
        )
    else:
        # For EXECUTION, ERROR_HANDLING, PLAN_EXECUTION - reset directly
        self.fsm_orchestrator.reset(session_id)
    
    current_state = FSMState.IDLE

elif current_state == FSMState.PLAN_REVIEW:
    # In PLAN_REVIEW state - waiting for user approval
    # Do NOT process as new message, just return
    logger.info(
        f"Session {session_id} in PLAN_REVIEW state, waiting for user approval. "
        f"Ignoring duplicate process() call."
    )
    return  # Exit early, don't process
```

### Вариант 2: Проверить, откуда идет повторный вызов

Найти место, где `process()` вызывается повторно после `_coordinate_plan_execution()` и исправить там.

## 🔧 Рекомендация

**Вариант 1** - самый простой и безопасный. Добавить проверку состояния `PLAN_REVIEW` и выходить рано, не обрабатывая как новое сообщение.

## 📌 Дополнительная проблема: Диалог не отображается

Возможно, клиент (IDE) не обрабатывает chunk `type="plan_approval_required"` правильно. Нужно проверить:

1. Отправляется ли chunk с правильным типом
2. Получает ли клиент этот chunk
3. Обрабатывает ли AgentChatBloc этот тип сообщения
