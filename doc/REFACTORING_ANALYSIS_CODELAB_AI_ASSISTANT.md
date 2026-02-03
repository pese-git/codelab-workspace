# Анализ и рекомендации по рефакторингу codelab-ai-service

**Дата:** 2 февраля 2026  
**Версия:** 1.0  
**Статус:** ✅ Готово к обсуждению

---

## Оглавление

1. [Обзор архитектуры](#обзор-архитектуры)
2. [Анализ протокола взаимодействия](#анализ-протокола-взаимодействия)
3. [Выявленные проблемы](#выявленные-проблемы)
4. [Рекомендации по рефакторингу](#рекомендации-по-рефакторингу)
5. [План миграции](#план-миграции)

---

## Обзор архитектуры

### Текущая структура

Система состоит из двух основных компонентов:

```
┌─────────────────┐         WebSocket          ┌──────────────────┐
│   codelab_ide   │ ◄─────────────────────────► │     gateway      │
│   (клиент)      │                             │   (прокси-слой)  │
└─────────────────┘                             └──────────────────┘
                                                         │
                                                         │ HTTP/SSE
                                                         ▼
                                                ┌──────────────────┐
                                                │  agent-runtime   │
                                                │  (бизнес-логика) │
                                                └──────────────────┘
```

#### Gateway Service
- **Роль:** Прокси-слой между IDE и agent-runtime
- **Протокол с IDE:** WebSocket (двунаправленный)
- **Протокол с agent-runtime:** HTTP + SSE streaming
- **Основные файлы:**
  - `gateway/app/main.py` - точка входа
  - `gateway/app/api/v1/endpoints.py` - все endpoints (658 строк!)
  - `gateway/app/models/websocket.py` - модели протокола
  - `gateway/app/services/session_manager.py` - управление WS-сессиями
  - `gateway/app/services/token_buffer_manager.py` - буферизация токенов

#### Agent Runtime Service
- **Роль:** Основная бизнес-логика AI-агентов
- **Архитектура:** Clean Architecture + DDD + Event-Driven
- **Основные компоненты:**
  - Domain Layer (entities, services, repositories)
  - Application Layer (commands, queries, coordinators)
  - Infrastructure Layer (persistence, events)
  - API Layer (routers, schemas)

---

## Анализ протокола взаимодействия

### Протокол Gateway ↔ IDE (WebSocket)

**Типы сообщений от IDE к Gateway:**
- `user_message` - сообщение пользователя
- `tool_result` - результат выполнения инструмента
- `switch_agent` - запрос переключения агента
- `hitl_decision` - решение пользователя по HITL
- `plan_decision` - решение по одобрению плана

**Типы сообщений от Gateway к IDE:**
- `assistant_message` - ответ ассистента (streaming)
- `tool_call` - запрос на выполнение инструмента
- `agent_switched` - уведомление о переключении агента
- `plan_approval_required` - запрос одобрения плана
- `error` - сообщение об ошибке

### Протокол Gateway ↔ Agent Runtime (HTTP/SSE)

**REST Endpoints (прокси):**
- `GET /agents` - список агентов
- `GET /agents/{session_id}/current` - текущий агент
- `GET /sessions` - список сессий
- `POST /sessions` - создание сессии
- `GET /sessions/{session_id}/history` - история сообщений
- `GET /sessions/{session_id}/pending-approvals` - ожидающие одобрения
- `GET /events/metrics/*` - метрики
- `GET /events/audit-log` - аудит-лог

**Streaming Endpoint:**
- `POST /agent/message/stream` - обработка сообщений через SSE

---

## Выявленные проблемы

### 🔴 Критические проблемы

#### 1. Массивное дублирование кода в Gateway endpoints

**Проблема:** В файле `gateway/app/api/v1/endpoints.py` (658 строк) содержится 10+ proxy endpoints с идентичной структурой обработки ошибок.

**Пример дублирования:**
```python
# Повторяется в каждом endpoint:
async with httpx.AsyncClient(timeout=30.0) as client:
    try:
        response = await client.get(
            f"{AppConfig.AGENT_URL}/...",
            headers={"X-Internal-Auth": AppConfig.INTERNAL_API_KEY},
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"Agent Runtime error: {e.response.status_code}, {e.response.text}")
        return JSONResponse(
            status_code=e.response.status_code,
            content={"error": f"Agent Runtime error: {e.response.status_code}"}
        )
    except Exception as e:
        logger.error(f"Error proxying to Agent Runtime: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Gateway error: {str(e)}"}
        )
```

**Количество повторений:** ~10 раз (строки 38-63, 66-92, 95-121, 124-150, 153-182, 185-230, 233-282, 285-317, 320-359, 362-412)

**Влияние:**
- Сложность поддержки (изменения нужно вносить в 10 местах)
- Высокий риск ошибок при модификации
- Нарушение DRY принципа

---

#### 2. Монолитный WebSocket handler

**Проблема:** WebSocket endpoint в `gateway/app/api/v1/endpoints.py` (строки 452-658) содержит 206 строк сложной логики в одной функции.

**Что делает функция:**
1. Принимает WebSocket соединение
2. Парсит и валидирует 5 разных типов сообщений
3. Пересылает в agent-runtime через HTTP streaming
4. Парсит SSE stream
5. Обрабатывает ошибки
6. Управляет lifecycle соединения

**Проблемы:**
- Нарушение Single Responsibility Principle
- Сложность тестирования
- Трудность добавления новых типов сообщений
- Смешивание concerns (парсинг, валидация, проксирование, обработка ошибок)

---

#### 3. Отсутствие абстракции для HTTP-клиента

**Проблема:** Прямое использование `httpx.AsyncClient` в каждом endpoint без абстракции.

**Последствия:**
- Невозможность легко подменить HTTP-клиент
- Сложность добавления middleware (retry, circuit breaker, rate limiting)
- Затруднено тестирование (нужно мокать httpx напрямую)
- Дублирование конфигурации (timeout, headers)

---

### 🟡 Средние проблемы

#### 4. Слабая типизация в WebSocket протоколе

**Проблема:** В WebSocket handler используется динамическая обработка `message_data.get("type")` без строгой типизации.

**Код:**
```python
ide_msg = json.loads(raw_msg)
msg_type = ide_msg.get("type")

if msg_type == "user_message":
    msg = WSUserMessage.model_validate(ide_msg)
elif msg_type == "tool_result":
    msg = WSToolResult.model_validate(ide_msg)
# ... еще 3 типа
```

**Проблемы:**
- Валидация происходит после парсинга типа
- Нет единой точки валидации
- Сложно добавить новый тип сообщения
- Отсутствует type safety на уровне кода

---

#### 5. Отсутствие централизованной обработки ошибок

**Проблема:** Каждый endpoint обрабатывает ошибки по-своему, нет единого подхода.

**Примеры различий:**
- Некоторые endpoints возвращают `JSONResponse` с ошибкой
- WebSocket handler отправляет `WSErrorResponse`
- Разные форматы логирования
- Разные HTTP статус-коды для похожих ошибок

---

#### 6. Избыточная логика в роутерах agent-runtime

**Проблема:** В `agent-runtime/app/api/v1/routers/messages_router.py` (310 строк) содержится много повторяющейся логики для разных типов сообщений.

**Дублирование:**
```python
# Повторяется для каждого типа сообщения:
async def generate():
    try:
        async for chunk in service.process_xxx(...):
            yield f"data: {chunk.model_dump_json()}\n\n"
    except Exception as e:
        logger.error(f"Error processing xxx: {e}", exc_info=True)
        error_chunk = StreamChunk(type="error", error=str(e), is_final=True)
        yield f"data: {error_chunk.model_dump_json()}\n\n"

return StreamingResponse(
    generate(),
    media_type="text/event-stream",
    headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no"
    }
)
```

**Количество повторений:** 5 раз (для каждого типа сообщения)

---

### 🟢 Незначительные проблемы

#### 7. Неоптимальная структура конфигурации

**Проблема:** `AppConfig` в gateway использует переменные класса вместо instance variables.

```python
class AppConfig:
    AGENT_URL: str = os.getenv("GATEWAY__AGENT_URL", "http://localhost:8001")
    INTERNAL_API_KEY: str = os.getenv("GATEWAY__INTERNAL_API_KEY", "change-me-internal-key")
    # ...
```

**Недостатки:**
- Невозможно создать несколько конфигураций для тестирования
- Сложно переопределить значения в тестах
- Нет валидации конфигурации при старте

---

#### 8. Отсутствие метрик и observability в Gateway

**Проблема:** Gateway не собирает метрики о:
- Количестве активных WebSocket соединений
- Времени обработки запросов
- Количестве ошибок проксирования
- Размере передаваемых данных

---

## Рекомендации по рефакторингу

### Приоритет 1: Рефакторинг Gateway (не нарушает протокол)

#### Рекомендация 1.1: Создать HTTP Proxy Service

**Цель:** Устранить дублирование кода в proxy endpoints.

**Решение:**
```python
# gateway/app/services/agent_runtime_proxy.py

from typing import Optional, Dict, Any
import httpx
from fastapi.responses import JSONResponse

class AgentRuntimeProxy:
    """Сервис для проксирования запросов в Agent Runtime."""
    
    def __init__(
        self,
        base_url: str,
        internal_api_key: str,
        timeout: float = 30.0
    ):
        self._base_url = base_url
        self._internal_api_key = internal_api_key
        self._timeout = timeout
    
    async def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None
    ) -> JSONResponse:
        """Проксировать GET запрос."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await client.get(
                    f"{self._base_url}{path}",
                    params=params,
                    headers={"X-Internal-Auth": self._internal_api_key},
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                return self._handle_http_error(e)
            except Exception as e:
                return self._handle_generic_error(e)
    
    async def post(
        self,
        path: str,
        json: Optional[Dict[str, Any]] = None
    ) -> JSONResponse:
        """Проксировать POST запрос."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await client.post(
                    f"{self._base_url}{path}",
                    json=json,
                    headers={"X-Internal-Auth": self._internal_api_key},
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                return self._handle_http_error(e)
            except Exception as e:
                return self._handle_generic_error(e)
    
    def _handle_http_error(self, e: httpx.HTTPStatusError) -> JSONResponse:
        """Обработать HTTP ошибку от Agent Runtime."""
        logger.error(
            f"Agent Runtime error: {e.response.status_code}, "
            f"{e.response.text}"
        )
        return JSONResponse(
            status_code=e.response.status_code,
            content={
                "error": f"Agent Runtime error: {e.response.status_code}"
            }
        )
    
    def _handle_generic_error(self, e: Exception) -> JSONResponse:
        """Обработать общую ошибку."""
        logger.error(f"Error proxying to Agent Runtime: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Gateway error: {str(e)}"}
        )
```

**Использование:**
```python
# gateway/app/api/v1/endpoints.py

@router.get("/agents")
async def list_agents(proxy: AgentRuntimeProxy = Depends(get_proxy)):
    return await proxy.get("/agents")

@router.get("/sessions")
async def list_sessions(proxy: AgentRuntimeProxy = Depends(get_proxy)):
    return await proxy.get("/sessions")

@router.post("/sessions")
async def create_session(proxy: AgentRuntimeProxy = Depends(get_proxy)):
    return await proxy.post("/sessions")
```

**Результат:**
- ✅ Устранено дублирование ~200 строк кода
- ✅ Единая точка обработки ошибок
- ✅ Легко добавить retry, circuit breaker
- ✅ Упрощено тестирование
- ✅ **Протокол не нарушен**

---

#### Рекомендация 1.2: Рефакторинг WebSocket Handler

**Цель:** Разделить монолитный handler на компоненты.

**Решение:**
```python
# gateway/app/services/websocket/message_parser.py

from typing import Union
from pydantic import ValidationError
from app.models.websocket import (
    WSUserMessage, WSToolResult, WSSwitchAgent,
    WSHITLDecision, WSPlanDecision
)

WSMessage = Union[
    WSUserMessage,
    WSToolResult,
    WSSwitchAgent,
    WSHITLDecision,
    WSPlanDecision
]

class WebSocketMessageParser:
    """Парсер WebSocket сообщений с валидацией."""
    
    def parse(self, raw_message: str) -> WSMessage:
        """
        Парсит и валидирует WebSocket сообщение.
        
        Raises:
            ValueError: Если сообщение невалидно
        """
        try:
            data = json.loads(raw_message)
            msg_type = data.get("type")
            
            if msg_type == "user_message":
                return WSUserMessage.model_validate(data)
            elif msg_type == "tool_result":
                return WSToolResult.model_validate(data)
            elif msg_type == "switch_agent":
                return WSSwitchAgent.model_validate(data)
            elif msg_type == "hitl_decision":
                return WSHITLDecision.model_validate(data)
            elif msg_type == "plan_decision":
                return WSPlanDecision.model_validate(data)
            else:
                raise ValueError(f"Unknown message type: {msg_type}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")
        except ValidationError as e:
            raise ValueError(f"Validation error: {e}")


# gateway/app/services/websocket/sse_stream_handler.py

class SSEStreamHandler:
    """Обработчик SSE stream от Agent Runtime."""
    
    async def process_stream(
        self,
        response: httpx.Response,
        websocket: WebSocket
    ) -> None:
        """
        Читает SSE stream и пересылает события в WebSocket.
        """
        current_event_type = None
        
        async for line in response.aiter_lines():
            if not line:
                current_event_type = None
                continue
            
            if line.startswith("event: "):
                current_event_type = line[7:].strip()
                if current_event_type == "done":
                    break
                continue
            
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                
                if current_event_type == "message":
                    await self._forward_message(data_str, websocket)
                continue
            
            if line.startswith(":"):
                # Heartbeat, игнорируем
                continue
    
    async def _forward_message(
        self,
        data_str: str,
        websocket: WebSocket
    ) -> None:
        """Пересылает сообщение в WebSocket."""
        try:
            data = json.loads(data_str)
            # Фильтруем null значения
            filtered_data = {k: v for k, v in data.items() if v is not None}
            await websocket.send_json(filtered_data)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse SSE data: {e}")


# gateway/app/services/websocket/websocket_handler.py

class WebSocketHandler:
    """Главный обработчик WebSocket соединений."""
    
    def __init__(
        self,
        message_parser: WebSocketMessageParser,
        sse_handler: SSEStreamHandler,
        agent_runtime_url: str,
        internal_api_key: str
    ):
        self._parser = message_parser
        self._sse_handler = sse_handler
        self._agent_runtime_url = agent_runtime_url
        self._internal_api_key = internal_api_key
    
    async def handle_connection(
        self,
        websocket: WebSocket,
        session_id: str
    ) -> None:
        """Обрабатывает WebSocket соединение."""
        await websocket.accept()
        logger.info(f"[{session_id}] WebSocket connected")
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                while True:
                    # Получаем и парсим сообщение
                    raw_msg = await websocket.receive_text()
                    
                    try:
                        message = self._parser.parse(raw_msg)
                    except ValueError as e:
                        await self._send_error(websocket, str(e))
                        continue
                    
                    # Пересылаем в Agent Runtime
                    await self._forward_to_agent(
                        client,
                        websocket,
                        session_id,
                        message
                    )
        except WebSocketDisconnect:
            logger.info(f"[{session_id}] WebSocket disconnected")
        except Exception as e:
            logger.error(f"[{session_id}] WS fatal error: {e}", exc_info=True)
    
    async def _forward_to_agent(
        self,
        client: httpx.AsyncClient,
        websocket: WebSocket,
        session_id: str,
        message: WSMessage
    ) -> None:
        """Пересылает сообщение в Agent Runtime через HTTP streaming."""
        try:
            async with client.stream(
                "POST",
                f"{self._agent_runtime_url}/agent/message/stream",
                json={
                    "session_id": session_id,
                    "message": message.model_dump()
                },
                headers={"X-Internal-Auth": self._internal_api_key},
            ) as response:
                response.raise_for_status()
                await self._sse_handler.process_stream(response, websocket)
        except httpx.HTTPStatusError as e:
            error_msg = f"Agent error: {e.response.status_code}"
            await self._send_error(websocket, error_msg)
        except Exception as e:
            error_msg = f"Streaming error: {str(e)}"
            await self._send_error(websocket, error_msg)
    
    async def _send_error(self, websocket: WebSocket, message: str) -> None:
        """Отправляет сообщение об ошибке в WebSocket."""
        error = WSErrorResponse(type="error", content=message)
        await websocket.send_json(error.model_dump())
```

**Использование:**
```python
# gateway/app/api/v1/endpoints.py

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    handler: WebSocketHandler = Depends(get_websocket_handler)
):
    """WebSocket endpoint для связи с IDE."""
    await handler.handle_connection(websocket, session_id)
```

**Результат:**
- ✅ Разделение ответственности (SRP)
- ✅ Упрощено тестирование каждого компонента
- ✅ Легко добавить новые типы сообщений
- ✅ Улучшена читаемость кода
- ✅ **Протокол не нарушен**

---

#### Рекомендация 1.3: Улучшить конфигурацию

**Цель:** Сделать конфигурацию более гибкой и тестируемой.

**Решение:**
```python
# gateway/app/core/config.py

from pydantic_settings import BaseSettings
from pydantic import Field, validator

class AppConfig(BaseSettings):
    """Конфигурация Gateway сервиса."""
    
    # Agent Runtime
    agent_url: str = Field(
        default="http://localhost:8001",
        description="URL Agent Runtime сервиса"
    )
    internal_api_key: str = Field(
        default="change-me-internal-key",
        description="Ключ для внутренней аутентификации"
    )
    
    # Timeouts
    request_timeout: float = Field(
        default=30.0,
        ge=1.0,
        le=300.0,
        description="Таймаут для обычных запросов (сек)"
    )
    agent_stream_timeout: float = Field(
        default=60.0,
        ge=1.0,
        le=600.0,
        description="Таймаут для streaming запросов (сек)"
    )
    
    # Logging
    log_level: str = Field(
        default="INFO",
        description="Уровень логирования"
    )
    
    # Auth
    use_jwt_auth: bool = Field(
        default=False,
        description="Использовать JWT аутентификацию"
    )
    jwt_issuer: str = Field(
        default="https://auth.codelab.local",
        description="JWT issuer"
    )
    jwt_audience: str = Field(
        default="codelab-api",
        description="JWT audience"
    )
    auth_service_url: str = Field(
        default="http://auth-service:8003",
        description="URL Auth сервиса"
    )
    
    # Version
    version: str = Field(
        default="0.1.0",
        description="Версия сервиса"
    )
    
    @property
    def jwks_url(self) -> str:
        """URL для получения JWKS."""
        return f"{self.auth_service_url}/.well-known/jwks.json"
    
    @validator("log_level")
    def validate_log_level(cls, v):
        """Валидация уровня логирования."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {v}")
        return v.upper()
    
    class Config:
        env_prefix = "GATEWAY__"
        case_sensitive = False
        env_file = ".env"
        env_file_encoding = "utf-8"


# Создаем singleton instance
config = AppConfig()
```

**Результат:**
- ✅ Валидация конфигурации при старте
- ✅ Легко создать тестовую конфигурацию
- ✅ Автодокументирование через Field descriptions
- ✅ Type safety
- ✅ **Протокол не нарушен**

---

### Приоритет 2: Рефакторинг Agent Runtime (не нарушает протокол)

#### Рекомендация 2.1: Создать SSE Response Builder

**Цель:** Устранить дублирование в messages_router.

**Решение:**
```python
# agent-runtime/app/api/v1/utils/sse_response.py

from typing import AsyncGenerator, Callable, Awaitable
from fastapi.responses import StreamingResponse
from ....models.schemas import StreamChunk
import logging

logger = logging.getLogger("agent-runtime.api.sse")

class SSEResponseBuilder:
    """Построитель SSE streaming ответов."""
    
    @staticmethod
    def create_stream_response(
        generator: AsyncGenerator[StreamChunk, None],
        operation_name: str
    ) -> StreamingResponse:
        """
        Создает SSE streaming response с обработкой ошибок.
        
        Args:
            generator: Генератор chunks от сервиса
            operation_name: Название операции для логирования
            
        Returns:
            StreamingResponse с SSE форматом
        """
        async def generate():
            try:
                async for chunk in generator:
                    # Логируем специальные типы для отладки
                    if chunk.type == "plan_approval_required":
                        logger.info(
                            f"[SSE] Sending {chunk.type} chunk for {operation_name}"
                        )
                    
                    yield f"data: {chunk.model_dump_json(exclude_none=False)}\n\n"
                    
            except Exception as e:
                logger.error(
                    f"Error in {operation_name}: {e}",
                    exc_info=True
                )
                error_chunk = StreamChunk(
                    type="error",
                    error=str(e),
                    is_final=True
                )
                yield f"data: {error_chunk.model_dump_json()}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
```

**Использование:**
```python
# agent-runtime/app/api/v1/routers/messages_router.py

@router.post("/stream")
async def message_stream_sse(
    request: MessageStreamRequest,
    message_orchestration_service=Depends(get_message_orchestration_service)
):
    session_id = request.session_id
    message_data = request.message
    message_type = message_data.get("type")
    
    if message_type == "user_message":
        content = message_data.get("content", "")
        agent_type_str = message_data.get("agent_type")
        agent_type = AgentType(agent_type_str) if agent_type_str else None
        
        generator = message_orchestration_service.process_message(
            session_id=session_id,
            message=content,
            agent_type=agent_type
        )
        
        return SSEResponseBuilder.create_stream_response(
            generator,
            operation_name=f"user_message[{session_id}]"
        )
    
    elif message_type == "tool_result":
        call_id = message_data.get("call_id")
        result = message_data.get("result")
        error = message_data.get("error")
        
        if not call_id:
            raise HTTPException(400, "call_id is required")
        
        generator = message_orchestration_service.process_tool_result(
            session_id=session_id,
            call_id=call_id,
            result=result,
            error=error
        )
        
        return SSEResponseBuilder.create_stream_response(
            generator,
            operation_name=f"tool_result[{session_id}:{call_id}]"
        )
    
    # ... аналогично для других типов
```

**Результат:**
- ✅ Устранено дублирование ~100 строк кода
- ✅ Единая обработка ошибок в SSE
- ✅ Упрощено добавление новых типов сообщений
- ✅ **Протокол не нарушен**

---

#### Рекомендация 2.2: Создать Message Handler Registry

**Цель:** Упростить добавление новых типов сообщений.

**Решение:**
```python
# agent-runtime/app/api/v1/handlers/message_handler.py

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, Any
from ....models.schemas import StreamChunk

class MessageHandler(ABC):
    """Базовый класс для обработчиков сообщений."""
    
    @abstractmethod
    async def handle(
        self,
        session_id: str,
        message_data: Dict[str, Any],
        orchestration_service
    ) -> AsyncGenerator[StreamChunk, None]:
        """Обработать сообщение."""
        pass
    
    @abstractmethod
    def validate(self, message_data: Dict[str, Any]) -> None:
        """Валидировать данные сообщения."""
        pass


# agent-runtime/app/api/v1/handlers/user_message_handler.py

class UserMessageHandler(MessageHandler):
    """Обработчик user_message."""
    
    def validate(self, message_data: Dict[str, Any]) -> None:
        if "content" not in message_data:
            raise ValueError("content is required")
    
    async def handle(
        self,
        session_id: str,
        message_data: Dict[str, Any],
        orchestration_service
    ) -> AsyncGenerator[StreamChunk, None]:
        content = message_data.get("content", "")
        agent_type_str = message_data.get("agent_type")
        agent_type = AgentType(agent_type_str) if agent_type_str else None
        
        async for chunk in orchestration_service.process_message(
            session_id=session_id,
            message=content,
            agent_type=agent_type
        ):
            yield chunk


# agent-runtime/app/api/v1/handlers/registry.py

class MessageHandlerRegistry:
    """Реестр обработчиков сообщений."""
    
    def __init__(self):
        self._handlers: Dict[str, MessageHandler] = {}
    
    def register(self, message_type: str, handler: MessageHandler) -> None:
        """Зарегистрировать обработчик."""
        self._handlers[message_type] = handler
    
    def get_handler(self, message_type: str) -> MessageHandler:
        """Получить обработчик по типу сообщения."""
        handler = self._handlers.get(message_type)
        if not handler:
            raise ValueError(f"Unknown message type: {message_type}")
        return handler


# Инициализация реестра
registry = MessageHandlerRegistry()
registry.register("user_message", UserMessageHandler())
registry.register("tool_result", ToolResultHandler())
registry.register("switch_agent", SwitchAgentHandler())
registry.register("hitl_decision", HITLDecisionHandler())
registry.register("plan_decision", PlanDecisionHandler())
```

**Использование:**
```python
# agent-runtime/app/api/v1/routers/messages_router.py

@router.post("/stream")
async def message_stream_sse(
    request: MessageStreamRequest,
    message_orchestration_service=Depends(get_message_orchestration_service),
    handler_registry: MessageHandlerRegistry = Depends(get_handler_registry)
):
    session_id = request.session_id
    message_data = request.message
    message_type = message_data.get("type")
    
    try:
        # Получаем обработчик из реестра
        handler = handler_registry.get_handler(message_type)
        
        # Валидируем данные
        handler.validate(message_data)
        
        # Обрабатываем сообщение
        generator = handler.handle(
            session_id,
            message_data,
            message_orchestration_service
        )
        
        # Возвращаем SSE response
        return SSEResponseBuilder.create_stream_response(
            generator,
            operation_name=f"{message_type}[{session_id}]"
        )
        
    except ValueError as e:
        raise HTTPException(400, str(e))
```

**Результат:**
- ✅ Упрощено добавление новых типов сообщений
- ✅ Разделение ответственности
- ✅ Улучшена тестируемость
- ✅ Код роутера сократился с 310 до ~50 строк
- ✅ **Протокол не нарушен**

---

### Приоритет 3: Улучшения без изменения кода

#### Рекомендация 3.1: Добавить метрики в Gateway

**Цель:** Улучшить observability.

**Решение:**
```python
# gateway/app/services/metrics.py

from prometheus_client import Counter, Histogram, Gauge
import time

# Метрики WebSocket
ws_connections_total = Counter(
    "gateway_ws_connections_total",
    "Total WebSocket connections",
    ["session_id"]
)

ws_active_connections = Gauge(
    "gateway_ws_active_connections",
    "Active WebSocket connections"
)

ws_messages_received = Counter(
    "gateway_ws_messages_received_total",
    "Total messages received from IDE",
    ["message_type"]
)

ws_messages_sent = Counter(
    "gateway_ws_messages_sent_total",
    "Total messages sent to IDE",
    ["message_type"]
)

# Метрики проксирования
proxy_requests_total = Counter(
    "gateway_proxy_requests_total",
    "Total proxy requests to Agent Runtime",
    ["endpoint", "method", "status"]
)

proxy_request_duration = Histogram(
    "gateway_proxy_request_duration_seconds",
    "Proxy request duration",
    ["endpoint", "method"]
)

# Метрики ошибок
proxy_errors_total = Counter(
    "gateway_proxy_errors_total",
    "Total proxy errors",
    ["endpoint", "error_type"]
)
```

**Результат:**
- ✅ Visibility в production
- ✅ Возможность настроить алерты
- ✅ Анализ производительности
- ✅ **Протокол не нарушен**

---

#### Рекомендация 3.2: Добавить интеграционные тесты

**Цель:** Гарантировать совместимость протокола.

**Решение:**
```python
# gateway/tests/test_websocket_protocol.py

import pytest
from fastapi.testclient import TestClient

@pytest.mark.asyncio
async def test_user_message_flow():
    """Тест полного flow user_message."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws/test-session") as websocket:
            # Отправляем user_message
            websocket.send_json({
                "type": "user_message",
                "content": "Hello",
                "role": "user"
            })
            
            # Ожидаем assistant_message
            response = websocket.receive_json()
            assert response["type"] == "assistant_message"
            assert "token" in response


@pytest.mark.asyncio
async def test_tool_call_flow():
    """Тест flow с tool_call."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws/test-session") as websocket:
            # Отправляем сообщение
            websocket.send_json({
                "type": "user_message",
                "content": "Read file test.py",
                "role": "user"
            })
            
            # Ожидаем tool_call
            response = websocket.receive_json()
            assert response["type"] == "tool_call"
            call_id = response["call_id"]
            
            # Отправляем tool_result
            websocket.send_json({
                "type": "tool_result",
                "call_id": call_id,
                "result": {"content": "file content"}
            })
            
            # Ожидаем продолжение
            response = websocket.receive_json()
            assert response["type"] == "assistant_message"
```

**Результат:**
- ✅ Защита от регрессий
- ✅ Документация протокола через тесты
- ✅ Уверенность при рефакторинге
- ✅ **Протокол не нарушен**

---

## План миграции

### Фаза 1: Gateway Refactoring (1-2 недели)

**Неделя 1:**
1. ✅ Создать `AgentRuntimeProxy` сервис
2. ✅ Рефакторить все proxy endpoints
3. ✅ Добавить unit тесты для proxy
4. ✅ Обновить конфигурацию на Pydantic Settings

**Неделя 2:**
1. ✅ Создать `WebSocketMessageParser`
2. ✅ Создать `SSEStreamHandler`
3. ✅ Создать `WebSocketHandler`
4. ✅ Рефакторить WebSocket endpoint
5. ✅ Добавить интеграционные тесты

**Критерии успеха:**
- Все существующие тесты проходят
- Новые тесты покрывают >80% кода
- Протокол работает без изменений
- Код gateway сокращен на ~300 строк

---

### Фаза 2: Agent Runtime Refactoring (1 неделя)

**Неделя 3:**
1. ✅ Создать `SSEResponseBuilder`
2. ✅ Создать `MessageHandler` абстракцию
3. ✅ Создать `MessageHandlerRegistry`
4. ✅ Реализовать handlers для всех типов сообщений
5. ✅ Рефакторить `messages_router`
6. ✅ Добавить unit тесты

**Критерии успеха:**
- Все существующие тесты проходят
- Код messages_router сокращен с 310 до ~50 строк
- Легко добавить новый тип сообщения
- Протокол работает без изменений

---

### Фаза 3: Observability (1 неделя)

**Неделя 4:**
1. ✅ Добавить Prometheus метрики в Gateway
2. ✅ Добавить Prometheus метрики в Agent Runtime
3. ✅ Настроить Grafana дашборды
4. ✅ Добавить health checks
5. ✅ Документировать метрики

**Критерии успеха:**
- Метрики собираются корректно
- Дашборды показывают ключевые показатели
- Настроены базовые алерты

---

## Заключение

### Ключевые выводы

1. **Протокол взаимодействия хорошо спроектирован** и не требует изменений
2. **Основные проблемы** - дублирование кода и монолитные функции
3. **Все рефакторинги** можно выполнить без нарушения протокола
4. **Архитектура agent-runtime** следует Clean Architecture, но есть возможности для улучшения на уровне API

### Приоритеты

**Высокий приоритет (сделать в первую очередь):**
- ✅ Рефакторинг Gateway proxy endpoints (Рекомендация 1.1)
- ✅ Рефакторинг WebSocket handler (Рекомендация 1.2)
- ✅ Рефакторинг messages_router (Рекомендация 2.1)

**Средний приоритет:**
- ⚠️ Message Handler Registry (Рекомендация 2.2)
- ⚠️ Улучшение конфигурации (Рекомендация 1.3)

**Низкий приоритет:**
- 📊 Метрики и observability (Рекомендация 3.1)
- 🧪 Интеграционные тесты (Рекомендация 3.2)

### Ожидаемые результаты

После выполнения всех рекомендаций:
- **Сокращение кода:** ~500 строк
- **Улучшение поддерживаемости:** значительное
- **Упрощение тестирования:** значительное
- **Нарушение протокола:** ❌ НЕТ
- **Breaking changes:** ❌ НЕТ

---

**Документ подготовлен:** 2 февраля 2026  
**Автор:** AI Code Analyzer  
**Статус:** ✅ Готово к обсуждению и реализации
