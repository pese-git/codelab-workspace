# 📊 Анализ Infrastructure Layer для Фазы 10.2

**Дата:** 6 февраля 2026  
**Автор:** Agent Runtime Team  
**Статус:** 🔍 Анализ завершен

---

## 🎯 Цель анализа

Проанализировать текущее состояние Infrastructure Layer и определить компоненты, требующие миграции на новую DDD-архитектуру в рамках Фазы 10.2.

---

## 📦 Текущая структура Infrastructure Layer

```
app/infrastructure/
├── adapters/                    # Адаптеры для legacy интеграции
│   ├── agent_context_manager_adapter.py
│   ├── event_publisher_adapter.py
│   └── session_manager_adapter.py
├── cleanup/                     # Очистка сессий
│   └── session_cleanup.py
├── concurrency/                 # Управление конкурентностью
│   └── session_lock.py
├── events/                      # Публикация событий
│   └── llm_event_publisher.py
├── llm/                        # LLM клиенты
│   ├── client.py
│   ├── llm_client.py
│   └── tool_parser.py
├── persistence/                # Персистентность
│   ├── database.py
│   ├── mappers/               # ⚠️ ТРЕБУЕТ МИГРАЦИИ
│   │   ├── session_mapper.py          (Legacy)
│   │   ├── conversation_mapper.py     (✅ Новый)
│   │   ├── agent_context_mapper.py    (Legacy)
│   │   ├── agent_mapper.py            (✅ Новый)
│   │   └── plan_mapper.py             (Legacy)
│   ├── models/                # Database models
│   │   ├── session.py
│   │   ├── agent_context.py
│   │   └── plan.py
│   └── repositories/          # ⚠️ ТРЕБУЕТ МИГРАЦИИ
│       ├── session_repository_impl.py          (Legacy)
│       ├── conversation_repository_impl.py     (✅ Новый)
│       ├── agent_context_repository_impl.py    (Legacy)
│       ├── agent_repository_impl.py            (✅ Новый)
│       ├── plan_repository_impl.py             (Legacy)
│       ├── approval_repository_impl.py
│       └── fsm_state_repository_impl.py
└── resilience/                 # Устойчивость
    ├── circuit_breaker.py
    └── retry_handler.py
```

---

## 🔍 Детальный анализ компонентов

### 1. Mappers (5 файлов)

#### ✅ Новые Mappers (уже мигрированы)

| Mapper | Статус | Entity | Model | Создан |
|--------|--------|--------|-------|--------|
| [`ConversationMapper`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/mappers/conversation_mapper.py) | ✅ Готов | `Conversation` | `SessionModel` | Фаза 10.1.1 |
| [`AgentMapper`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/mappers/agent_mapper.py) | ✅ Готов | `Agent` | `AgentContextModel` | Фаза 10.1.2 |

**Особенности:**
- Используют новые DDD entities
- Используют Value Objects (ConversationId, AgentId, etc.)
- Полная поддержка Pydantic моделей
- Обработка вложенных структур (MessageCollection, AgentSwitchRecord)

#### ⚠️ Legacy Mappers (требуют обновления)

| Mapper | Статус | Entity | Model | Проблема |
|--------|--------|--------|-------|----------|
| [`SessionMapper`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/mappers/session_mapper.py) | ⚠️ Legacy | `Session` (old) | `SessionModel` | Использует старую entity |
| [`AgentContextMapper`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/mappers/agent_context_mapper.py) | ⚠️ Legacy | `AgentContext` (old) | `AgentContextModel` | Использует старую entity |
| [`PlanMapper`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/mappers/plan_mapper.py) | ⚠️ Legacy | `Plan` (old) | `PlanModel` | Использует старую entity |

**Проблемы:**
- Используют legacy entities из `app.domain.entities.*`
- Не используют Value Objects
- Не поддерживают Pydantic валидацию
- Ручная сериализация/десериализация JSON

#### 🆕 Отсутствующие Mappers

| Mapper | Нужен для | Entity | Model |
|--------|-----------|--------|-------|
| `ExecutionPlanMapper` | ✅ Да | `ExecutionPlan` | `PlanModel` |

**Обоснование:**
- `ExecutionPlan` - новая DDD entity из `execution_context`
- Заменяет старую `Plan` entity
- Использует `PlanId`, `SubtaskId`, `PlanStatus` Value Objects
- Требует отдельный mapper для корректной работы

---

### 2. Repository Implementations (7 файлов)

#### ✅ Новые Repositories (уже мигрированы)

| Repository | Статус | Entity | Mapper | Создан |
|------------|--------|--------|--------|--------|
| [`ConversationRepositoryImpl`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/repositories/conversation_repository_impl.py) | ✅ Готов | `Conversation` | `ConversationMapper` | Фаза 10.1.1 |
| [`AgentRepositoryImpl`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/repositories/agent_repository_impl.py) | ✅ Готов | `Agent` | `AgentMapper` | Фаза 10.1.2 |

**Особенности:**
- Реализуют новые repository интерфейсы
- Используют новые mappers
- Поддержка snapshot (save_snapshot/get_snapshot)
- Полная поддержка Value Objects

#### ⚠️ Legacy Repositories (требуют обновления)

| Repository | Статус | Entity | Mapper | Проблема |
|------------|--------|--------|--------|----------|
| [`SessionRepositoryImpl`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/repositories/session_repository_impl.py) | ⚠️ Legacy | `Session` (old) | `SessionMapper` | Использует legacy mapper |
| [`AgentContextRepositoryImpl`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/repositories/agent_context_repository_impl.py) | ⚠️ Legacy | `AgentContext` (old) | `AgentContextMapper` | Использует legacy mapper |
| [`PlanRepositoryImpl`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/repositories/plan_repository_impl.py) | ⚠️ Legacy | `Plan` (old) | `PlanMapper` | Использует legacy mapper |

**Проблемы:**
- Используют legacy mappers
- Не поддерживают snapshot методы
- Не используют Value Objects в сигнатурах

#### ✅ Repositories без изменений

| Repository | Статус | Причина |
|------------|--------|---------|
| [`ApprovalRepositoryImpl`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/repositories/approval_repository_impl.py) | ✅ OK | Не зависит от мигрируемых entities |
| [`FSMStateRepositoryImpl`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/repositories/fsm_state_repository_impl.py) | ✅ OK | Не зависит от мигрируемых entities |

#### 🆕 Отсутствующие Repositories

| Repository | Нужен для | Entity | Mapper |
|------------|-----------|--------|--------|
| `ExecutionPlanRepositoryImpl` | ✅ Да | `ExecutionPlan` | `ExecutionPlanMapper` |

**Обоснование:**
- Интерфейс `ExecutionPlanRepository` уже существует
- Нужна реализация для работы с БД
- Должен использовать `ExecutionPlanMapper`

---

### 3. Database Models (3 файла)

#### Текущие модели

| Model | Таблица | Используется для | Статус |
|-------|---------|------------------|--------|
| [`SessionModel`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/models/session.py) | `sessions` | Session + Conversation | ✅ OK |
| [`AgentContextModel`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/models/agent_context.py) | `agent_contexts` | AgentContext + Agent | ✅ OK |
| [`PlanModel`](../codelab-ai-service/agent-runtime/app/infrastructure/persistence/models/plan.py) | `plans` | Plan + ExecutionPlan | ✅ OK |

**Вывод:** Database models НЕ требуют изменений!

**Обоснование:**
- Модели БД независимы от domain entities
- Один model может использоваться несколькими mappers
- `SessionModel` используется и `SessionMapper`, и `ConversationMapper`
- `AgentContextModel` используется и `AgentContextMapper`, и `AgentMapper`
- `PlanModel` будет использоваться и `PlanMapper`, и `ExecutionPlanMapper`

---

## 📊 Матрица зависимостей

### Legacy → New Entity Mapping

| Legacy Entity | New Entity | Model | Legacy Mapper | New Mapper | Статус |
|---------------|------------|-------|---------------|------------|--------|
| `Session` | `Conversation` | `SessionModel` | `SessionMapper` | `ConversationMapper` ✅ | Mapper готов |
| `AgentContext` | `Agent` | `AgentContextModel` | `AgentContextMapper` | `AgentMapper` ✅ | Mapper готов |
| `Plan` | `ExecutionPlan` | `PlanModel` | `PlanMapper` | `ExecutionPlanMapper` ❌ | Нужен новый |

### Repository Dependencies

```
SessionRepositoryImpl (Legacy)
  └── SessionMapper (Legacy)
        └── Session entity (Legacy)

ConversationRepositoryImpl (New) ✅
  └── ConversationMapper (New) ✅
        └── Conversation entity (New) ✅

AgentContextRepositoryImpl (Legacy)
  └── AgentContextMapper (Legacy)
        └── AgentContext entity (Legacy)

AgentRepositoryImpl (New) ✅
  └── AgentMapper (New) ✅
        └── Agent entity (New) ✅

PlanRepositoryImpl (Legacy)
  └── PlanMapper (Legacy)
        └── Plan entity (Legacy)

ExecutionPlanRepositoryImpl (Missing) ❌
  └── ExecutionPlanMapper (Missing) ❌
        └── ExecutionPlan entity (New) ✅
```

---

## 🎯 Компоненты для миграции в Фазе 10.2

### Приоритет 1: Критические (обязательные)

1. **ExecutionPlanMapper** (новый)
   - Создать mapper для `ExecutionPlan` → `PlanModel`
   - Поддержка Value Objects: `PlanId`, `SubtaskId`, `PlanStatus`
   - Конвертация `Subtask` entities
   - ~200-250 строк кода

2. **ExecutionPlanRepositoryImpl** (новый)
   - Реализация `ExecutionPlanRepository` интерфейса
   - Использование `ExecutionPlanMapper`
   - Методы: find_by_id, find_by_conversation_id, save, delete
   - ~300-400 строк кода

### Приоритет 2: Важные (для полноты)

3. **PlanMapper** (обновление)
   - Обновить для совместимости с новыми типами
   - Добавить поддержку `PlanId` Value Object
   - Сохранить обратную совместимость
   - ~50-100 строк изменений

4. **PlanRepositoryImpl** (обновление)
   - Обновить для использования обновленного `PlanMapper`
   - Добавить методы snapshot (если нужны)
   - ~50-100 строк изменений

### Приоритет 3: Опциональные (можно отложить)

5. **SessionMapper** (обновление/deprecation)
   - Пометить как deprecated
   - Добавить предупреждения о миграции на `ConversationMapper`
   - ~20-30 строк изменений

6. **AgentContextMapper** (обновление/deprecation)
   - Пометить как deprecated
   - Добавить предупреждения о миграции на `AgentMapper`
   - ~20-30 строк изменений

7. **SessionRepositoryImpl** (обновление/deprecation)
   - Пометить как deprecated
   - Делегировать в `ConversationRepositoryImpl` через адаптер
   - ~50-100 строк изменений

8. **AgentContextRepositoryImpl** (обновление/deprecation)
   - Пометить как deprecated
   - Делегировать в `AgentRepositoryImpl` через адаптер
   - ~50-100 строк изменений

---

## 📈 Оценка трудозатрат

### Вариант 1: Минимальный (только критические)

| Компонент | Оценка | Тесты | Итого |
|-----------|--------|-------|-------|
| ExecutionPlanMapper | 1.5ч | 0.5ч | 2ч |
| ExecutionPlanRepositoryImpl | 2ч | 1ч | 3ч |
| **Итого** | **3.5ч** | **1.5ч** | **5ч** |

### Вариант 2: Полный (все компоненты)

| Компонент | Оценка | Тесты | Итого |
|-----------|--------|-------|-------|
| ExecutionPlanMapper | 1.5ч | 0.5ч | 2ч |
| ExecutionPlanRepositoryImpl | 2ч | 1ч | 3ч |
| PlanMapper update | 0.5ч | 0.5ч | 1ч |
| PlanRepositoryImpl update | 0.5ч | 0.5ч | 1ч |
| Legacy deprecation (4 файла) | 1ч | 0.5ч | 1.5ч |
| **Итого** | **5.5ч** | **3ч** | **8.5ч** |

### Вариант 3: Оптимальный (критические + важные)

| Компонент | Оценка | Тесты | Итого |
|-----------|--------|-------|-------|
| ExecutionPlanMapper | 1.5ч | 0.5ч | 2ч |
| ExecutionPlanRepositoryImpl | 2ч | 1ч | 3ч |
| PlanMapper update | 0.5ч | 0.5ч | 1ч |
| PlanRepositoryImpl update | 0.5ч | 0.5ч | 1ч |
| **Итого** | **4.5ч** | **2.5ч** | **7ч** |

---

## 🎯 Рекомендации

### Рекомендуемый подход: Вариант 3 (Оптимальный)

**Обоснование:**
1. ✅ Создаем критически важные компоненты (ExecutionPlan)
2. ✅ Обновляем существующие для совместимости
3. ⏸️ Откладываем deprecation до Фазы 10.4 (Legacy Code Removal)
4. ⚡ Экономим время (7ч вместо 8.5ч)
5. 🎯 Фокус на функциональности, а не на cleanup

### Порядок выполнения

1. **Шаг 1:** Создать `ExecutionPlanMapper` (2ч)
   - Изучить `ExecutionPlan` entity
   - Реализовать to_entity и to_model
   - Написать unit тесты

2. **Шаг 2:** Создать `ExecutionPlanRepositoryImpl` (3ч)
   - Реализовать интерфейс `ExecutionPlanRepository`
   - Использовать `ExecutionPlanMapper`
   - Написать unit тесты

3. **Шаг 3:** Обновить `PlanMapper` (1ч)
   - Добавить поддержку `PlanId` Value Object
   - Обеспечить совместимость
   - Обновить тесты

4. **Шаг 4:** Обновить `PlanRepositoryImpl` (1ч)
   - Использовать обновленный mapper
   - Добавить snapshot методы (если нужны)
   - Обновить тесты

### Критерии успеха

- ✅ `ExecutionPlanMapper` создан и протестирован
- ✅ `ExecutionPlanRepositoryImpl` создан и протестирован
- ✅ `PlanMapper` обновлен для совместимости
- ✅ `PlanRepositoryImpl` обновлен
- ✅ Все тесты проходят (100%)
- ✅ Docker работает без ошибок
- ✅ Обратная совместимость сохранена

---

## 🔗 Связанные документы

- [Прогресс Фазы 10](agent-runtime-phase-10-progress.md)
- [Отчет Фазы 10.1.4](agent-runtime-phase-10-1-4-report.md)
- [Стратегия Фазы 10.2](agent-runtime-phase-10-2-strategy.md) (будет создан)
- [План Фазы 10.2](agent-runtime-phase-10-2-plan.md) (будет создан)

---

**Последнее обновление:** 6 февраля 2026, 19:17 UTC+3
