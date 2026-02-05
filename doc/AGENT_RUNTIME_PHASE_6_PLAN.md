# Фаза 6: Approval Context — План рефакторинга

**Дата начала:** 2026-02-05  
**Статус:** 🚀 Готов к выполнению  
**Предыдущая фаза:** ✅ Фаза 5 завершена (100%)

## 📋 Цели Фазы 6

Рефакторинг **Approval Context** для управления утверждениями и HITL (Human-in-the-Loop) политиками.

### Основные задачи

1. Создать Value Objects для Approval Context
2. Рефакторить ApprovalRequest entity
3. Создать ApprovalService
4. Обновить HITLPolicyService
5. Создать Repository interface
6. Написать unit тесты

## 🎯 Scope

### Текущие компоненты для рефакторинга

**Entities:**
- `ApprovalRequest` — запрос на утверждение
- `HITLPolicy` — политика HITL
- `HITLPolicyRule` — правило политики
- `PendingApprovalState` — состояние ожидающего утверждения

**Services:**
- `HITLPolicyService` — управление политиками HITL
- `ApprovalService` — обработка утверждений

**Repositories:**
- Нужно создать `ApprovalRepository` interface

## 📦 Планируемая структура

```
approval_context/
├── value_objects/
│   ├── __init__.py
│   ├── approval_id.py          # Typed ID для утверждения
│   ├── approval_status.py      # Статус утверждения
│   ├── approval_type.py        # Тип утверждения (tool, plan, etc.)
│   └── policy_action.py        # Действие политики (approve, reject, ask)
├── entities/
│   ├── __init__.py
│   ├── approval_request.py     # Рефакторенный запрос
│   ├── hitl_policy.py          # Рефакторенная политика
│   └── policy_rule.py          # Рефакторенное правило
├── events/
│   ├── __init__.py
│   └── approval_events.py      # События утверждений
├── repositories/
│   ├── __init__.py
│   └── approval_repository.py  # Interface
├── services/
│   ├── __init__.py
│   ├── approval_service.py     # Обработка утверждений
│   └── hitl_policy_service.py  # Управление политиками
└── __init__.py
```

## 🔨 Компоненты для создания

### Value Objects (4 файла, ~400 строк)

#### 1. ApprovalId
```python
class ApprovalId(ValueObject):
    """Typed ID для утверждения."""
    value: str
    
    def __init__(self, value: str):
        if not value or not value.strip():
            raise ValueError("Approval ID cannot be empty")
        self._value = value
```

#### 2. ApprovalStatus
```python
class ApprovalStatusEnum(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"

class ApprovalStatus(ValueObject):
    """Статус утверждения с валидацией переходов."""
    
    _VALID_TRANSITIONS = {
        ApprovalStatusEnum.PENDING: {
            ApprovalStatusEnum.APPROVED,
            ApprovalStatusEnum.REJECTED,
            ApprovalStatusEnum.EXPIRED
        },
        ApprovalStatusEnum.APPROVED: set(),  # Terminal
        ApprovalStatusEnum.REJECTED: set(),  # Terminal
        ApprovalStatusEnum.EXPIRED: set(),   # Terminal
    }
    
    def can_transition_to(self, target: "ApprovalStatus") -> bool: ...
    def is_terminal(self) -> bool: ...
```

#### 3. ApprovalType
```python
class ApprovalTypeEnum(str, Enum):
    TOOL_CALL = "tool_call"
    PLAN_EXECUTION = "plan_execution"
    AGENT_SWITCH = "agent_switch"
    FILE_OPERATION = "file_operation"

class ApprovalType(ValueObject):
    """Тип утверждения."""
    value: ApprovalTypeEnum
```

#### 4. PolicyAction
```python
class PolicyActionEnum(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    ASK_USER = "ask_user"

class PolicyAction(ValueObject):
    """Действие политики."""
    value: PolicyActionEnum
```

### Entities (3 файла, ~500 строк)

#### 1. ApprovalRequest
```python
class ApprovalRequest(Entity):
    """
    Запрос на утверждение.
    
    Рефакторенная версия с Value Objects.
    """
    id: ApprovalId
    approval_type: ApprovalType
    status: ApprovalStatus
    request_data: Dict[str, Any]
    decision: Optional[str] = None
    decided_at: Optional[datetime] = None
    
    def approve(self, decision: str) -> None: ...
    def reject(self, reason: str) -> None: ...
    def expire(self) -> None: ...
```

#### 2. HITLPolicy
```python
class HITLPolicy(Entity):
    """
    Политика HITL.
    
    Определяет правила для автоматического принятия решений.
    """
    id: str
    name: str
    rules: List[PolicyRule]
    is_active: bool
    
    def evaluate(self, request: ApprovalRequest) -> PolicyAction: ...
    def add_rule(self, rule: PolicyRule) -> None: ...
```

#### 3. PolicyRule
```python
class PolicyRule(ValueObject):
    """
    Правило политики.
    
    Определяет условие и действие.
    """
    condition: str  # JSON path expression
    action: PolicyAction
    priority: int
    
    def matches(self, request_data: Dict[str, Any]) -> bool: ...
```

### Domain Events (8 событий, ~300 строк)

```python
# approval_events.py

class ApprovalRequested(DomainEvent):
    """Запрошено утверждение."""
    approval_id: ApprovalId
    approval_type: ApprovalType
    requested_at: datetime

class ApprovalGranted(DomainEvent):
    """Утверждение одобрено."""
    approval_id: ApprovalId
    decision: str
    approved_at: datetime

class ApprovalRejected(DomainEvent):
    """Утверждение отклонено."""
    approval_id: ApprovalId
    reason: str
    rejected_at: datetime

class ApprovalExpired(DomainEvent):
    """Утверждение истекло."""
    approval_id: ApprovalId
    expired_at: datetime

class PolicyEvaluated(DomainEvent):
    """Политика оценена."""
    approval_id: ApprovalId
    policy_id: str
    action: PolicyAction
    evaluated_at: datetime

class PolicyRuleMatched(DomainEvent):
    """Правило политики сработало."""
    approval_id: ApprovalId
    rule_condition: str
    action: PolicyAction

class AutoApprovalGranted(DomainEvent):
    """Автоматическое утверждение."""
    approval_id: ApprovalId
    policy_id: str
    auto_approved_at: datetime

class UserDecisionRequired(DomainEvent):
    """Требуется решение пользователя."""
    approval_id: ApprovalId
    reason: str
    requested_at: datetime
```

### Repository Interface (~150 строк)

```python
class ApprovalRepository(Repository[ApprovalRequest, ApprovalId]):
    """
    Типобезопасный интерфейс репозитория для утверждений.
    """
    
    @abstractmethod
    async def find_by_id(self, approval_id: ApprovalId) -> Optional[ApprovalRequest]:
        """Найти утверждение по ID."""
        pass
    
    @abstractmethod
    async def find_pending_by_session(self, session_id: str) -> List[ApprovalRequest]:
        """Найти ожидающие утверждения для сессии."""
        pass
    
    @abstractmethod
    async def save(self, approval: ApprovalRequest) -> None:
        """Сохранить утверждение."""
        pass
```

### Domain Services (2 файла, ~600 строк)

#### 1. ApprovalService
```python
class ApprovalService:
    """
    Domain Service для обработки утверждений.
    
    Responsibilities:
    - Создание запросов на утверждение
    - Обработка решений пользователя
    - Управление жизненным циклом утверждений
    - Генерация Domain Events
    """
    
    async def request_approval(
        self,
        approval_type: ApprovalType,
        request_data: Dict[str, Any],
        session_id: str
    ) -> ApprovalRequest: ...
    
    async def grant_approval(
        self,
        approval_id: ApprovalId,
        decision: str
    ) -> None: ...
    
    async def reject_approval(
        self,
        approval_id: ApprovalId,
        reason: str
    ) -> None: ...
```

#### 2. HITLPolicyService
```python
class HITLPolicyService:
    """
    Domain Service для управления HITL политиками.
    
    Responsibilities:
    - Оценка политик
    - Автоматическое принятие решений
    - Управление правилами
    """
    
    async def evaluate_request(
        self,
        approval_request: ApprovalRequest
    ) -> PolicyAction: ...
    
    async def add_policy_rule(
        self,
        policy_id: str,
        rule: PolicyRule
    ) -> None: ...
```

## 📊 Ожидаемые улучшения

### Метрики

| Метрика | До | После | Улучшение |
|---------|-----|-------|-----------|
| Типобезопасность | Примитивы (str) | Value Objects | +100% |
| Размер ApprovalRequest | ~200 строк | ~150 строк | -25% |
| Цикломатическая сложность | 8-10 | 3-5 | -60% |
| Покрытие тестами | 0% | 80%+ | +80% |

### Архитектурные улучшения

- ✅ Value Objects для типобезопасности
- ✅ Domain Events для трассировки
- ✅ Явная валидация переходов статусов
- ✅ Инкапсуляция бизнес-правил
- ✅ Готовность к Event Sourcing

## 🧪 Тестирование

### Unit тесты (3 файла, ~700 строк)

1. **test_value_objects.py** — Тесты для Value Objects
   - ApprovalId валидация
   - ApprovalStatus переходы
   - ApprovalType валидация
   - PolicyAction валидация

2. **test_entities.py** — Тесты для Entities
   - ApprovalRequest жизненный цикл
   - HITLPolicy оценка
   - PolicyRule matching

3. **test_services.py** — Тесты для Services
   - ApprovalService операции
   - HITLPolicyService оценка

## ⏱️ Оценка времени

- **Value Objects:** 2-3 часа
- **Entities:** 3-4 часа
- **Events:** 1-2 часа
- **Repository:** 1 час
- **Services:** 4-5 часов
- **Tests:** 3-4 часа
- **Документация:** 1 час

**Итого:** 15-20 часов (2-3 дня)

## 🚀 Следующие шаги

1. Создать Value Objects
2. Рефакторить Entities
3. Создать Domain Events
4. Создать Repository interface
5. Рефакторить Services
6. Написать unit тесты
7. Обновить документацию

## 📈 Прогресс после Фазы 6

| Фаза | Статус | Прогресс |
|------|--------|----------|
| Фазы 1-5 | ✅ | 100% |
| **Фаза 6: Approval Context** | 🚀 | **0%** |
| Фазы 7-9 | ⏳ | 0% |

**Ожидаемый прогресс после Фазы 6:** 67% (6 из 9 фаз)
