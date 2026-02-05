# 🚀 Agent Runtime Refactoring — Фаза 8: Tool Context

**Дата начала:** 5 февраля 2026  
**Статус:** 🔄 В процессе  
**Предыдущая фаза:** [Фаза 7: LLM Context](AGENT_RUNTIME_PHASE_7_COMPLETION_REPORT.md)

---

## 📋 Обзор

**Цель:** Рефакторинг Tool Context с применением DDD паттернов для типобезопасной работы с инструментами.

**Текущее состояние:**
- [`ToolRegistry`](../codelab-ai-service/agent-runtime/app/domain/services/tool_registry.py) — 456 строк, реестр инструментов
- [`ToolFilterService`](../codelab-ai-service/agent-runtime/app/domain/services/tool_filter_service.py) — 198 строк, фильтрация инструментов
- [`ToolCall`](../codelab-ai-service/agent-runtime/app/domain/entities/llm_response.py) — часть LLMResponse, 49 строк
- [`execute_local_tool`](../codelab-ai-service/agent-runtime/app/domain/services/tool_registry.py) — функция выполнения локальных инструментов

**Проблемы:**
1. **Примитивная обсессия** — Использование строк для tool_name, call_id
2. **Отсутствие Value Objects** — Нет типобезопасности для Tool концепций
3. **Смешивание concerns** — ToolRegistry содержит и спецификации, и выполнение
4. **Нет Domain Events** — Невозможно отследить выполнение инструментов
5. **Слабая валидация** — Минимальная проверка параметров инструментов
6. **ToolCall в LLMResponse** — Должен быть в Tool Context

---

## 🎯 Цели фазы

### 1. Типобезопасность
- ✅ Value Objects для всех Tool концепций
- ✅ Валидация на уровне типов
- ✅ Невозможность создать невалидное состояние

### 2. Разделение ответственностей
- ✅ Entities для доменной логики
- ✅ Value Objects для примитивов
- ✅ Domain Services для сложной логики
- ✅ Ports для абстракции выполнения

### 3. Event-Driven Architecture
- ✅ Domain Events для всех Tool операций
- ✅ Трассировка выполнения инструментов
- ✅ Аудит результатов

### 4. Тестируемость
- ✅ 100% покрытие unit тестами
- ✅ Изолированные компоненты
- ✅ Моки для внешних зависимостей

---

## 📦 Компоненты для создания

### Value Objects (7 файлов, ~850 строк)

#### 1. ToolName
**Файл:** `app/domain/tool_context/value_objects/tool_name.py`  
**Размер:** ~120 строк

```python
class ToolName(ValueObject):
    """
    Value Object для имени инструмента.
    
    Валидация:
    - Не пустое
    - Формат: snake_case
    - Длина: 1-100 символов
    - Только буквы, цифры, подчеркивания
    
    Примеры:
    - "read_file"
    - "write_file"
    - "execute_command"
    - "switch_mode"
    """
    value: str
    
    @staticmethod
    def from_string(value: str) -> "ToolName"
    
    def is_local_tool(self) -> bool
    def is_ide_tool(self) -> bool
    def __str__(self) -> str
```

#### 2. ToolCallId
**Файл:** `app/domain/tool_context/value_objects/tool_call_id.py`  
**Размер:** ~100 строк

```python
class ToolCallId(ValueObject):
    """
    Value Object для ID вызова инструмента.
    
    Валидация:
    - Не пустое
    - Формат: call_xxx или UUID
    - Уникальность
    """
    value: str
    
    @staticmethod
    def generate() -> "ToolCallId"
    
    @staticmethod
    def from_string(value: str) -> "ToolCallId"
    
    def __str__(self) -> str
    def __hash__(self) -> int
```

#### 3. ToolArguments
**Файл:** `app/domain/tool_context/value_objects/tool_arguments.py`  
**Размер:** ~150 строк

```python
class ToolArguments(ValueObject):
    """
    Value Object для аргументов инструмента.
    
    Валидация:
    - Валидный JSON
    - Соответствие схеме инструмента
    - Максимальный размер
    
    Методы:
    - validate_against_schema(schema: Dict) -> bool
    - get(key: str) -> Any
    - has(key: str) -> bool
    """
    arguments: Dict[str, Any]
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "ToolArguments"
    
    @staticmethod
    def from_json(json_str: str) -> "ToolArguments"
    
    def validate_against_schema(self, schema: Dict) -> Tuple[bool, Optional[str]]
    def get(self, key: str, default: Any = None) -> Any
    def has(self, key: str) -> bool
    def to_dict(self) -> Dict[str, Any]
```

#### 4. ToolResult
**Файл:** `app/domain/tool_context/value_objects/tool_result.py`  
**Размер:** ~150 строк

```python
class ToolResult(ValueObject):
    """
    Value Object для результата выполнения инструмента.
    
    Атрибуты:
    - content: str — Результат выполнения
    - is_error: bool — Флаг ошибки
    - metadata: Dict — Дополнительные данные
    
    Методы:
    - success(content: str) -> ToolResult
    - error(message: str) -> ToolResult
    - is_success() -> bool
    """
    content: str
    is_error: bool
    metadata: Dict[str, Any]
    
    @staticmethod
    def success(content: str, metadata: Optional[Dict] = None) -> "ToolResult"
    
    @staticmethod
    def error(message: str, metadata: Optional[Dict] = None) -> "ToolResult"
    
    def is_success(self) -> bool
    def get_content(self) -> str
```

#### 5. ToolCategory
**Файл:** `app/domain/tool_context/value_objects/tool_category.py`  
**Размер:** ~120 строк

```python
class ToolCategory(ValueObject):
    """
    Value Object для категории инструмента.
    
    Категории:
    - FILE_SYSTEM: read_file, write_file, list_files
    - COMMAND: execute_command
    - SEARCH: search_in_code
    - AGENT: switch_mode
    - UTILITY: echo, calculator
    """
    value: str
    
    @staticmethod
    def file_system() -> "ToolCategory"
    
    @staticmethod
    def command() -> "ToolCategory"
    
    @staticmethod
    def search() -> "ToolCategory"
    
    @staticmethod
    def agent() -> "ToolCategory"
    
    @staticmethod
    def utility() -> "ToolCategory"
    
    def is_dangerous(self) -> bool
    def requires_approval(self) -> bool
```

#### 6. ToolExecutionMode
**Файл:** `app/domain/tool_context/value_objects/tool_execution_mode.py`  
**Размер:** ~100 строк

```python
class ToolExecutionMode(ValueObject):
    """
    Value Object для режима выполнения инструмента.
    
    Режимы:
    - LOCAL: Выполняется в agent-runtime
    - IDE: Выполняется на стороне IDE
    - REMOTE: Выполняется на удаленном сервере
    """
    value: str
    
    @staticmethod
    def local() -> "ToolExecutionMode"
    
    @staticmethod
    def ide() -> "ToolExecutionMode"
    
    @staticmethod
    def remote() -> "ToolExecutionMode"
    
    def is_local(self) -> bool
    def is_ide(self) -> bool
```

#### 7. ToolPermission
**Файл:** `app/domain/tool_context/value_objects/tool_permission.py`  
**Размер:** ~110 строк

```python
class ToolPermission(ValueObject):
    """
    Value Object для прав доступа к инструменту.
    
    Уровни:
    - READ_ONLY: Только чтение
    - READ_WRITE: Чтение и запись
    - EXECUTE: Выполнение команд
    - ADMIN: Административные операции
    """
    level: str
    
    @staticmethod
    def read_only() -> "ToolPermission"
    
    @staticmethod
    def read_write() -> "ToolPermission"
    
    @staticmethod
    def execute() -> "ToolPermission"
    
    @staticmethod
    def admin() -> "ToolPermission"
    
    def allows(self, required: "ToolPermission") -> bool
```

---

### Entities (3 файла, ~550 строк)

#### 1. ToolCall
**Файл:** `app/domain/tool_context/entities/tool_call.py`  
**Размер:** ~200 строк

```python
class ToolCall(BaseEntity):
    """
    Entity для вызова инструмента.
    
    Атрибуты:
    - id: ToolCallId
    - tool_name: ToolName
    - arguments: ToolArguments
    - created_at: datetime
    - requires_approval: bool
    
    Методы:
    - validate() -> Tuple[bool, Optional[str]]
    - to_llm_format() -> Dict
    - mark_approved() -> None
    
    Events:
    - ToolCallCreated
    - ToolCallValidated
    - ToolCallApproved
    """
    id: ToolCallId
    tool_name: ToolName
    arguments: ToolArguments
    created_at: datetime
    requires_approval: bool
    approved: bool
    
    def validate(self, tool_spec: "ToolSpecification") -> Tuple[bool, Optional[str]]
    def to_llm_format(self) -> Dict[str, Any]
    def mark_approved(self) -> None
```

#### 2. ToolSpecification
**Файл:** `app/domain/tool_context/entities/tool_specification.py`  
**Размер:** ~250 строк

```python
class ToolSpecification(BaseEntity):
    """
    Entity для спецификации инструмента.
    
    Атрибуты:
    - name: ToolName
    - description: str
    - parameters: Dict (JSON Schema)
    - category: ToolCategory
    - execution_mode: ToolExecutionMode
    - required_permission: ToolPermission
    
    Методы:
    - validate_arguments(args: ToolArguments) -> bool
    - to_openai_format() -> Dict
    - is_dangerous() -> bool
    
    Events:
    - ToolSpecificationCreated
    - ToolSpecificationUpdated
    """
    name: ToolName
    description: str
    parameters: Dict[str, Any]
    category: ToolCategory
    execution_mode: ToolExecutionMode
    required_permission: ToolPermission
    
    def validate_arguments(self, args: ToolArguments) -> Tuple[bool, Optional[str]]
    def to_openai_format(self) -> Dict[str, Any]
    def is_dangerous(self) -> bool
    def requires_approval(self) -> bool
```

#### 3. ToolExecution
**Файл:** `app/domain/tool_context/entities/tool_execution.py`  
**Размер:** ~200 строк

```python
class ToolExecution(BaseEntity):
    """
    Entity для выполнения инструмента.
    
    Атрибуты:
    - id: ToolCallId
    - tool_call: ToolCall
    - result: Optional[ToolResult]
    - started_at: datetime
    - completed_at: Optional[datetime]
    - duration_ms: Optional[int]
    - error: Optional[str]
    
    Методы:
    - start() -> None
    - complete(result: ToolResult) -> None
    - fail(error: str) -> None
    - get_duration_ms() -> Optional[int]
    
    Events:
    - ToolExecutionStarted
    - ToolExecutionCompleted
    - ToolExecutionFailed
    """
    id: ToolCallId
    tool_call: ToolCall
    result: Optional[ToolResult]
    started_at: datetime
    completed_at: Optional[datetime]
    error: Optional[str]
    
    def start(self) -> None
    def complete(self, result: ToolResult) -> None
    def fail(self, error: str) -> None
    def get_duration_ms(self) -> Optional[int]
```

---

### Domain Events (10 событий, ~350 строк)

**Файл:** `app/domain/tool_context/events/tool_events.py`

```python
# ToolCall Events
class ToolCallCreated(DomainEvent)
class ToolCallValidated(DomainEvent)
class ToolCallApproved(DomainEvent)
class ToolCallRejected(DomainEvent)

# ToolExecution Events
class ToolExecutionStarted(DomainEvent)
class ToolExecutionCompleted(DomainEvent)
class ToolExecutionFailed(DomainEvent)

# ToolSpecification Events
class ToolSpecificationCreated(DomainEvent)
class ToolSpecificationUpdated(DomainEvent)
class ToolSpecificationRemoved(DomainEvent)
```

---

### Domain Services (4 файла, ~650 строк)

#### 1. ToolValidator
**Файл:** `app/domain/tool_context/services/tool_validator.py`  
**Размер:** ~180 строк

```python
class ToolValidator:
    """
    Domain Service для валидации инструментов.
    
    Методы:
    - validate_tool_call(tool_call: ToolCall, spec: ToolSpecification) -> Tuple[bool, Optional[str]]
    - validate_arguments(args: ToolArguments, schema: Dict) -> Tuple[bool, List[str]]
    - validate_permissions(tool: ToolSpecification, permission: ToolPermission) -> bool
    """
    
    def validate_tool_call(
        self,
        tool_call: ToolCall,
        spec: ToolSpecification
    ) -> Tuple[bool, Optional[str]]
    
    def validate_arguments(
        self,
        args: ToolArguments,
        schema: Dict[str, Any]
    ) -> Tuple[bool, List[str]]
    
    def validate_permissions(
        self,
        tool: ToolSpecification,
        permission: ToolPermission
    ) -> bool
```

#### 2. ToolRegistry
**Файл:** `app/domain/tool_context/services/tool_registry.py`  
**Размер:** ~200 строк

```python
class ToolRegistry:
    """
    Domain Service для управления реестром инструментов.
    
    Методы:
    - register_tool(spec: ToolSpecification) -> None
    - get_tool(name: ToolName) -> Optional[ToolSpecification]
    - get_all_tools() -> List[ToolSpecification]
    - filter_by_category(category: ToolCategory) -> List[ToolSpecification]
    - filter_by_permission(permission: ToolPermission) -> List[ToolSpecification]
    """
    
    def register_tool(self, spec: ToolSpecification) -> None
    def get_tool(self, name: ToolName) -> Optional[ToolSpecification]
    def get_all_tools(self) -> List[ToolSpecification]
    def filter_by_category(self, category: ToolCategory) -> List[ToolSpecification]
    def filter_by_permission(self, permission: ToolPermission) -> List[ToolSpecification]
```

#### 3. ToolFilterService
**Файл:** `app/domain/tool_context/services/tool_filter_service.py`  
**Размер:** ~150 строк

```python
class ToolFilterService:
    """
    Domain Service для фильтрации инструментов.
    
    Методы:
    - filter_for_agent(agent_type: AgentType) -> List[ToolSpecification]
    - filter_by_allowed_list(allowed: List[ToolName]) -> List[ToolSpecification]
    - is_tool_allowed(tool: ToolName, allowed: List[ToolName]) -> bool
    """
    
    def __init__(self, registry: ToolRegistry)
    
    def filter_for_agent(
        self,
        agent_type: AgentType
    ) -> List[ToolSpecification]
    
    def filter_by_allowed_list(
        self,
        allowed: List[ToolName]
    ) -> List[ToolSpecification]
    
    def is_tool_allowed(
        self,
        tool: ToolName,
        allowed: List[ToolName]
    ) -> bool
```

#### 4. ToolExecutor
**Файл:** `app/domain/tool_context/services/tool_executor.py`  
**Размер:** ~120 строк

```python
class ToolExecutor:
    """
    Domain Service для координации выполнения инструментов.
    
    Методы:
    - execute(tool_call: ToolCall) -> ToolExecution
    - can_execute_locally(tool: ToolName) -> bool
    - requires_approval(tool_call: ToolCall) -> bool
    """
    
    def __init__(
        self,
        registry: ToolRegistry,
        local_executor: ILocalToolExecutor,
        ide_executor: IIDEToolExecutor
    )
    
    async def execute(
        self,
        tool_call: ToolCall
    ) -> ToolExecution
    
    def can_execute_locally(self, tool: ToolName) -> bool
    def requires_approval(self, tool_call: ToolCall) -> bool
```

---

### Ports (2 файла, ~200 строк)

#### 1. ILocalToolExecutor
**Файл:** `app/domain/tool_context/ports/local_tool_executor.py`  
**Размер:** ~100 строк

```python
class ILocalToolExecutor(ABC):
    """
    Port для выполнения локальных инструментов.
    
    Локальные инструменты выполняются в agent-runtime:
    - echo
    - calculator
    - switch_mode
    """
    
    @abstractmethod
    async def execute(
        self,
        tool_call: ToolCall
    ) -> ToolResult:
        """Выполнить локальный инструмент"""
        pass
    
    @abstractmethod
    def supports(self, tool_name: ToolName) -> bool:
        """Проверить поддержку инструмента"""
        pass
```

#### 2. IIDEToolExecutor
**Файл:** `app/domain/tool_context/ports/ide_tool_executor.py`  
**Размер:** ~100 строк

```python
class IIDEToolExecutor(ABC):
    """
    Port для выполнения инструментов на стороне IDE.
    
    IDE инструменты выполняются через WebSocket:
    - read_file
    - write_file
    - execute_command
    - search_in_code
    - list_files
    """
    
    @abstractmethod
    async def execute(
        self,
        tool_call: ToolCall
    ) -> ToolResult:
        """Выполнить IDE инструмент"""
        pass
    
    @abstractmethod
    async def is_available(self) -> bool:
        """Проверить доступность IDE"""
        pass
```

---

## 🧪 Unit Tests

### Структура тестов

```
tests/unit/domain/tool_context/
├── __init__.py
├── test_value_objects.py          # ~500 строк, 50+ тестов
├── test_entities.py                # ~400 строк, 35+ тестов
└── test_services.py                # ~450 строк, 40+ тестов
```

### Покрытие

| Компонент | Тесты | Покрытие |
|-----------|-------|----------|
| Value Objects | 50+ | 100% |
| Entities | 35+ | 100% |
| Domain Services | 40+ | 100% |
| **Всего** | **125+** | **100%** |

---

## 📊 Метрики улучшений

### До рефакторинга

| Метрика | Значение |
|---------|----------|
| Типобезопасность | Примитивы (str, dict) |
| Валидация | Минимальная |
| Domain Events | 0 |
| Покрытие тестами | ~50% |
| Цикломатическая сложность | 8-12 |
| ToolCall в | LLMResponse (неправильно) |

### После рефакторинга

| Метрика | Значение | Улучшение |
|---------|----------|-----------|
| Типобезопасность | Value Objects | +100% |
| Валидация | Полная на уровне типов | +100% |
| Domain Events | 10 событий | +∞ |
| Покрытие тестами | 100% (125+ тестов) | +50% |
| Цикломатическая сложность | 3-5 | -60% |
| ToolCall в | Tool Context (правильно) | ✅ |

---

## 🗂️ Структура файлов

```
app/domain/tool_context/
├── __init__.py
├── value_objects/
│   ├── __init__.py
│   ├── tool_name.py                # ~120 строк
│   ├── tool_call_id.py             # ~100 строк
│   ├── tool_arguments.py           # ~150 строк
│   ├── tool_result.py              # ~150 строк
│   ├── tool_category.py            # ~120 строк
│   ├── tool_execution_mode.py      # ~100 строк
│   └── tool_permission.py          # ~110 строк
├── entities/
│   ├── __init__.py
│   ├── tool_call.py                # ~200 строк
│   ├── tool_specification.py       # ~250 строк
│   └── tool_execution.py           # ~200 строк
├── events/
│   ├── __init__.py
│   └── tool_events.py              # ~350 строк
├── services/
│   ├── __init__.py
│   ├── tool_validator.py           # ~180 строк
│   ├── tool_registry.py            # ~200 строк
│   ├── tool_filter_service.py      # ~150 строк
│   └── tool_executor.py            # ~120 строк
└── ports/
    ├── __init__.py
    ├── local_tool_executor.py      # ~100 строк
    └── ide_tool_executor.py        # ~100 строк

tests/unit/domain/tool_context/
├── __init__.py
├── test_value_objects.py           # ~500 строк
├── test_entities.py                # ~400 строк
└── test_services.py                # ~450 строк
```

**Всего:** 24 файла, ~3,700 строк кода

---

## 🎯 План выполнения

### Шаг 1: Value Objects (2.5 часа)
- [ ] Создать структуру директорий
- [ ] ToolName
- [ ] ToolCallId
- [ ] ToolArguments
- [ ] ToolResult
- [ ] ToolCategory
- [ ] ToolExecutionMode
- [ ] ToolPermission

### Шаг 2: Entities (1.5 часа)
- [ ] ToolCall
- [ ] ToolSpecification
- [ ] ToolExecution

### Шаг 3: Domain Events (30 мин)
- [ ] 10 событий в tool_events.py

### Шаг 4: Domain Services (2 часа)
- [ ] ToolValidator
- [ ] ToolRegistry (рефакторинг)
- [ ] ToolFilterService (рефакторинг)
- [ ] ToolExecutor

### Шаг 5: Ports (30 мин)
- [ ] ILocalToolExecutor
- [ ] IIDEToolExecutor

### Шаг 6: Unit Tests (3 часа)
- [ ] test_value_objects.py (50+ тестов)
- [ ] test_entities.py (35+ тестов)
- [ ] test_services.py (40+ тестов)

### Шаг 7: Документация (30 мин)
- [ ] AGENT_RUNTIME_PHASE_8_COMPLETION_REPORT.md
- [ ] Обновить AGENT_RUNTIME_REFACTORING_PROGRESS.md

**Общее время:** ~10.5 часов

---

## 🔄 Интеграция с другими контекстами

### LLM Context
- ToolCall перемещается из LLMResponse в Tool Context
- LLMRequest использует ToolSpecification для tools параметра

### Session Context
- ToolExecution связана с ConversationId
- История выполнения инструментов в сессии

### Agent Context
- ToolFilterService использует AgentCapabilities
- Разные агенты имеют доступ к разным инструментам

### Approval Context
- ToolCall может требовать approval
- ToolCategory определяет необходимость одобрения

### Execution Context
- ToolExecution связана с SubtaskId
- Инструменты выполняются в контексте плана

---

## ✅ Критерии завершения

- [ ] Все Value Objects созданы и протестированы
- [ ] Все Entities созданы и протестированы
- [ ] Все Domain Events определены
- [ ] Все Domain Services реализованы
- [ ] Все Ports определены
- [ ] 100% покрытие unit тестами (125+ тестов)
- [ ] ToolCall перемещен из LLMResponse в Tool Context
- [ ] Документация завершена
- [ ] Код прошел review

---

## 📝 Заметки

### Ключевые решения

1. **ToolCall как Entity** — Полноценная доменная сущность, а не Value Object
2. **ToolSpecification для метаданных** — Отделение спецификации от вызова
3. **ToolExecution для трассировки** — Полный аудит выполнения
4. **Ports для абстракции** — Независимость от способа выполнения

### Важные изменения

1. **ToolCall перемещается** — Из `app/domain/entities/llm_response.py` в `app/domain/tool_context/entities/tool_call.py`
2. **ToolRegistry рефакторится** — Становится Domain Service с ToolSpecification
3. **ToolFilterService обновляется** — Использует новые Value Objects

### Риски

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| Breaking changes в ToolCall | Высокая | Адаптеры для обратной совместимости |
| Сложность миграции | Средняя | Постепенная миграция с Strangler Fig |
| Производительность | Низкая | Value Objects легковесные |

---

**Автор:** Sergey Penkovsky  
**Дата создания:** 5 февраля 2026, 16:15 MSK
