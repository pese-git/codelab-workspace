# 🚀 Agent Runtime Refactoring — Фаза 7: LLM Context

**Дата начала:** 5 февраля 2026  
**Статус:** 🔄 В процессе  
**Предыдущая фаза:** [Фаза 6: Approval Context](AGENT_RUNTIME_PHASE_6_COMPLETION_REPORT.md)

---

## 📋 Обзор

**Цель:** Рефакторинг LLM Context с применением DDD паттернов для типобезопасной работы с LLM провайдерами.

**Текущее состояние:**
- [`LLMClient`](../codelab-ai-service/agent-runtime/app/infrastructure/llm/llm_client.py) — 275 строк, абстракция над LLM API
- [`LLMResponse`](../codelab-ai-service/agent-runtime/app/domain/entities/llm_response.py) — 266 строк, доменные сущности
- [`LLMResponseProcessor`](../codelab-ai-service/agent-runtime/app/domain/services/llm_response_processor.py) — 156 строк, обработка ответов

**Проблемы:**
1. **Примитивная обсессия** — Использование строк для model, provider
2. **Отсутствие Value Objects** — Нет типобезопасности для LLM концепций
3. **Смешивание concerns** — LLMResponse содержит и сырые данные, и бизнес-логику
4. **Нет Domain Events** — Невозможно отследить LLM взаимодействия
5. **Слабая валидация** — Минимальная проверка параметров запросов

---

## 🎯 Цели фазы

### 1. Типобезопасность
- ✅ Value Objects для всех LLM концепций
- ✅ Валидация на уровне типов
- ✅ Невозможность создать невалидное состояние

### 2. Разделение ответственностей
- ✅ Entities для доменной логики
- ✅ Value Objects для примитивов
- ✅ Domain Services для сложной логики
- ✅ Ports для абстракции инфраструктуры

### 3. Event-Driven Architecture
- ✅ Domain Events для всех LLM операций
- ✅ Трассировка запросов/ответов
- ✅ Аудит использования токенов

### 4. Тестируемость
- ✅ 100% покрытие unit тестами
- ✅ Изолированные компоненты
- ✅ Моки для внешних зависимостей

---

## 📦 Компоненты для создания

### Value Objects (6 файлов, ~600 строк)

#### 1. ModelName
**Файл:** `app/domain/llm_context/value_objects/model_name.py`  
**Размер:** ~100 строк

```python
class ModelName(ValueObject):
    """
    Value Object для имени LLM модели.
    
    Валидация:
    - Не пустое
    - Формат: provider/model или просто model
    - Известные провайдеры: openai, anthropic, google, etc.
    
    Примеры:
    - "gpt-4"
    - "claude-3-opus-20240229"
    - "openai/gpt-4-turbo"
    """
    value: str
    
    @staticmethod
    def from_string(value: str) -> "ModelName"
    
    def get_provider(self) -> Optional[str]
    def get_model(self) -> str
    def is_openai(self) -> bool
    def is_anthropic(self) -> bool
```

#### 2. PromptTemplate
**Файл:** `app/domain/llm_context/value_objects/prompt_template.py`  
**Размер:** ~120 строк

```python
class PromptTemplate(ValueObject):
    """
    Value Object для шаблона промпта.
    
    Валидация:
    - Не пустой
    - Валидные плейсхолдеры {variable}
    - Максимальная длина
    
    Методы:
    - render(variables: Dict) -> str
    - get_variables() -> List[str]
    - validate_variables(variables: Dict) -> bool
    """
    template: str
    max_length: int = 10000
    
    def render(self, variables: Dict[str, Any]) -> str
    def get_variables(self) -> List[str]
```

#### 3. TokenLimit
**Файл:** `app/domain/llm_context/value_objects/token_limit.py`  
**Размер:** ~100 строк

```python
class TokenLimit(ValueObject):
    """
    Value Object для лимита токенов.
    
    Валидация:
    - Положительное число
    - Не превышает максимум модели
    - Разумные значения (100-128000)
    """
    value: int
    
    @staticmethod
    def for_model(model: ModelName) -> "TokenLimit"
    
    def is_within_limit(self, usage: TokenUsage) -> bool
    def remaining(self, usage: TokenUsage) -> int
```

#### 4. Temperature
**Файл:** `app/domain/llm_context/value_objects/temperature.py`  
**Размер:** ~80 строк

```python
class Temperature(ValueObject):
    """
    Value Object для температуры генерации.
    
    Валидация:
    - Диапазон: 0.0 - 2.0
    - Рекомендуемые значения: 0.0, 0.7, 1.0
    """
    value: float
    
    @staticmethod
    def conservative() -> "Temperature"  # 0.0
    
    @staticmethod
    def balanced() -> "Temperature"  # 0.7
    
    @staticmethod
    def creative() -> "Temperature"  # 1.0
```

#### 5. LLMRequestId
**Файл:** `app/domain/llm_context/value_objects/llm_request_id.py`  
**Размер:** ~100 строк

```python
class LLMRequestId(ValueObject):
    """
    Value Object для ID LLM запроса.
    
    Валидация:
    - UUID формат
    - Уникальность
    """
    value: str
    
    @staticmethod
    def generate() -> "LLMRequestId"
    
    def __str__(self) -> str
    def __hash__(self) -> int
```

#### 6. FinishReason
**Файл:** `app/domain/llm_context/value_objects/finish_reason.py`  
**Размер:** ~100 строк

```python
class FinishReason(ValueObject):
    """
    Value Object для причины завершения генерации.
    
    Значения:
    - STOP: Нормальное завершение
    - LENGTH: Достигнут лимит токенов
    - TOOL_CALLS: Вызов инструментов
    - CONTENT_FILTER: Фильтр контента
    - ERROR: Ошибка
    """
    value: str
    
    @staticmethod
    def stop() -> "FinishReason"
    
    @staticmethod
    def length() -> "FinishReason"
    
    @staticmethod
    def tool_calls() -> "FinishReason"
    
    def is_normal(self) -> bool
    def is_error(self) -> bool
```

---

### Entities (2 файла, ~400 строк)

#### 1. LLMRequest
**Файл:** `app/domain/llm_context/entities/llm_request.py`  
**Размер:** ~200 строк

```python
class LLMRequest(BaseEntity):
    """
    Entity для LLM запроса.
    
    Атрибуты:
    - id: LLMRequestId
    - model: ModelName
    - messages: List[Dict]
    - tools: List[Dict]
    - temperature: Temperature
    - max_tokens: TokenLimit
    - created_at: datetime
    
    Методы:
    - validate() -> bool
    - estimate_tokens() -> int
    - to_api_format() -> Dict
    
    Events:
    - LLMRequestCreated
    - LLMRequestValidated
    """
    id: LLMRequestId
    model: ModelName
    messages: List[Dict[str, Any]]
    tools: List[Dict[str, Any]]
    temperature: Optional[Temperature]
    max_tokens: Optional[TokenLimit]
    created_at: datetime
    
    def validate(self) -> Tuple[bool, Optional[str]]
    def estimate_tokens(self) -> int
    def to_api_format(self) -> Dict[str, Any]
```

#### 2. LLMInteraction
**Файл:** `app/domain/llm_context/entities/llm_interaction.py`  
**Размер:** ~200 строк

```python
class LLMInteraction(BaseEntity):
    """
    Entity для полного цикла взаимодействия с LLM.
    
    Атрибуты:
    - id: LLMRequestId
    - request: LLMRequest
    - response: Optional[LLMResponse]
    - started_at: datetime
    - completed_at: Optional[datetime]
    - duration_ms: Optional[int]
    - error: Optional[str]
    
    Методы:
    - start() -> None
    - complete(response: LLMResponse) -> None
    - fail(error: str) -> None
    - get_duration() -> Optional[int]
    
    Events:
    - LLMInteractionStarted
    - LLMInteractionCompleted
    - LLMInteractionFailed
    """
    id: LLMRequestId
    request: LLMRequest
    response: Optional[LLMResponse]
    started_at: datetime
    completed_at: Optional[datetime]
    error: Optional[str]
    
    def start(self) -> None
    def complete(self, response: LLMResponse) -> None
    def fail(self, error: str) -> None
    def get_duration_ms(self) -> Optional[int]
```

---

### Domain Events (8 событий, ~300 строк)

**Файл:** `app/domain/llm_context/events/llm_events.py`

```python
# Request Events
class LLMRequestCreated(DomainEvent)
class LLMRequestValidated(DomainEvent)
class LLMRequestSent(DomainEvent)

# Response Events
class LLMResponseReceived(DomainEvent)
class LLMResponseProcessed(DomainEvent)

# Interaction Events
class LLMInteractionStarted(DomainEvent)
class LLMInteractionCompleted(DomainEvent)
class LLMInteractionFailed(DomainEvent)
```

---

### Domain Services (3 файла, ~500 строк)

#### 1. LLMRequestBuilder
**Файл:** `app/domain/llm_context/services/llm_request_builder.py`  
**Размер:** ~180 строк

```python
class LLMRequestBuilder:
    """
    Domain Service для построения LLM запросов.
    
    Методы:
    - build_chat_request() -> LLMRequest
    - build_tool_request() -> LLMRequest
    - validate_messages() -> bool
    - optimize_context() -> List[Dict]
    """
    
    def build_chat_request(
        self,
        model: ModelName,
        messages: List[Dict],
        temperature: Optional[Temperature] = None,
        max_tokens: Optional[TokenLimit] = None
    ) -> LLMRequest
    
    def build_tool_request(
        self,
        model: ModelName,
        messages: List[Dict],
        tools: List[Dict],
        temperature: Optional[Temperature] = None
    ) -> LLMRequest
```

#### 2. LLMResponseValidator
**Файл:** `app/domain/llm_context/services/llm_response_validator.py`  
**Размер:** ~160 строк

```python
class LLMResponseValidator:
    """
    Domain Service для валидации LLM ответов.
    
    Методы:
    - validate_response() -> Tuple[bool, List[str]]
    - validate_tool_calls() -> Tuple[bool, List[str]]
    - validate_content() -> Tuple[bool, Optional[str]]
    - check_token_usage() -> bool
    """
    
    def validate_response(
        self,
        response: LLMResponse
    ) -> Tuple[bool, List[str]]
    
    def validate_tool_calls(
        self,
        tool_calls: List[ToolCall]
    ) -> Tuple[bool, List[str]]
```

#### 3. TokenEstimator
**Файл:** `app/domain/llm_context/services/token_estimator.py`  
**Размер:** ~160 строк

```python
class TokenEstimator:
    """
    Domain Service для оценки использования токенов.
    
    Методы:
    - estimate_messages() -> int
    - estimate_tools() -> int
    - estimate_total() -> int
    - will_exceed_limit() -> bool
    """
    
    def estimate_messages(
        self,
        messages: List[Dict],
        model: ModelName
    ) -> int
    
    def estimate_tools(
        self,
        tools: List[Dict]
    ) -> int
    
    def will_exceed_limit(
        self,
        request: LLMRequest,
        limit: TokenLimit
    ) -> bool
```

---

### Ports (2 файла, ~200 строк)

#### 1. ILLMProvider
**Файл:** `app/domain/llm_context/ports/llm_provider.py`  
**Размер:** ~120 строк

```python
class ILLMProvider(ABC):
    """
    Port для LLM провайдера.
    
    Абстракция над конкретными реализациями (OpenAI, Anthropic, etc.)
    """
    
    @abstractmethod
    async def chat_completion(
        self,
        request: LLMRequest
    ) -> LLMResponse:
        """Выполнить chat completion"""
        pass
    
    @abstractmethod
    async def validate_model(
        self,
        model: ModelName
    ) -> bool:
        """Проверить доступность модели"""
        pass
    
    @abstractmethod
    async def get_model_info(
        self,
        model: ModelName
    ) -> Dict[str, Any]:
        """Получить информацию о модели"""
        pass
```

#### 2. ITokenCounter
**Файл:** `app/domain/llm_context/ports/token_counter.py`  
**Размер:** ~80 строк

```python
class ITokenCounter(ABC):
    """
    Port для подсчета токенов.
    
    Абстракция над tiktoken, anthropic tokenizer, etc.
    """
    
    @abstractmethod
    def count_tokens(
        self,
        text: str,
        model: ModelName
    ) -> int:
        """Подсчитать токены в тексте"""
        pass
    
    @abstractmethod
    def count_messages(
        self,
        messages: List[Dict],
        model: ModelName
    ) -> int:
        """Подсчитать токены в сообщениях"""
        pass
```

---

## 🧪 Unit Tests

### Структура тестов

```
tests/unit/domain/llm_context/
├── __init__.py
├── test_value_objects.py          # ~400 строк, 40+ тестов
├── test_entities.py                # ~300 строк, 25+ тестов
└── test_services.py                # ~350 строк, 30+ тестов
```

### Покрытие

| Компонент | Тесты | Покрытие |
|-----------|-------|----------|
| Value Objects | 40+ | 100% |
| Entities | 25+ | 100% |
| Domain Services | 30+ | 100% |
| **Всего** | **95+** | **100%** |

---

## 📊 Метрики улучшений

### До рефакторинга

| Метрика | Значение |
|---------|----------|
| Типобезопасность | Примитивы (str, int) |
| Валидация | Минимальная |
| Domain Events | 0 |
| Покрытие тестами | ~60% |
| Цикломатическая сложность | 8-12 |

### После рефакторинга

| Метрика | Значение | Улучшение |
|---------|----------|-----------|
| Типобезопасность | Value Objects | +100% |
| Валидация | Полная на уровне типов | +100% |
| Domain Events | 8 событий | +∞ |
| Покрытие тестами | 100% (95+ тестов) | +40% |
| Цикломатическая сложность | 3-5 | -60% |

---

## 🗂️ Структура файлов

```
app/domain/llm_context/
├── __init__.py
├── value_objects/
│   ├── __init__.py
│   ├── model_name.py              # ~100 строк
│   ├── prompt_template.py         # ~120 строк
│   ├── token_limit.py             # ~100 строк
│   ├── temperature.py             # ~80 строк
│   ├── llm_request_id.py          # ~100 строк
│   └── finish_reason.py           # ~100 строк
├── entities/
│   ├── __init__.py
│   ├── llm_request.py             # ~200 строк
│   └── llm_interaction.py         # ~200 строк
├── events/
│   ├── __init__.py
│   └── llm_events.py              # ~300 строк
├── services/
│   ├── __init__.py
│   ├── llm_request_builder.py    # ~180 строк
│   ├── llm_response_validator.py # ~160 строк
│   └── token_estimator.py        # ~160 строк
└── ports/
    ├── __init__.py
    ├── llm_provider.py            # ~120 строк
    └── token_counter.py           # ~80 строк

tests/unit/domain/llm_context/
├── __init__.py
├── test_value_objects.py          # ~400 строк
├── test_entities.py               # ~300 строк
└── test_services.py               # ~350 строк
```

**Всего:** 21 файл, ~3,050 строк кода

---

## 🎯 План выполнения

### Шаг 1: Value Objects (2 часа)
- [x] Создать структуру директорий
- [ ] ModelName
- [ ] PromptTemplate
- [ ] TokenLimit
- [ ] Temperature
- [ ] LLMRequestId
- [ ] FinishReason

### Шаг 2: Entities (1 час)
- [ ] LLMRequest
- [ ] LLMInteraction

### Шаг 3: Domain Events (30 мин)
- [ ] 8 событий в llm_events.py

### Шаг 4: Domain Services (1.5 часа)
- [ ] LLMRequestBuilder
- [ ] LLMResponseValidator
- [ ] TokenEstimator

### Шаг 5: Ports (30 мин)
- [ ] ILLMProvider
- [ ] ITokenCounter

### Шаг 6: Unit Tests (2 часа)
- [ ] test_value_objects.py (40+ тестов)
- [ ] test_entities.py (25+ тестов)
- [ ] test_services.py (30+ тестов)

### Шаг 7: Документация (30 мин)
- [ ] AGENT_RUNTIME_PHASE_7_SUMMARY.md
- [ ] AGENT_RUNTIME_PHASE_7_COMPLETION_REPORT.md
- [ ] Обновить AGENT_RUNTIME_REFACTORING_PROGRESS.md

**Общее время:** ~8 часов

---

## 🔄 Интеграция с другими контекстами

### Session Context
- LLMRequest использует ConversationId для связи с сессией
- LLMInteraction отслеживает запросы в рамках сессии

### Agent Context
- ModelName зависит от AgentType (разные модели для разных агентов)
- Temperature настраивается по типу агента

### Approval Context
- LLMRequest может требовать approval для дорогих моделей
- TokenLimit проверяется через ApprovalPolicy

### Execution Context
- LLMInteraction связана с SubtaskId
- Токены учитываются в метриках выполнения

---

## ✅ Критерии завершения

- [x] Все Value Objects созданы и протестированы
- [ ] Все Entities созданы и протестированы
- [ ] Все Domain Events определены
- [ ] Все Domain Services реализованы
- [ ] Все Ports определены
- [ ] 100% покрытие unit тестами (95+ тестов)
- [ ] Документация завершена
- [ ] Код прошел review

---

## 📝 Заметки

### Ключевые решения

1. **ModelName как Value Object** — Типобезопасность для моделей
2. **Temperature с фабричными методами** — Удобство использования
3. **LLMInteraction для трассировки** — Полный аудит взаимодействий
4. **Ports для абстракции** — Независимость от конкретных провайдеров

### Риски

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| Сложность миграции | Средняя | Адаптеры для старого кода |
| Производительность | Низкая | Value Objects легковесные |
| Обратная совместимость | Низкая | Сохранение старых интерфейсов |

---

**Автор:** Sergey Penkovsky  
**Дата создания:** 5 февраля 2026, 14:37 MSK
