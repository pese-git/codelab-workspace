# Анализ метода stream_response(): Clean Architecture и SOLID

**Дата:** 24 января 2026  
**Файл:** [`app/infrastructure/llm/streaming.py:40`](codelab-ai-service/agent-runtime/app/infrastructure/llm/streaming.py:40)  
**Метод:** `stream_response()`

---

## Исполнительное резюме

Метод [`stream_response()`](codelab-ai-service/agent-runtime/app/infrastructure/llm/streaming.py:40) демонстрирует **значительные нарушения** принципов SOLID и Clean Architecture. Функция имеет **множественные ответственности**, высокую связанность и нарушает принцип единственной ответственности (SRP).

### Оценка соответствия

| Принцип | Оценка | Комментарий |
|---------|--------|-------------|
| **SRP** | ❌ 2/10 | Множественные ответственности |
| **OCP** | ⚠️ 5/10 | Сложно расширять без модификации |
| **LSP** | N/A | Не применимо (не наследование) |
| **ISP** | ⚠️ 6/10 | Слишком много параметров |
| **DIP** | ⚠️ 4/10 | Прямые зависимости от конкретных реализаций |
| **Clean Architecture** | ❌ 3/10 | Смешивание слоев |

**Общая оценка: 4/10** ❌

---

## 1. Нарушение Single Responsibility Principle (SRP)

### Проблема: Множественные ответственности

Функция `stream_response()` выполняет **как минимум 8 различных ответственностей**:

```python
async def stream_response(
    session_id: str,
    history: List[dict],
    allowed_tools: Optional[List[str]] = None,
    session_mgr: Optional["SessionManagerAdapter"] = None,
    correlation_id: Optional[str] = None
) -> AsyncGenerator[StreamChunk, None]:
```

#### Ответственности функции:

1. **Фильтрация инструментов** (строки 76-86)
   ```python
   tools_to_use = TOOLS_SPEC
   if allowed_tools is not None:
       tools_to_use = [tool for tool in TOOLS_SPEC if tool["function"]["name"] in allowed_tools]
   ```

2. **Подготовка LLM запроса** (строки 88-94)
   ```python
   llm_request = {
       "model": AppConfig.LLM_MODEL,
       "messages": history,
       "stream": False,
       "tools": tools_to_use,
   }
   ```

3. **Публикация событий** (строки 98-110, 263-276, 308-321, 333-340)
   ```python
   await event_bus.publish(LLMRequestStartedEvent(...))
   await event_bus.publish(LLMRequestCompletedEvent(...))
   await event_bus.publish(LLMRequestFailedEvent(...))
   ```

4. **Вызов LLM API** (строки 113-118)
   ```python
   response_data = await llm_proxy_client.chat_completion(...)
   ```

5. **Парсинг ответа LLM** (строки 134-152)
   ```python
   result_message = response_data["choices"][0]["message"]
   content = result_message.get("content", "")
   tool_calls, clean_content = parse_tool_calls(content, metadata)
   ```

6. **HITL (Human-in-the-Loop) логика** (строки 192-220)
   ```python
   requires_approval, reason = hitl_policy_service.requires_approval(tool_call.tool_name)
   if requires_approval:
       await hitl_manager.add_pending(...)
       await event_bus.publish(ToolApprovalRequiredEvent(...))
   ```

7. **Персистентность сообщений** (строки 246-250, 295)
   ```python
   await session_mgr.append_assistant_with_tool_calls(...)
   await session_mgr.append_message(session_id, "assistant", clean_content)
   ```

8. **Генерация стрима** (строки 253-280, 300-324)
   ```python
   chunk = StreamChunk(type="tool_call", ...)
   yield chunk
   ```

### Последствия нарушения SRP:

- ❌ **Сложность тестирования**: Невозможно протестировать отдельные части
- ❌ **Сложность понимания**: 348 строк кода в одной функции
- ❌ **Высокая связанность**: Зависит от 10+ внешних компонентов
- ❌ **Сложность изменения**: Изменение одной части может сломать другие
- ❌ **Нарушение Clean Architecture**: Смешивание бизнес-логики и инфраструктуры

---

## 2. Нарушение Dependency Inversion Principle (DIP)

### Проблема: Прямые зависимости от конкретных реализаций

```python
# Прямые импорты конкретных реализаций
from app.infrastructure.llm.client import llm_proxy_client  # Конкретная реализация
from app.domain.services.tool_registry import TOOLS_SPEC  # Глобальная переменная
from app.domain.services.hitl_policy import hitl_policy_service  # Конкретная реализация
from app.domain.services.hitl_management import hitl_manager  # Конкретная реализация
from app.events.event_bus import event_bus  # Глобальный singleton

# Использование глобального состояния
if session_mgr is None:
    from app.main import session_manager_adapter as global_mgr  # Импорт из main!
    session_mgr = global_mgr
```

### Последствия:

- ❌ **Невозможно подменить зависимости** для тестирования
- ❌ **Жесткая связанность** с конкретными реализациями
- ❌ **Нарушение Clean Architecture**: Infrastructure слой зависит от глобального состояния
- ❌ **Сложность unit-тестирования**: Нужно мокировать глобальные переменные

### Правильный подход (DIP):

```python
# Зависимости должны передаваться через конструктор или параметры
class LLMStreamService:
    def __init__(
        self,
        llm_client: LLMClient,  # Интерфейс, не реализация
        event_publisher: EventPublisher,  # Интерфейс
        hitl_policy: HITLPolicy,  # Интерфейс
        hitl_manager: HITLManager,  # Интерфейс
        tool_registry: ToolRegistry  # Интерфейс
    ):
        self._llm_client = llm_client
        self._event_publisher = event_publisher
        self._hitl_policy = hitl_policy
        self._hitl_manager = hitl_manager
        self._tool_registry = tool_registry
    
    async def stream_response(
        self,
        session_id: str,
        history: List[dict],
        session_mgr: SessionManager,  # Обязательный параметр
        allowed_tools: Optional[List[str]] = None,
        correlation_id: Optional[str] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        # Использование инжектированных зависимостей
        tools = self._tool_registry.get_tools(allowed_tools)
        await self._event_publisher.publish(...)
```

---

## 3. Нарушение Interface Segregation Principle (ISP)

### Проблема: Слишком много параметров и опциональных зависимостей

```python
async def stream_response(
    session_id: str,
    history: List[dict],
    allowed_tools: Optional[List[str]] = None,  # Опциональный
    session_mgr: Optional["SessionManagerAdapter"] = None,  # Опциональный, но критичный!
    correlation_id: Optional[str] = None  # Опциональный
) -> AsyncGenerator[StreamChunk, None]:
```

### Проблемы:

1. **`session_mgr` опциональный, но критичный**:
   ```python
   if session_mgr is None:
       from app.main import session_manager_adapter as global_mgr
       session_mgr = global_mgr
       if session_mgr is None:
           raise RuntimeError("SessionManager adapter not initialized")
   ```
   - Если параметр критичный, он должен быть обязательным!

2. **Слишком много параметров** - признак нарушения SRP

### Правильный подход:

```python
# Вариант 1: Все критичные параметры обязательны
async def stream_response(
    session_id: str,
    history: List[dict],
    session_mgr: SessionManager,  # Обязательный!
    allowed_tools: Optional[List[str]] = None,
    correlation_id: Optional[str] = None
) -> AsyncGenerator[StreamChunk, None]:
    pass

# Вариант 2: Использовать объект конфигурации
@dataclass
class StreamConfig:
    session_id: str
    history: List[dict]
    session_mgr: SessionManager
    allowed_tools: Optional[List[str]] = None
    correlation_id: Optional[str] = None

async def stream_response(config: StreamConfig) -> AsyncGenerator[StreamChunk, None]:
    pass
```

---

## 4. Нарушение Open/Closed Principle (OCP)

### Проблема: Сложно расширять без модификации

Чтобы добавить новую функциональность (например, новый тип события или обработку нового типа ответа), нужно модифицировать функцию `stream_response()`.

**Примеры:**

1. **Добавление нового типа события** - нужно добавить код в функцию
2. **Изменение логики HITL** - нужно модифицировать середину функции
3. **Добавление нового типа tool call** - нужно изменять парсинг

### Правильный подход (Strategy Pattern):

```python
class LLMResponseHandler(ABC):
    @abstractmethod
    async def handle(self, response: LLMResponse) -> StreamChunk:
        pass

class ToolCallHandler(LLMResponseHandler):
    async def handle(self, response: LLMResponse) -> StreamChunk:
        # Обработка tool calls
        pass

class AssistantMessageHandler(LLMResponseHandler):
    async def handle(self, response: LLMResponse) -> StreamChunk:
        # Обработка обычных сообщений
        pass

class LLMStreamService:
    def __init__(self, handlers: List[LLMResponseHandler]):
        self._handlers = handlers
    
    async def stream_response(self, ...):
        response = await self._llm_client.chat_completion(...)
        
        # Найти подходящий handler
        for handler in self._handlers:
            if handler.can_handle(response):
                chunk = await handler.handle(response)
                yield chunk
                return
```

---

## 5. Нарушение Clean Architecture

### Проблема: Смешивание слоев

Функция находится в **Infrastructure Layer**, но содержит:

1. **Бизнес-логику** (должна быть в Domain Layer):
   ```python
   # Валидация бизнес-правил
   if len(tool_calls) > 1:
       logger.warning("LLM attempted to call multiple tools!")
   
   # HITL бизнес-логика
   requires_approval, reason = hitl_policy_service.requires_approval(tool_call.tool_name)
   ```

2. **Application Layer логику** (координация):
   ```python
   # Координация между сервисами
   await hitl_manager.add_pending(...)
   await event_bus.publish(...)
   await session_mgr.append_assistant_with_tool_calls(...)
   ```

3. **Infrastructure логику** (правильно):
   ```python
   # Вызов внешнего API
   response_data = await llm_proxy_client.chat_completion(...)
   ```

### Правильное разделение:

```
┌─────────────────────────────────────────────────────────┐
│                    API Layer                             │
│  - Принимает HTTP запрос                                 │
│  - Вызывает Application Layer handler                    │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│                Application Layer                         │
│  StreamLLMResponseHandler:                               │
│  - Координирует вызов LLM                                │
│  - Публикует события                                     │
│  - Сохраняет сообщения через domain service              │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│                  Domain Layer                            │
│  LLMResponseProcessor:                                   │
│  - Валидация tool calls (бизнес-правила)                │
│  - HITL policy проверка                                  │
│  - Создание доменных событий                             │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│               Infrastructure Layer                       │
│  LLMClient:                                              │
│  - Вызов LLM API                                         │
│  - Парсинг ответа                                        │
│  - Преобразование в доменные объекты                     │
└─────────────────────────────────────────────────────────┘
```

---

## 6. Рекомендации по рефакторингу

### 6.1 Разделить на отдельные классы (SRP)

```python
# 1. LLM Client (Infrastructure)
class LLMClient:
    async def chat_completion(
        self,
        model: str,
        messages: List[dict],
        tools: List[dict]
    ) -> LLMResponse:
        """Вызов LLM API и парсинг ответа"""
        pass

# 2. Tool Filter (Domain Service)
class ToolFilterService:
    def __init__(self, tool_registry: ToolRegistry):
        self._tool_registry = tool_registry
    
    def filter_tools(self, allowed_tools: Optional[List[str]]) -> List[dict]:
        """Фильтрация инструментов по разрешенным"""
        pass

# 3. LLM Response Processor (Domain Service)
class LLMResponseProcessor:
    def __init__(self, hitl_policy: HITLPolicy):
        self._hitl_policy = hitl_policy
    
    def process_response(self, response: LLMResponse) -> ProcessedResponse:
        """Обработка ответа LLM (валидация, HITL проверка)"""
        pass

# 4. Event Publisher Service (Infrastructure Adapter)
class LLMEventPublisher:
    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus
    
    async def publish_request_started(self, session_id: str, ...):
        """Публикация события начала запроса"""
        pass
    
    async def publish_request_completed(self, session_id: str, ...):
        """Публикация события завершения запроса"""
        pass

# 5. Stream Generator (Application Service)
class LLMStreamService:
    def __init__(
        self,
        llm_client: LLMClient,
        tool_filter: ToolFilterService,
        response_processor: LLMResponseProcessor,
        event_publisher: LLMEventPublisher,
        session_service: SessionManagementService,
        hitl_manager: HITLManager
    ):
        self._llm_client = llm_client
        self._tool_filter = tool_filter
        self._response_processor = response_processor
        self._event_publisher = event_publisher
        self._session_service = session_service
        self._hitl_manager = hitl_manager
    
    async def stream_response(
        self,
        session_id: str,
        history: List[dict],
        session_mgr: SessionManager,  # Обязательный!
        allowed_tools: Optional[List[str]] = None,
        correlation_id: Optional[str] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Генерация стрима ответа от LLM.
        
        Координирует:
        1. Фильтрацию инструментов
        2. Вызов LLM
        3. Обработку ответа
        4. Публикацию событий
        5. Сохранение сообщений
        6. Генерацию стрима
        """
        try:
            # 1. Фильтрация инструментов
            tools = self._tool_filter.filter_tools(allowed_tools)
            
            # 2. Публикация события начала
            await self._event_publisher.publish_request_started(
                session_id, len(history), len(tools), correlation_id
            )
            
            # 3. Вызов LLM
            response = await self._llm_client.chat_completion(
                model=AppConfig.LLM_MODEL,
                messages=history,
                tools=tools
            )
            
            # 4. Обработка ответа (валидация, HITL)
            processed = self._response_processor.process_response(response)
            
            # 5. Обработка tool calls
            if processed.has_tool_calls:
                yield await self._handle_tool_call(
                    session_id, processed, session_mgr, correlation_id
                )
                return
            
            # 6. Обработка обычного сообщения
            yield await self._handle_assistant_message(
                session_id, processed, session_mgr, correlation_id
            )
            
        except Exception as e:
            await self._event_publisher.publish_request_failed(
                session_id, str(e), correlation_id
            )
            yield StreamChunk(type="error", error=str(e), is_final=True)
    
    async def _handle_tool_call(
        self,
        session_id: str,
        processed: ProcessedResponse,
        session_mgr: SessionManager,
        correlation_id: Optional[str]
    ) -> StreamChunk:
        """Обработка tool call (выделено в отдельный метод)"""
        tool_call = processed.tool_calls[0]
        
        # HITL проверка
        if processed.requires_approval:
            await self._hitl_manager.add_pending(
                session_id=session_id,
                call_id=tool_call.id,
                tool_name=tool_call.tool_name,
                arguments=tool_call.arguments,
                reason=processed.approval_reason
            )
        
        # Сохранение сообщения
        await self._session_service.add_message(
            session_id=session_id,
            role="assistant",
            content="",
            tool_calls=[tool_call.to_dict()]
        )
        
        # Публикация события
        await self._event_publisher.publish_request_completed(
            session_id, has_tool_calls=True, correlation_id=correlation_id
        )
        
        # Генерация chunk
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
        session_mgr: SessionManager,
        correlation_id: Optional[str]
    ) -> StreamChunk:
        """Обработка обычного сообщения (выделено в отдельный метод)"""
        # Сохранение сообщения
        await self._session_service.add_message(
            session_id=session_id,
            role="assistant",
            content=processed.content
        )
        
        # Публикация события
        await self._event_publisher.publish_request_completed(
            session_id, has_tool_calls=False, correlation_id=correlation_id
        )
        
        # Генерация chunk
        return StreamChunk(
            type="assistant_message",
            content=processed.content,
            token=processed.content,
            is_final=True
        )
```

### 6.2 Использовать Dependency Injection

```python
# app/core/dependencies.py

async def get_llm_stream_service(
    llm_client: LLMClient = Depends(get_llm_client),
    tool_filter: ToolFilterService = Depends(get_tool_filter_service),
    response_processor: LLMResponseProcessor = Depends(get_response_processor),
    event_publisher: LLMEventPublisher = Depends(get_llm_event_publisher),
    session_service: SessionManagementService = Depends(get_session_management_service),
    hitl_manager: HITLManager = Depends(get_hitl_manager)
) -> LLMStreamService:
    return LLMStreamService(
        llm_client=llm_client,
        tool_filter=tool_filter,
        response_processor=response_processor,
        event_publisher=event_publisher,
        session_service=session_service,
        hitl_manager=hitl_manager
    )
```

### 6.3 Создать интерфейсы для зависимостей

```python
# app/domain/services/llm_service.py

class LLMClient(ABC):
    """Интерфейс для LLM клиента"""
    
    @abstractmethod
    async def chat_completion(
        self,
        model: str,
        messages: List[dict],
        tools: List[dict]
    ) -> LLMResponse:
        pass

class ToolRegistry(ABC):
    """Интерфейс для реестра инструментов"""
    
    @abstractmethod
    def get_all_tools(self) -> List[dict]:
        pass
    
    @abstractmethod
    def filter_tools(self, allowed: List[str]) -> List[dict]:
        pass

class EventPublisher(ABC):
    """Интерфейс для публикации событий"""
    
    @abstractmethod
    async def publish(self, event: DomainEvent) -> None:
        pass
```

---

## 7. Итоговая оценка и выводы

### 7.1 Критические проблемы

1. ❌ **Нарушение SRP**: Функция имеет 8+ ответственностей
2. ❌ **Нарушение DIP**: Прямые зависимости от конкретных реализаций
3. ❌ **Нарушение Clean Architecture**: Смешивание слоев
4. ❌ **Использование глобального состояния**: Импорт из `app.main`
5. ❌ **Сложность тестирования**: Невозможно unit-тестировать

### 7.2 Значительные проблемы

1. ⚠️ **Нарушение ISP**: Опциональные критичные параметры
2. ⚠️ **Нарушение OCP**: Сложно расширять без модификации
3. ⚠️ **Высокая связанность**: 10+ внешних зависимостей
4. ⚠️ **Длина функции**: 348 строк (рекомендуется < 50)

### 7.3 Рекомендации по приоритетам

#### Высокий приоритет (критично)

1. **Разделить на отдельные классы** согласно SRP
2. **Использовать Dependency Injection** вместо глобальных переменных
3. **Создать интерфейсы** для всех зависимостей (DIP)
4. **Убрать импорт из `app.main`** - это антипаттерн

#### Средний приоритет

1. Сделать `session_mgr` обязательным параметром
2. Выделить обработку tool calls в отдельный метод
3. Выделить обработку assistant message в отдельный метод
4. Создать `LLMEventPublisher` для публикации событий

#### Низкий приоритет

1. Использовать Strategy Pattern для обработки разных типов ответов
2. Добавить unit-тесты для каждого компонента
3. Документировать архитектурные решения

### 7.4 Итоговая оценка

**Оценка соответствия: 4/10** ❌

Функция `stream_response()` требует **значительного рефакторинга** для соответствия принципам Clean Architecture и SOLID. Текущая реализация работает, но имеет высокую техническую задолженность и будет сложна в поддержке и расширении.

---

## 8. План рефакторинга

### Этап 1: Выделение сервисов (1-2 дня)

1. Создать `LLMClient` интерфейс и реализацию
2. Создать `ToolFilterService`
3. Создать `LLMResponseProcessor`
4. Создать `LLMEventPublisher`

### Этап 2: Создание Application Service (1 день)

1. Создать `LLMStreamService` класс
2. Настроить Dependency Injection
3. Переместить логику из `stream_response()` в методы класса

### Этап 3: Тестирование (1-2 дня)

1. Написать unit-тесты для каждого сервиса
2. Написать integration тесты для `LLMStreamService`
3. Проверить обратную совместимость

### Этап 4: Миграция (1 день)

1. Обновить вызовы `stream_response()` в роутерах
2. Удалить старую функцию
3. Обновить документацию

**Общее время: 4-6 дней**

---

## Заключение

Метод [`stream_response()`](codelab-ai-service/agent-runtime/app/infrastructure/llm/streaming.py:40) является **техническим долгом** проекта и требует рефакторинга. Несмотря на то, что функция работает, она нарушает фундаментальные принципы проектирования и усложняет поддержку и развитие системы.

Рекомендуется **запланировать рефакторинг** в ближайшем спринте для улучшения качества кодовой базы и снижения технического долга.

---

**Подготовлено:** AI Architecture Auditor  
**Дата:** 24 января 2026  
**Версия документа:** 1.0
