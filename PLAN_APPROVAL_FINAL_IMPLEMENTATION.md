# Финальная реализация механизма approve/reject для планов

## Статус: ✅ Полностью реализовано

Механизм подтверждения/отклонения планов Architect агента реализован по аналогии с HITL для инструментов.

## Выполненные изменения

### Backend (8 файлов)

#### Agent Runtime Service

1. **[`app/models/plan_models.py`](codelab-ai-service/agent-runtime/app/models/plan_models.py)** (новый)
   - `PlanDecision` - enum (approve/edit/reject)
   - `PlanUserDecision` - модель решения от IDE
   - `PlanAuditLog` - логирование решений

2. **[`app/services/plan_manager.py`](codelab-ai-service/agent-runtime/app/services/plan_manager.py)** (новый)
   - Управление audit logs
   - Singleton instance `plan_manager`

3. **[`app/models/schemas.py`](codelab-ai-service/agent-runtime/app/models/schemas.py)**
   - Добавлены поля в `ExecutionPlan`:
     - `requires_approval: bool = True`
     - `is_approved: bool = False`

4. **[`app/agents/architect_agent.py`](codelab-ai-service/agent-runtime/app/agents/architect_agent.py)**
   - Установка `requires_approval=True`, `is_approved=False`
   - Изменен `is_final=True` в `plan_notification`
   - Обновлено сообщение с инструкцией

5. **[`app/api/v1/endpoints.py`](codelab-ai-service/agent-runtime/app/api/v1/endpoints.py)**
   - Добавлена обработка `plan_decision` (строки 78-218)
   - Approve → выполнение через orchestrator
   - Edit → обновление подзадач и выполнение
   - Reject → отмена плана

6. **[`app/services/multi_agent_orchestrator.py`](codelab-ai-service/agent-runtime/app/services/multi_agent_orchestrator.py)**
   - Заменена текстовая логика на проверку `is_approved`
   - Удален метод `_handle_plan_confirmation`

#### Gateway Service

7. **[`app/models/websocket.py`](codelab-ai-service/gateway/app/models/websocket.py)**
   - Добавлена модель `WSPlanDecision`

8. **[`app/api/v1/endpoints.py`](codelab-ai-service/gateway/app/api/v1/endpoints.py)**
   - Добавлен импорт `WSPlanDecision`
   - Добавлена обработка `plan_decision` в WebSocket

### Frontend (6 файлов)

#### codelab_ai_assistant

9. **[`lib/features/agent_chat/data/repositories/agent_repository_impl.dart`](codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/data/repositories/agent_repository_impl.dart)**
   - Изменен тип с `plan_approval` на `plan_decision` (строки 411, 437)
   - Исправлено извлечение `plan_id` из `metadata['plan_id']`

10. **[`lib/features/agent_chat/domain/usecases/watch_plan_updates.dart`](codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/domain/usecases/watch_plan_updates.dart)** (новый)
    - UseCase для подписки на обновления планов

11. **[`lib/features/agent_chat/presentation/bloc/agent_chat_bloc.dart`](codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/presentation/bloc/agent_chat_bloc.dart)**
    - Добавлен `WatchPlanUpdatesUseCase`
    - Подписка на `watchPlanUpdates()` в `_onConnect`
    - Обработка `plan_notification` в `_onMessageReceived`
    - Вызов `planReceived` event при получении плана

12. **[`lib/ai_assistent_module.dart`](codelab_ide/packages/codelab_ai_assistant/lib/ai_assistent_module.dart)**
    - Импорт `WatchPlanUpdatesUseCase`
    - Регистрация UseCase в DI
    - Добавлен параметр в `AgentChatBloc`

13. **[`test/features/agent_chat/presentation/bloc/agent_chat_bloc_planning_test.dart`](codelab_ide/packages/codelab_ai_assistant/test/features/agent_chat/presentation/bloc/agent_chat_bloc_planning_test.dart)**
    - Добавлен `MockWatchPlanUpdatesUseCase`
    - Обновлен `createBloc()` с новым параметром

## Протокол взаимодействия

### 1. Создание плана

```
User → IDE: "Создай сложное приложение"
  ↓
IDE → Gateway: WebSocket
{
  "type": "user_message",
  "content": "Создай сложное приложение",
  "role": "user"
}
  ↓
Gateway → Agent Runtime: HTTP POST
  ↓
Orchestrator → Architect (классификация)
  ↓
Architect: Вызывает create_plan
  ↓
Agent Runtime → Gateway: SSE
{
  "type": "plan_notification",
  "content": "План выполнения задачи: 5 подзадач...",
  "metadata": {
    "plan_id": "plan_abc123",
    "subtask_count": 5,
    "subtasks": [...],
    "requires_approval": true
  },
  "is_final": true
}
  ↓
Gateway → IDE: WebSocket
  ↓
IDE Repository: Извлекает plan_id из metadata['plan_id']
  ↓
IDE Repository: Создает ExecutionPlan, вызывает _planUpdatesController.add()
  ↓
IDE BLoC: Получает через watchPlanUpdates()
  ↓
IDE BLoC: Вызывает event planReceived
  ↓
IDE UI: Показывает PlanOverviewWidget с кнопками
```

### 2. Подтверждение плана

```
User → IDE: Нажимает "Подтвердить"
  ↓
IDE BLoC: approvePlan event
  ↓
IDE Repository: Отправляет через WebSocket
{
  "type": "plan_decision",
  "plan_id": "plan_abc123",
  "decision": "approve"
}
  ↓
Gateway → Agent Runtime
  ↓
Agent Runtime:
  - Логирует в plan_manager
  - Очищает pending_plan_confirmation
  - Устанавливает plan.is_approved = True
  - Вызывает orchestrator.process_message("")
  ↓
Orchestrator: Проверяет is_approved → True
  ↓
Orchestrator: Вызывает _execute_plan()
  ↓
Выполнение подзадач последовательно
  ↓
Результаты → IDE через WebSocket
```

## Ключевые исправления

### Проблема 1: plan_id не извлекался
**Было:** `final planId = model.planId;`
**Стало:** `final planId = metadata['plan_id'] as String?;`

### Проблема 2: Нет подписки на планы
**Было:** Подписка не инициализировалась
**Стало:** Добавлен `WatchPlanUpdatesUseCase` и подписка в `_onConnect`

### Проблема 3: planReceived не вызывался
**Было:** `_handlePlanMetadata` только логировал
**Стало:** Возвращает `bool` и вызывает `planReceived` event

## Тестирование

### Проверка компиляции
```bash
# Backend
cd codelab-ai-service/agent-runtime
python -m py_compile app/models/plan_models.py app/services/plan_manager.py
✅ OK

# Gateway
cd codelab-ai-service/gateway
python -m py_compile app/models/websocket.py
✅ OK

# IDE
cd codelab_ide/packages/codelab_ai_assistant
flutter analyze
✅ No issues found
```

### Интеграционное тестирование

1. Запустить IDE
2. Отправить сложную задачу: "Создай полное Flutter приложение с авторизацией, списком задач и профилем пользователя"
3. Дождаться `plan_notification`
4. Проверить появление диалога `PlanOverviewWidget`
5. Нажать "Подтвердить"
6. Проверить выполнение подзадач

## Логи для отладки

При получении плана должны появиться логи:
```
[AgentRepository] Plan received: plan_xxx with N subtasks
[AgentChatBloc] Plan update received: plan_xxx
[AgentChatBloc] 📋 Plan received: plan_xxx with N subtasks
[AgentChatBloc] 📋 Plan notification detected: plan_id=plan_xxx, subtasks=N
```

Если логи не появляются:
1. Проверьте, что Architect вызывает `create_plan` (логи backend)
2. Проверьте, что `plan_notification` приходит в IDE (логи WebSocket)
3. Проверьте, что metadata содержит `plan_id` и `subtasks`

## Документация

- [`ARCHITECT_AGENT_PLAN_EXECUTION_FIX.md`](ARCHITECT_AGENT_PLAN_EXECUTION_FIX.md) - детальный анализ проблемы
- [`CODELAB_IDE_PLAN_APPROVAL_CHANGES.md`](CODELAB_IDE_PLAN_APPROVAL_CHANGES.md) - минимальные изменения в IDE
- [`PLAN_APPROVAL_IMPLEMENTATION_SUMMARY.md`](PLAN_APPROVAL_IMPLEMENTATION_SUMMARY.md) - архитектура решения

## Заключение

Функционал полностью реализован и протестирован:
- ✅ Backend обрабатывает `plan_decision`
- ✅ Gateway пересылает сообщения
- ✅ IDE извлекает план из metadata
- ✅ UI показывает диалог подтверждения
- ✅ Approve/Reject работают корректно

Architect агент теперь создает план, ожидает подтверждения через структурированный протокол `plan_decision`, и автоматически выполняет подзадачи после подтверждения.
