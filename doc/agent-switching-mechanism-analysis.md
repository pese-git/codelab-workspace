# Анализ механизма переключения агентов в agent-runtime

## Обзор архитектуры

Agent-runtime использует **мультиагентную систему** с событийно-ориентированной архитектурой (Event-Driven Architecture) для управления переключением между специализированными агентами.

## Ключевые компоненты

### 1. Типы агентов ([`base_agent.py`](../codelab-ai-service/agent-runtime/app/agents/base_agent.py:18))

```python
class AgentType(str, Enum):
    ORCHESTRATOR = "orchestrator"  # Координатор
    CODER = "coder"               # Написание кода
    ARCHITECT = "architect"        # Проектирование
    DEBUG = "debug"               # Отладка
    ASK = "ask"                   # Ответы на вопросы
    UNIVERSAL = "universal"        # Универсальный (single-agent mode)
```

### 2. Регистрация агентов ([`agents/__init__.py`](../codelab-ai-service/agent-runtime/app/agents/__init__.py:20))

При старте приложения происходит автоматическая регистрация агентов:

**Multi-agent режим** (MULTI_AGENT_MODE=true):
- Orchestrator + 4 специализированных агента (Coder, Architect, Debug, Ask)

**Single-agent режим** (MULTI_AGENT_MODE=false):
- Orchestrator + Universal agent (обрабатывает все типы задач)

### 3. AgentRouter ([`agent_router.py`](../codelab-ai-service/agent-runtime/app/services/agent_router.py:14))

Центральный реестр агентов:
- **Регистрация**: [`register_agent()`](../codelab-ai-service/agent-runtime/app/services/agent_router.py:29)
- **Получение**: [`get_agent(agent_type)`](../codelab-ai-service/agent-runtime/app/services/agent_router.py:51)
- **Список**: [`list_agents()`](../codelab-ai-service/agent-runtime/app/services/agent_router.py:87)

## Механизм переключения агентов

### Этап 1: Точка входа ([`endpoints.py`](../codelab-ai-service/agent-runtime/app/api/v1/endpoints.py:40))

Запрос поступает через SSE endpoint `/agent/message/stream`:

```python
@router.post("/agent/message/stream")
async def message_stream_sse(request: AgentStreamRequest):
```

Поддерживаемые типы сообщений:
- **`user_message`** - обычное сообщение пользователя
- **`tool_result`** - результат выполнения инструмента
- **`switch_agent`** - явный запрос на переключение агента
- **`hitl_decision`** - решение пользователя (HITL - Human-in-the-Loop)

### Этап 2: MultiAgentOrchestrator ([`multi_agent_orchestrator.py`](../codelab-ai-service/agent-runtime/app/services/multi_agent_orchestrator.py:30))

Координирует работу мультиагентной системы через метод [`process_message()`](../codelab-ai-service/agent-runtime/app/services/multi_agent_orchestrator.py:41):

#### 2.1 Явное переключение агента

```python
if agent_type:  # Явный запрос на переключение
    if context.current_agent != agent_type:
        # Публикация события AgentSwitchedEvent
        await event_bus.publish(
            AgentSwitchedEvent(
                session_id=session_id,
                from_agent=from_agent.value,
                to_agent=agent_type.value,
                reason="User requested agent switch"
            )
        )
```

#### 2.2 Автоматическая маршрутизация через Orchestrator

Если текущий агент - Orchestrator и есть сообщение:

```python
if context.current_agent == AgentType.ORCHESTRATOR and message:
    orchestrator = agent_router.get_agent(AgentType.ORCHESTRATOR)
    
    # Orchestrator анализирует и возвращает switch_agent chunk
    async for chunk in orchestrator.process(...):
        if chunk.type == "switch_agent":
            target_agent = AgentType(chunk.metadata.get("target_agent"))
            
            # Публикация события переключения
            await event_bus.publish(AgentSwitchedEvent(...))
```

### Этап 3: OrchestratorAgent - Классификация задач ([`orchestrator_agent.py`](../codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py:69))

Orchestrator использует **LLM-based классификацию** для определения подходящего агента:

#### 3.1 Проверка режима работы

```python
available_agents = agent_router.list_agents()

if AgentType.UNIVERSAL in available_agents and len(available_agents) == 2:
    # Single-agent mode: маршрутизация на Universal
    target_agent = AgentType.UNIVERSAL
else:
    # Multi-agent mode: LLM классификация
    target_agent, classification_info = await self.classify_task_with_llm(message)
```

#### 3.2 LLM-классификация ([`classify_task_with_llm()`](../codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py:147))

```python
async def classify_task_with_llm(self, message: str):
    # Вызов LLM с промптом классификации
    response = await llm_proxy_client.chat_completion(
        model=AppConfig.LLM_MODEL,
        messages=[
            {"role": "system", "content": "You are a task classifier..."},
            {"role": "user", "content": classification_prompt}
        ],
        temperature=0.3  # Низкая температура для стабильности
    )
    
    # Парсинг JSON ответа
    classification = json.loads(content)
    # {"agent": "coder", "confidence": "high", "reasoning": "..."}
    
    return target_agent, classification
```

#### 3.3 Fallback классификация

При ошибке LLM используется keyword-based классификация ([`_fallback_classify()`](../codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py:225)):

```python
def _fallback_classify(self, message: str) -> AgentType:
    message_lower = message.lower()
    
    if any(kw in message_lower for kw in ["create", "write", "implement", ...]):
        return AgentType.CODER
    elif any(kw in message_lower for kw in ["design", "architecture", ...]):
        return AgentType.ARCHITECT
    # ... и т.д.
```

### Этап 4: Событийно-ориентированное обновление контекста

#### 4.1 Публикация события ([`agent_events.py`](../codelab-ai-service/agent-runtime/app/events/agent_events.py:12))

```python
class AgentSwitchedEvent(BaseEvent):
    def __init__(self, session_id, from_agent, to_agent, reason, confidence=None):
        super().__init__(
            event_type=EventType.AGENT_SWITCHED,
            event_category=EventCategory.AGENT,
            data={
                "from_agent": from_agent,
                "to_agent": to_agent,
                "reason": reason,
                "confidence": confidence,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
```

#### 4.2 Обработка события ([`agent_context_subscriber.py`](../codelab-ai-service/agent-runtime/app/events/subscribers/agent_context_subscriber.py:16))

AgentContextSubscriber автоматически обновляет контекст:

```python
async def _on_agent_switched(self, event: BaseEvent):
    session_id = event.session_id
    to_agent = event.data.get("to_agent")
    
    # Получение контекста
    context = agent_context_manager.get(session_id)
    
    # Обновление контекста (без вызова switch_agent для избежания циклов)
    context.agent_history.append({
        "from_agent": from_agent,
        "to_agent": to_agent,
        "reason": reason,
        "timestamp": event.timestamp.isoformat()
    })
    
    context.current_agent = AgentType(to_agent)
    context.last_switch_at = event.timestamp
    context.switch_count += 1
    context._needs_persist = True  # Пометка для сохранения в БД
```

### Этап 5: Управление контекстом агента ([`agent_context_async.py`](../codelab-ai-service/agent-runtime/app/services/agent_context_async.py:18))

#### 5.1 AgentContext - состояние сессии

```python
class AgentContext(BaseModel):
    session_id: str
    current_agent: AgentType = AgentType.ORCHESTRATOR
    agent_history: List[Dict[str, Any]] = []  # История переключений
    metadata: Dict[str, Any] = {}
    switch_count: int = 0
    last_switch_at: Optional[datetime] = None
```

#### 5.2 AsyncAgentContextManager - управление контекстами

- **Инициализация**: Загрузка контекстов из БД при старте
- **Background writer**: Автоматическое сохранение изменений каждые 5 секунд
- **Персистентность**: Сохранение в PostgreSQL через DatabaseService

```python
async def _background_writer(self):
    while True:
        await asyncio.sleep(5)
        
        # Поиск контекстов, требующих сохранения
        contexts_to_persist = [
            sid for sid, ctx in self._contexts.items() 
            if ctx._needs_persist
        ]
        
        # Сохранение в БД
        for session_id in contexts_to_persist:
            await self._db_service.save_agent_context(...)
```

## Полный поток переключения агента

```
1. Пользователь отправляет сообщение
   ↓
2. POST /agent/message/stream (endpoints.py)
   ↓
3. MultiAgentOrchestrator.process_message()
   ↓
4. Проверка текущего агента
   ├─ Если Orchestrator → Классификация задачи
   │  ├─ LLM-based классификация (classify_task_with_llm)
   │  └─ Fallback keyword-based (при ошибке)
   │
   └─ Если специализированный агент → Продолжение работы
   ↓
5. Публикация AgentSwitchedEvent
   ↓
6. Event Bus распространяет событие подписчикам:
   ├─ AgentContextSubscriber → Обновляет контекст
   ├─ MetricsCollector → Собирает метрики
   ├─ AuditLogger → Логирует переключение
   └─ PersistenceSubscriber → Сохраняет в БД
   ↓
7. Обновление AgentContext
   ├─ current_agent = новый агент
   ├─ agent_history.append(запись о переключении)
   ├─ switch_count += 1
   └─ _needs_persist = True
   ↓
8. Background writer сохраняет в PostgreSQL (каждые 5 сек)
   ↓
9. Новый агент обрабатывает сообщение
   ↓
10. Результат возвращается через SSE stream
```

## Способы переключения агента

### 1. Автоматическое (через Orchestrator)
```json
{
  "message": {
    "type": "user_message",
    "content": "Create a new React component"
  }
}
```
→ Orchestrator классифицирует → Переключение на Coder

### 2. Явное переключение
```json
{
  "message": {
    "type": "switch_agent",
    "agent_type": "architect",
    "content": "Design the system architecture"
  }
}
```
→ Прямое переключение на Architect

### 3. Переключение из агента
Агент может запросить переключение, вернув chunk с `type="switch_agent"`:
```python
yield StreamChunk(
    type="switch_agent",
    metadata={"target_agent": "debug", "reason": "Need debugging"}
)
```

## Персистентность и восстановление

### Сохранение в БД
- **Таблица**: `agent_contexts`
- **Поля**: session_id, current_agent, agent_history, metadata, switch_count
- **Механизм**: Background writer + event-driven persistence

### Восстановление после перезапуска
```python
async def initialize(self):
    # Загрузка всех контекстов из БД
    session_ids = await self._db_service.list_all_sessions(db)
    for session_id in session_ids:
        context_data = await self._db_service.load_agent_context(db, session_id)
        self._contexts[session_id] = AgentContext(**context_data)
```

## API для работы с агентами

### Получение текущего агента
```
GET /agents/{session_id}/current
```
Возвращает:
```json
{
  "session_id": "uuid",
  "current_agent": "coder",
  "agent_history": [...],
  "switch_count": 3
}
```

### Список всех агентов
```
GET /agents
```
Возвращает информацию о зарегистрированных агентах.

### История сессии
```
GET /sessions/{session_id}/history
```
Включает историю переключений агентов.

## Преимущества архитектуры

1. **Event-Driven**: Слабая связанность компонентов через события
2. **Персистентность**: Автоматическое сохранение состояния в БД
3. **Масштабируемость**: Легко добавлять новых подписчиков событий
4. **Наблюдаемость**: Автоматический сбор метрик и аудит
5. **LLM-классификация**: Интеллектуальная маршрутизация задач
6. **Fallback механизм**: Устойчивость при ошибках LLM
7. **Гибкость**: Поддержка multi-agent и single-agent режимов

## Метрики и мониторинг

События переключения агентов автоматически собираются:
- **MetricsCollector**: Статистика переключений
- **AuditLogger**: Аудит всех переключений
- **SessionMetricsCollector**: Метрики по сессиям

Доступ через API:
```
GET /events/metrics
GET /events/audit-log?event_type=AGENT_SWITCHED
GET /events/stats
```

## Заключение

Механизм переключения агентов в agent-runtime реализован через:
- **Событийно-ориентированную архитектуру** (Event-Driven)
- **LLM-based интеллектуальную классификацию** задач
- **Автоматическую персистентность** состояния
- **Слабую связанность** компонентов через Event Bus
- **Гибкую систему подписчиков** для расширяемости

Это обеспечивает надежное, масштабируемое и наблюдаемое переключение между специализированными агентами в зависимости от типа задачи.
