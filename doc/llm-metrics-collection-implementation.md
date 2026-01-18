# Реализация сбора метрик LLM для benchmark-standalone

> **Документ описывает два подхода:**
> 1. **Быстрое решение** - расширение WebSocket протокола (2-3 дня)
> 2. **Event-Driven Architecture** - масштабируемое решение (4-6 недель)

## Проблема

Согласно анализу [`multiagent-analyze/notebook.ipynb`](../multiagent-analyze/notebook.ipynb), benchmark показывает **0 LLM вызовов, 0 токенов, $0.00 стоимость**, хотя система выполняет 118 tool calls и 43 agent switches.

**Причина**: `benchmark-standalone` является отдельным приложением, которое общается с сервисом только через REST API и WebSocket. Метрики LLM генерируются внутри Agent Runtime, но **не передаются обратно** в benchmark-standalone.

## Архитектура

```
benchmark-standalone (клиент)
    ↓ WebSocket
Gateway (прокси)
    ↓ HTTP SSE Stream
Agent Runtime (LLM логика)
    ↓ HTTP
LLM Proxy (вызовы LLM)
```

## Решение: Расширение WebSocket протокола

Добавить новый тип сообщения `llm_metrics` для передачи метрик LLM через существующий WebSocket канал.

---

## Изменения в Agent Runtime

### 1. Добавить модель для метрик LLM

**Файл**: `codelab-ai-service/agent-runtime/app/models/schemas.py`

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class LLMMetrics(BaseModel):
    """Метрики LLM вызова для передачи в benchmark"""
    agent_type: str = Field(..., description="Тип агента (coder, architect, etc.)")
    model: str = Field(..., description="Модель LLM (gpt-4, claude-3, etc.)")
    input_tokens: int = Field(..., ge=0, description="Количество входных токенов")
    output_tokens: int = Field(..., ge=0, description="Количество выходных токенов")
    duration_seconds: float = Field(..., ge=0, description="Длительность вызова в секундах")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    call_id: str = Field(..., description="UUID вызова для трейсинга")

class StreamChunk(BaseModel):
    """Existing model - add llm_metrics field"""
    type: str
    # ... existing fields ...
    
    # NEW: LLM metrics
    llm_metrics: Optional[LLMMetrics] = None
```

### 2. Модифицировать LLM Stream Service для сбора метрик

**Файл**: `codelab-ai-service/agent-runtime/app/services/llm_stream_service.py`

```python
import time
import uuid
from datetime import datetime, timezone

async def stream_response(
    session_id: str,
    history: List[dict],
    allowed_tools: Optional[List[str]] = None,
    session_mgr: Optional[AsyncSessionManager] = None,
    agent_type: str = "unknown"  # NEW: добавить параметр agent_type
) -> AsyncGenerator[StreamChunk, None]:
    """
    Generate streaming response from LLM with metrics collection.
    """
    if session_mgr is None:
        from app.services.session_manager_async import session_manager as global_mgr
        session_mgr = global_mgr
        if session_mgr is None:
            raise RuntimeError("SessionManager not initialized")
    
    try:
        logger.info(
            f"Starting LLM stream for session {session_id} with {len(history)} messages"
        )
        
        # Filter tools based on allowed_tools
        tools_to_use = TOOLS_SPEC
        if allowed_tools is not None:
            tools_to_use = [
                tool for tool in TOOLS_SPEC
                if tool["function"]["name"] in allowed_tools
            ]
        
        # NEW: Start timing
        llm_start_time = time.time()
        call_id = str(uuid.uuid4())
        
        logger.debug(f"LLM call started: call_id={call_id}, agent={agent_type}")
        
        # Call LLM proxy
        response_data = await llm_proxy_client.chat_completion(
            model=AppConfig.LLM_MODEL,
            messages=history,
            tools=tools_to_use,
            stream=False
        )
        
        # NEW: Calculate duration
        llm_duration = time.time() - llm_start_time
        
        # NEW: Extract token usage from response
        usage = response_data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        
        logger.info(
            f"LLM call completed: call_id={call_id}, "
            f"tokens={input_tokens}/{output_tokens}, "
            f"duration={llm_duration:.2f}s"
        )
        
        # NEW: Create metrics object
        llm_metrics = LLMMetrics(
            agent_type=agent_type,
            model=AppConfig.LLM_MODEL,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            duration_seconds=llm_duration,
            timestamp=datetime.now(timezone.utc),
            call_id=call_id
        )
        
        # Extract message from response
        result_message = response_data["choices"][0]["message"]
        content = result_message.get("content", "")
        metadata = {}
        
        # ... existing tool_calls parsing logic ...
        
        # Handle tool calls
        if tool_calls:
            # ... existing tool call logic ...
            
            # Send tool_call chunk WITH metrics
            chunk = StreamChunk(
                type="tool_call",
                call_id=tool_call.id,
                tool_name=tool_call.tool_name,
                arguments=tool_call.arguments,
                requires_approval=requires_approval,
                llm_metrics=llm_metrics,  # NEW: добавить метрики
                is_final=True
            )
            
            logger.debug(f"Yielding tool_call chunk with metrics: {tool_call.tool_name}")
            yield chunk
            return
        
        # Handle regular assistant message
        # ... existing content processing ...
        
        await session_mgr.append_message(session_id, "assistant", clean_content)
        
        # Send assistant message chunk WITH metrics
        chunk = StreamChunk(
            type="assistant_message",
            content=clean_content,
            token=clean_content,
            llm_metrics=llm_metrics,  # NEW: добавить метрики
            is_final=True
        )
        
        logger.debug("Yielding assistant_message chunk with metrics")
        yield chunk
        
    except Exception as e:
        logger.error(
            f"Exception in stream_response for session {session_id}: {e}",
            exc_info=True
        )
        
        error_chunk = StreamChunk(
            type="error",
            error=str(e),
            is_final=True
        )
        yield error_chunk
```

### 3. Передать agent_type в stream_response

**Файл**: `codelab-ai-service/agent-runtime/app/services/multi_agent_orchestrator.py`

```python
async def process_message(
    self,
    session_id: str,
    message: str,
    agent_type: Optional[AgentType] = None
) -> AsyncGenerator[StreamChunk, None]:
    """Process message through multi-agent system"""
    
    # ... existing agent selection logic ...
    
    # Get current agent
    current_agent = agent_router.get_agent(agent_context.current_agent)
    
    logger.info(
        f"Processing with agent: {current_agent.agent_type.value} "
        f"for session {session_id}"
    )
    
    # Stream response from agent WITH agent_type
    async for chunk in stream_response(
        session_id=session_id,
        history=history,
        allowed_tools=current_agent.get_allowed_tools(),
        session_mgr=self.session_mgr,
        agent_type=current_agent.agent_type.value  # NEW: передать тип агента
    ):
        yield chunk
```

---

## Изменения в Gateway

### 1. Обновить модели WebSocket

**Файл**: `codelab-ai-service/gateway/app/models/websocket.py`

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class WSLLMMetrics(BaseModel):
    """LLM metrics для передачи через WebSocket"""
    agent_type: str
    model: str
    input_tokens: int
    output_tokens: int
    duration_seconds: float
    timestamp: datetime
    call_id: str

class WSAssistantMessage(BaseModel):
    """Assistant message с метриками"""
    type: str = "assistant_message"
    token: str
    is_final: bool = False
    llm_metrics: Optional[WSLLMMetrics] = None  # NEW

class WSToolCall(BaseModel):
    """Tool call с метриками"""
    type: str = "tool_call"
    call_id: str
    tool_name: str
    arguments: dict
    requires_approval: bool = False
    llm_metrics: Optional[WSLLMMetrics] = None  # NEW
```

### 2. Пробросить метрики через Gateway WebSocket

**Файл**: `codelab-ai-service/gateway/app/api/v1/endpoints.py`

В функции `websocket_endpoint`, в блоке обработки SSE stream:

```python
# Обрабатываем строку с данными
if line.startswith("data: "):
    data_str = line[6:]
    
    if data_str == "[DONE]":
        logger.info(f"[{session_id}] Received [DONE] marker")
        break
    
    if current_event_type == "message":
        try:
            data = json.loads(data_str)
            msg_type = data.get('type')
            
            # NEW: Логировать если есть метрики LLM
            if 'llm_metrics' in data and data['llm_metrics']:
                metrics = data['llm_metrics']
                logger.info(
                    f"[{session_id}] LLM metrics: agent={metrics.get('agent_type')}, "
                    f"tokens={metrics.get('input_tokens')}/{metrics.get('output_tokens')}, "
                    f"model={metrics.get('model')}"
                )
            
            # Фильтруем null значения
            filtered_data = {k: v for k, v in data.items() if v is not None}
            
            logger.debug(f"[{session_id}] Forwarding to IDE: type={msg_type}")
            
            # Пересылаем событие в IDE через WebSocket (включая llm_metrics)
            await websocket.send_json(filtered_data)
            
        except json.JSONDecodeError as e:
            logger.warning(f"[{session_id}] Failed to parse SSE data: {e}")
```

---

## Изменения в benchmark-standalone

### 1. Обработать llm_metrics в WebSocket клиенте

**Файл**: `benchmark-standalone/src/client.py`

В методе `execute_task`, добавить обработку метрик:

```python
async def execute_task(
    self,
    task: Dict[str, Any],
    tool_executor: MockToolExecutor,
    validator: Optional[TaskValidator],
    collector: MetricsCollector,
    task_execution_id: UUID
) -> bool:
    """Execute task via Gateway WebSocket with metrics collection"""
    
    # ... existing setup ...
    
    try:
        ws_endpoint = f"{self.ws_url}/{session_id}"
        async with websockets.connect(ws_endpoint) as websocket:
            logger.info(f"🔌 Connected to Gateway WebSocket")
            
            # Send initial message
            await websocket.send(json.dumps({
                "type": "user_message",
                "content": task_description,
                "role": "user"
            }))
            
            # Process responses
            while True:
                try:
                    data = await asyncio.wait_for(
                        websocket.recv(),
                        timeout=self.timeout
                    )
                    msg = json.loads(data)
                    msg_type = msg.get("type")
                    
                    # NEW: Extract and record LLM metrics if present
                    llm_metrics = msg.get("llm_metrics")
                    if llm_metrics:
                        logger.info(
                            f"📊 LLM metrics: agent={llm_metrics.get('agent_type')}, "
                            f"tokens={llm_metrics.get('input_tokens')}/"
                            f"{llm_metrics.get('output_tokens')}, "
                            f"model={llm_metrics.get('model')}, "
                            f"duration={llm_metrics.get('duration_seconds'):.2f}s"
                        )
                        
                        # Record LLM call metric
                        await collector.record_llm_call(
                            task_execution_id=task_execution_id,
                            agent_type=llm_metrics.get('agent_type', 'unknown'),
                            input_tokens=llm_metrics.get('input_tokens', 0),
                            output_tokens=llm_metrics.get('output_tokens', 0),
                            model=llm_metrics.get('model', 'unknown'),
                            duration_seconds=llm_metrics.get('duration_seconds', 0.0)
                        )
                    
                    if msg_type == "assistant_message":
                        token = msg.get("token", "")
                        response_text += token
                        
                        if msg.get("is_final"):
                            logger.info(f"✅ Received final message ({len(response_text)} chars)")
                            break
                    
                    elif msg_type == "tool_call":
                        tool_calls_count += 1
                        
                        call_id = msg.get("call_id")
                        tool_name = msg.get("tool_name")
                        arguments = msg.get("arguments", {})
                        
                        logger.info(
                            f"🔧 Tool call #{tool_calls_count}: {tool_name} "
                            f"(call_id={call_id[:8]}...)"
                        )
                        
                        # Execute tool locally
                        start_time = time.time()
                        tool_result = await tool_executor.execute_tool(
                            tool_name, arguments
                        )
                        duration = time.time() - start_time
                        
                        # Record tool call metric
                        await collector.record_tool_call(
                            task_execution_id=task_execution_id,
                            tool_name=tool_name,
                            success=tool_result.get('success', False),
                            duration_seconds=duration,
                            error=tool_result.get('error')
                        )
                        
                        # Send tool result back
                        await websocket.send(json.dumps({
                            "type": "tool_result",
                            "call_id": call_id,
                            "result": tool_result
                        }))
                    
                    # ... existing agent_switched, error handling ...
                    
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout waiting for response ({self.timeout}s)")
                    has_error = True
                    break
            
            # ... existing validation and completion logic ...
```

### 2. Добавить валидацию метрик

**Файл**: `benchmark-standalone/src/collector.py`

```python
async def get_experiment_summary(self, experiment_id: UUID) -> Dict[str, Any]:
    """Get summary with LLM metrics validation"""
    
    # ... existing code ...
    
    # Calculate total tokens
    total_input_tokens = 0
    total_output_tokens = 0
    total_llm_calls = 0
    
    for task in tasks:
        total_input_tokens += sum(call.input_tokens for call in task.llm_calls)
        total_output_tokens += sum(call.output_tokens for call in task.llm_calls)
        total_llm_calls += len(task.llm_calls)
    
    # NEW: Validate benchmark
    if total_llm_calls == 0:
        logger.warning(
            f"⚠️ BENCHMARK INVALID: No LLM calls detected for experiment {experiment_id}. "
            f"Multi-Agent system must make at least 1 LLM call per task."
        )
    
    # Calculate cost
    cost = (total_input_tokens * 0.003 + total_output_tokens * 0.015) / 1000
    
    return {
        "experiment_id": str(experiment_id),
        "mode": experiment.mode,
        "total_tasks": total_tasks,
        "successful_tasks": successful_tasks,
        "failed_tasks": failed_tasks,
        "success_rate": successful_tasks / total_tasks if total_tasks > 0 else 0.0,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_llm_calls": total_llm_calls,  # NEW
        "estimated_cost_usd": round(cost, 4),
        "is_valid": total_llm_calls > 0  # NEW: флаг валидности
    }
```

---

## Структура данных метрик

### Формат передачи через WebSocket

```json
{
  "type": "assistant_message",
  "token": "Here is the solution...",
  "is_final": true,
  "llm_metrics": {
    "agent_type": "coder",
    "model": "gpt-4",
    "input_tokens": 1250,
    "output_tokens": 450,
    "duration_seconds": 3.45,
    "timestamp": "2026-01-17T12:00:00.000Z",
    "call_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
  }
}
```

### Хранение в базе данных

Таблица `poc_llm_calls` уже существует в [`benchmark-standalone/src/models.py`](../benchmark-standalone/src/models.py:195):

```python
class LLMCall(Base):
    """LLM API call tracking."""
    __tablename__ = "poc_llm_calls"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_execution_id: Mapped[str] = mapped_column(String(36), ForeignKey(...))
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # ... timestamps ...
```

---

## План внедрения

### Фаза 1: Agent Runtime (Priority 0)
1. ✅ Добавить `LLMMetrics` модель в `app/models/schemas.py`
2. ✅ Модифицировать `llm_stream_service.py` для сбора метрик
3. ✅ Передать `agent_type` в `stream_response` из orchestrator
4. ✅ Добавить логирование метрик LLM

### Фаза 2: Gateway
1. ✅ Обновить WebSocket модели для поддержки `llm_metrics`
2. ✅ Пробросить метрики через Gateway без изменений
3. ✅ Добавить логирование метрик в Gateway

### Фаза 3: benchmark-standalone
1. ✅ Обработать `llm_metrics` в WebSocket клиенте
2. ✅ Записать метрики через `MetricsCollector.record_llm_call()`
3. ✅ Добавить валидацию: `total_llm_calls > 0`
4. ✅ Обновить отчеты для отображения метрик LLM

### Фаза 4: Тестирование
1. ✅ Запустить одну задачу и проверить метрики
2. ✅ Убедиться что `total_llm_calls > 0`
3. ✅ Проверить корректность токенов и стоимости
4. ✅ Запустить полный benchmark

---

## Альтернативные решения

### Вариант 2: REST API endpoint для метрик

Добавить endpoint в Agent Runtime:

```python
@router.get("/sessions/{session_id}/metrics")
async def get_session_metrics(session_id: str):
    """Get LLM metrics for session"""
    # Query from database or in-memory cache
    return {
        "llm_calls": [...],
        "total_input_tokens": 1250,
        "total_output_tokens": 450,
        "total_cost": 0.0105
    }
```

**Минусы**:
- Требует дополнительный HTTP запрос после каждой задачи
- Сложнее синхронизировать с WebSocket потоком
- Нужно хранить метрики в памяти или БД

### Вариант 3: Server-Sent Events (SSE) для метрик

Отдельный SSE stream параллельно с WebSocket.

**Минусы**:
- Усложняет архитектуру
- Два соединения вместо одного
- Сложнее синхронизировать события

---

## Преимущества выбранного решения

1. ✅ **Минимальные изменения** - используем существующий WebSocket канал
2. ✅ **Реал-тайм** - метрики передаются сразу после LLM вызова
3. ✅ **Обратная совместимость** - `llm_metrics` опциональное поле
4. ✅ **Простота** - не требует новых endpoints или соединений
5. ✅ **Трейсинг** - `call_id` позволяет связать метрики с tool calls

---

## Ожидаемый результат

После внедрения, benchmark должен показывать:

```
Total LLM Calls: 45
Input Tokens: 18,750
Output Tokens: 6,200
Total Tokens: 24,950
Estimated Cost: $0.15
```

Вместо текущих:

```
Total LLM Calls: 0  ❌
Input Tokens: 0     ❌
Output Tokens: 0    ❌
Total Tokens: 0     ❌
Estimated Cost: $0.00  ❌
```

---

## Дополнительные улучшения

### 1. Метрики по агентам

```python
# В отчете показывать breakdown по агентам
{
    "coder": {"calls": 25, "tokens": 15000},
    "architect": {"calls": 10, "tokens": 5000},
    "debug": {"calls": 10, "tokens": 4950}
}
```

### 2. Latency метрики

```python
# Добавить в LLMMetrics
class LLMMetrics(BaseModel):
    # ... existing fields ...
    ttft: Optional[float] = None  # Time To First Token
    tps: Optional[float] = None   # Tokens Per Second
```

### 3. Кэширование метрик

```python
# В Agent Runtime кэшировать метрики сессии
class SessionMetricsCache:
    def __init__(self):
        self._cache: Dict[str, List[LLMMetrics]] = {}
    
    def add(self, session_id: str, metrics: LLMMetrics):
        if session_id not in self._cache:
            self._cache[session_id] = []
        self._cache[session_id].append(metrics)
```

---

## Заключение

Данное решение позволяет benchmark-standalone собирать полные метрики LLM, несмотря на архитектуру с отдельным сервисом и REST/WebSocket коммуникацией. Изменения минимальны, обратно совместимы и не требуют изменения протокола WebSocket.

После внедрения, бенчмарк станет валидным и позволит корректно сравнивать Single-Agent и Multi-Agent архитектуры по метрикам:
- Task Success Rate
- Time To Useful Answer
- Cost per Task
- LLM Calls per Task
- Token Efficiency
