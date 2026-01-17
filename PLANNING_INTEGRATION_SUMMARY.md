# Итоговый отчет: Интеграция системы планирования в codelab_ide

## Дата: 2026-01-15

---

## 📊 Анализ текущего состояния

### ✅ Что уже работает

#### 1. Backend (agent-runtime)
- **Architect Agent** создает планы через инструмент `create_plan`
- **ExecutionPlan** и **Subtask** модели реализованы
- **SessionManager** управляет планами в памяти
- **MultiAgentOrchestrator** выполняет подзадачи последовательно
- Все типы сообщений планирования работают:
  - `plan_notification` - уведомление о создании плана
  - `plan_update` - обновление плана
  - `plan_progress` - прогресс выполнения
  - `plan_approval` - подтверждение/отклонение

#### 2. Frontend (codelab_ide) - Протокол
- **WebSocket модели** полностью поддерживают планирование:
  - `WSPlanNotification`
  - `WSPlanUpdate`
  - `WSPlanProgress`
  - `WSPlanApproval`
- **MessageMapper** корректно преобразует сообщения
- **Метаданные** планирования передаются и сохраняются

### ❌ Что отсутствует в Frontend

- Domain entities для планов (ExecutionPlan, Subtask)
- Use cases для работы с планами
- Расширение AgentRepository
- Логика управления планами в BLoC
- UI компоненты для визуализации
- Диалоги подтверждения планов

---

## 🎯 Выполненная работа

### 1. Domain Layer ✅

#### Созданы Entity классы:

**[`ExecutionPlan`](codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/domain/entities/execution_plan.dart)**
```dart
class ExecutionPlan {
  final String planId;
  final String sessionId;
  final String originalTask;
  final List<Subtask> subtasks;
  final DateTime createdAt;
  final int currentSubtaskIndex;
  final bool isComplete;
  final bool isPendingConfirmation;
  
  // Методы:
  - approve() - подтвердить план
  - getNextPendingSubtask() - получить следующую подзадачу
  - updateSubtask() - обновить подзадачу
  - markSubtaskInProgress/Completed/Failed() - управление статусами
  - progress - расчет прогресса (0.0-1.0)
  - estimatedTotalTime - оценка времени
}
```

**[`Subtask`](codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/domain/entities/execution_plan.dart)**
```dart
class Subtask {
  final String id;
  final String description;
  final String agent;
  final Option<String> estimatedTime;
  final SubtaskStatus status;
  final Option<String> result;
  final Option<String> error;
  final List<String> dependencies;
  
  // Методы:
  - markInProgress/Completed/Failed/Skipped()
  - areDependenciesMet() - проверка зависимостей
}
```

**[`SubtaskStatus`](codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/domain/entities/execution_plan.dart)**
```dart
enum SubtaskStatus {
  pending,      // ⏸️ Ожидает
  inProgress,   // ⚙️ Выполняется
  completed,    // ✅ Завершена
  failed,       // ❌ Ошибка
  skipped,      // ⏭️ Пропущена
}

// Расширения:
- isFinished, isActive, isPending
- icon, displayName
```

### 2. Use Cases ✅

**[`ApprovePlanUseCase`](codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/domain/usecases/approve_plan.dart)**
- Подтверждение плана пользователем
- Отправка plan_approval с decision="approve"

**[`RejectPlanUseCase`](codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/domain/usecases/reject_plan.dart)**
- Отклонение плана с указанием причины
- Отправка plan_approval с decision="reject"

### 3. Документация ✅

**[`PLANNING_SUPPORT_ANALYSIS_CODELAB_IDE.md`](PLANNING_SUPPORT_ANALYSIS_CODELAB_IDE.md)**
- Детальный анализ поддержки планирования
- Сравнение с agent-runtime
- Архитектурные различия
- Рекомендации по интеграции

**[`PLANNING_INTEGRATION_IMPLEMENTATION_GUIDE.md`](codelab_ide/PLANNING_INTEGRATION_IMPLEMENTATION_GUIDE.md)**
- Пошаговое руководство по реализации
- Готовый код для всех компонентов
- Примеры UI компонентов
- Чеклист реализации

---

## 📋 Что нужно доделать

### Шаг 1: Расширить AgentRepository (2-3 часа)

```dart
// domain/repositories/agent_repository.dart
abstract class AgentRepository {
  // Добавить методы:
  FutureEither<Unit> approvePlan({
    required String planId,
    Option<String> feedback,
  });
  
  FutureEither<Unit> rejectPlan({
    required String planId,
    required String reason,
  });
  
  FutureEither<Option<ExecutionPlan>> getActivePlan();
  
  StreamEither<ExecutionPlan> watchPlanUpdates();
}
```

### Шаг 2: Реализовать в AgentRepositoryImpl (3-4 часа)

```dart
// data/repositories/agent_repository_impl.dart
@override
Future<Either<Failure, Unit>> approvePlan({
  required String planId,
  Option<String> feedback = const None(),
}) async {
  try {
    final message = WSPlanApproval(
      planId: planId,
      decision: 'approve',
      feedback: feedback.getOrElse(() => null),
    );
    
    await _webSocketDataSource.sendMessage(message.toJson());
    return right(unit);
  } catch (e) {
    return left(ServerFailure('Failed to approve plan: $e'));
  }
}

// Аналогично для rejectPlan, getActivePlan, watchPlanUpdates
```

### Шаг 3: Расширить AgentChatBloc (4-5 часов)

#### 3.1 Добавить в State:
```dart
@freezed
abstract class AgentChatState with _$AgentChatState {
  const factory AgentChatState({
    // ... существующие поля
    required Option<ExecutionPlan> activePlan,
    required bool isPlanPendingConfirmation,
  }) = _AgentChatState;
}
```

#### 3.2 Добавить Events:
```dart
const factory AgentChatEvent.planReceived(ExecutionPlan plan) = PlanReceivedEvent;
const factory AgentChatEvent.approvePlan(String planId) = ApprovePlanEvent;
const factory AgentChatEvent.rejectPlan(String planId, String reason) = RejectPlanEvent;
const factory AgentChatEvent.planProgressUpdated(...) = PlanProgressUpdatedEvent;
```

#### 3.3 Реализовать обработчики:
```dart
Future<void> _onPlanReceived(PlanReceivedEvent event, Emitter emit) async {
  emit(state.copyWith(
    activePlan: some(event.plan),
    isPlanPendingConfirmation: event.plan.isPendingConfirmation,
  ));
}

Future<void> _onApprovePlan(ApprovePlanEvent event, Emitter emit) async {
  final result = await _approvePlan(ApprovePlanParams(planId: event.planId));
  // Обработка результата
}

// Аналогично для других событий
```

#### 3.4 Обновить _onMessageReceived:
```dart
// Проверять metadata на наличие информации о плане
event.message.metadata.fold(
  () => null,
  (meta) {
    if (meta.containsKey('plan_id')) {
      _handlePlanMetadata(meta, emit);
    }
  },
);
```

### Шаг 4: Создать UI компоненты с Fluent UI (6-8 часов)

#### 4.1 PlanOverviewWidget

```dart
import 'package:fluent_ui/fluent_ui.dart';

class PlanOverviewWidget extends StatelessWidget {
  final ExecutionPlan plan;
  final VoidCallback? onApprove;
  final ValueChanged<String>? onReject;
  
  @override
  Widget build(BuildContext context) {
    return Card(
      child: Column(
        children: [
          // Заголовок с иконкой
          Row(
            children: [
              Icon(FluentIcons.task_list, size: 32),
              SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('План выполнения', 
                      style: FluentTheme.of(context).typography.title),
                    Text(plan.originalTask,
                      style: FluentTheme.of(context).typography.body),
                  ],
                ),
              ),
            ],
          ),
          
          SizedBox(height: 16),
          
          // Прогресс-бар (если не ожидает подтверждения)
          if (!plan.isPendingConfirmation) ...[
            ProgressBar(value: plan.progress * 100),
            SizedBox(height: 8),
            Text('${plan.completedCount}/${plan.totalCount} подзадач завершено'),
            SizedBox(height: 16),
          ],
          
          // Список подзадач
          ...plan.subtasks.asMap().entries.map((entry) {
            return SubtaskTile(
              subtask: entry.value,
              index: entry.key + 1,
            );
          }),
          
          // Оценка времени
          plan.estimatedTotalTime.fold(
            () => SizedBox.shrink(),
            (time) => Text('Оценка времени: $time'),
          ),
          
          // Кнопки подтверждения
          if (plan.isPendingConfirmation) ...[
            SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                Button(
                  onPressed: () => _showRejectDialog(context),
                  child: Text('Отклонить'),
                ),
                SizedBox(width: 8),
                FilledButton(
                  onPressed: onApprove,
                  child: Text('Подтвердить'),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
  
  void _showRejectDialog(BuildContext context) {
    final controller = TextEditingController();
    
    showDialog(
      context: context,
      builder: (context) => ContentDialog(
        title: Text('Отклонить план'),
        content: TextBox(
          controller: controller,
          placeholder: 'Укажите причину отклонения',
          maxLines: 3,
        ),
        actions: [
          Button(
            onPressed: () => Navigator.pop(context),
            child: Text('Отмена'),
          ),
          FilledButton(
            onPressed: () {
              final reason = controller.text.trim();
              if (reason.isNotEmpty) {
                onReject?.call(reason);
                Navigator.pop(context);
              }
            },
            child: Text('Отклонить'),
          ),
        ],
      ),
    );
  }
}
```

#### 4.2 SubtaskTile

```dart
class SubtaskTile extends StatelessWidget {
  final Subtask subtask;
  final int index;
  
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.symmetric(vertical: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Иконка статуса
          Text(subtask.status.icon, style: TextStyle(fontSize: 20)),
          SizedBox(width: 12),
          
          // Содержимое
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Описание
                Text(
                  '$index. ${subtask.description}',
                  style: TextStyle(
                    fontWeight: subtask.status.isActive 
                      ? FontWeight.bold 
                      : FontWeight.normal,
                    decoration: subtask.status == SubtaskStatus.completed
                      ? TextDecoration.lineThrough
                      : null,
                  ),
                ),
                
                SizedBox(height: 4),
                
                // Метаданные
                Wrap(
                  spacing: 8,
                  children: [
                    // Агент
                    InfoLabel(
                      label: 'Агент',
                      child: Text(subtask.agent),
                    ),
                    
                    // Время
                    subtask.estimatedTime.fold(
                      () => SizedBox.shrink(),
                      (time) => InfoLabel(
                        label: 'Время',
                        child: Text(time),
                      ),
                    ),
                    
                    // Статус
                    InfoLabel(
                      label: 'Статус',
                      child: Text(subtask.status.displayName),
                    ),
                  ],
                ),
                
                // Ошибка
                subtask.error.fold(
                  () => SizedBox.shrink(),
                  (error) => Padding(
                    padding: EdgeInsets.only(top: 8),
                    child: Text(
                      'Ошибка: $error',
                      style: TextStyle(
                        color: Colors.red,
                        fontSize: 12,
                      ),
                    ),
                  ),
                ),
                
                // Зависимости
                if (subtask.dependencies.isNotEmpty)
                  Padding(
                    padding: EdgeInsets.only(top: 4),
                    child: Text(
                      'Зависит от: ${subtask.dependencies.join(", ")}',
                      style: TextStyle(fontSize: 12),
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
```

#### 4.3 PlanProgressIndicator

```dart
class PlanProgressIndicator extends StatelessWidget {
  final ExecutionPlan plan;
  final VoidCallback? onTap;
  
  @override
  Widget build(BuildContext context) {
    return Button(
      onPressed: onTap,
      child: Container(
        padding: EdgeInsets.all(12),
        child: Row(
          children: [
            Icon(FluentIcons.task_list),
            SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Выполнение плана',
                    style: FluentTheme.of(context).typography.bodyStrong),
                  SizedBox(height: 4),
                  ProgressBar(value: plan.progress * 100),
                  SizedBox(height: 4),
                  Text('${plan.completedCount}/${plan.totalCount} подзадач',
                    style: FluentTheme.of(context).typography.caption),
                ],
              ),
            ),
            Icon(FluentIcons.chevron_right),
          ],
        ),
      ),
    );
  }
}
```

### Шаг 5: Интегрировать с ChatScreen (2-3 часа)

```dart
// presentation/pages/chat_screen.dart

@override
Widget build(BuildContext context) {
  return BlocBuilder<AgentChatBloc, AgentChatState>(
    builder: (context, state) {
      return Column(
        children: [
          // Индикатор активного плана
          state.activePlan.fold(
            () => SizedBox.shrink(),
            (plan) {
              if (plan.isPendingConfirmation) {
                // Показать полный обзор для подтверждения
                return PlanOverviewWidget(
                  plan: plan,
                  onApprove: () => context.read<AgentChatBloc>().add(
                    AgentChatEvent.approvePlan(plan.planId),
                  ),
                  onReject: (reason) => context.read<AgentChatBloc>().add(
                    AgentChatEvent.rejectPlan(plan.planId, reason),
                  ),
                );
              } else if (!plan.isComplete) {
                // Показать компактный индикатор
                return PlanProgressIndicator(
                  plan: plan,
                  onTap: () => _showPlanDetails(context, plan),
                );
              }
              return SizedBox.shrink();
            },
          ),
          
          // Список сообщений
          Expanded(
            child: MessageList(messages: state.messages),
          ),
          
          // Поле ввода
          MessageInput(
            onSend: (text) => context.read<AgentChatBloc>().add(
              AgentChatEvent.sendMessage(text),
            ),
          ),
        ],
      );
    },
  );
}

void _showPlanDetails(BuildContext context, ExecutionPlan plan) {
  showDialog(
    context: context,
    builder: (context) => ContentDialog(
      constraints: BoxConstraints(maxWidth: 600, maxHeight: 800),
      content: SingleChildScrollView(
        child: PlanOverviewWidget(plan: plan),
      ),
      actions: [
        Button(
          onPressed: () => Navigator.pop(context),
          child: Text('Закрыть'),
        ),
      ],
    ),
  );
}
```

### Шаг 6: Обновить Dependency Injection (1-2 часа)

```dart
// ai_assistent_module.dart

@module
abstract class AiAssistentModule {
  // Use cases для планирования
  @singleton
  ApprovePlanUseCase provideApprovePlanUseCase(AgentRepository repository) =>
      ApprovePlanUseCase(repository);
  
  @singleton
  RejectPlanUseCase provideRejectPlanUseCase(AgentRepository repository) =>
      RejectPlanUseCase(repository);
  
  @singleton
  GetActivePlanUseCase provideGetActivePlanUseCase(AgentRepository repository) =>
      GetActivePlanUseCase(repository);
  
  // Обновить AgentChatBloc
  @singleton
  AgentChatBloc provideAgentChatBloc(
    // ... существующие параметры
    ApprovePlanUseCase approvePlan,
    RejectPlanUseCase rejectPlan,
    GetActivePlanUseCase getActivePlan,
    Logger logger,
  ) =>
      AgentChatBloc(
        // ... существующие параметры
        approvePlan: approvePlan,
        rejectPlan: rejectPlan,
        getActivePlan: getActivePlan,
        logger: logger,
      );
}
```

### Шаг 7: Добавить тесты (4-6 часов)

#### 7.1 Тесты для ExecutionPlan
```dart
// test/features/agent_chat/domain/entities/execution_plan_test.dart
void main() {
  group('ExecutionPlan', () {
    test('should create plan with pending subtasks', () { ... });
    test('should calculate progress correctly', () { ... });
    test('should mark subtask as completed', () { ... });
    test('should handle dependencies', () { ... });
  });
}
```

#### 7.2 Тесты для Use Cases
```dart
// test/features/agent_chat/domain/usecases/approve_plan_test.dart
void main() {
  group('ApprovePlanUseCase', () {
    test('should approve plan through repository', () { ... });
    test('should handle errors', () { ... });
  });
}
```

#### 7.3 Тесты для BLoC
```dart
// test/features/agent_chat/presentation/bloc/agent_chat_bloc_test.dart
void main() {
  group('AgentChatBloc - Planning', () {
    test('should handle plan received event', () { ... });
    test('should approve plan', () { ... });
    test('should reject plan', () { ... });
    test('should update plan progress', () { ... });
  });
}
```

---

## ⏱️ Оценка трудозатрат

| Задача | Время | Приоритет |
|--------|-------|-----------|
| Расширить AgentRepository | 2-3 часа | Высокий |
| Реализовать в AgentRepositoryImpl | 3-4 часа | Высокий |
| Расширить AgentChatBloc | 4-5 часов | Высокий |
| Создать UI компоненты (Fluent UI) | 6-8 часов | Средний |
| Интегрировать с ChatScreen | 2-3 часа | Средний |
| Обновить DI | 1-2 часа | Средний |
| Добавить тесты | 4-6 часов | Низкий |
| **ИТОГО** | **22-31 час** | |

---

## 🎯 Рекомендации по реализации

### Порядок выполнения:

1. **День 1 (6-8 часов)**:
   - Расширить AgentRepository
   - Реализовать методы в AgentRepositoryImpl
   - Создать GetActivePlanUseCase

2. **День 2 (6-8 часов)**:
   - Расширить AgentChatBloc (State, Events)
   - Реализовать обработчики событий
   - Обновить _onMessageReceived

3. **День 3 (6-8 часов)**:
   - Создать UI компоненты с Fluent UI
   - PlanOverviewWidget
   - SubtaskTile
   - PlanProgressIndicator

4. **День 4 (4-6 часов)**:
   - Интегрировать с ChatScreen
   - Обновить DI
   - Тестирование интеграции

5. **День 5 (опционально, 4-6 часов)**:
   - Добавить unit тесты
   - Добавить widget тесты
   - Документация

### Критические моменты:

1. **Обработка метаданных**: Правильно парсить metadata из WebSocket сообщений
2. **Состояние плана**: Синхронизировать состояние между сервером и клиентом
3. **UI/UX**: Обеспечить интуитивный интерфейс для подтверждения планов
4. **Ошибки**: Обрабатывать все возможные ошибки (сеть, парсинг, и т.д.)

---

## 📚 Ключевые файлы

### Созданные:
- ✅ [`execution_plan.dart`](codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/domain/entities/execution_plan.dart)
- ✅ [`approve_plan.dart`](codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/domain/usecases/approve_plan.dart)
- ✅ [`reject_plan.dart`](codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/domain/usecases/reject_plan.dart)
- ✅ [`PLANNING_SUPPORT_ANALYSIS_CODELAB_IDE.md`](PLANNING_SUPPORT_ANALYSIS_CODELAB_IDE.md)
- ✅ [`PLANNING_INTEGRATION_IMPLEMENTATION_GUIDE.md`](codelab_ide/PLANNING_INTEGRATION_IMPLEMENTATION_GUIDE.md)

### Требуют изменений:
- ⏳ `agent_repository.dart` - добавить методы для планов
- ⏳ `agent_repository_impl.dart` - реализовать методы
- ⏳ `agent_chat_bloc.dart` - расширить для планирования
- ⏳ `chat_screen.dart` - интегрировать UI планов
- ⏳ `ai_assistent_module.dart` - обновить DI

### Нужно создать:
- ⏳ `get_active_plan.dart` - use case
- ⏳ `plan_overview_widget.dart` - UI компонент
- ⏳ `subtask_tile.dart` - UI компонент
- ⏳ `plan_progress_indicator.dart` - UI компонент
- ⏳ Тесты для всех компонентов

---

## 🚀 Следующие шаги

1. Начать с расширения AgentRepository (самый критичный компонент)
2. Реализовать методы в AgentRepositoryImpl
3. Расширить AgentChatBloc для управления планами
4. Создать UI компоненты с Fluent UI
5. Интегрировать все компоненты
6. Протестировать end-to-end

---

## 📞 Поддержка

Все необходимые инструкции и примеры кода находятся в:
- [`PLANNING_INTEGRATION_IMPLEMENTATION_GUIDE.md`](codelab_ide/PLANNING_INTEGRATION_IMPLEMENTATION_GUIDE.md)

При возникновении вопросов обращайтесь к документации agent-runtime:
- [`PLANNING_SYSTEM_GUIDE.md`](codelab-ai-service/agent-runtime/PLANNING_SYSTEM_GUIDE.md)
