# Статус интеграции системы планирования в codelab_ide

## Дата: 2026-01-15
## Статус: Частично реализовано (30% завершено)

---

## ✅ Полностью реализовано

### 1. Анализ и документация
- ✅ [`PLANNING_SUPPORT_ANALYSIS_CODELAB_IDE.md`](PLANNING_SUPPORT_ANALYSIS_CODELAB_IDE.md) - полный анализ
- ✅ [`PLANNING_INTEGRATION_IMPLEMENTATION_GUIDE.md`](codelab_ide/PLANNING_INTEGRATION_IMPLEMENTATION_GUIDE.md) - руководство
- ✅ [`PLANNING_INTEGRATION_SUMMARY.md`](PLANNING_INTEGRATION_SUMMARY.md) - итоговый отчет

### 2. Domain Layer (Clean Architecture)
- ✅ [`ExecutionPlan`](codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/domain/entities/execution_plan.dart) entity
- ✅ [`Subtask`](codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/domain/entities/execution_plan.dart) entity
- ✅ [`SubtaskStatus`](codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/domain/entities/execution_plan.dart) enum
- ✅ Freezed code generation выполнена

### 3. Use Cases
- ✅ [`ApprovePlanUseCase`](codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/domain/usecases/approve_plan.dart)
- ✅ [`RejectPlanUseCase`](codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/domain/usecases/reject_plan.dart)

### 4. Repository Interface
- ✅ [`AgentRepository`](codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/domain/repositories/agent_repository.dart) расширен методами:
  - `approvePlan()`
  - `rejectPlan()`
  - `getActivePlan()`
  - `watchPlanUpdates()`

---

## ⏳ Требует реализации

### Критический приоритет (необходимо для работы)

#### 1. GetActivePlanUseCase
**Файл**: `lib/features/agent_chat/domain/usecases/get_active_plan.dart`

```dart
import 'package:fpdart/fpdart.dart';
import '../../../../core/error/failures.dart';
import '../../../../core/usecases/usecase.dart';
import '../entities/execution_plan.dart';
import '../repositories/agent_repository.dart';

class GetActivePlanUseCase implements UseCase<Option<ExecutionPlan>, NoParams> {
  final AgentRepository _repository;
  
  const GetActivePlanUseCase(this._repository);
  
  @override
  Future<Either<Failure, Option<ExecutionPlan>>> call(NoParams params) async {
    return _repository.getActivePlan();
  }
}
```

#### 2. AgentRepositoryImpl - реализация методов планирования
**Файл**: `lib/features/agent_chat/data/repositories/agent_repository_impl.dart`

Необходимо добавить:

```dart
// Поле для хранения активного плана
Option<ExecutionPlan> _activePlan = none();
final _planUpdatesController = StreamController<Either<Failure, ExecutionPlan>>.broadcast();

@override
Future<Either<Failure, Unit>> approvePlan({
  required String planId,
  Option<String> feedback = const None(),
}) async {
  try {
    final message = {
      'type': 'plan_approval',
      'plan_id': planId,
      'decision': 'approve',
      'feedback': feedback.getOrElse(() => null),
    };
    
    // Отправить через WebSocket
    _webSocketDataSource.send(jsonEncode(message));
    
    // Обновить локальное состояние
    _activePlan.fold(
      () => null,
      (plan) {
        _activePlan = some(plan.approve());
      },
    );
    
    return right(unit);
  } catch (e) {
    return left(ServerFailure('Failed to approve plan: $e'));
  }
}

@override
Future<Either<Failure, Unit>> rejectPlan({
  required String planId,
  required String reason,
}) async {
  try {
    final message = {
      'type': 'plan_approval',
      'plan_id': planId,
      'decision': 'reject',
      'feedback': reason,
    };
    
    _webSocketDataSource.send(jsonEncode(message));
    
    // Очистить активный план
    _activePlan = none();
    
    return right(unit);
  } catch (e) {
    return left(ServerFailure('Failed to reject plan: $e'));
  }
}

@override
Future<Either<Failure, Option<ExecutionPlan>>> getActivePlan() async {
  return right(_activePlan);
}

@override
StreamEither<ExecutionPlan> watchPlanUpdates() {
  return _planUpdatesController.stream;
}

// В методе _handleWebSocketMessage добавить обработку сообщений планирования:
void _handleWebSocketMessage(dynamic data) {
  // ... существующий код
  
  final messageType = data['type'] as String?;
  
  if (messageType == 'plan_notification') {
    _handlePlanNotification(data);
  } else if (messageType == 'plan_update') {
    _handlePlanUpdate(data);
  } else if (messageType == 'plan_progress') {
    _handlePlanProgress(data);
  }
}

void _handlePlanNotification(Map<String, dynamic> data) {
  try {
    final planId = data['plan_id'] as String;
    final metadata = data['metadata'] as Map<String, dynamic>?;
    
    if (metadata != null && metadata.containsKey('subtasks')) {
      final subtasksData = metadata['subtasks'] as List<dynamic>;
      final subtasks = subtasksData.map((st) {
        final stMap = st as Map<String, dynamic>;
        return Subtask.pending(
          id: stMap['id'] as String,
          description: stMap['description'] as String,
          agent: stMap['agent'] as String,
          estimatedTime: stMap['estimated_time'] != null
              ? some(stMap['estimated_time'] as String)
              : none(),
          dependencies: (stMap['dependencies'] as List<dynamic>?)
                  ?.map((d) => d as String)
                  .toList() ??
              [],
        );
      }).toList();
      
      final plan = ExecutionPlan.create(
        planId: planId,
        sessionId: _currentSessionId ?? '',
        originalTask: metadata['original_task'] as String? ?? '',
        subtasks: subtasks,
      );
      
      _activePlan = some(plan);
      _planUpdatesController.add(right(plan));
    }
  } catch (e) {
    _planUpdatesController.add(left(ServerFailure('Failed to parse plan: $e')));
  }
}

void _handlePlanProgress(Map<String, dynamic> data) {
  try {
    final planId = data['plan_id'] as String;
    final stepId = data['step_id'] as String;
    final statusStr = data['status'] as String;
    
    _activePlan.fold(
      () => null,
      (plan) {
        if (plan.planId != planId) return;
        
        ExecutionPlan updatedPlan;
        
        switch (statusStr) {
          case 'in_progress':
            updatedPlan = plan.markSubtaskInProgress(stepId);
            break;
          case 'completed':
            updatedPlan = plan.markSubtaskCompleted(stepId);
            break;
          case 'failed':
            final error = data['error'] as String? ?? 'Unknown error';
            updatedPlan = plan.markSubtaskFailed(stepId, error);
            break;
          default:
            updatedPlan = plan;
        }
        
        _activePlan = some(updatedPlan);
        _planUpdatesController.add(right(updatedPlan));
      },
    );
  } catch (e) {
    _planUpdatesController.add(left(ServerFailure('Failed to update plan progress: $e')));
  }
}
```

### Высокий приоритет

#### 3. AgentChatBloc - расширение для планирования

**Изменения в State**:
```dart
@freezed
abstract class AgentChatState with _$AgentChatState {
  const factory AgentChatState({
    required List<Message> messages,
    required bool isLoading,
    required bool isConnected,
    required String currentAgent,
    required Option<String> error,
    required Option<ApprovalRequestWithCompleter> pendingApproval,
    required Option<ExecutionPlan> activePlan,  // НОВОЕ
    required bool isPlanPendingConfirmation,     // НОВОЕ
  }) = _AgentChatState;

  factory AgentChatState.initial() => AgentChatState(
    messages: const [],
    isLoading: false,
    isConnected: false,
    currentAgent: AgentType.orchestrator,
    error: none(),
    pendingApproval: none(),
    activePlan: none(),                          // НОВОЕ
    isPlanPendingConfirmation: false,            // НОВОЕ
  );
}
```

**Новые события**:
```dart
@freezed
class AgentChatEvent with _$AgentChatEvent {
  // ... существующие события
  
  const factory AgentChatEvent.planReceived(ExecutionPlan plan) = PlanReceivedEvent;
  const factory AgentChatEvent.approvePlan(String planId) = ApprovePlanEvent;
  const factory AgentChatEvent.rejectPlan(String planId, String reason) = RejectPlanEvent;
  const factory AgentChatEvent.planProgressUpdated(
    String planId,
    String subtaskId,
    SubtaskStatus status,
  ) = PlanProgressUpdatedEvent;
}
```

**Обработчики событий** - см. [`PLANNING_INTEGRATION_IMPLEMENTATION_GUIDE.md`](codelab_ide/PLANNING_INTEGRATION_IMPLEMENTATION_GUIDE.md) раздел "Шаг 3.3"

### Средний приоритет

#### 4. UI компоненты (Fluent UI)

Создать файлы:
- `lib/features/agent_chat/presentation/widgets/plan_overview_widget.dart`
- `lib/features/agent_chat/presentation/widgets/subtask_tile.dart`
- `lib/features/agent_chat/presentation/widgets/plan_progress_indicator.dart`

Полный код в [`PLANNING_INTEGRATION_SUMMARY.md`](PLANNING_INTEGRATION_SUMMARY.md) раздел "Шаг 4"

#### 5. Интеграция с ChatScreen

Обновить `lib/features/agent_chat/presentation/pages/chat_screen.dart` - см. [`PLANNING_INTEGRATION_SUMMARY.md`](PLANNING_INTEGRATION_SUMMARY.md) раздел "Шаг 5"

#### 6. Dependency Injection

Обновить `lib/ai_assistent_module.dart` - см. [`PLANNING_INTEGRATION_SUMMARY.md`](PLANNING_INTEGRATION_SUMMARY.md) раздел "Шаг 6"

### Низкий приоритет

#### 7. Тесты

- Unit тесты для ExecutionPlan
- Unit тесты для Use Cases
- Unit тесты для BLoC
- Widget тесты для UI компонентов

---

## 📊 Прогресс реализации

| Компонент | Статус | Прогресс |
|-----------|--------|----------|
| Анализ и документация | ✅ Завершено | 100% |
| Domain Entities | ✅ Завершено | 100% |
| Use Cases (2/3) | ⏳ Частично | 67% |
| Repository Interface | ✅ Завершено | 100% |
| Repository Implementation | ❌ Не начато | 0% |
| BLoC расширение | ❌ Не начато | 0% |
| UI компоненты | ❌ Не начато | 0% |
| Интеграция | ❌ Не начато | 0% |
| DI | ❌ Не начато | 0% |
| Тесты | ❌ Не начато | 0% |
| **ОБЩИЙ ПРОГРЕСС** | | **30%** |

---

## ⏱️ Оставшееся время

| Задача | Оценка |
|--------|--------|
| GetActivePlanUseCase | 30 мин |
| AgentRepositoryImpl | 3-4 часа |
| AgentChatBloc | 4-5 часов |
| UI компоненты | 6-8 часов |
| Интеграция | 2-3 часа |
| DI | 1-2 часа |
| Тесты | 4-6 часов |
| **ИТОГО** | **20-28 часов** |

---

## 🎯 Следующие шаги

### Немедленно:
1. Создать `GetActivePlanUseCase` (30 мин)
2. Реализовать методы в `AgentRepositoryImpl` (3-4 часа)
3. Запустить build_runner для генерации BLoC кода

### Затем:
4. Расширить `AgentChatBloc` (4-5 часов)
5. Создать UI компоненты (6-8 часов)
6. Интегрировать все части (2-3 часа)

### В конце:
7. Обновить DI (1-2 часа)
8. Добавить тесты (4-6 часов)

---

## 📚 Ключевые документы

1. **Для продолжения разработки**:
   - [`PLANNING_INTEGRATION_IMPLEMENTATION_GUIDE.md`](codelab_ide/PLANNING_INTEGRATION_IMPLEMENTATION_GUIDE.md) - детальные инструкции
   - [`PLANNING_INTEGRATION_SUMMARY.md`](PLANNING_INTEGRATION_SUMMARY.md) - готовый код

2. **Для понимания архитектуры**:
   - [`PLANNING_SUPPORT_ANALYSIS_CODELAB_IDE.md`](PLANNING_SUPPORT_ANALYSIS_CODELAB_IDE.md) - технический анализ
   - [`agent-runtime/PLANNING_SYSTEM_GUIDE.md`](codelab-ai-service/agent-runtime/PLANNING_SYSTEM_GUIDE.md) - backend документация

---

## ✅ Что уже работает

### Backend (agent-runtime)
- ✅ Architect Agent создает планы
- ✅ Все типы сообщений планирования
- ✅ SessionManager управляет планами
- ✅ MultiAgentOrchestrator выполняет подзадачи

### Frontend (codelab_ide)
- ✅ WebSocket протокол поддерживает планирование
- ✅ Domain entities созданы
- ✅ Repository interface расширен
- ✅ Use cases созданы (2/3)

### Что НЕ работает
- ❌ Отправка plan_approval на сервер
- ❌ Получение и обработка plan_notification
- ❌ Отображение планов в UI
- ❌ Подтверждение/отклонение планов пользователем

---

## 🔧 Быстрый старт для продолжения

```bash
# 1. Создать GetActivePlanUseCase
touch codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/domain/usecases/get_active_plan.dart

# 2. Открыть AgentRepositoryImpl
code codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/data/repositories/agent_repository_impl.dart

# 3. Добавить методы из этого документа (раздел "AgentRepositoryImpl")

# 4. Запустить build_runner
cd codelab_ide/packages/codelab_ai_assistant
dart run build_runner build --delete-conflicting-outputs

# 5. Продолжить с AgentChatBloc
```

---

## 📞 Контакты и поддержка

При возникновении вопросов:
1. Проверьте [`PLANNING_INTEGRATION_IMPLEMENTATION_GUIDE.md`](codelab_ide/PLANNING_INTEGRATION_IMPLEMENTATION_GUIDE.md)
2. Изучите примеры кода в [`PLANNING_INTEGRATION_SUMMARY.md`](PLANNING_INTEGRATION_SUMMARY.md)
3. Обратитесь к backend документации [`PLANNING_SYSTEM_GUIDE.md`](codelab-ai-service/agent-runtime/PLANNING_SYSTEM_GUIDE.md)

---

**Последнее обновление**: 2026-01-15 14:12 UTC
**Автор**: AI Assistant
**Версия**: 1.0
