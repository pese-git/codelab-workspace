# 🚀 План полного перехода на новую архитектуру Agent Runtime

**Дата создания:** 6 февраля 2026  
**Статус:** 📋 План готов к выполнению  
**Цель:** Полная миграция с legacy entities на новые bounded contexts

---

## 📊 Текущее состояние

### ✅ Что уже сделано (Фазы 1-9)

1. **Новая архитектура создана** - 8 bounded contexts, 155+ файлов
2. **Адаптеры работают** - SessionAdapter, AgentContextAdapter (27/27 тестов)
3. **Repositories реализованы** - ConversationRepositoryImpl, AgentRepositoryImpl
4. **Тесты написаны** - 505+ unit тестов с покрытием 95-100%
5. **Обратная совместимость** - старый код продолжает работать

### ⚠️ Что осталось сделать

**Legacy entities все еще используются:**
- [`app/domain/entities/session.py`](../codelab-ai-service/agent-runtime/app/domain/entities/session.py) - 501 строка
- [`app/domain/entities/agent_context.py`](../codelab-ai-service/agent-runtime/app/domain/entities/agent_context.py) - 349 строк
- [`app/domain/entities/plan.py`](../codelab-ai-service/agent-runtime/app/domain/entities/plan.py) - 483 строки
- [`app/domain/entities/message.py`](../codelab-ai-service/agent-runtime/app/domain/entities/message.py)
- [`app/domain/entities/approval.py`](../codelab-ai-service/agent-runtime/app/domain/entities/approval.py)
- [`app/domain/entities/llm_response.py`](../codelab-ai-service/agent-runtime/app/domain/entities/llm_response.py)

**Domain Services используют legacy entities:**
- 12 сервисов импортируют старые entities
- MessageProcessor, AgentSwitcher, ExecutionEngine и др.

---

## 🎯 Стратегия миграции

### Принципы

1. **Постепенность** - мигрируем по одному сервису за раз
2. **Безопасность** - сохраняем работоспособность на каждом шаге
3. **Тестирование** - проверяем после каждого изменения
4. **Откат** - возможность вернуться к предыдущему состоянию

### Подход: Strangler Fig Pattern

```
Legacy Code ──────────────────────────────────────────┐
     │                                                 │
     │  Фаза 10.1: Миграция Domain Services           │
     ├──────────────────────────────────────────────► │
     │                                                 │
     │  Фаза 10.2: Миграция Infrastructure            │
     ├──────────────────────────────────────────────► │
     │                                                 │
     │  Фаза 10.3: Миграция Application Layer         │
     ├──────────────────────────────────────────────► │
     │                                                 │
     │  Фаза 10.4: Удаление Legacy Code               │
     └──────────────────────────────────────────────► New Architecture
```

---

## 📋 Фаза 10: Полная миграция

### Фаза 10.1: Миграция Domain Services (8-10 часов)

**Цель:** Обновить все domain services для работы с новыми entities

#### Шаг 1.1: SessionManagementService → ConversationService

**Файл:** [`app/domain/services/session_management.py`](../codelab-ai-service/agent-runtime/app/domain/services/session_management.py)

**Изменения:**
```python
# Было:
from ..entities.session import Session
from ..repositories.session_repository import SessionRepository

# Станет:
from ..session_context.entities.conversation import Conversation
from ..session_context.repositories.conversation_repository import ConversationRepository
from ..adapters.session_adapter import SessionAdapter  # Временно для совместимости
```

**Действия:**
1. Заменить импорты Session → Conversation
2. Обновить типы параметров и возвращаемых значений
3. Использовать ConversationRepository вместо SessionRepository
4. Обновить методы для работы с MessageCollection
5. Добавить адаптер для обратной совместимости (временно)
6. Обновить тесты

**Оценка:** 2 часа

---

#### Шаг 1.2: AgentOrchestrationService → AgentCoordinationService

**Файл:** [`app/domain/services/agent_orchestration.py`](../codelab-ai-service/agent-runtime/app/domain/services/agent_orchestration.py)

**Изменения:**
```python
# Было:
from ..entities.agent_context import AgentContext, AgentType
from ..repositories.agent_context_repository import AgentContextRepository

# Станет:
from ..agent_context.entities.agent import Agent
from ..agent_context.value_objects.agent_capabilities import AgentType
from ..agent_context.repositories.agent_repository import AgentRepository
from ..adapters.agent_context_adapter import AgentContextAdapter  # Временно
```

**Действия:**
1. Заменить AgentContext → Agent
2. Использовать AgentCapabilities вместо простого enum
3. Обновить AgentRepository
4. Использовать AgentRouterService для маршрутизации
5. Добавить адаптер для обратной совместимости
6. Обновить тесты

**Оценка:** 2 часа

---

#### Шаг 1.3: ExecutionEngine → PlanExecutionService

**Файл:** [`app/domain/services/execution_engine.py`](../codelab-ai-service/agent-runtime/app/domain/services/execution_engine.py)

**Изменения:**
```python
# Было:
from ..entities.plan import Plan, PlanStatus, Subtask, SubtaskStatus

# Станет:
from ..execution_context.entities.execution_plan import ExecutionPlan
from ..execution_context.entities.subtask import Subtask
from ..execution_context.value_objects.plan_status import PlanStatus
from ..execution_context.value_objects.subtask_status import SubtaskStatus
from ..execution_context.services.plan_execution_service import PlanExecutionService
```

**Действия:**
1. Заменить Plan → ExecutionPlan
2. Использовать Value Objects для статусов
3. Делегировать логику в PlanExecutionService
4. Обновить DependencyResolver
5. Обновить SubtaskExecutor
6. Обновить тесты

**Оценка:** 3 часа

---

#### Шаг 1.4: Остальные Domain Services

**Файлы для обновления:**
- [`message_processor.py`](../codelab-ai-service/agent-runtime/app/domain/services/message_processor.py)
- [`agent_switcher.py`](../codelab-ai-service/agent-runtime/app/domain/services/agent_switcher.py)
- [`tool_result_handler.py`](../codelab-ai-service/agent-runtime/app/domain/services/tool_result_handler.py)
- [`hitl_decision_handler.py`](../codelab-ai-service/agent-runtime/app/domain/services/hitl_decision_handler.py)
- [`plan_approval_handler.py`](../codelab-ai-service/agent-runtime/app/domain/services/plan_approval_handler.py)
- [`subtask_executor.py`](../codelab-ai-service/agent-runtime/app/domain/services/subtask_executor.py)
- [`dependency_resolver.py`](../codelab-ai-service/agent-runtime/app/domain/services/dependency_resolver.py)
- [`helpers/agent_switch_helper.py`](../codelab-ai-service/agent-runtime/app/domain/services/helpers/agent_switch_helper.py)

**Действия для каждого:**
1. Заменить импорты legacy entities на новые
2. Обновить типы параметров
3. Использовать Value Objects
4. Обновить тесты

**Оценка:** 3 часа (по 20-30 минут на сервис)

---

### Фаза 10.2: Миграция Infrastructure Layer (4-6 часов)

**Цель:** Обновить infrastructure для работы только с новыми entities

#### Шаг 2.1: Обновить Mappers

**Файлы:**
- [`app/infrastructure/persistence/mappers/session_mapper.py`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/mappers/session_mapper.py)
- [`app/infrastructure/persistence/mappers/agent_context_mapper.py`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/mappers/agent_context_mapper.py)
- [`app/infrastructure/persistence/mappers/plan_mapper.py`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/mappers/plan_mapper.py)

**Действия:**
1. Переименовать SessionMapper → ConversationMapper (уже есть)
2. Переименовать AgentContextMapper → AgentMapper (уже есть)
3. Переименовать PlanMapper → ExecutionPlanMapper
4. Удалить старые mappers
5. Обновить тесты

**Оценка:** 2 часа

---

#### Шаг 2.2: Обновить Repository Implementations

**Файлы:**
- [`app/infrastructure/persistence/repositories/session_repository_impl.py`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/repositories/session_repository_impl.py)
- [`app/infrastructure/persistence/repositories/agent_context_repository_impl.py`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/repositories/agent_context_repository_impl.py)
- [`app/infrastructure/persistence/repositories/plan_repository_impl.py`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/repositories/plan_repository_impl.py)

**Действия:**
1. Заменить SessionRepositoryImpl на ConversationRepositoryImpl (уже есть)
2. Заменить AgentContextRepositoryImpl на AgentRepositoryImpl (уже есть)
3. Создать ExecutionPlanRepositoryImpl
4. Удалить старые implementations
5. Обновить DI container
6. Обновить тесты

**Оценка:** 2 часа

---

#### Шаг 2.3: Обновить Adapters

**Файлы:**
- [`app/infrastructure/adapters/session_manager_adapter.py`](../codelab-ai-service/agent-runtime/app/infrastructure/adapters/session_manager_adapter.py)
- [`app/infrastructure/adapters/agent_context_manager_adapter.py`](../codelab-ai-service/agent-runtime/app/infrastructure/adapters/agent_context_manager_adapter.py)

**Действия:**
1. Обновить SessionManagerAdapter для работы с Conversation
2. Обновить AgentContextManagerAdapter для работы с Agent
3. Использовать адаптеры обратной совместимости из domain layer
4. Обновить тесты

**Оценка:** 2 часа

---

### Фаза 10.3: Миграция Application Layer (3-4 часа)

**Цель:** Обновить API endpoints и handlers

#### Шаг 3.1: Обновить API Routers

**Файлы:**
- [`app/api/v1/routers/sessions_router.py`](../codelab-ai-service/agent-runtime/app/api/v1/routers/sessions_router.py)
- [`app/api/v1/routers/agents_router.py`](../codelab-ai-service/agent-runtime/app/api/v1/routers/agents_router.py)
- [`app/api/v1/routers/plans_router.py`](../codelab-ai-service/agent-runtime/app/api/v1/routers/plans_router.py)

**Действия:**
1. Обновить зависимости для использования новых repositories
2. Использовать Use Cases вместо прямых вызовов сервисов
3. Обновить response schemas (DTOs)
4. Обновить тесты

**Оценка:** 2 часа

---

#### Шаг 3.2: Обновить Schemas (DTOs)

**Файлы:**
- [`app/api/v1/schemas/session_schemas.py`](../codelab-ai-service/agent-runtime/app/api/v1/schemas/session_schemas.py)
- [`app/api/v1/schemas/agent_schemas.py`](../codelab-ai-service/agent-runtime/app/api/v1/schemas/agent_schemas.py)
- [`app/api/v1/schemas/plan_schemas.py`](../codelab-ai-service/agent-runtime/app/api/v1/schemas/plan_schemas.py)

**Действия:**
1. Обновить DTOs для работы с новыми entities
2. Добавить методы from_entity() для новых entities
3. Сохранить обратную совместимость API
4. Обновить тесты

**Оценка:** 1 час

---

#### Шаг 3.3: Обновить DI Container

**Файл:** [`app/core/di/container.py`](../codelab-ai-service/agent-runtime/app/core/di/container.py)

**Действия:**
1. Зарегистрировать новые repositories
2. Зарегистрировать новые services
3. Удалить регистрации legacy компонентов
4. Обновить factory functions
5. Проверить все зависимости

**Оценка:** 1 час

---

### Фаза 10.4: Удаление Legacy Code (2-3 часа)

**Цель:** Удалить старые entities и неиспользуемый код

#### Шаг 4.1: Удалить Legacy Entities

**Файлы для удаления:**
```
app/domain/entities/
├── session.py              ❌ Удалить (заменен на Conversation)
├── agent_context.py        ❌ Удалить (заменен на Agent)
├── plan.py                 ❌ Удалить (заменен на ExecutionPlan)
├── message.py              ⚠️  Проверить использование
├── approval.py             ⚠️  Проверить использование
├── llm_response.py         ⚠️  Проверить использование
├── hitl.py                 ⚠️  Проверить использование
├── execution_state.py      ⚠️  Проверить использование
├── fsm_state.py            ⚠️  Проверить использование
└── base.py                 ❌ Удалить (заменен на shared/base_entity.py)
```

**Действия:**
1. Проверить, что entities не используются (grep/search)
2. Удалить файлы
3. Обновить `__init__.py`
4. Запустить все тесты
5. Проверить, что ничего не сломалось

**Оценка:** 1 час

---

#### Шаг 4.2: Удалить Legacy Repositories

**Файлы для удаления:**
```
app/domain/repositories/
├── session_repository.py           ❌ Удалить
├── agent_context_repository.py     ❌ Удалить
├── plan_repository.py              ❌ Удалить
└── base.py                         ❌ Удалить (заменен на shared/repository.py)
```

**Действия:**
1. Проверить, что repositories не используются
2. Удалить файлы
3. Обновить `__init__.py`
4. Запустить тесты

**Оценка:** 30 минут

---

#### Шаг 4.3: Удалить Legacy Infrastructure

**Файлы для удаления:**
```
app/infrastructure/persistence/
├── repositories/
│   ├── session_repository_impl.py          ❌ Удалить
│   ├── agent_context_repository_impl.py    ❌ Удалить
│   └── plan_repository_impl.py             ❌ Удалить
└── mappers/
    ├── session_mapper.py                   ❌ Удалить
    ├── agent_context_mapper.py             ❌ Удалить
    └── plan_mapper.py                      ❌ Удалить
```

**Действия:**
1. Проверить, что implementations не используются
2. Удалить файлы
3. Обновить `__init__.py`
4. Запустить тесты

**Оценка:** 30 минут

---

#### Шаг 4.4: Удалить Адаптеры (опционально)

**Файлы:**
- [`app/domain/adapters/session_adapter.py`](../codelab-ai-service/agent-runtime/app/domain/adapters/session_adapter.py)
- [`app/domain/adapters/agent_context_adapter.py`](../codelab-ai-service/agent-runtime/app/domain/adapters/agent_context_adapter.py)

**Решение:**
- ⚠️ **Рекомендация:** Оставить адаптеры на 1-2 месяца для возможности отката
- После стабилизации в production можно удалить

**Оценка:** 30 минут (если удалять)

---

### Фаза 10.5: Финализация (2-3 часа)

**Цель:** Проверка, документация, деплой

#### Шаг 5.1: Комплексное тестирование

**Действия:**
1. Запустить все unit тесты
2. Запустить integration тесты
3. Провести manual testing критических сценариев
4. Проверить performance (benchmarks)
5. Проверить memory usage

**Критические сценарии:**
- Создание сессии
- Отправка сообщения
- Переключение агента
- Создание и выполнение плана
- HITL approval
- Tool execution

**Оценка:** 1 час

---

#### Шаг 5.2: Обновить документацию

**Файлы для обновления:**
- `README.md` - обновить примеры использования
- `doc/ARCHITECTURE.md` - обновить диаграммы
- `doc/API.md` - обновить API документацию
- `doc/MIGRATION_GUIDE.md` - создать руководство для разработчиков

**Действия:**
1. Обновить примеры кода
2. Обновить диаграммы архитектуры
3. Создать migration guide
4. Обновить API документацию
5. Добавить troubleshooting секцию

**Оценка:** 1 час

---

#### Шаг 5.3: Code Review и Merge

**Действия:**
1. Создать Pull Request
2. Провести code review с командой
3. Исправить замечания
4. Получить approvals
5. Merge в main branch

**Оценка:** 1 час

---

## 📊 Общая оценка времени

| Фаза | Описание | Время |
|------|----------|-------|
| **10.1** | Миграция Domain Services | 8-10 часов |
| **10.2** | Миграция Infrastructure | 4-6 часов |
| **10.3** | Миграция Application Layer | 3-4 часа |
| **10.4** | Удаление Legacy Code | 2-3 часа |
| **10.5** | Финализация | 2-3 часа |
| **ИТОГО** | | **19-26 часов** |

**Рекомендуемый график:** 3-4 рабочих дня

---

## ✅ Чеклист выполнения

### Фаза 10.1: Domain Services
- [ ] SessionManagementService → ConversationService
- [ ] AgentOrchestrationService → AgentCoordinationService
- [ ] ExecutionEngine → PlanExecutionService
- [ ] MessageProcessor обновлен
- [ ] AgentSwitcher обновлен
- [ ] ToolResultHandler обновлен
- [ ] HITLDecisionHandler обновлен
- [ ] PlanApprovalHandler обновлен
- [ ] SubtaskExecutor обновлен
- [ ] DependencyResolver обновлен
- [ ] AgentSwitchHelper обновлен
- [ ] Все тесты domain services проходят

### Фаза 10.2: Infrastructure
- [ ] ConversationMapper создан
- [ ] AgentMapper создан
- [ ] ExecutionPlanMapper создан
- [ ] ConversationRepositoryImpl работает
- [ ] AgentRepositoryImpl работает
- [ ] ExecutionPlanRepositoryImpl создан
- [ ] SessionManagerAdapter обновлен
- [ ] AgentContextManagerAdapter обновлен
- [ ] Все тесты infrastructure проходят

### Фаза 10.3: Application Layer
- [ ] SessionsRouter обновлен
- [ ] AgentsRouter обновлен
- [ ] PlansRouter обновлен
- [ ] Session DTOs обновлены
- [ ] Agent DTOs обновлены
- [ ] Plan DTOs обновлены
- [ ] DI Container обновлен
- [ ] Все тесты API проходят

### Фаза 10.4: Legacy Code
- [ ] Legacy entities удалены
- [ ] Legacy repositories удалены
- [ ] Legacy infrastructure удалена
- [ ] Адаптеры оставлены (временно)
- [ ] Все тесты проходят после удаления

### Фаза 10.5: Финализация
- [ ] Unit тесты: 100% проходят
- [ ] Integration тесты: 100% проходят
- [ ] Manual testing: пройден
- [ ] Performance: проверен
- [ ] README обновлен
- [ ] ARCHITECTURE обновлена
- [ ] MIGRATION_GUIDE создан
- [ ] API документация обновлена
- [ ] Code review пройден
- [ ] PR merged

---

## ⚠️ Риски и митигация

### Риск 1: Breaking Changes в API

**Вероятность:** Средняя  
**Влияние:** Высокое  
**Митигация:**
- Сохранить обратную совместимость через DTOs
- Использовать адаптеры для конвертации
- Провести тщательное тестирование API
- Версионирование API (v1 → v2)

### Риск 2: Регрессия функциональности

**Вероятность:** Средняя  
**Влияние:** Высокое  
**Митигация:**
- Comprehensive тестирование на каждом шаге
- Сохранить адаптеры для возможности отката
- Feature flags для постепенного rollout
- Мониторинг метрик в production

### Риск 3: Performance Degradation

**Вероятность:** Низкая  
**Влияние:** Среднее  
**Митигация:**
- Benchmarking до и после миграции
- Профилирование критических путей
- Оптимизация запросов к БД
- Кэширование где необходимо

### Риск 4: Data Migration Issues

**Вероятность:** Низкая  
**Влияние:** Высокое  
**Митигация:**
- Использовать те же таблицы БД (SessionModel, AgentContextModel)
- Mappers обеспечивают совместимость
- Тестирование на копии production данных
- Rollback план

---

## 🚀 Стратегия деплоя

### Вариант 1: Big Bang (не рекомендуется)

Развернуть все изменения сразу.

**Плюсы:**
- Быстро
- Просто

**Минусы:**
- Высокий риск
- Сложно откатить
- Большой blast radius

### Вариант 2: Phased Rollout (рекомендуется)

Постепенное развертывание с feature flags.

**Этапы:**
1. **Week 1:** Деплой с feature flag OFF (код есть, но не используется)
2. **Week 2:** Включить для 10% трафика
3. **Week 3:** Включить для 50% трафика
4. **Week 4:** Включить для 100% трафика
5. **Week 5-8:** Мониторинг и стабилизация
6. **Week 9:** Удалить legacy code

**Плюсы:**
- Низкий риск
- Легко откатить
- Постепенная валидация

**Минусы:**
- Дольше
- Нужны feature flags

### Вариант 3: Canary Deployment

Развернуть на одном сервере, затем на всех.

**Этапы:**
1. Деплой на canary сервер (1 из N)
2. Мониторинг 24-48 часов
3. Если OK → деплой на все серверы
4. Если проблемы → откат canary

**Плюсы:**
- Средний риск
- Быстрая валидация
- Легко откатить

**Минусы:**
- Нужна инфраструктура для canary

---

## 📈 Метрики успеха

### Технические метрики

| Метрика | Цель |
|---------|------|
| **Unit тесты** | 100% проходят |
| **Integration тесты** | 100% проходят |
| **Code coverage** | ≥ 90% |
| **Legacy code** | 0 строк |
| **Response time** | ≤ текущего + 10% |
| **Memory usage** | ≤ текущего + 10% |
| **Error rate** | ≤ текущего |

### Бизнес метрики

| Метрика | Цель |
|---------|------|
| **Uptime** | ≥ 99.9% |
| **User complaints** | 0 |
| **Rollbacks** | 0 |
| **Incidents** | 0 |

---

## 🎯 Следующие шаги

### Немедленно (эта неделя)

1. ✅ Создать ветку `feature/full-migration`
2. ✅ Начать с Фазы 10.1.1 (SessionManagementService)
3. ✅ Написать тесты для миграции
4. ✅ Провести code review

### Краткосрочно (следующая неделя)

1. Завершить Фазу 10.1 (Domain Services)
2. Начать Фазу 10.2 (Infrastructure)
3. Провести промежуточное тестирование

### Среднесрочно (2-3 недели)

1. Завершить Фазы 10.2-10.4
2. Провести комплексное тестирование
3. Подготовить к деплою

### Долгосрочно (1-2 месяца)

1. Phased rollout в production
2. Мониторинг и стабилизация
3. Удалить адаптеры и legacy code

---

## 📚 Дополнительные ресурсы

### Документация

- [Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Domain-Driven Design](https://martinfowler.com/bliki/DomainDrivenDesign.html)
- [Strangler Fig Pattern](https://martinfowler.com/bliki/StranglerFigApplication.html)
- [Feature Flags](https://martinfowler.com/articles/feature-toggles.html)

### Инструменты

- **Testing:** pytest, pytest-asyncio, pytest-cov
- **Profiling:** py-spy, memory_profiler
- **Monitoring:** Prometheus, Grafana
- **Feature Flags:** LaunchDarkly, Unleash

---

## 💡 Советы и best practices

### Во время миграции

1. **Коммитьте часто** - маленькие атомарные коммиты
2. **Тестируйте постоянно** - после каждого изменения
3. **Документируйте решения** - почему сделали так, а не иначе
4. **Общайтесь с командой** - синхронизация важна
5. **Не спешите** - лучше медленно и правильно

### После миграции

1. **Мониторьте метрики** - следите за performance и errors
2. **Собирайте feedback** - от команды и пользователей
3. **Документируйте lessons learned** - что прошло хорошо/плохо
4. **Планируйте улучшения** - что можно сделать лучше
5. **Празднуйте успех** - это большое достижение! 🎉

---

**Автор:** AI Assistant  
**Дата:** 6 февраля 2026  
**Версия:** 1.0  
**Статус:** 📋 Готов к выполнению

---

## 🎉 Заключение

Этот план обеспечивает **безопасную и постепенную** миграцию на новую архитектуру. Следуя этому плану, вы сможете:

1. ✅ Полностью перейти на новые bounded contexts
2. ✅ Удалить весь legacy код
3. ✅ Сохранить работоспособность системы
4. ✅ Минимизировать риски
5. ✅ Получить чистую, поддерживаемую архитектуру

**Оценка времени:** 19-26 часов (3-4 рабочих дня)  
**Риски:** Минимальные при следовании плану  
**Результат:** Полностью рефакторенный сервис на Clean Architecture + DDD

**Готовы начать? Удачи! 🚀**
