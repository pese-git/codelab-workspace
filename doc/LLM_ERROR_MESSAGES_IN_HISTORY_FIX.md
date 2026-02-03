# LLM Error Messages in History Fix

## 🐛 Проблема

После HITL approval LLM возвращает ошибку, которая сохраняется в историю как assistant message. Это создает **множественные assistant messages подряд**, что недопустимо в OpenAI API.

## 🔍 Корневая причина

### Неправильная история сообщений

```json
[
  {
    "role": "assistant",
    "tool_calls": [{"id": "call_XXX", "function": {"name": "create_directory", ...}}]
  },
  {
    "role": "assistant",  // ❌ ОШИБКА: множественные assistant messages!
    "content": "[Error] LiteLLM proxy unavailable: No tool output found for function call call_XXX"
  },
  {
    "role": "assistant",  // ❌ Еще одна ошибка!
    "content": "[Error] LiteLLM proxy unavailable..."
  },
  // ... повторяется 10+ раз!
  {
    "role": "tool",
    "content": "{\"path\": \"lib\", ...}",
    "tool_call_id": "call_XXX"
  }
]
```

### Почему это происходит

1. Agent вызывает tool → `assistant` message с `tool_calls` сохраняется
2. Tool требует HITL approval → SSE разрывается
3. Пользователь одобряет tool
4. **HITLDecisionHandler вызывает ToolResultHandler**
5. ToolResultHandler добавляет tool result в историю
6. ToolResultHandler вызывает agent.process() для продолжения
7. **Agent вызывает LLM с историей, где есть tool_calls БЕЗ tool message между ними**
8. LLM Proxy/OpenRouter возвращает ошибку: "No tool output found for function call"
9. **Ошибка сохраняется как assistant message**
10. Цикл повторяется!

## 🎯 Корневая проблема

**После HITL approval в истории должен быть:**
```json
[
  {"role": "assistant", "tool_calls": [...]},
  {"role": "tool", "content": "...", "tool_call_id": "call_XXX"}  // ✅ Tool result
]
```

**Но фактически в истории:**
```json
[
  {"role": "assistant", "tool_calls": [...]},
  // ❌ НЕТ tool message! (был удален в нашем исправлении)
]
```

## 🔧 Решение

### Проблема в нашем исправлении!

В [`hitl_decision_handler.py:144`](../codelab-ai-service/agent-runtime/app/domain/services/hitl_decision_handler.py:144) мы **удалили** добавление tool message в историю:

```python
# ИСПРАВЛЕНИЕ: НЕ добавлять HITL approval result в историю как tool message!
# ❌ ЭТО НЕПРАВИЛЬНО!
```

**Проблема**: Мы удалили добавление tool message, но **ToolResultHandler ожидает, что tool message УЖЕ в истории**!

### Правильное решение

**НЕ удалять** добавление tool message, а **изменить его содержимое**:

```python
# Добавить tool result в историю (НЕ HITL approval result!)
# Для HITL approval нужно добавить ФИКТИВНЫЙ tool result,
# который будет заменен реальным результатом от ToolResultHandler
await self._session_service.add_message(
    session_id=session_id,
    role="tool",
    content=json.dumps(result.get("arguments")),  // ✅ Аргументы tool, не approval result
    name=tool_name,
    tool_call_id=call_id
)
```

Или **вообще не вызывать ToolResultHandler**, а сразу выполнить tool и продолжить!

## 📝 Рекомендуемое решение

### Вариант 1: Вернуть добавление tool message (исправленное)

```python
# Добавить tool result в историю
# Для approved/edited - добавляем аргументы
# Для rejected - добавляем feedback
if result.get("status") in ["approved", "approved_with_edits"]:
    tool_content = json.dumps(result.get("arguments"))
else:
    tool_content = json.dumps({"error": result.get("feedback")})

await self._session_service.add_message(
    session_id=session_id,
    role="tool",
    content=tool_content,
    name=tool_name,
    tool_call_id=call_id
)

# Продолжить выполнение через ToolResultHandler
async for chunk in self._tool_result_handler.handle(...):
    yield chunk
```

### Вариант 2: Не вызывать ToolResultHandler (проще)

```python
# НЕ вызывать ToolResultHandler, а просто вернуть chunk
# Клиент сам отправит tool_result обратно
yield StreamChunk(
    type="tool_result",
    content=json.dumps(result),
    metadata={"call_id": call_id, "tool_name": tool_name},
    is_final=True
)
```

## ✅ Итог

Наше исправление **создало новую проблему**:
- Удалили добавление tool message
- ToolResultHandler ожидает tool message в истории
- История становится невалидной
- LLM возвращает ошибку
- Ошибка сохраняется как assistant message
- Цикл повторяется

**Нужно вернуть добавление tool message, но с правильным содержимым!**
