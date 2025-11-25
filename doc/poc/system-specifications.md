# 🟥 **System Specifications — Codelab POC**
Версия: 1.0
Статус: Дополнительные спецификации для POC

---

# 1. Health Check Protocol

## 1.1 Назначение

Health check endpoints необходимы для:
- Мониторинга доступности сервисов
- Автоматического перезапуска при сбоях
- Load balancer health checks
- Диагностики проблем

## 1.2 Стандартный формат

Все сервисы POC должны реализовать endpoint:

```
GET /health
```

### Успешный ответ (200 OK):

```json
{
  "status": "healthy",
  "service": "gateway-service",
  "version": "1.0.0",
  "uptime": 3600,
  "timestamp": "2025-11-26T10:30:00Z",
  "checks": {
    "database": "ok",
    "redis": "ok",
    "downstream_services": {
      "agent_runtime": "ok",
      "llm_proxy": "ok"
    }
  }
}
```

### Ответ при проблемах (503 Service Unavailable):

```json
{
  "status": "unhealthy",
  "service": "gateway-service",
  "version": "1.0.0",
  "timestamp": "2025-11-26T10:30:00Z",
  "checks": {
    "database": "ok",
    "redis": "error: connection refused",
    "downstream_services": {
      "agent_runtime": "ok",
      "llm_proxy": "timeout"
    }
  }
}
```

## 1.3 Проверки для каждого сервиса

### Gateway Service:
- WebSocket server status
- Connection to Agent Runtime Service
- Memory usage < 80%

### Agent Runtime Service:
- Connection to LLM Proxy
- Session storage availability
- Active sessions count

### LLM Proxy Service:
- At least one LLM provider available
- Rate limit not exceeded
- Response time < 5s

## 1.4 Liveness vs Readiness

```
GET /health/live   # Процесс жив
GET /health/ready  # Готов обслуживать запросы
```

---

# 2. File Size Limits

## 2.1 Ограничения для tool_result

### read_file:
- **Максимальный размер файла:** 1 MB (1,048,576 bytes)
- **Максимальная длина пути:** 255 символов
- **Поддерживаемые кодировки:** UTF-8 (в POC)

### write_file:
- **Максимальный размер содержимого:** 1 MB
- **Максимальная длина пути:** 255 символов

### git.diff:
- **Максимальный размер diff:** 5 MB
- **Максимальное количество файлов в diff:** 100

### apply_patch:
- **Максимальный размер patch:** 5 MB
- **Максимальное количество изменяемых файлов:** 50

### Обработка превышения лимитов:

```json
{
  "type": "tool_result",
  "call_id": "call_123",
  "error": {
    "code": "FILE_TOO_LARGE",
    "message": "File size 2.5MB exceeds maximum allowed size of 1MB",
    "details": {
      "file_size": 2621440,
      "max_size": 1048576
    }
  }
}
```

## 2.2 Ограничения для сообщений

### WebSocket сообщения:
- **Максимальный размер сообщения:** 10 MB
- **Максимальная длина user_message:** 10,000 символов
- **Максимальное количество токенов в ответе:** 4,096 (настраивается)

### Streaming токены:
- **Максимальный размер одного токена:** 1 KB
- **Максимальная частота отправки:** 100 токенов/сек

---

# 3. Authentication Protocol

## 3.1 Базовая аутентификация для POC

### API Key Authentication

Все запросы к сервисам должны содержать API key в заголовке:

```
Authorization: Bearer sk-poc-XXXXXXXXXXXXXXXX
```

### Формат API Key:
- Префикс: `sk-poc-` (для POC)
- Длина: 32 символа после префикса
- Символы: alphanumeric (a-z, A-Z, 0-9)

### Пример запроса:

```http
GET /health HTTP/1.1
Host: gateway.codelab.ai
Authorization: Bearer sk-poc-abcd1234efgh5678ijkl9012mnop3456
```

## 3.2 WebSocket аутентификация

### Вариант 1: Query parameter (для POC)

```
ws://gateway.codelab.ai/ws/session123?api_key=sk-poc-XXXXX
```

### Вариант 2: Первое сообщение

```json
{
  "type": "auth",
  "api_key": "sk-poc-XXXXX"
}
```

Ответ при успешной аутентификации:

```json
{
  "type": "auth_result",
  "status": "authenticated",
  "session_id": "sess_abc123"
}
```

Ответ при ошибке:

```json
{
  "type": "auth_result",
  "status": "failed",
  "error": "Invalid API key"
}
```

## 3.3 Межсервисная аутентификация

Для взаимодействия между сервисами используется внутренний ключ:

```
X-Internal-Auth: internal-poc-key-XXXXX
```

### Проверка прав:

```python
# Gateway → Agent Runtime
headers = {
    "X-Internal-Auth": "internal-poc-key-12345",
    "X-Original-User": "user-api-key-hash"
}
```

## 3.4 Обработка ошибок аутентификации

### 401 Unauthorized:

```json
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Missing or invalid API key"
  }
}
```

### 403 Forbidden:

```json
{
  "error": {
    "code": "FORBIDDEN",
    "message": "API key does not have access to this resource"
  }
}
```

---

# 4. Rate Limiting (MVP)

## 4.1 Лимиты для POC

### Per API Key:
- **Requests per minute:** 60
- **Requests per hour:** 1000
- **Concurrent WebSocket connections:** 5

### Per IP (fallback):
- **Requests per minute:** 20
- **Requests per hour:** 200

### LLM Requests:
- **Tokens per minute:** 10,000
- **Requests per minute:** 10

## 4.2 Rate Limit Headers

Ответ включает заголовки:

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1701234567
```

## 4.3 Превышение лимита (429 Too Many Requests):

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Try again in 30 seconds.",
    "retry_after": 30
  }
}
```

---

# 5. Интеграция с другими документами

Эти спецификации дополняют:
- [tools-specification.md](./tools-specification.md) - для лимитов размеров файлов
- [tech-req-gateway.md](./tech-req-gateway.md) - для health checks и аутентификации
- [tech-req-agent-runtime-service.md](./tech-req-agent-runtime-service.md) - для межсервисной аутентификации
- [tech-req-llm-proxy-service.md](./tech-req-llm-proxy-service.md) - для rate limiting

---

# 6. Конфигурация (config.yaml пример)

```yaml
# Limits configuration
limits:
  file:
    max_size: 1048576  # 1MB
    max_path_length: 255
  diff:
    max_size: 5242880  # 5MB
    max_files: 100
  message:
    max_size: 10485760  # 10MB
    max_user_message_length: 10000
  streaming:
    max_tokens: 4096
    max_tokens_per_second: 100

# Authentication
auth:
  api_key_prefix: "sk-poc-"
  internal_key: ${INTERNAL_AUTH_KEY}
  
# Rate limits
rate_limits:
  per_api_key:
    requests_per_minute: 60
    requests_per_hour: 1000
  per_ip:
    requests_per_minute: 20
    requests_per_hour: 200
  llm:
    tokens_per_minute: 10000
    requests_per_minute: 10

# Health check
health_check:
  interval: 30s
  timeout: 5s
  failure_threshold: 3
```

---

# 7. Примеры реализации

## 7.1 Health check endpoint (FastAPI):

```python
from fastapi import FastAPI, status
from datetime import datetime
import time

app = FastAPI()
start_time = time.time()

@app.get("/health")
async def health_check():
    checks = {
        "database": check_database(),
        "redis": check_redis(),
        "downstream_services": {
            "agent_runtime": await check_agent_runtime(),
            "llm_proxy": await check_llm_proxy()
        }
    }
    
    is_healthy = all(
        check == "ok" 
        for check in checks.values() 
        if isinstance(check, str)
    )
    
    return {
        "status": "healthy" if is_healthy else "unhealthy",
        "service": "gateway-service",
        "version": "1.0.0",
        "uptime": int(time.time() - start_time),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "checks": checks
    }, status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
```

## 7.2 API Key validation:

```python
from fastapi import Header, HTTPException

async def validate_api_key(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer sk-poc-"):
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "UNAUTHORIZED", "message": "Missing or invalid API key"}}
        )
    
    api_key = authorization.replace("Bearer ", "")
    # Validate key format and check in database
    if not is_valid_api_key(api_key):
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "UNAUTHORIZED", "message": "Invalid API key"}}
        )
    
    return api_key
```

## 7.3 File size validation:

```python
MAX_FILE_SIZE = 1048576  # 1MB

def validate_file_size(content: str, file_path: str):
    size = len(content.encode('utf-8'))
    if size > MAX_FILE_SIZE:
        return {
            "error": {
                "code": "FILE_TOO_LARGE",
                "message": f"File size {size/1048576:.1f}MB exceeds maximum allowed size of 1MB",
                "details": {
                    "file_size": size,
                    "max_size": MAX_FILE_SIZE
                }
            }
        }
    return None
```
