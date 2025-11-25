# 🟥 **Streaming Protocol Specification — Codelab POC**
Версия: 1.0
Статус: Спецификация протоколов потоковой передачи данных

---

# 1. Обзор архитектуры streaming

```mermaid
flowchart LR
    IDE[IDE] <-->|WebSocket| GW[Gateway]
    GW <-->|REST + SSE| Agent[Agent Runtime]
    Agent <-->|REST + SSE| LLM[LLM Proxy]
    LLM <-->|Provider API| Provider[OpenAI/Anthropic]
```

## Ключевые принципы:

1. **Реиспользование соединений:** IDE уже имеет WebSocket соединение с Gateway
2. **SSE для HTTP streaming:** Между сервисами используется Server-Sent Events
3. **Единый формат сообщений:** JSON для всех протоколов
4. **Graceful degradation:** Fallback на polling при недоступности streaming

---

# 2. Протоколы по компонентам

## 2.1 IDE ↔ Gateway (WebSocket)

### Преимущества WebSocket здесь:
- Двунаправленная связь уже установлена
- Низкая latency
- Поддержка real-time updates
- Единое соединение для всех типов сообщений

### Формат streaming токенов:

```json
// Gateway → IDE
{
  "type": "assistant_message",
  "message_id": "msg_123",
  "token": "import",
  "is_final": false
}

// Финальное сообщение
{
  "type": "assistant_message",
  "message_id": "msg_123",
  "is_final": true
}
```

---

## 2.2 Gateway ↔ Agent Runtime (REST + SSE)

### Инициация streaming:

```http
POST /agent/message/stream HTTP/1.1
Content-Type: application/json
Authorization: Bearer internal-poc-key-12345

{
  "session_id": "sess_1",
  "message": {
    "type": "user_message",
    "content": "Refactor auth module"
  }
}
```

### SSE Response:

```http
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache

event: token
data: {"type": "assistant_message", "session_id": "sess_1", "message_id": "msg_123", "token": "I'll", "is_final": false}

event: token
data: {"type": "assistant_message", "session_id": "sess_1", "message_id": "msg_123", "token": " help", "is_final": false}

event: tool_call
data: {"type": "tool_call", "call_id": "call_456", "tool_name": "read_file", "args": {"path": "src/auth.js"}}

event: token
data: {"type": "assistant_message", "session_id": "sess_1", "message_id": "msg_123", "token": " you", "is_final": false}

event: complete
data: {"type": "assistant_message", "session_id": "sess_1", "message_id": "msg_123", "is_final": true}
```

---

## 2.3 Agent Runtime ↔ LLM Proxy (REST + SSE)

### Запрос к LLM:

```http
POST /llm/stream HTTP/1.1
Content-Type: application/json
X-Internal-Auth: internal-llm-key

{
  "model": "gpt-4-turbo",
  "messages": [
    {"role": "user", "content": "Refactor auth module"}
  ],
  "tools": [...],
  "temperature": 0.7,
  "stream": true
}
```

### SSE Response от LLM Proxy:

```http
HTTP/1.1 200 OK
Content-Type: text/event-stream

event: token
data: {"type": "token", "token": "I'll", "index": 0}

event: token
data: {"type": "token", "token": " analyze", "index": 1}

event: tool_call
data: {"type": "tool_call", "id": "call_abc", "name": "read_file", "arguments": "{\"path\": \"src/auth.js\"}"}

event: token
data: {"type": "token", "token": " the", "index": 2}

event: complete
data: {"type": "complete", "finish_reason": "stop", "usage": {"prompt_tokens": 50, "completion_tokens": 150, "total_tokens": 200}}
```

---

# 3. Обработка ошибок в streaming

## 3.1 Прерывание соединения

### WebSocket (IDE ↔ Gateway):
```json
{
  "type": "error",
  "code": "STREAM_INTERRUPTED",
  "message": "Connection lost during streaming",
  "recovery": {
    "message_id": "msg_123",
    "last_token_index": 42
  }
}
```

### SSE (между сервисами):
```
event: error
data: {"type": "error", "code": "PROVIDER_ERROR", "message": "LLM provider timeout"}

event: retry
data: {"retry_after": 1000}
```

## 3.2 Восстановление streaming

Gateway должен:
1. Буферизировать последние N токенов (по умолчанию 10)
2. При reconnect отправить buffered токены
3. Продолжить streaming с точки прерывания

---

# 4. Примеры реализации

## 4.1 FastAPI SSE endpoint (Agent Runtime):

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator
import json
import asyncio

app = FastAPI()

async def generate_tokens(session_id: str, message: dict) -> AsyncGenerator[str, None]:
    """Генератор SSE событий"""
    
    # Начало reasoning
    async for token in llm_proxy.stream_completion(message):
        if token.type == "text":
            event = {
                "type": "assistant_message",
                "session_id": session_id,
                "message_id": token.message_id,
                "token": token.text,
                "is_final": False
            }
            yield f"event: token\ndata: {json.dumps(event)}\n\n"
            
        elif token.type == "tool_call":
            event = {
                "type": "tool_call",
                "call_id": token.call_id,
                "tool_name": token.name,
                "args": token.arguments
            }
            yield f"event: tool_call\ndata: {json.dumps(event)}\n\n"
    
    # Завершение
    complete_event = {
        "type": "assistant_message",
        "session_id": session_id,
        "message_id": message_id,
        "is_final": True
    }
    yield f"event: complete\ndata: {json.dumps(complete_event)}\n\n"

@app.post("/agent/message/stream")
async def stream_message(request: MessageRequest):
    return StreamingResponse(
        generate_tokens(request.session_id, request.message),
        media_type="text/event-stream"
    )
```

## 4.2 Gateway WebSocket relay:

```python
import aiohttp
import json
from fastapi import WebSocket

async def relay_sse_to_websocket(
    sse_url: str, 
    websocket: WebSocket,
    session_id: str
):
    """Проксирует SSE stream в WebSocket"""
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            sse_url,
            json={"session_id": session_id},
            headers={"X-Internal-Auth": INTERNAL_KEY}
        ) as response:
            
            async for line in response.content:
                if line.startswith(b"data: "):
                    data = json.loads(line[6:])
                    
                    # Преобразуем формат для IDE
                    if data["type"] == "assistant_message":
                        await websocket.send_json({
                            "type": "assistant_message",
                            "message_id": data["message_id"],
                            "token": data.get("token", ""),
                            "is_final": data.get("is_final", False)
                        })
                    
                    elif data["type"] == "tool_call":
                        await websocket.send_json(data)
```

## 4.3 Client-side WebSocket handler (IDE):

```dart
// Flutter WebSocket streaming handler
void handleStreaming(WebSocketChannel channel) {
  channel.stream.listen(
    (message) {
      final data = jsonDecode(message);
      
      switch (data['type']) {
        case 'assistant_message':
          if (data['is_final']) {
            completeMessage(data['message_id']);
          } else {
            appendToken(data['message_id'], data['token']);
          }
          break;
          
        case 'tool_call':
          executeToolCall(data);
          break;
          
        case 'error':
          handleStreamError(data);
          break;
      }
    },
    onError: (error) => handleConnectionError(error),
    onDone: () => handleConnectionClosed(),
  );
}
```

---

# 5. Производительность и оптимизация

## 5.1 Буферизация

- **Gateway:** буферизует до 10 последних токенов
- **Agent Runtime:** буферизует tool_calls до получения полного JSON
- **IDE:** буферизует токены для рендеринга по словам/строкам

## 5.2 Batching

При высокой скорости генерации токенов:
- Группировка токенов в пакеты по 5-10 штук
- Отправка с интервалом 50-100ms
- Снижение overhead на мелких сообщениях

## 5.3 Compression

- WebSocket: включить per-message deflate
- SSE: использовать gzip encoding
- Экономия bandwidth до 70%

---

# 6. Мониторинг streaming

Метрики для отслеживания:

1. **Latency:**
   - Time to first token (TTFT)
   - Inter-token delay
   - End-to-end latency

2. **Throughput:**
   - Tokens per second
   - Messages per second
   - Active streams count

3. **Errors:**
   - Stream interruptions
   - Recovery attempts
   - Failed streams

Пример метрик в логах:

```json
{
  "event": "stream_complete",
  "session_id": "sess_1",
  "message_id": "msg_123",
  "metrics": {
    "ttft_ms": 234,
    "total_tokens": 150,
    "duration_ms": 3456,
    "tokens_per_second": 43.4,
    "interruptions": 0
  }
}
```

---

# 7. Совместимость с компонентами

Этот протокол используется в:
- [tech-req-gateway.md](./tech-req-gateway.md) - WebSocket relay
- [tech-req-agent-runtime-service.md](./tech-req-agent-runtime-service.md) - SSE generation
- [tech-req-llm-proxy-service.md](./tech-req-llm-proxy-service.md) - LLM streaming
- [flow-flutter-ide-poc.md](./flow-flutter-ide-poc.md) - WebSocket consumption
