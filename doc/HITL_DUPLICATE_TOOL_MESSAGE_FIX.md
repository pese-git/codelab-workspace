# HITL Duplicate Tool Message Fix

## 🐛 Проблема

После HITL approval LLM возвращает ошибку:
```
Error code: 400 - "No tool output found for function call call_V4LlKRXorI0cDPfGS2l8e2lx."
```

## 🔍 Корневая причина

### Неправильный формат истории сообщений

После HITL approval в историю добавлялось **ДВА tool message** с одним `tool_call_id`:

```json
[
  {
    "role": "assistant",
    "tool_calls": [{"id": "call_V4LlKRXorI0cDPfGS2l8e2lx", "function": {"name": "create_directory", ...}}]
  },
  {
    "role": "tool",
    "content": "{\"status\": \"approved\", \"tool_name\": \"create_directory\", ...}",  // ❌ HITL approval result
    "tool_call_id": "call_V4LlKRXorI0cDPfGS2l8e2lx"
  },
  {
    "role": "tool",
    "content": "{\"path\": \"lib\", \"recursive\": true}",  // ✅ Tool execution result
    "tool_call_id": "call_V4LlKRXorI0cDPfGS2l8e2lx"
  }
]
```

**Проблема**: OpenAI API **НЕ поддерживает** несколько tool messages с одним `tool_call_id`!

### Где добавлялся дубликат

**Файл**: [`hitl_decision_handler.py:148`](../codelab-ai-service/agent-runtime/app/domain/services/hitl_decision_handler.py:148)

**Было**:
```python
# Добавить результат в историю сессии
result_str = json.dumps(result)  # {"status": "approved", "tool_name": "create_directory", ...}
await self._session_service.add_message(
    session_id=session_id,
    role="tool",  // ❌ Добавляет HITL approval как tool message!
    content=result_str,
    name=tool_name,
    tool_call_id=call_id
)
```

Затем `ToolResultHandler` добавлял **второй** tool message с результатом выполнения.

## 🔧 Решение

### Исправление в [`hitl_decision_handler.py:144`](../codelab-ai-service/agent-runtime/app/domain/services/hitl_decision_handler.py:144)

**Было**:
```python
logger.info(f"[DEBUG] Approval status updated, now adding result to session history")

# Добавить результат в историю сессии
result_str = json.dumps(result)
await self._session_service.add_message(
    session_id=session_id,
    role="tool",
    content=result_str,
    name=tool_name,
    tool_call_id=call_id
)

logger.info(
    f"HITL результат добавлен в сессию {session_id}, "
    f"продолжаем выполнение через ToolResultHandler"
)

# Продолжить выполнение через ToolResultHandler
async for chunk in self._tool_result_handler.handle(...):
    yield chunk
```

**Стало**:
```python
logger.info(f"[DEBUG] Approval status updated")

# ИСПРАВЛЕНИЕ: НЕ добавлять HITL approval result в историю как tool message!
# Это создает дубликат tool message и ломает формат OpenAI API.
# Вместо этого, сразу продолжаем выполнение через ToolResultHandler,
# который добавит ПРАВИЛЬНЫЙ tool result после выполнения.

logger.info(
    f"HITL approval processed for session {session_id}, "
    f"продолжаем выполнение через ToolResultHandler"
)

# Продолжить выполнение через ToolResultHandler
async for chunk in self._tool_result_handler.handle(...):
    yield chunk
```

## ✅ Результат

### До исправления:
```
1. assistant с tool_calls
2. tool с HITL approval result  ❌ ДУБЛИКАТ!
3. tool с execution result      ❌ ДУБЛИКАТ!
4. LLM error: "No tool output found"
```

### После исправления:
```
1. assistant с tool_calls
2. tool с execution result  ✅ ОДИН tool message!
3. LLM работает корректно
```

## 📝 Изменённые файлы

1. ✅ [`hitl_decision_handler.py`](../codelab-ai-service/agent-runtime/app/domain/services/hitl_decision_handler.py) - удалено добавление HITL approval в историю

## 🎯 Итог

**Проблема решена:**
- ✅ HITL approval НЕ добавляется в историю как tool message
- ✅ Только один tool message с результатом выполнения
- ✅ LLM получает правильный формат истории
- ✅ Нет ошибок "No tool output found"
- ✅ Subtasks выполняются корректно
