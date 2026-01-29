# Подход с сохранением process() в агентах

**Дата:** 25 января 2026  
**Вопрос:** Можно ли оставить логику в `process()` методе агентов?

---

## Краткий ответ

**ДА, можно!** ✅

Но `stream_handler` должен передаваться как **параметр метода**, а не храниться в агенте. Это сохранит Clean Architecture и позволит агентам иметь кастомную логику.

---

## Правильная реализация

### Вариант 1: Stream handler как параметр (рекомендуется)

```python
# app/agents/base_agent.py

class BaseAgent(ABC):
    """
    Базовый класс агента.
    
    Агенты содержат доменную логику обработки сообщений,
    но НЕ хранят зависимости от Application Layer.
    """
    
    def __init__(
        self,
        agent_type: AgentType,
        system_prompt: str,
        allowed_tools: List[str],
        file_restrictions: Optional[List[str]] = None
    ):
        self.agent_type = agent_type
        self.system_prompt = system_prompt
        self.allowed_tools = allowed_tools
        self.file_restrictions = file_restrictions or []
    
    @abstractmethod
    async def process(
        self,
        session_id: str,
        message: str,
        context: Dict[str, Any],
        session: Session,
        session_service: SessionManagementService,
        stream_handler: "StreamLLMResponseHandler"  # Параметр, не поле!
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Обработать сообщение через агента.
        
        Args:
            session_id: ID сессии
            message: Сообщение пользователя
            context: Контекст агента
            session: Доменная сущность сессии
            session_service: Сервис управления сессиями
            stream_handler: Handler для стриминга (передается извне)
            
        Yields:
            StreamChunk: Чанки для стриминга
        """
        pass
```

### Реализация в конкретных агентах

#### CoderAgent - простая логика

```python
# app/agents/coder_agent.py

from typing import AsyncGenerator, Dict, Any
from .base_agent import BaseAgent, AgentType
from .prompts.coder import CODER_SYSTEM_PROMPT
from app.models.schemas import StreamChunk

class CoderAgent(BaseAgent):
    """Агент для написания кода"""
    
    def __init__(self):
        super().__init__(
            agent_type=AgentType.CODER,
            system_prompt=CODER_SYSTEM_PROMPT,
            allowed_tools=[
                "read_file",
                "write_to_file",
                "apply_diff",
                "list_files",
                "search_files",
                "execute_command"
            ]
        )
    
    async def process(
        self,
        session_id: str,
        message: str,
        context: Dict[str, Any],
        session: Session,
        session_service: SessionManagementService,
        stream_handler: StreamLLMResponseHandler
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Обработка сообщения через Coder агента.
        
        Логика:
        1. Получить историю с system prompt
        2. Вызвать stream_handler с конфигурацией агента
        3. Передать стрим клиенту
        """
        # Получить историю
        history = session.get_history_for_llm()
        
        # Добавить system prompt в начало
        history = [
            {"role": "system", "content": self.system_prompt},
            *history
        ]
        
        # Вызвать stream handler
        async for chunk in stream_handler.handle(
            session_id=session_id,
            history=history,
            model="gpt-4",  # Можно из конфига
            allowed_tools=self.allowed_tools,
            correlation_id=context.get("correlation_id")
        ):
            yield chunk
```

#### OrchestratorAgent - кастомная логика

```python
# app/agents/orchestrator_agent.py

class OrchestratorAgent(BaseAgent):
    """
    Агент-оркестратор для маршрутизации задач.
    
    Имеет специфичную логику: анализирует сообщение
    и решает, нужно ли переключиться на другого агента.
    """
    
    def __init__(self):
        super().__init__(
            agent_type=AgentType.ORCHESTRATOR,
            system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
            allowed_tools=["switch_mode"]  # Только переключение
        )
    
    async def process(
        self,
        session_id: str,
        message: str,
        context: Dict[str, Any],
        session: Session,
        session_service: SessionManagementService,
        stream_handler: StreamLLMResponseHandler
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Обработка через Orchestrator.
        
        Кастомная логика:
        1. Анализировать сообщение
        2. Определить целевого агента
        3. Если нужно переключение - вернуть agent_switched chunk
        4. Иначе - обработать сообщение
        """
        # 1. Анализ сообщения для routing
        target_agent = await self._analyze_message(
            message=message,
            session=session,
            stream_handler=stream_handler
        )
        
        # 2. Если нужно переключение
        if target_agent and target_agent != AgentType.ORCHESTRATOR:
            # Вернуть chunk о переключении
            yield StreamChunk(
                type="agent_switched",
                content=f"Switching to {target_agent.value} agent",
                agent_type=target_agent.value,
                reason="Task requires specialized agent",
                is_final=True
            )
            return
        
        # 3. Иначе обработать сообщение
        history = session.get_history_for_llm()
        history = [{"role": "system", "content": self.system_prompt}, *history]
        
        async for chunk in stream_handler.handle(
            session_id=session_id,
            history=history,
            model="gpt-4",
            allowed_tools=self.allowed_tools
        ):
            yield chunk
    
    async def _analyze_message(
        self,
        message: str,
        session: Session,
        stream_handler: StreamLLMResponseHandler
    ) -> Optional[AgentType]:
        """
        Проанализировать сообщение и определить целевого агента.
        
        Это доменная логика Orchestrator агента.
        Использует LLM для анализа намерения пользователя.
        """
        # Специальный промпт для routing
        routing_prompt = """
        Analyze the user's message and determine which agent should handle it:
        - coder: Writing, editing, or refactoring code
        - architect: Planning, designing, or documenting architecture
        - debug: Investigating bugs, analyzing errors
        - ask: Answering questions, explaining concepts
        
        Respond with just the agent name.
        """
        
        routing_history = [
            {"role": "system", "content": routing_prompt},
            {"role": "user", "content": message}
        ]
        
        # Вызвать LLM для routing (без инструментов)
        async for chunk in stream_handler.handle(
            session_id=session.id,
            history=routing_history,
            model="gpt-4",
            allowed_tools=[]  # Нет инструментов для routing
        ):
            if chunk.type == "assistant_message":
                agent_name = chunk.content.strip().lower()
                try:
                    return AgentType(agent_name)
                except ValueError:
                    return None
        
        return None
```

---

## Обновление MessageOrchestrationService

```python
# app/domain/services/message_orchestration.py

class MessageOrchestrationService:
    """
    Сервис оркестрации сообщений.
    
    Координирует обработку через агентов,
    передавая им необходимые зависимости.
    """
    
    def __init__(
        self,
        session_service: SessionManagementService,
        agent_service: AgentOrchestrationService,
        agent_router: AgentRouter,
        lock_manager: SessionLockManager,
        event_publisher,
        stream_handler: StreamLLMResponseHandler
    ):
        self._session_service = session_service
        self._agent_service = agent_service
        self._agent_router = agent_router
        self._lock_manager = lock_manager
        self._event_publisher = event_publisher
        self._stream_handler = stream_handler
    
    async def process_message(
        self,
        session_id: str,
        message: str,
        agent_type: Optional[AgentType] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Обработать сообщение через агента.
        
        Координация:
        1. Получить сессию
        2. Определить агента
        3. Добавить user message
        4. Вызвать agent.process() с stream_handler
        5. Передать стрим клиенту
        """
        # 1. Получить сессию
        session = await self._session_service.get_or_create_session(session_id)
        
        # 2. Определить агента
        if agent_type is None:
            # Автоматический routing
            agent_type = await self._route_to_agent(session_id, message)
        
        agent = self._agent_router.get_agent(agent_type)
        
        # 3. Добавить user message
        await self._session_service.add_message(
            session_id=session_id,
            role="user",
            content=message
        )
        
        # Получить обновленную сессию
        session = await self._session_service.get_session(session_id)
        
        # 4. Вызвать agent.process() с stream_handler как параметром
        async for chunk in agent.process(
            session_id=session_id,
            message=message,
            context={},
            session=session,
            session_service=self._session_service,
            stream_handler=self._stream_handler  # Передаем handler
        ):
            yield chunk
```

---

## Сравнение подходов

### Подход 1: Агенты как конфигурация (без process)

**Плюсы:**
- ✅ Агенты максимально простые
- ✅ Вся логика стриминга в одном месте
- ✅ Легко тестировать
- ✅ Меньше дублирования кода

**Минусы:**
- ⚠️ Сложнее добавить кастомную логику для агента
- ⚠️ Orchestrator требует специальной обработки

**Когда использовать:**
- Все агенты работают одинаково (только промпт и инструменты отличаются)
- Нет специфичной логики для агентов

### Подход 2: Агенты с process() методом (stream_handler как параметр)

**Плюсы:**
- ✅ Каждый агент может иметь кастомную логику
- ✅ Orchestrator легко реализовать routing
- ✅ Гибкость для будущих расширений
- ✅ Соблюдение Clean Architecture (handler передается извне)

**Минусы:**
- ⚠️ Небольшое дублирование кода в простых агентах
- ⚠️ Нужно передавать stream_handler через все вызовы

**Когда использовать:**
- Агенты имеют разную логику обработки
- Orchestrator делает routing
- Нужна гибкость для будущих расширений

---

## Рекомендация: Подход 2 (с process)

Для вашего проекта рекомендую **Подход 2**, потому что:

1. **Orchestrator имеет специфичную логику** - routing к другим агентам
2. **Гибкость** - в будущем агенты могут иметь разную логику
3. **Соблюдение Clean Architecture** - handler передается как параметр

### Правильная реализация

```python
# app/agents/base_agent.py

class BaseAgent(ABC):
    """Базовый класс агента"""
    
    def __init__(
        self,
        agent_type: AgentType,
        system_prompt: str,
        allowed_tools: List[str],
        file_restrictions: Optional[List[str]] = None
    ):
        # НЕТ stream_handler в конструкторе!
        self.agent_type = agent_type
        self.system_prompt = system_prompt
        self.allowed_tools = allowed_tools
        self.file_restrictions = file_restrictions or []
    
    @abstractmethod
    async def process(
        self,
        session_id: str,
        message: str,
        context: Dict[str, Any],
        session: Session,
        session_service: SessionManagementService,
        stream_handler: StreamLLMResponseHandler  # Параметр метода!
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Обработать сообщение.
        
        stream_handler передается как параметр,
        а не хранится в агенте.
        """
        pass
```

```python
# app/agents/coder_agent.py

class CoderAgent(BaseAgent):
    """Агент для написания кода"""
    
    def __init__(self):
        super().__init__(
            agent_type=AgentType.CODER,
            system_prompt=CODER_SYSTEM_PROMPT,
            allowed_tools=["read_file", "write_to_file", ...]
        )
    
    async def process(
        self,
        session_id: str,
        message: str,
        context: Dict[str, Any],
        session: Session,
        session_service: SessionManagementService,
        stream_handler: StreamLLMResponseHandler  # Получаем извне
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Обработка через Coder агента.
        
        Простая логика: просто вызвать stream_handler.
        """
        # Получить историю
        history = session.get_history_for_llm()
        
        # Добавить system prompt
        history = [
            {"role": "system", "content": self.system_prompt},
            *history
        ]
        
        # Вызвать stream handler (передан как параметр)
        async for chunk in stream_handler.handle(
            session_id=session_id,
            history=history,
            model="gpt-4",
            allowed_tools=self.allowed_tools,
            correlation_id=context.get("correlation_id")
        ):
            yield chunk
```

```python
# app/agents/orchestrator_agent.py

class OrchestratorAgent(BaseAgent):
    """Агент-оркестратор с кастомной логикой"""
    
    def __init__(self):
        super().__init__(
            agent_type=AgentType.ORCHESTRATOR,
            system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
            allowed_tools=["switch_mode"]
        )
    
    async def process(
        self,
        session_id: str,
        message: str,
        context: Dict[str, Any],
        session: Session,
        session_service: SessionManagementService,
        stream_handler: StreamLLMResponseHandler
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Обработка через Orchestrator.
        
        Кастомная логика:
        1. Анализировать сообщение
        2. Определить целевого агента
        3. Вернуть agent_switched chunk
        """
        # 1. Анализ для routing
        target_agent = await self._analyze_for_routing(
            message=message,
            session=session,
            stream_handler=stream_handler  # Используем для анализа
        )
        
        # 2. Если нужно переключение
        if target_agent and target_agent != AgentType.ORCHESTRATOR:
            yield StreamChunk(
                type="agent_switched",
                content=f"Switching to {target_agent.value} agent",
                agent_type=target_agent.value,
                reason="Task requires specialized agent",
                is_final=True
            )
            return
        
        # 3. Иначе обработать сообщение
        history = session.get_history_for_llm()
        history = [{"role": "system", "content": self.system_prompt}, *history]
        
        async for chunk in stream_handler.handle(
            session_id=session_id,
            history=history,
            model="gpt-4",
            allowed_tools=self.allowed_tools
        ):
            yield chunk
    
    async def _analyze_for_routing(
        self,
        message: str,
        session: Session,
        stream_handler: StreamLLMResponseHandler
    ) -> Optional[AgentType]:
        """
        Доменная логика routing.
        
        Использует LLM для анализа намерения пользователя.
        """
        routing_prompt = """Analyze and determine which agent should handle this task..."""
        
        routing_history = [
            {"role": "system", "content": routing_prompt},
            {"role": "user", "content": message}
        ]
        
        async for chunk in stream_handler.handle(
            session_id=session.id,
            history=routing_history,
            model="gpt-4",
            allowed_tools=[]  # Нет инструментов для routing
        ):
            if chunk.type == "assistant_message":
                agent_name = chunk.content.strip().lower()
                try:
                    return AgentType(agent_name)
                except ValueError:
                    return None
        
        return None
```

### Обновление MessageOrchestrationService

```python
# app/domain/services/message_orchestration.py

class MessageOrchestrationService:
    """Сервис оркестрации сообщений"""
    
    def __init__(
        self,
        session_service: SessionManagementService,
        agent_service: AgentOrchestrationService,
        agent_router: AgentRouter,
        lock_manager: SessionLockManager,
        event_publisher,
        stream_handler: StreamLLMResponseHandler  # Инжектируем
    ):
        self._session_service = session_service
        self._agent_service = agent_service
        self._agent_router = agent_router
        self._lock_manager = lock_manager
        self._event_publisher = event_publisher
        self._stream_handler = stream_handler  # Сохраняем
    
    async def process_message(
        self,
        session_id: str,
        message: str,
        agent_type: Optional[AgentType] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Обработать сообщение через агента.
        
        Передает stream_handler агенту как параметр.
        """
        # Получить сессию
        session = await self._session_service.get_or_create_session(session_id)
        
        # Определить агента
        if agent_type is None:
            agent_type = AgentType.ORCHESTRATOR  # По умолчанию
        
        agent = self._agent_router.get_agent(agent_type)
        
        # Добавить user message
        await self._session_service.add_message(
            session_id=session_id,
            role="user",
            content=message
        )
        
        # Получить обновленную сессию
        session = await self._session_service.get_session(session_id)
        
        # Вызвать agent.process() с stream_handler
        async for chunk in agent.process(
            session_id=session_id,
            message=message,
            context={},
            session=session,
            session_service=self._session_service,
            stream_handler=self._stream_handler  # Передаем как параметр
        ):
            yield chunk
```

---

## Почему stream_handler как параметр, а не поле?

### ❌ Неправильно: Хранить в агенте

```python
class BaseAgent:
    def __init__(self, ..., stream_handler: StreamLLMResponseHandler):
        self._stream_handler = stream_handler  # Хранится в агенте
```

**Проблемы:**
1. Domain Layer зависит от Application Layer
2. Нарушение Dependency Rule
3. Агент становится stateful (хранит зависимость)
4. Сложнее тестировать (нужно мокировать при создании)

### ✅ Правильно: Передавать как параметр

```python
class BaseAgent:
    async def process(
        self,
        ...,
        stream_handler: StreamLLMResponseHandler  # Параметр метода
    ):
        # Используется локально, не хранится
        async for chunk in stream_handler.handle(...):
            yield chunk
```

**Преимущества:**
1. Domain Layer НЕ зависит от Application Layer (зависимость только в сигнатуре метода)
2. Соблюдение Dependency Rule
3. Агент остается stateless (не хранит зависимости)
4. Легко тестировать (мок передается при вызове)
5. Гибкость (можно передать разные handlers для разных вызовов)

---

## Диаграмма зависимостей

```
┌─────────────────────────────────────────────────────────┐
│                  API Layer                               │
│  POST /agent/message/stream                              │
│      ↓ вызывает                                          │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│              Application Layer                           │
│  ┌────────────────────────────────────────────────────┐ │
│  │ MessageOrchestrationService                        │ │
│  │   - Хранит stream_handler                          │ │
│  │   - Передает его агентам как параметр              │ │
│  └────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────┐ │
│  │ StreamLLMResponseHandler                           │ │
│  │   - Координирует стриминг                          │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
         ↓ вызывает (передает handler)      ↓ использует
┌──────────────────────────┐    ┌──────────────────────────┐
│     Domain Layer         │    │  Infrastructure Layer    │
│  ┌────────────────────┐  │    │  ┌────────────────────┐ │
│  │ CoderAgent         │  │    │  │   LLMClient        │ │
│  │                    │  │    │  │                    │ │
│  │ process(           │  │    │  │ chat_completion()  │ │
│  │   ...,             │  │    │  └────────────────────┘ │
│  │   stream_handler   │  │    │                          │
│  │ )                  │  │    │  ┌────────────────────┐ │
│  │                    │  │    │  │ LLMEventPublisher  │ │
│  │ НЕ хранит handler! │  │    │  │                    │ │
│  └────────────────────┘  │    │  │ publish_*()        │ │
└──────────────────────────┘    │  └────────────────────┘ │
                                └──────────────────────────┘
```

**Ключевой момент:**
- `MessageOrchestrationService` (Application) **хранит** `stream_handler`
- Агенты (Domain) **получают** `stream_handler` как **параметр метода**
- Агенты **НЕ хранят** `stream_handler` как поле

---

## Заключение

### Ответ на вопрос

**Можно ли оставить логику в process()?**

✅ **ДА!** Это даже лучше для гибкости.

**Как правильно передавать stream_handler?**

✅ **Как параметр метода `process()`**, а НЕ как поле класса.

```python
# ПРАВИЛЬНО ✅
async def process(
    self,
    ...,
    stream_handler: StreamLLMResponseHandler  # Параметр
) -> AsyncGenerator[StreamChunk, None]:
    async for chunk in stream_handler.handle(...):
        yield chunk

# НЕПРАВИЛЬНО ❌
def __init__(self, ..., stream_handler: StreamLLMResponseHandler):
    self._stream_handler = stream_handler  # Поле класса
```

### Преимущества этого подхода

1. ✅ Соблюдение Clean Architecture (Domain не зависит от Application)
2. ✅ Гибкость для кастомной логики агентов
3. ✅ Легко тестировать (мок передается при вызове)
4. ✅ Агенты остаются stateless
5. ✅ Возможность передать разные handlers для разных сценариев

---

**Подготовлено:** AI Architecture Auditor  
**Дата:** 25 января 2026  
**Версия документа:** 1.0
