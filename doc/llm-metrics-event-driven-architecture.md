# Event-Driven Architecture для сбора метрик LLM

> **Дополнение к** [`llm-metrics-collection-implementation.md`](llm-metrics-collection-implementation.md)
> 
> Описывает масштабируемое решение на основе Event Bus для сбора метрик.

## Обзор

Event-Driven подход обеспечивает:
- ✅ **Слабую связанность** - компоненты не зависят друг от друга
- ✅ **Масштабируемость** - легко добавлять новых подписчиков
- ✅ **Расширяемость** - новые типы событий без изменения существующего кода
- ✅ **Аудит** - полная история всех событий системы
- ✅ **Replay** - возможность воспроизвести события для отладки

## Архитектура с Event Bus

```
┌─────────────────────────────────────────────────────────────┐
│                      Agent Runtime                          │
│                                                             │
│  ┌──────────────┐         ┌─────────────────┐             │
│  │ LLM Service  │────────>│   Event Bus     │             │
│  └──────────────┘  emit   │                 │             │
│                            │  - llm_call     │             │
│  ┌──────────────┐         │  - tool_call    │             │
│  │ Tool Service │────────>│  - agent_switch │             │
│  └──────────────┘         │  - error        │             │
│                            └────────┬────────┘             │
│  ┌──────────────┐                  │                       │
│  │ Orchestrator │────────>         │                       │
│  └──────────────┘                  │                       │
│                                    │                       │
│                            ┌───────▼────────┐              │
│                            │  Subscribers   │              │
│                            │                │              │
│                            │ • MetricsCollector            │
│                            │ • WebSocketEmitter            │
│                            │ • DatabaseLogger              │
│                            │ • AuditLogger                 │
│                            └────────────────┘              │
└─────────────────────────────────────────────────────────────┘
                                    │
                                    │ WebSocket
                                    ▼
                            ┌───────────────┐
                            │    Gateway    │
                            └───────┬───────┘
                                    │
                                    ▼
                            ┌───────────────┐
                            │  benchmark-   │
                            │  standalone   │
                            └───────────────┘
```

## Реализация Event Bus

### 1. Определение типов событий

**Файл**: `codelab-ai-service/agent-runtime/app/events/event_types.py`

```python
"""Event types for event-driven architecture"""
from enum import Enum
from typing import Any, Dict, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field
import uuid


class EventType(str, Enum):
    """Типы событий в системе"""
    # LLM события
    LLM_CALL_STARTED = "llm_call_started"
    LLM_CALL_COMPLETED = "llm_call_completed"
    LLM_CALL_FAILED = "llm_call_failed"
    
    # Tool события
    TOOL_CALL_REQUESTED = "tool_call_requested"
    TOOL_CALL_APPROVED = "tool_call_approved"
    TOOL_CALL_REJECTED = "tool_call_rejected"
    TOOL_RESULT_RECEIVED = "tool_result_received"
    
    # Agent события
    AGENT_SWITCHED = "agent_switched"
    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    
    # Session события
    SESSION_CREATED = "session_created"
    SESSION_MESSAGE_ADDED = "session_message_added"
    
    # Error события
    ERROR_OCCURRED = "error_occurred"


class BaseEvent(BaseModel):
    """Базовый класс для всех событий"""
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    session_id: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LLMCallStartedEvent(BaseEvent):
    """Событие начала LLM вызова"""
    event_type: EventType = EventType.LLM_CALL_STARTED
    agent_type: str
    model: str
    message_count: int
    tools_count: int


class LLMCallCompletedEvent(BaseEvent):
    """Событие завершения LLM вызова"""
    event_type: EventType = EventType.LLM_CALL_COMPLETED
    agent_type: str
    model: str
    input_tokens: int
    output_tokens: int
    duration_seconds: float
    call_id: str
    has_tool_calls: bool = False


class LLMCallFailedEvent(BaseEvent):
    """Событие ошибки LLM вызова"""
    event_type: EventType = EventType.LLM_CALL_FAILED
    agent_type: str
    model: str
    error_message: str
    duration_seconds: float


class ToolCallRequestedEvent(BaseEvent):
    """Событие запроса tool call"""
    event_type: EventType = EventType.TOOL_CALL_REQUESTED
    call_id: str
    tool_name: str
    arguments: Dict[str, Any]
    requires_approval: bool


class ToolResultReceivedEvent(BaseEvent):
    """Событие получения результата tool"""
    event_type: EventType = EventType.TOOL_RESULT_RECEIVED
    call_id: str
    tool_name: str
    success: bool
    duration_seconds: float
    error: Optional[str] = None


class AgentSwitchedEvent(BaseEvent):
    """Событие переключения агента"""
    event_type: EventType = EventType.AGENT_SWITCHED
    from_agent: Optional[str]
    to_agent: str
    reason: str


class ErrorOccurredEvent(BaseEvent):
    """Событие ошибки"""
    event_type: EventType = EventType.ERROR_OCCURRED
    error_type: str
    error_message: str
    stack_trace: Optional[str] = None
```

### 2. Реализация Event Bus

**Файл**: `codelab-ai-service/agent-runtime/app/events/event_bus.py`

```python
"""Event Bus implementation for pub/sub pattern"""
import asyncio
import logging
from typing import Callable, Dict, List
from collections import defaultdict

from app.events.event_types import BaseEvent, EventType

logger = logging.getLogger("agent-runtime.event_bus")


class EventBus:
    """
    Event Bus для pub/sub паттерна.
    
    Поддерживает:
    - Асинхронную публикацию событий
    - Множественных подписчиков на один тип события
    - Wildcard подписки (на все события)
    - Обработку ошибок в подписчиках
    """
    
    def __init__(self):
        # Подписчики по типу события: EventType -> List[Callable]
        self._subscribers: Dict[EventType, List[Callable]] = defaultdict(list)
        
        # Wildcard подписчики (получают все события)
        self._wildcard_subscribers: List[Callable] = []
        
        # Статистика
        self._events_published = 0
        self._events_failed = 0
        
        logger.info("EventBus initialized")
    
    def subscribe(
        self,
        event_type: EventType,
        handler: Callable[[BaseEvent], None]
    ) -> None:
        """
        Подписаться на событие определенного типа.
        
        Args:
            event_type: Тип события
            handler: Async функция-обработчик события
        """
        self._subscribers[event_type].append(handler)
        logger.info(
            f"Subscribed handler {handler.__name__} to {event_type.value}"
        )
    
    def subscribe_all(self, handler: Callable[[BaseEvent], None]) -> None:
        """
        Подписаться на все события (wildcard).
        
        Args:
            handler: Async функция-обработчик события
        """
        self._wildcard_subscribers.append(handler)
        logger.info(f"Subscribed wildcard handler {handler.__name__}")
    
    def unsubscribe(
        self,
        event_type: EventType,
        handler: Callable[[BaseEvent], None]
    ) -> None:
        """Отписаться от события"""
        if handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)
            logger.info(
                f"Unsubscribed handler {handler.__name__} from {event_type.value}"
            )
    
    async def publish(self, event: BaseEvent) -> None:
        """
        Опубликовать событие.
        
        Все подписчики вызываются асинхронно и параллельно.
        Ошибки в подписчиках логируются, но не прерывают обработку.
        
        Args:
            event: Событие для публикации
        """
        self._events_published += 1
        
        logger.debug(
            f"Publishing event: {event.event_type.value} "
            f"(id={event.event_id}, session={event.session_id})"
        )
        
        # Собираем всех подписчиков
        handlers = []
        
        # Подписчики на конкретный тип события
        if event.event_type in self._subscribers:
            handlers.extend(self._subscribers[event.event_type])
        
        # Wildcard подписчики
        handlers.extend(self._wildcard_subscribers)
        
        if not handlers:
            logger.debug(f"No subscribers for {event.event_type.value}")
            return
        
        # Вызываем всех подписчиков параллельно
        tasks = []
        for handler in handlers:
            task = asyncio.create_task(
                self._safe_call_handler(handler, event)
            )
            tasks.append(task)
        
        # Ждем завершения всех обработчиков
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _safe_call_handler(
        self,
        handler: Callable[[BaseEvent], None],
        event: BaseEvent
    ) -> None:
        """
        Безопасный вызов обработчика с обработкой ошибок.
        
        Args:
            handler: Функция-обработчик
            event: Событие
        """
        try:
            await handler(event)
        except Exception as e:
            self._events_failed += 1
            logger.error(
                f"Error in event handler {handler.__name__} "
                f"for event {event.event_type.value}: {e}",
                exc_info=True
            )
    
    def get_stats(self) -> Dict[str, int]:
        """Получить статистику Event Bus"""
        return {
            "events_published": self._events_published,
            "events_failed": self._events_failed,
            "subscribers_count": sum(
                len(handlers) for handlers in self._subscribers.values()
            ),
            "wildcard_subscribers_count": len(self._wildcard_subscribers)
        }


# Глобальный экземпляр Event Bus
event_bus = EventBus()
```

### 3. Подписчики для метрик

**Файл**: `codelab-ai-service/agent-runtime/app/events/subscribers/metrics_subscriber.py`

```python
"""Subscriber для сбора метрик"""
import logging
from app.events.event_types import (
    BaseEvent,
    LLMCallCompletedEvent,
    ToolCallRequestedEvent,
    ToolResultReceivedEvent,
    AgentSwitchedEvent
)

logger = logging.getLogger("agent-runtime.metrics_subscriber")


class MetricsSubscriber:
    """
    Подписчик для сбора метрик в памяти.
    
    Собирает метрики по сессиям для последующей отправки через WebSocket
    или REST API.
    """
    
    def __init__(self):
        # Метрики по сессиям: session_id -> metrics
        self._session_metrics = {}
        logger.info("MetricsSubscriber initialized")
    
    async def handle_llm_call_completed(self, event: LLMCallCompletedEvent) -> None:
        """Обработать завершение LLM вызова"""
        session_id = event.session_id
        
        if session_id not in self._session_metrics:
            self._session_metrics[session_id] = {
                "llm_calls": [],
                "tool_calls": [],
                "agent_switches": []
            }
        
        # Сохранить метрики LLM вызова
        self._session_metrics[session_id]["llm_calls"].append({
            "event_id": event.event_id,
            "agent_type": event.agent_type,
            "model": event.model,
            "input_tokens": event.input_tokens,
            "output_tokens": event.output_tokens,
            "duration_seconds": event.duration_seconds,
            "call_id": event.call_id,
            "has_tool_calls": event.has_tool_calls,
            "timestamp": event.timestamp.isoformat()
        })
        
        logger.debug(
            f"Recorded LLM call: session={session_id}, "
            f"tokens={event.input_tokens}/{event.output_tokens}"
        )
    
    async def handle_tool_call_requested(self, event: ToolCallRequestedEvent) -> None:
        """Обработать запрос tool call"""
        session_id = event.session_id
        
        if session_id not in self._session_metrics:
            self._session_metrics[session_id] = {
                "llm_calls": [],
                "tool_calls": [],
                "agent_switches": []
            }
        
        self._session_metrics[session_id]["tool_calls"].append({
            "event_id": event.event_id,
            "call_id": event.call_id,
            "tool_name": event.tool_name,
            "requires_approval": event.requires_approval,
            "timestamp": event.timestamp.isoformat()
        })
        
        logger.debug(
            f"Recorded tool call: session={session_id}, tool={event.tool_name}"
        )
    
    async def handle_agent_switched(self, event: AgentSwitchedEvent) -> None:
        """Обработать переключение агента"""
        session_id = event.session_id
        
        if session_id not in self._session_metrics:
            self._session_metrics[session_id] = {
                "llm_calls": [],
                "tool_calls": [],
                "agent_switches": []
            }
        
        self._session_metrics[session_id]["agent_switches"].append({
            "event_id": event.event_id,
            "from_agent": event.from_agent,
            "to_agent": event.to_agent,
            "reason": event.reason,
            "timestamp": event.timestamp.isoformat()
        })
        
        logger.debug(
            f"Recorded agent switch: session={session_id}, "
            f"{event.from_agent} -> {event.to_agent}"
        )
    
    def get_session_metrics(self, session_id: str) -> dict:
        """Получить метрики сессии"""
        return self._session_metrics.get(session_id, {
            "llm_calls": [],
            "tool_calls": [],
            "agent_switches": []
        })
    
    def clear_session_metrics(self, session_id: str) -> None:
        """Очистить метрики сессии"""
        if session_id in self._session_metrics:
            del self._session_metrics[session_id]
            logger.debug(f"Cleared metrics for session {session_id}")


# Глобальный экземпляр
metrics_subscriber = MetricsSubscriber()
```

**Файл**: `codelab-ai-service/agent-runtime/app/events/subscribers/websocket_subscriber.py`

```python
"""Subscriber для отправки событий через WebSocket"""
import logging
from app.events.event_types import (
    BaseEvent,
    LLMCallCompletedEvent,
    EventType
)
from app.models.schemas import StreamChunk, LLMMetrics

logger = logging.getLogger("agent-runtime.websocket_subscriber")


class WebSocketSubscriber:
    """
    Подписчик для отправки событий через WebSocket.
    
    Преобразует события в StreamChunk и отправляет через SSE.
    """
    
    def __init__(self):
        # Очереди событий по сессиям: session_id -> asyncio.Queue
        self._session_queues = {}
        logger.info("WebSocketSubscriber initialized")
    
    async def handle_llm_call_completed(self, event: LLMCallCompletedEvent) -> None:
        """
        Обработать завершение LLM вызова.
        
        Создает StreamChunk с метриками для отправки через WebSocket.
        """
        session_id = event.session_id
        
        # Создать метрики для отправки
        llm_metrics = LLMMetrics(
            agent_type=event.agent_type,
            model=event.model,
            input_tokens=event.input_tokens,
            output_tokens=event.output_tokens,
            duration_seconds=event.duration_seconds,
            timestamp=event.timestamp,
            call_id=event.call_id
        )
        
        # Создать chunk с метриками
        # Этот chunk будет добавлен к следующему assistant_message или tool_call
        chunk = StreamChunk(
            type="llm_metrics",
            llm_metrics=llm_metrics,
            is_final=False
        )
        
        # Добавить в очередь сессии для отправки
        if session_id in self._session_queues:
            await self._session_queues[session_id].put(chunk)
        
        logger.debug(
            f"Queued LLM metrics for WebSocket: session={session_id}, "
            f"tokens={event.input_tokens}/{event.output_tokens}"
        )
    
    def register_session(self, session_id: str, queue: 'asyncio.Queue') -> None:
        """Зарегистрировать очередь для сессии"""
        self._session_queues[session_id] = queue
        logger.debug(f"Registered WebSocket queue for session {session_id}")
    
    def unregister_session(self, session_id: str) -> None:
        """Удалить очередь сессии"""
        if session_id in self._session_queues:
            del self._session_queues[session_id]
            logger.debug(f"Unregistered WebSocket queue for session {session_id}")


# Глобальный экземпляр
websocket_subscriber = WebSocketSubscriber()
```

### 4. Интеграция Event Bus в LLM Service

**Файл**: `codelab-ai-service/agent-runtime/app/services/llm_stream_service.py`

```python
import time
import uuid
import traceback
from datetime import datetime, timezone

from app.events.event_bus import event_bus
from app.events.event_types import (
    LLMCallStartedEvent,
    LLMCallCompletedEvent,
    LLMCallFailedEvent,
    ToolCallRequestedEvent
)

async def stream_response(
    session_id: str,
    history: List[dict],
    allowed_tools: Optional[List[str]] = None,
    session_mgr: Optional[AsyncSessionManager] = None,
    agent_type: str = "unknown"
) -> AsyncGenerator[StreamChunk, None]:
    """Generate streaming response from LLM with event-driven metrics"""
    
    if session_mgr is None:
        from app.services.session_manager_async import session_manager as global_mgr
        session_mgr = global_mgr
        if session_mgr is None:
            raise RuntimeError("SessionManager not initialized")
    
    call_id = str(uuid.uuid4())
    llm_start_time = time.time()
    
    try:
        logger.info(f"Starting LLM stream for session {session_id}")
        
        # Filter tools
        tools_to_use = TOOLS_SPEC
        if allowed_tools is not None:
            tools_to_use = [
                tool for tool in TOOLS_SPEC
                if tool["function"]["name"] in allowed_tools
            ]
        
        # NEW: Publish LLM_CALL_STARTED event
        await event_bus.publish(LLMCallStartedEvent(
            session_id=session_id,
            agent_type=agent_type,
            model=AppConfig.LLM_MODEL,
            message_count=len(history),
            tools_count=len(tools_to_use)
        ))
        
        # Call LLM proxy
        response_data = await llm_proxy_client.chat_completion(
            model=AppConfig.LLM_MODEL,
            messages=history,
            tools=tools_to_use,
            stream=False
        )
        
        # Calculate duration and extract tokens
        llm_duration = time.time() - llm_start_time
        usage = response_data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        
        # Extract message
        result_message = response_data["choices"][0]["message"]
        content = result_message.get("content", "")
        metadata = {}
        
        # Extract tool_calls
        if isinstance(content, list):
            for obj in content:
                if isinstance(obj, dict) and "tool_calls" in obj and obj["tool_calls"]:
                    metadata["tool_calls"] = obj["tool_calls"]
                    break
        else:
            if "tool_calls" in result_message:
                metadata["tool_calls"] = result_message["tool_calls"]
        
        # Parse tool calls
        tool_calls, clean_content = parse_tool_calls(content, metadata)
        
        # NEW: Publish LLM_CALL_COMPLETED event
        await event_bus.publish(LLMCallCompletedEvent(
            session_id=session_id,
            agent_type=agent_type,
            model=AppConfig.LLM_MODEL,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            duration_seconds=llm_duration,
            call_id=call_id,
            has_tool_calls=len(tool_calls) > 0
        ))
        
        # Handle tool calls
        if tool_calls:
            if len(tool_calls) > 1:
                logger.warning(
                    f"LLM attempted to call {len(tool_calls)} tools simultaneously! "
                    f"Only the first tool will be executed."
                )
            
            tool_call = tool_calls[0]
            
            # Check approval
            requires_approval, reason = hitl_policy_service.requires_approval(
                tool_call.tool_name
            )
            
            # NEW: Publish TOOL_CALL_REQUESTED event
            await event_bus.publish(ToolCallRequestedEvent(
                session_id=session_id,
                call_id=tool_call.id,
                tool_name=tool_call.tool_name,
                arguments=tool_call.arguments,
                requires_approval=requires_approval
            ))
            
            # If approval required, save pending state
            if requires_approval:
                await hitl_manager.add_pending(
                    session_id=session_id,
                    call_id=tool_call.id,
                    tool_name=tool_call.tool_name,
                    arguments=tool_call.arguments,
                    reason=reason
                )
            
            # Save assistant message with tool_call
            assistant_msg = {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.tool_name,
                        "arguments": json.dumps(tool_call.arguments)
                    }
                }]
            }
            
            session_state = session_mgr.get(session_id)
            if session_state:
                session_state.messages.append(assistant_msg)
                await session_mgr._schedule_persist(session_id)
            
            # Send tool_call chunk (metrics already sent via event)
            chunk = StreamChunk(
                type="tool_call",
                call_id=tool_call.id,
                tool_name=tool_call.tool_name,
                arguments=tool_call.arguments,
                requires_approval=requires_approval,
                is_final=True
            )
            
            yield chunk
            return
        
        # Handle assistant message
        if isinstance(content, list) and len(content) > 0:
            if isinstance(content[0], dict) and "content" in content[0]:
                clean_content = content[0]["content"]
            else:
                clean_content = str(content)
        elif not isinstance(clean_content, str):
            clean_content = str(clean_content) if clean_content else ""
        
        await session_mgr.append_message(session_id, "assistant", clean_content)
        
        # Send assistant message chunk (metrics already sent via event)
        chunk = StreamChunk(
            type="assistant_message",
            content=clean_content,
            token=clean_content,
            is_final=True
        )
        
        yield chunk
        
    except Exception as e:
        llm_duration = time.time() - llm_start_time
        logger.error(f"Exception in stream_response: {e}", exc_info=True)
        
        # NEW: Publish LLM_CALL_FAILED event
        await event_bus.publish(LLMCallFailedEvent(
            session_id=session_id,
            agent_type=agent_type,
            model=AppConfig.LLM_MODEL,
            error_message=str(e),
            duration_seconds=llm_duration
        ))
        
        error_chunk = StreamChunk(
            type="error",
            error=str(e),
            is_final=True
        )
        yield error_chunk
```

### 5. Публикация событий переключения агентов

**Файл**: `codelab-ai-service/agent-runtime/app/services/multi_agent_orchestrator.py`

```python
from app.events.event_bus import event_bus
from app.events.event_types import AgentSwitchedEvent

async def process_message(
    self,
    session_id: str,
    message: str,
    agent_type: Optional[AgentType] = None
) -> AsyncGenerator[StreamChunk, None]:
    """Process message through multi-agent system with events"""
    
    # ... existing agent selection logic ...
    
    # Check if agent switch occurred
    if agent_context.current_agent != previous_agent:
        # NEW: Publish AGENT_SWITCHED event
        await event_bus.publish(AgentSwitchedEvent(
            session_id=session_id,
            from_agent=previous_agent.value if previous_agent else None,
            to_agent=agent_context.current_agent.value,
            reason=switch_reason
        ))
        
        # Yield agent_switched chunk
        yield StreamChunk(
            type="agent_switched",
            metadata={
                "from_agent": previous_agent.value if previous_agent else None,
                "to_agent": agent_context.current_agent.value,
                "reason": switch_reason
            },
            is_final=False
        )
    
    # Stream response from agent
    async for chunk in stream_response(
        session_id=session_id,
        history=history,
        allowed_tools=current_agent.get_allowed_tools(),
        session_mgr=self.session_mgr,
        agent_type=current_agent.agent_type.value
    ):
        yield chunk
```

### 6. Инициализация Event Bus

**Файл**: `codelab-ai-service/agent-runtime/app/main.py`

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    logger.info("Starting Agent Runtime Service...")
    
    try:
        # ... existing initialization ...
        
        # NEW: Initialize Event Bus subscribers
        from app.events.event_bus import event_bus
        from app.events.event_types import EventType
        from app.events.subscribers.metrics_subscriber import metrics_subscriber
        from app.events.subscribers.websocket_subscriber import websocket_subscriber
        
        # Subscribe metrics collector
        event_bus.subscribe(
            EventType.LLM_CALL_COMPLETED,
            metrics_subscriber.handle_llm_call_completed
        )
        event_bus.subscribe(
            EventType.TOOL_CALL_REQUESTED,
            metrics_subscriber.handle_tool_call_requested
        )
        event_bus.subscribe(
            EventType.AGENT_SWITCHED,
            metrics_subscriber.handle_agent_switched
        )
        
        # Subscribe WebSocket emitter
        event_bus.subscribe(
            EventType.LLM_CALL_COMPLETED,
            websocket_subscriber.handle_llm_call_completed
        )
        
        logger.info("✓ Event Bus subscribers initialized")
        
    except Exception as e:
        logger.error(f"Failed to initialize: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Agent Runtime Service...")
```

### 7. REST API для получения метрик

**Файл**: `codelab-ai-service/agent-runtime/app/api/v1/endpoints.py`

```python
@router.get("/sessions/{session_id}/metrics")
async def get_session_metrics(session_id: str):
    """
    Get collected metrics for a session.
    
    Returns LLM calls, tool calls, and agent switches collected via Event Bus.
    """
    from app.events.subscribers.metrics_subscriber import metrics_subscriber
    
    metrics = metrics_subscriber.get_session_metrics(session_id)
    
    # Calculate totals
    total_input_tokens = sum(
        call["input_tokens"] for call in metrics["llm_calls"]
    )
    total_output_tokens = sum(
        call["output_tokens"] for call in metrics["llm_calls"]
    )
    total_cost = (total_input_tokens * 0.003 + total_output_tokens * 0.015) / 1000
    
    return {
        "session_id": session_id,
        "llm_calls": metrics["llm_calls"],
        "tool_calls": metrics["tool_calls"],
        "agent_switches": metrics["agent_switches"],
        "summary": {
            "total_llm_calls": len(metrics["llm_calls"]),
            "total_tool_calls": len(metrics["tool_calls"]),
            "total_agent_switches": len(metrics["agent_switches"]),
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_tokens": total_input_tokens + total_output_tokens,
            "estimated_cost_usd": round(total_cost, 4)
        }
    }


@router.get("/metrics/event-bus")
async def get_event_bus_metrics():
    """Получить статистику Event Bus"""
    from app.events.event_bus import event_bus
    return event_bus.get_stats()
```

## Интеграция с benchmark-standalone

### Вариант 1: WebSocket (реал-тайм)

События автоматически преобразуются в StreamChunk через `WebSocketSubscriber` и отправляются через существующий WebSocket канал (как в основном решении).

### Вариант 2: REST API (после задачи)

**Файл**: `benchmark-standalone/src/client.py`

```python
async def execute_task(
    self,
    task: Dict[str, Any],
    tool_executor: MockToolExecutor,
    validator: Optional[TaskValidator],
    collector: MetricsCollector,
    task_execution_id: UUID
) -> bool:
    """Execute task and collect metrics via REST API"""
    
    # ... existing WebSocket execution ...
    
    # После завершения задачи получить метрики через REST API
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/sessions/{session_id}/metrics",
                headers=await self.auth_manager.get_headers()
            )
            response.raise_for_status()
            metrics = response.json()
            
            # Записать все LLM вызовы
            for llm_call in metrics["llm_calls"]:
                await collector.record_llm_call(
                    task_execution_id=task_execution_id,
                    agent_type=llm_call["agent_type"],
                    input_tokens=llm_call["input_tokens"],
                    output_tokens=llm_call["output_tokens"],
                    model=llm_call["model"],
                    duration_seconds=llm_call["duration_seconds"]
                )
            
            logger.info(
                f"📊 Collected metrics: {metrics['summary']['total_llm_calls']} LLM calls, "
                f"{metrics['summary']['total_tokens']} tokens"
            )
            
    except Exception as e:
        logger.warning(f"Failed to collect metrics via REST API: {e}")
    
    return success
```

## Преимущества Event-Driven подхода

### 1. Слабая связанность

```python
# LLM Service не знает о MetricsCollector
# Просто публикует событие
await event_bus.publish(LLMCallCompletedEvent(...))

# MetricsCollector подписывается независимо
event_bus.subscribe(
    EventType.LLM_CALL_COMPLETED,
    metrics_subscriber.handle_llm_call_completed
)
```

### 2. Легко добавлять новых подписчиков

```python
# Добавить аудит логирование
class AuditSubscriber:
    async def handle_all_events(self, event: BaseEvent):
        await audit_log.write(event)

audit_subscriber = AuditSubscriber()
event_bus.subscribe_all(audit_subscriber.handle_all_events)
```

### 3. Replay событий для отладки

```python
class EventRecorder:
    """Записывает все события для replay"""
    def __init__(self):
        self.events = []
    
    async def record(self, event: BaseEvent):
        self.events.append(event)
    
    async def replay(self):
        """Воспроизвести события"""
        for event in self.events:
            await event_bus.publish(event)

recorder = EventRecorder()
event_bus.subscribe_all(recorder.record)
```

### 4. Database persistence subscriber

```python
class DatabaseSubscriber:
    """Сохраняет события в БД для аудита"""
    
    async def handle_all_events(self, event: BaseEvent):
        async with get_db_session() as db:
            event_record = EventLog(
                event_id=event.event_id,
                event_type=event.event_type.value,
                session_id=event.session_id,
                timestamp=event.timestamp,
                data=event.model_dump()
            )
            db.add(event_record)
            await db.commit()

db_subscriber = DatabaseSubscriber()
event_bus.subscribe_all(db_subscriber.handle_all_events)
```

## План внедрения Event-Driven Architecture

### Неделя 1-2: Реализация Event Bus
- ✅ Создать `EventBus` класс
- ✅ Определить `EventType` enum и event models
- ✅ Реализовать базовую pub/sub функциональность
- ✅ Написать unit тесты для Event Bus
- ✅ Добавить статистику и мониторинг

### Неделя 3-4: Миграция на события
- ✅ Публикация событий из `llm_stream_service.py`
- ✅ Публикация событий из `multi_agent_orchestrator.py`
- ✅ Создать `MetricsSubscriber`
- ✅ Создать `WebSocketSubscriber`
- ✅ Тестирование интеграции

### Неделя 5-6: Расширенные возможности
- ✅ Добавить `AuditSubscriber` для логирования
- ✅ Добавить `DatabaseSubscriber` для персистентности
- ✅ Реализовать Event Replay для отладки
- ✅ Добавить REST API для метрик
- ✅ Документация и примеры

## Сравнение подходов

| Аспект | WebSocket расширение | Event-Driven |
|--------|---------------------|--------------|
| **Время внедрения** | 2-3 дня | 4-6 недель |
| **Сложность** | Низкая | Средняя |
| **Масштабируемость** | Ограниченная | Высокая |
| **Расширяемость** | Требует изменений | Легко добавлять |
| **Тестируемость** | Средняя | Высокая |
| **Отладка** | Сложная | Легкая (replay) |
| **Аудит** | Нет | Полный |
| **Обратная совместимость** | Да | Да |
| **Мониторинг** | Ограниченный | Полный |

## Рекомендация

### Краткосрочная перспектива (MVP)
Использовать **WebSocket расширение** для быстрого решения проблемы с метриками.

### Долгосрочная перспектива (Production)
Мигрировать на **Event-Driven Architecture** для:
- Лучшей масштабируемости
- Упрощения добавления новых фич
- Полного аудита системы
- Упрощения отладки и мониторинга

### Гибридный подход
1. **Фаза 1 (неделя 1)**: Внедрить WebSocket расширение для метрик
2. **Фаза 2 (недели 2-7)**: Параллельно разработать Event Bus
3. **Фаза 3 (неделя 8)**: Мигрировать на Event-Driven, сохранив WebSocket как транспорт

---

## Заключение

**Event-Driven Architecture** - это стратегическое решение, которое:
- Делает систему более гибкой и расширяемой
- Упрощает добавление новых типов метрик и подписчиков
- Обеспечивает полный аудит всех событий системы
- Позволяет легко отлаживать проблемы через replay событий
- Подготавливает систему к масштабированию

В сочетании с WebSocket расширением (для быстрого MVP), Event-Driven подход обеспечивает долгосрочную масштабируемость и поддерживаемость системы сбора метрик.
