# Анализ ответственности stream_response: Правильное разделение по слоям

**Дата:** 24 января 2026  
**Вопрос:** За что должна отвечать функция `stream_response()` и на каком слое должна быть реализована?

---

## Краткий ответ

**Функция `stream_response()` должна быть разделена на несколько компонентов по разным слоям:**

1. **Infrastructure Layer** - `LLMClient`: Вызов LLM API и парсинг ответа
2. **Domain Layer** - `LLMResponseProcessor`: Бизнес-логика обработки ответа
3. **Application Layer** - `StreamLLMResponseHandler`: Координация и оркестрация
4. **API Layer** - Роутер: Прием HTTP запроса и возврат SSE стрима

---

## Детальный анализ по слоям

### 1. Infrastructure Layer (Инфраструктурный слой)

**Ответственность:** Технические детали взаимодействия с внешними системами

#### 1.1 LLMClient - Вызов LLM API

```python
# app/infrastructure/llm/client.py

from typing import List, Dict
from abc import ABC, abstractmethod

class LLMResponse:
    """Доменный объект ответа LLM"""
    def __init__(
        self,
        content: str,
        tool_calls: List[ToolCall],
        usage: TokenUsage,
        model: str
    ):
        self.content = content
        self.tool_calls = tool_calls
        self.usage = usage
        self.model = model

class LLMClient(ABC):
    """Интерфейс LLM клиента (в Domain Layer)"""
    
    @abstractmethod
    async def chat_completion(
        self,
        model: str,
        messages: List[Dict],
        tools: List[Dict]
    ) -> LLMResponse:
        """Вызов LLM API и преобразование в доменный объект"""
        pass

class LLMProxyClient(LLMClient):
    """Конкретная реализация для LiteLLM Proxy"""
    
    async def chat_completion(
        self,
        model: str,
        messages: List[Dict],
        tools: List[Dict]
    ) -> LLMResponse:
        """
        Ответственность:
        1. Вызов HTTP API LiteLLM Proxy
        2. Обработка ошибок сети
        3. Парсинг JSON ответа
        4. Преобразование в доменный объект LLMResponse
        """
        # Вызов API
        response_data = await self._http_client.post(
            url=self._base_url,
            json={
                "model": model,
                "messages": messages,
                "tools": tools,
                "stream": False
            }
        )
        
        # Парсинг и преобразование
        return self._parse_response(response_data)
    
    def _parse_response(self, data: Dict) -> LLMResponse:
        """Преобразование JSON в доменный объект"""
        message = data["choices"][0]["message"]
        
        # Парсинг tool calls
        tool_calls = []
        if "tool_calls" in message:
            tool_calls = [
                ToolCall(
                    id=tc["id"],
                    tool_name=tc["function"]["name"],
                    arguments=json.loads(tc["function"]["arguments"])
                )
                for tc in message["tool_calls"]
            ]
        
        # Парсинг usage
        usage = TokenUsage(
            prompt_tokens=data.get("usage", {}).get("prompt_tokens", 0),
            completion_tokens=data.get("usage", {}).get("completion_tokens", 0),
            total_tokens=data.get("usage", {}).get("total_tokens", 0)
        )
        
        return LLMResponse(
            content=message.get("content", ""),
            tool_calls=tool_calls,
            usage=usage,
            model=data.get("model", model)
        )
```

**Что НЕ должно быть в Infrastructure:**
- ❌ Бизнес-логика (валидация tool calls, HITL проверки)
- ❌ Координация между сервисами
- ❌ Публикация доменных событий
- ❌ Сохранение в БД

---

### 2. Domain Layer (Доменный слой)

**Ответственность:** Бизнес-логика и правила

#### 2.1 LLMResponseProcessor - Обработка ответа LLM

```python
# app/domain/services/llm_response_processor.py

from typing import Tuple, Optional
from ..entities.llm_response import LLMResponse, ProcessedResponse
from .hitl_policy import HITLPolicy

class LLMResponseProcessor:
    """
    Доменный сервис обработки ответа LLM.
    
    Ответственность:
    1. Валидация ответа (бизнес-правила)
    2. Проверка HITL политики
    3. Создание ProcessedResponse с метаданными
    """
    
    def __init__(self, hitl_policy: HITLPolicy):
        self._hitl_policy = hitl_policy
    
    def process_response(self, response: LLMResponse) -> ProcessedResponse:
        """
        Обработка ответа LLM согласно бизнес-правилам.
        
        Бизнес-правила:
        1. Агент может вызвать только ОДИН инструмент за раз
        2. Некоторые инструменты требуют одобрения (HITL)
        3. Пустой content допустим только при наличии tool_calls
        """
        # Валидация: только один tool call
        if len(response.tool_calls) > 1:
            # Бизнес-правило: берем только первый
            logger.warning(
                f"LLM attempted {len(response.tool_calls)} tool calls. "
                f"Taking only the first one."
            )
            tool_calls = [response.tool_calls[0]]
        else:
            tool_calls = response.tool_calls
        
        # Проверка HITL политики
        requires_approval = False
        approval_reason = None
        
        if tool_calls:
            tool_call = tool_calls[0]
            requires_approval, approval_reason = self._hitl_policy.requires_approval(
                tool_call.tool_name
            )
        
        # Создание ProcessedResponse
        return ProcessedResponse(
            content=response.content,
            tool_calls=tool_calls,
            usage=response.usage,
            model=response.model,
            requires_approval=requires_approval,
            approval_reason=approval_reason
        )
```

#### 2.2 ToolFilterService - Фильтрация инструментов

```python
# app/domain/services/tool_filter_service.py

from typing import List, Optional, Dict
from .tool_registry import ToolRegistry

class ToolFilterService:
    """
    Доменный сервис фильтрации инструментов.
    
    Ответственность:
    1. Фильтрация инструментов по разрешенным для агента
    2. Применение бизнес-правил доступа к инструментам
    """
    
    def __init__(self, tool_registry: ToolRegistry):
        self._tool_registry = tool_registry
    
    def filter_tools(
        self,
        allowed_tools: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Фильтрация инструментов по разрешенным.
        
        Бизнес-правило:
        - Если allowed_tools = None, возвращаем все инструменты
        - Если allowed_tools указан, возвращаем только разрешенные
        """
        all_tools = self._tool_registry.get_all_tools()
        
        if allowed_tools is None:
            return all_tools
        
        return [
            tool for tool in all_tools
            if tool["function"]["name"] in allowed_tools
        ]
```

**Что НЕ должно быть в Domain:**
- ❌ HTTP запросы
- ❌ Работа с БД напрямую (только через репозитории)
- ❌ Детали SSE стриминга
- ❌ FastAPI зависимости

---

### 3. Application Layer (Слой приложения)

**Ответственность:** Координация и оркестрация use cases

#### 3.1 StreamLLMResponseHandler - Координатор стриминга

```python
# app/application/handlers/stream_llm_response_handler.py

from typing import AsyncGenerator, List, Dict, Optional
from ...domain.services.llm_response_processor import LLMResponseProcessor
from ...domain.services.tool_filter_service import ToolFilterService
from ...domain.services.session_management import SessionManagementService
from ...domain.services.hitl_management import HITLManager
from ...infrastructure.llm.client import LLMClient
from ...infrastructure.events.event_publisher import EventPublisher
from ..dto.stream_chunk import StreamChunk

class StreamLLMResponseHandler:
    """
    Application Service для стриминга ответов LLM.
    
    Ответственность:
    1. Координация между доменными сервисами
    2. Публикация событий
    3. Сохранение результатов через доменные сервисы
    4. Генерация стрима для API слоя
    
    НЕ содержит:
    - Бизнес-логику (делегирует в Domain)
    - Технические детали LLM API (делегирует в Infrastructure)
    """
    
    def __init__(
        self,
        llm_client: LLMClient,
        tool_filter: ToolFilterService,
        response_processor: LLMResponseProcessor,
        event_publisher: EventPublisher,
        session_service: SessionManagementService,
        hitl_manager: HITLManager
    ):
        self._llm_client = llm_client
        self._tool_filter = tool_filter
        self._response_processor = response_processor
        self._event_publisher = event_publisher
        self._session_service = session_service
        self._hitl_manager = hitl_manager
    
    async def handle(
        self,
        session_id: str,
        history: List[Dict],
        model: str,
        allowed_tools: Optional[List[str]] = None,
        correlation_id: Optional[str] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Обработка запроса на стриминг ответа LLM.
        
        Use Case:
        1. Фильтровать инструменты по разрешенным
        2. Вызвать LLM через клиент
        3. Обработать ответ через доменный сервис
        4. Опубликовать события
        5. Сохранить результаты
        6. Сгенерировать стрим для клиента
        """
        try:
            # 1. Фильтрация инструментов (Domain)
            tools = self._tool_filter.filter_tools(allowed_tools)
            
            # 2. Публикация события начала (Infrastructure)
            await self._event_publisher.publish_llm_request_started(
                session_id=session_id,
                model=model,
                messages_count=len(history),
                tools_count=len(tools),
                correlation_id=correlation_id
            )
            
            # 3. Вызов LLM (Infrastructure)
            start_time = time.time()
            response = await self._llm_client.chat_completion(
                model=model,
                messages=history,
                tools=tools
            )
            duration_ms = int((time.time() - start_time) * 1000)
            
            # 4. Обработка ответа (Domain)
            processed = self._response_processor.process_response(response)
            
            # 5. Обработка tool calls или обычного сообщения
            if processed.has_tool_calls:
                chunk = await self._handle_tool_call(
                    session_id=session_id,
                    processed=processed,
                    duration_ms=duration_ms,
                    correlation_id=correlation_id
                )
            else:
                chunk = await self._handle_assistant_message(
                    session_id=session_id,
                    processed=processed,
                    duration_ms=duration_ms,
                    correlation_id=correlation_id
                )
            
            yield chunk
            
        except Exception as e:
            # Публикация события ошибки
            await self._event_publisher.publish_llm_request_failed(
                session_id=session_id,
                model=model,
                error=str(e),
                correlation_id=correlation_id
            )
            
            # Генерация error chunk
            yield StreamChunk(type="error", error=str(e), is_final=True)
    
    async def _handle_tool_call(
        self,
        session_id: str,
        processed: ProcessedResponse,
        duration_ms: int,
        correlation_id: Optional[str]
    ) -> StreamChunk:
        """
        Обработка tool call.
        
        Координация:
        1. Сохранение pending approval (если требуется)
        2. Сохранение сообщения в сессию
        3. Публикация событий
        4. Создание chunk для стрима
        """
        tool_call = processed.tool_calls[0]
        
        # 1. HITL: Сохранение pending approval
        if processed.requires_approval:
            await self._hitl_manager.add_pending(
                session_id=session_id,
                call_id=tool_call.id,
                tool_name=tool_call.tool_name,
                arguments=tool_call.arguments,
                reason=processed.approval_reason
            )
            
            # Публикация события approval required
            await self._event_publisher.publish_tool_approval_required(
                session_id=session_id,
                tool_name=tool_call.tool_name,
                call_id=tool_call.id,
                reason=processed.approval_reason,
                correlation_id=correlation_id
            )
        
        # 2. Сохранение сообщения через доменный сервис
        await self._session_service.add_message(
            session_id=session_id,
            role="assistant",
            content="",
            tool_calls=[tool_call.to_dict()]
        )
        
        # 3. Публикация события tool execution requested
        await self._event_publisher.publish_tool_execution_requested(
            session_id=session_id,
            tool_name=tool_call.tool_name,
            call_id=tool_call.id,
            correlation_id=correlation_id
        )
        
        # 4. Публикация события завершения LLM запроса
        await self._event_publisher.publish_llm_request_completed(
            session_id=session_id,
            model=processed.model,
            duration_ms=duration_ms,
            usage=processed.usage,
            has_tool_calls=True,
            correlation_id=correlation_id
        )
        
        # 5. Создание chunk для стрима
        return StreamChunk(
            type="tool_call",
            call_id=tool_call.id,
            tool_name=tool_call.tool_name,
            arguments=tool_call.arguments,
            requires_approval=processed.requires_approval,
            is_final=True
        )
    
    async def _handle_assistant_message(
        self,
        session_id: str,
        processed: ProcessedResponse,
        duration_ms: int,
        correlation_id: Optional[str]
    ) -> StreamChunk:
        """
        Обработка обычного сообщения ассистента.
        
        Координация:
        1. Сохранение сообщения в сессию
        2. Публикация событий
        3. Создание chunk для стрима
        """
        # 1. Сохранение сообщения
        await self._session_service.add_message(
            session_id=session_id,
            role="assistant",
            content=processed.content
        )
        
        # 2. Публикация события завершения
        await self._event_publisher.publish_llm_request_completed(
            session_id=session_id,
            model=processed.model,
            duration_ms=duration_ms,
            usage=processed.usage,
            has_tool_calls=False,
            correlation_id=correlation_id
        )
        
        # 3. Создание chunk для стрима
        return StreamChunk(
            type="assistant_message",
            content=processed.content,
            token=processed.content,
            is_final=True
        )
```

**Что НЕ должно быть в Application:**
- ❌ Бизнес-правила (должны быть в Domain)
- ❌ Технические детали HTTP/SSE (должны быть в API)
- ❌ Прямые SQL запросы (должны быть в Infrastructure)

---

### 4. API Layer (Слой представления)

**Ответственность:** HTTP интерфейс и SSE стриминг

#### 4.1 Messages Router - HTTP endpoint

```python
# app/api/v1/routers/messages_router.py

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from ....application.handlers.stream_llm_response_handler import StreamLLMResponseHandler
from ....core.dependencies import get_stream_llm_response_handler
from ..schemas.message_schemas import SendMessageRequest

router = APIRouter(prefix="/messages", tags=["messages"])

@router.post("/{session_id}/stream")
async def stream_message(
    session_id: str,
    request: SendMessageRequest,
    handler: StreamLLMResponseHandler = Depends(get_stream_llm_response_handler)
):
    """
    Отправить сообщение и получить стрим ответа.
    
    Ответственность API Layer:
    1. Прием HTTP запроса
    2. Валидация входных данных (Pydantic)
    3. Вызов Application Layer handler
    4. Преобразование AsyncGenerator в SSE стрим
    5. Обработка HTTP ошибок
    """
    try:
        # Получить историю сообщений
        # (через отдельный query handler)
        history = await get_session_history(session_id)
        
        # Добавить новое сообщение пользователя
        history.append({
            "role": "user",
            "content": request.content
        })
        
        # Вызов Application Layer handler
        async def event_generator():
            """Генератор SSE событий"""
            async for chunk in handler.handle(
                session_id=session_id,
                history=history,
                model=request.model or "default",
                allowed_tools=request.allowed_tools,
                correlation_id=request.correlation_id
            ):
                # Преобразование StreamChunk в SSE формат
                yield f"data: {chunk.model_dump_json()}\n\n"
        
        # Возврат SSE стрима
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
        
    except Exception as e:
        logger.error(f"Error streaming message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
```

**Что НЕ должно быть в API:**
- ❌ Бизнес-логика
- ❌ Прямые вызовы LLM API
- ❌ Работа с БД напрямую
- ❌ Публикация доменных событий

---

## Итоговая схема разделения ответственности

```
┌─────────────────────────────────────────────────────────────┐
│                      API Layer                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ POST /messages/{session_id}/stream                     │ │
│  │                                                        │ │
│  │ Ответственность:                                      │ │
│  │ • Прием HTTP запроса                                  │ │
│  │ • Валидация входных данных                            │ │
│  │ • Преобразование в SSE стрим                          │ │
│  │ • Обработка HTTP ошибок                               │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                           ↓ вызывает
┌─────────────────────────────────────────────────────────────┐
│                  Application Layer                           │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ StreamLLMResponseHandler                               │ │
│  │                                                        │ │
│  │ Ответственность:                                      │ │
│  │ • Координация между сервисами                         │ │
│  │ • Публикация событий                                  │ │
│  │ • Сохранение результатов                              │ │
│  │ • Генерация StreamChunk                               │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
         ↓ использует                    ↓ использует
┌──────────────────────────┐    ┌──────────────────────────┐
│     Domain Layer         │    │  Infrastructure Layer    │
│  ┌────────────────────┐  │    │  ┌────────────────────┐ │
│  │ToolFilterService   │  │    │  │   LLMClient        │ │
│  │                    │  │    │  │                    │ │
│  │ • Фильтрация       │  │    │  │ • Вызов LLM API    │ │
│  │   инструментов     │  │    │  │ • Парсинг ответа   │ │
│  └────────────────────┘  │    │  └────────────────────┘ │
│                          │    │                          │
│  ┌────────────────────┐  │    │  ┌────────────────────┐ │
│  │LLMResponseProcessor│  │    │  │ EventPublisher     │ │
│  │                    │  │    │  │                    │ │
│  │ • Валидация ответа │  │    │  │ • Публикация       │ │
│  │ • HITL проверка    │  │    │  │   событий в шину   │ │
│  │ • Бизнес-правила   │  │    │  └────────────────────┘ │
│  └────────────────────┘  │    └──────────────────────────┘
└──────────────────────────┘
```

---

## Сравнение: Текущая vs Правильная архитектура

### Текущая реализация (НЕПРАВИЛЬНО)

```python
# app/infrastructure/llm/streaming.py

async def stream_response(...):
    """
    ❌ Проблемы:
    - Смешивает все слои в одной функции
    - 348 строк кода
    - 8+ ответственностей
    - Невозможно тестировать
    - Использует глобальное состояние
    """
    # Infrastructure: Вызов LLM API
    response = await llm_proxy_client.chat_completion(...)
    
    # Domain: Валидация бизнес-правил
    if len(tool_calls) > 1:
        logger.warning("Multiple tool calls!")
    
    # Domain: HITL проверка
    requires_approval = hitl_policy_service.requires_approval(...)
    
    # Application: Координация
    await hitl_manager.add_pending(...)
    await event_bus.publish(...)
    await session_mgr.append_message(...)
    
    # API: Генерация стрима
    yield StreamChunk(...)
```

### Правильная реализация

```python
# Разделено по слоям:

# 1. Infrastructure Layer
class LLMProxyClient(LLMClient):
    async def chat_completion(...) -> LLMResponse:
        """Только вызов API и парсинг"""
        pass

# 2. Domain Layer
class LLMResponseProcessor:
    def process_response(self, response: LLMResponse) -> ProcessedResponse:
        """Только бизнес-логика"""
        pass

class ToolFilterService:
    def filter_tools(self, allowed: List[str]) -> List[Dict]:
        """Только фильтрация инструментов"""
        pass

# 3. Application Layer
class StreamLLMResponseHandler:
    async def handle(...) -> AsyncGenerator[StreamChunk, None]:
        """Только координация"""
        tools = self._tool_filter.filter_tools(allowed_tools)
        response = await self._llm_client.chat_completion(...)
        processed = self._response_processor.process_response(response)
        await self._event_publisher.publish(...)
        yield chunk

# 4. API Layer
@router.post("/messages/{session_id}/stream")
async def stream_message(...):
    """Только HTTP интерфейс"""
    async for chunk in handler.handle(...):
        yield f"data: {chunk.json()}\n\n"
```

---

## Преимущества правильной архитектуры

### 1. Тестируемость

```python
# Можно тестировать каждый компонент отдельно

# Test Infrastructure
async def test_llm_client():
    client = LLMProxyClient(http_client=mock_http)
    response = await client.chat_completion(...)
    assert response.content == "expected"

# Test Domain
def test_response_processor():
    processor = LLMResponseProcessor(hitl_policy=mock_policy)
    processed = processor.process_response(mock_response)
    assert processed.requires_approval == True

# Test Application
async def test_stream_handler():
    handler = StreamLLMResponseHandler(
        llm_client=mock_client,
        tool_filter=mock_filter,
        response_processor=mock_processor,
        event_publisher=mock_publisher,
        session_service=mock_session,
        hitl_manager=mock_hitl
    )
    chunks = [chunk async for chunk in handler.handle(...)]
    assert len(chunks) == 1
```

### 2. Расширяемость

```python
# Легко добавить новую реализацию LLM клиента
class OpenAIClient(LLMClient):
    async def chat_completion(...) -> LLMResponse:
        # Другая реализация
        pass

# Легко изменить HITL политику
class StrictHITLPolicy(HITLPolicy):
    def requires_approval(self, tool_name: str) -> Tuple[bool, str]:
        # Более строгая политика
        return True, "All tools require approval"
```

### 3. Поддерживаемость

- Каждый класс < 100 строк
- Одна ответственность
- Легко понять и изменить
- Легко найти баги

### 4. Переиспользуемость

```python
# LLMClient можно использовать в других use cases
class GenerateTitleHandler:
    def __init__(self, llm_client: LLMClient):
        self._llm_client = llm_client
    
    async def handle(self, messages: List[Dict]) -> str:
        response = await self._llm_client.chat_completion(...)
        return response.content
```

---

## Заключение

### Ответ на вопрос

**За что должна отвечать `stream_response()`?**

Функция `stream_response()` должна быть **разделена** на несколько компонентов:

1. **LLMClient** (Infrastructure) - Вызов LLM API
2. **LLMResponseProcessor** (Domain) - Бизнес-логика обработки
3. **ToolFilterService** (Domain) - Фильтрация инструментов
4. **StreamLLMResponseHandler** (Application) - Координация
5. **Router** (API) - HTTP интерфейс

**На каком слое должна быть реализована?**

Основная логика координации должна быть в **Application Layer** (`StreamLLMResponseHandler`), который использует сервисы из Domain и Infrastructure слоев.

### Ключевой принцип

> **Каждый слой должен иметь одну ответственность и зависеть только от слоев ниже (внутрь к Domain).**

Текущая реализация `stream_response()` нарушает этот принцип, смешивая все слои в одной функции. Правильная архитектура разделяет ответственности по слоям, что делает код тестируемым, расширяемым и поддерживаемым.

---

**Подготовлено:** AI Architecture Auditor  
**Дата:** 24 января 2026  
**Версия документа:** 1.0
