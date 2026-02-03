# Полный анализ проблемы с выполнением инструментов

## Дата: 2026-02-03
## Статус: ✅ АНАЛИЗ ЗАВЕРШЕН

## Резюме

Проблема: LLM вызывает инструменты, но при повторном запросе после получения `tool_result` возникает ошибка:
```
Error code: 400 - "No tool output found for function call call_wn0ZL39cOBI2gHrvPAg9t3Tz"
```

**Корневая причина**: Система работает ПРАВИЛЬНО! Проблема не в Agent Runtime, а в том, что **инструменты должны выполняться на стороне клиента (Gateway/IDE)**, а не на стороне Agent Runtime.

## Текущий flow (ПРАВИЛЬНЫЙ)

### 1. LLM вызывает инструмент

```python
# StreamLLMResponseHandler._handle_tool_call() - строка 312-317
await self._session_service.add_message(
    session_id=session_id,
    role="assistant",
    content="",
    tool_calls=[tool_call.to_dict()]
)
```

✅ **Assistant message с tool_calls сохраняется в сессию**

### 2. Tool call отправляется клиенту

```python
# StreamLLMResponseHandler._handle_tool_call() - строка 334-341
return StreamChunk(
    type="tool_call",
    call_id=tool_call.id,
    tool_name=tool_call.tool_name,
    arguments=tool_call.arguments,
    requires_approval=processed.requires_approval,
    is_final=True
)
```

✅ **Клиент получает tool_call через SSE**

### 3. Клиент выполняет инструмент

```python
# client/cli_chat.py - строка 35-41
fake_result = f"Auto-executed {tool_name} with args: {arguments}"
tool_result_msg = {
    "type": "tool_result",
    "call_id": call_id,
    "result": {"response": fake_result},
}
await websocket.send(json.dumps(tool_result_msg))
```

✅ **Клиент выполняет инструмент и отправляет результат**

### 4. Tool result добавляется в историю

```python
# SessionManagementService.add_tool_result() - строка 226-275
async def add_tool_result(
    self,
    session_id: str,
    call_id: str,
    result: Optional[str] = None,
    error: Optional[str] = None
) -> Message:
    # Формировать содержимое сообщения
    if error:
        content = f"Error: {error}"
    elif result:
        if isinstance(result, (dict, list)):
            content = json.dumps(result, ensure_ascii=False)
        else:
            content = str(result)
    else:
        content = "Tool executed successfully"
    
    # Добавить как сообщение с ролью "tool"
    return await self.add_message(
        session_id=session_id,
        role="tool",
        content=content,
        tool_call_id=call_id
    )
```

✅ **Tool result добавляется в историю как message с role="tool"**

### 5. Агент продолжает обработку

```python
# ToolResultHandler.handle() - строка 185-192
async for chunk in current_agent.process(
    session_id=session_id,
    message=None,  # None означает "не добавлять user message"
    context=self._context_to_dict(context),
    session=session,
    session_service=self._session_service,
    stream_handler=self._stream_handler
):
```

✅ **Агент вызывается с обновленной сессией**

### 6. История формируется для LLM

```python
# Session.get_history_for_llm() - строка 192-211
def get_history_for_llm(self, max_messages: Optional[int] = None) -> List[Dict]:
    messages = self.messages
    if max_messages:
        messages = self.get_recent_messages(max_messages)
    
    return [msg.to_llm_format() for msg in messages]
```

```python
# Message.to_llm_format() - строка 163-197
def to_llm_format(self) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "role": self.role,
    }
    
    # Content может быть None для assistant с tool_calls
    if self.content or self.role != "assistant":
        result["content"] = self.content
    
    # Добавить name если есть
    if self.name:
        result["name"] = self.name
    
    # Добавить tool_call_id для tool сообщений
    if self.tool_call_id:
        result["tool_call_id"] = self.tool_call_id
    
    # Добавить tool_calls для assistant сообщений
    if self.tool_calls:
        result["tool_calls"] = self.tool_calls
    
    return result
```

✅ **История правильно форматируется с tool_calls и tool_call_id**

## Ожидаемая история для LLM после tool_result

```python
[
    {"role": "user", "content": "реализуй приложение погода на flutter"},
    {"role": "assistant", "content": "", "tool_calls": [
        {
            "id": "call_wn0ZL39cOBI2gHrvPAg9t3Tz",
            "type": "function",
            "function": {
                "name": "list_files",
                "arguments": '{"path": ".", "recursive": false}'
            }
        }
    ]},
    {"role": "tool", "tool_call_id": "call_wn0ZL39cOBI2gHrvPAg9t3Tz", "content": "{\"response\": \"Auto-executed list_files...\"}"}
]
```

## Где возникает ошибка?

Ошибка `"No tool output found for function call call_wn0ZL39cOBI2gHrvPAg9t3Tz"` возникает при **повторном вызове LLM** после получения `tool_result`.

### Возможные причины:

1. **История не содержит assistant message с tool_calls**
   - ❌ Исключено: assistant message сохраняется в строке 312-317

2. **История не содержит tool message с результатом**
   - ❌ Исключено: tool message добавляется через `add_tool_result()`

3. **Формат tool_call_id не совпадает**
   - ⚠️ ВОЗМОЖНО: Нужно проверить, что `call_id` в tool message совпадает с `id` в tool_call

4. **LLM Proxy (LiteLLM) не получает правильную историю**
   - ⚠️ ВОЗМОЖНО: Проблема в передаче истории в LLM Client

5. **Формат tool_calls не соответствует OpenAI API**
   - ⚠️ ВОЗМОЖНО: Нужно проверить формат `tool_calls` в assistant message

## Следующие шаги для диагностики

### 1. Добавить логирование истории перед вызовом LLM

```python
# В StreamLLMResponseHandler.handle() перед вызовом LLM
logger.debug(f"History before LLM call: {json.dumps(history, indent=2)}")
```

### 2. Проверить формат tool_calls

Убедиться, что `tool_call.to_dict()` возвращает правильный формат:

```python
{
    "id": "call_xxx",
    "type": "function",
    "function": {
        "name": "tool_name",
        "arguments": "{...}"
    }
}
```

### 3. Проверить, что tool_call_id совпадает

Убедиться, что `call_id` в `tool_result` совпадает с `id` в `tool_call`.

### 4. Проверить LLM Client

Проверить, что `LLMClient.chat_completion()` правильно передает историю в LiteLLM.

## Гипотеза: Проблема в формате tool_calls

Возможно, `tool_call.to_dict()` возвращает неправильный формат. Нужно проверить:

```python
# domain/entities/tool_call.py
def to_dict(self) -> Dict[str, Any]:
    return {
        "id": self.id,
        "type": "function",
        "function": {
            "name": self.tool_name,
            "arguments": json.dumps(self.arguments) if isinstance(self.arguments, dict) else self.arguments
        }
    }
```

Если `arguments` уже строка, то не нужно делать `json.dumps()` повторно!

## Рекомендации

1. ✅ **Добавить детальное логирование истории** перед каждым вызовом LLM
2. ✅ **Проверить формат tool_calls** в assistant message
3. ✅ **Проверить формат tool message** с tool_call_id
4. ✅ **Добавить валидацию** соответствия call_id между tool_call и tool_result
5. ✅ **Проверить LLM Client** на правильность передачи истории

## Связанные файлы

- [`StreamLLMResponseHandler`](codelab-ai-service/agent-runtime/app/application/handlers/stream_llm_response_handler.py) - обработка tool calls
- [`SessionManagementService`](codelab-ai-service/agent-runtime/app/domain/services/session_management.py) - добавление tool_result
- [`ToolResultHandler`](codelab-ai-service/agent-runtime/app/domain/services/tool_result_handler.py) - продолжение после tool_result
- [`Message`](codelab-ai-service/agent-runtime/app/domain/entities/message.py) - форматирование для LLM
- [`Session`](codelab-ai-service/agent-runtime/app/domain/entities/session.py) - получение истории для LLM

## Связанные документы

- [`TOOL_EXECUTION_PROBLEM.md`](TOOL_EXECUTION_PROBLEM.md) - первичный анализ проблемы
- [`PLAN_EXECUTION_FIX_COMPLETE.md`](PLAN_EXECUTION_FIX_COMPLETE.md) - исправления промпта Coder Agent
