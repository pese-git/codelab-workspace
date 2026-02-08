# 📋 План Фазы 10.4: Удаление Legacy Code

**Дата:** 6 февраля 2026  
**Оценка:** 2-3 часа  
**Статус:** ⏳ Ожидает начала

---

## 🎯 Цель фазы

Полностью удалить legacy код и завершить миграцию на DDD-архитектуру:
- Удалить legacy entities
- Удалить старые repositories
- Удалить старые services
- Обновить все импорты
- Финальное тестирование

---

## 📋 Задачи

### 1. Анализ зависимостей (30 мин)

**Цель:** Найти все места использования legacy кода

**Действия:**
```bash
# Найти импорты legacy entities
cd codelab-ai-service/agent-runtime
grep -r "from app.domain.entities.session import" app/
grep -r "from app.domain.entities.agent_context import" app/
grep -r "from app.domain.entities.execution_plan import" app/

# Найти импорты legacy repositories
grep -r "from app.domain.repositories.session_repository import" app/
grep -r "from app.domain.repositories.agent_repository import" app/
grep -r "from app.domain.repositories.plan_repository import" app/

# Найти импорты legacy services
grep -r "from app.domain.services.session_management_service import" app/
grep -r "from app.domain.services.agent_orchestration_service import" app/
grep -r "from app.domain.services.execution_engine import" app/
```

**Результат:**
- Список всех файлов, использующих legacy код
- Карта зависимостей
- План замены импортов

---

### 2. Удаление legacy entities (30 мин)

**Файлы для удаления:**

1. `app/domain/entities/session.py`
   - Legacy `Session` entity
   - Заменен на `Conversation` в `app/domain/session_context/entities/conversation.py`

2. `app/domain/entities/agent_context.py`
   - Legacy `AgentContext` entity
   - Заменен на `Agent` в `app/domain/agent_context/entities/agent.py`

3. `app/domain/entities/execution_plan.py`
   - Legacy `ExecutionPlan` entity
   - Заменен на `ExecutionPlan` в `app/domain/execution_context/entities/execution_plan.py`

**Действия:**
```bash
# Удалить legacy entities
rm app/domain/entities/session.py
rm app/domain/entities/agent_context.py
rm app/domain/entities/execution_plan.py

# Проверить, что директория пуста
ls -la app/domain/entities/
```

**Проверка:**
- ✅ Файлы удалены
- ✅ Нет импортов legacy entities
- ✅ Тесты не ломаются

---

### 3. Удаление legacy repositories (30 мин)

**Файлы для удаления:**

1. `app/domain/repositories/session_repository.py`
   - Legacy `SessionRepository` abstract class
   - Заменен на `ConversationRepository` в `app/domain/session_context/repositories/conversation_repository.py`

2. `app/domain/repositories/agent_repository.py`
   - Legacy `AgentRepository` abstract class
   - Заменен на `AgentRepository` в `app/domain/agent_context/repositories/agent_repository.py`

3. `app/domain/repositories/plan_repository.py`
   - Legacy `PlanRepository` abstract class
   - Заменен на `ExecutionPlanRepository` в `app/domain/execution_context/repositories/execution_plan_repository.py`

**Действия:**
```bash
# Удалить legacy repositories
rm app/domain/repositories/session_repository.py
rm app/domain/repositories/agent_repository.py
rm app/domain/repositories/plan_repository.py

# Проверить, что директория пуста
ls -la app/domain/repositories/
```

**Проверка:**
- ✅ Файлы удалены
- ✅ Нет импортов legacy repositories
- ✅ DI Container использует новые repositories

---

### 4. Удаление legacy services (30 мин)

**Файлы для удаления:**

1. `app/domain/services/session_management_service.py`
   - Legacy `SessionManagementService`
   - Заменен на `ConversationManagementService` + `ConversationServiceAdapter`

2. `app/domain/services/agent_orchestration_service.py`
   - Legacy `AgentOrchestrationService`
   - Заменен на `AgentCoordinationService` + `AgentOrchestrationAdapter`

3. `app/domain/services/execution_engine.py`
   - Legacy `ExecutionEngine`
   - Заменен на `PlanExecutionService` + `ExecutionEngineAdapter`

**Действия:**
```bash
# Удалить legacy services
rm app/domain/services/session_management_service.py
rm app/domain/services/agent_orchestration_service.py
rm app/domain/services/execution_engine.py

# Проверить, что директория пуста
ls -la app/domain/services/
```

**Проверка:**
- ✅ Файлы удалены
- ✅ Нет импортов legacy services
- ✅ Все используют адаптеры

---

### 5. Обновление импортов (30 мин)

**Цель:** Заменить все импорты legacy кода на новые

**Файлы для проверки:**

1. `app/core/dependencies.py`
   - Проверить, что используются только новые сервисы
   - Убрать импорты legacy кода

2. `app/application/coordinators/*.py`
   - Обновить импорты в координаторах
   - Использовать только адаптеры

3. `app/api/routes/*.py`
   - Проверить API endpoints
   - Убедиться, что используются новые типы

4. `tests/**/*.py`
   - Обновить импорты в тестах
   - Использовать новые entities и services

**Действия:**
```bash
# Найти все импорты legacy кода
grep -r "from app.domain.entities" app/ tests/
grep -r "from app.domain.repositories" app/ tests/
grep -r "from app.domain.services" app/ tests/

# Заменить импорты (вручную или через sed)
# Пример:
# sed -i '' 's/from app.domain.entities.session/from app.domain.session_context.entities.conversation/g' file.py
```

**Проверка:**
- ✅ Нет импортов из `app/domain/entities/`
- ✅ Нет импортов из `app/domain/repositories/`
- ✅ Нет импортов из `app/domain/services/`

---

### 6. Удаление адаптеров (опционально, 30 мин)

**Цель:** Убрать адаптеры и использовать напрямую новые сервисы

**Файлы:**
1. `app/domain/adapters/conversation_service_adapter.py`
2. `app/domain/adapters/agent_orchestration_adapter.py`
3. `app/domain/adapters/execution_engine_adapter.py`

**Действия:**
1. Обновить `app/core/dependencies.py`:
   - `get_session_management_service()` → возвращать `ConversationManagementService`
   - `get_agent_orchestration_service()` → возвращать `AgentCoordinationService`
   - `get_execution_engine()` → возвращать `PlanExecutionService`

2. Обновить координаторы:
   - Использовать напрямую новые сервисы
   - Убрать `Union` типы

3. Удалить адаптеры:
   ```bash
   rm app/domain/adapters/conversation_service_adapter.py
   rm app/domain/adapters/agent_orchestration_adapter.py
   rm app/domain/adapters/execution_engine_adapter.py
   ```

**Проверка:**
- ✅ Адаптеры удалены
- ✅ Все используют напрямую новые сервисы
- ✅ Тесты проходят

**Примечание:** Этот шаг опционален. Можно оставить адаптеры для гибкости.

---

### 7. Финальное тестирование (30 мин)

**Цель:** Убедиться, что система работает корректно

**Действия:**

1. **Проверка синтаксиса:**
   ```bash
   cd codelab-ai-service/agent-runtime
   python -m py_compile app/**/*.py
   ```

2. **Запуск unit тестов:**
   ```bash
   pytest tests/unit/ -v
   ```

3. **Запуск integration тестов:**
   ```bash
   pytest tests/integration/ -v
   ```

4. **Проверка Docker:**
   ```bash
   docker compose restart agent-runtime
   docker compose logs agent-runtime --tail=100
   ```

5. **Проверка API:**
   ```bash
   curl http://localhost:8001/health
   curl http://localhost:8001/api/v1/sessions
   ```

**Проверка:**
- ✅ Все тесты проходят
- ✅ Docker запускается без ошибок
- ✅ API отвечает корректно
- ✅ Нет ошибок в логах

---

## 📊 Оценка времени

| Задача | Время |
|--------|-------|
| 1. Анализ зависимостей | 30 мин |
| 2. Удаление legacy entities | 30 мин |
| 3. Удаление legacy repositories | 30 мин |
| 4. Удаление legacy services | 30 мин |
| 5. Обновление импортов | 30 мин |
| 6. Удаление адаптеров (опц.) | 30 мин |
| 7. Финальное тестирование | 30 мин |
| **Итого** | **2.5-3.5 часа** |

---

## 🎯 Критерии успеха

1. ✅ Все legacy entities удалены
2. ✅ Все legacy repositories удалены
3. ✅ Все legacy services удалены
4. ✅ Нет импортов legacy кода
5. ✅ Все тесты проходят
6. ✅ Docker работает без ошибок
7. ✅ API отвечает корректно
8. ✅ Нет ошибок в логах

---

## ⚠️ Риски и митигация

### Риск 1: Пропущенные зависимости

**Описание:** Могут остаться файлы, использующие legacy код

**Митигация:**
- Тщательный поиск через `grep`
- Проверка всех импортов
- Запуск всех тестов

### Риск 2: Сломанные тесты

**Описание:** Тесты могут использовать legacy код

**Митигация:**
- Обновить импорты в тестах
- Использовать новые entities и services
- Запустить все тесты перед коммитом

### Риск 3: Проблемы с Docker

**Описание:** Docker может не запуститься после удаления

**Митигация:**
- Проверить логи Docker
- Откатиться на предыдущий коммит при необходимости
- Постепенное удаление с проверкой

---

## 📝 Чеклист выполнения

- [ ] Анализ зависимостей завершен
- [ ] Legacy entities удалены
- [ ] Legacy repositories удалены
- [ ] Legacy services удалены
- [ ] Импорты обновлены
- [ ] Адаптеры удалены (опционально)
- [ ] Unit тесты проходят
- [ ] Integration тесты проходят
- [ ] Docker работает
- [ ] API отвечает корректно
- [ ] Логи чистые
- [ ] Документация обновлена
- [ ] Коммит создан

---

## 📚 Документация

После завершения создать:

1. **Отчет о завершении:** `agent-runtime-phase-10-4-completion-report.md`
   - Список удаленных файлов
   - Статистика изменений
   - Результаты тестирования

2. **Финальный отчет Фазы 10:** `agent-runtime-phase-10-final-report.md`
   - Общая статистика всех подфаз
   - Достижения и результаты
   - Архитектурные улучшения

3. **Обновить прогресс:** `agent-runtime-phase-10-progress.md`
   - Отметить Фазу 10.4 как завершенную
   - Обновить общую статистику
   - Финальные метрики

---

## 🚀 После завершения

После успешного завершения Фазы 10.4:

1. ✅ **Миграция на DDD-архитектуру завершена**
2. ✅ **Legacy код полностью удален**
3. ✅ **Система работает на новой архитектуре**
4. ✅ **Готовность к новым фичам**

**Следующие шаги:**
- Мониторинг production
- Оптимизация производительности
- Новые фичи на базе DDD

---

## 🎉 Ожидаемый результат

После завершения Фазы 10.4:

```
✅ Domain Layer: 100% DDD
✅ Infrastructure Layer: 100% DDD
✅ Application Layer: 100% DDD
✅ Legacy Code: 0%

🎯 Миграция завершена!
```

**Архитектура:**
- ✅ Clean Architecture
- ✅ Domain-Driven Design
- ✅ SOLID принципы
- ✅ Типобезопасность
- ✅ Тестируемость

**Готовность к масштабированию:** 100% 🚀
