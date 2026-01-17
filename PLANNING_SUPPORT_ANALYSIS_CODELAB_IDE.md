# Анализ поддержки системы планирования в codelab_ide

## Дата анализа
2026-01-15

## Резюме

**Вывод: codelab_ide (codelab_ai_assistant) ПОДДЕРЖИВАЕТ систему планирования, реализованную в agent-runtime**

Приложение имеет полную поддержку всех компонентов системы планирования на уровне моделей данных и протокола WebSocket, но **НЕ имеет UI компонентов** для отображения и взаимодействия с планами.

---

## Детальный анализ

### 1. Поддержка типов сообщений планирования

#### ✅ Реализовано в agent-runtime:
- `plan_notification` - уведомление о создании плана
- `plan_update` - обновление плана (изменение шагов)
- `plan_progress` - прогресс выполнения шага
- `plan_approval` - подтверждение/отклонение плана

#### ✅ Поддержка в codelab_ide:

**Модели WebSocket сообщений** ([`ws_message.dart`](codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/data/models/ws_message.dart)):

```dart
// Уведомление о создании плана
const factory WSMessage.planNotification({
  @JsonKey(name: 'plan_id') required String planId,
  required String content,
  required Map<String, dynamic> metadata,
}) = WSPlanNotification;

// Обновление плана
const factory WSMessage.planUpdate({
  @JsonKey(name: 'plan_id') required String planId,
  required List<Map<String, dynamic>> steps,
  @JsonKey(name: 'current_step') String? currentStep,
}) = WSPlanUpdate;

// Прогресс выполнения
const factory WSMessage.planProgress({
  @JsonKey(name: 'plan_id') required String planId,
  @JsonKey(name: 'step_id') required String stepId,
  String? result,
  required String status,
}) = WSPlanProgress;

// Подтверждение плана
const factory WSMessage.planApproval({
  @JsonKey(name: 'plan_id') required String planId,
  required String decision, // "approve", "reject"
  String? feedback,
}) = WSPlanApproval;
```

**Модели сообщений** ([`message_model.dart`](codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/data/models/message_model.dart)):

```dart
@freezed
class MessageModel with _$MessageModel {
  const factory MessageModel({
    required String type,
    String? content,
    
    // Поля для планирования
    @JsonKey(name: 'plan_id') String? planId,
    List<Map<String, dynamic>>? steps,
    @JsonKey(name: 'current_step') String? currentStep,
    @JsonKey(name: 'step_id') String? stepId,
    String? status,
    String? decision,
    String? feedback,
    
    Map<String, dynamic>? metadata,
  }) = _MessageModel;
}
```

### 2. Маппинг сообщений планирования

**MessageMapper** ([`message_mapper.dart`](codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/data/mappers/message_mapper.dart)) корректно преобразует WebSocket сообщения в domain entities:

```dart
planNotification: (planId, content, metadata) => Message(
  id: messageId,
  role: MessageRole.system,
  content: MessageContent.text(
    text: content,
    isFinal: true,
  ),
  timestamp: DateTime.now(),
  metadata: some({
    'plan_id': planId,
    ...metadata,
  }),
),

planUpdate: (planId, steps, currentStep) => Message(
  // ... аналогично
  metadata: some({
    'plan_id': planId,
    'steps': steps,
    'current_step': currentStep,
  }),
),

planProgress: (planId, stepId, result, status) => Message(
  // ... аналогично
  metadata: some({
    'plan_id': planId,
    'step_id': stepId,
    'result': result,
    'status': status,
  }),
),
```

### 3. Обработка сообщений в BLoC

**AgentChatBloc** ([`agent_chat_bloc.dart`](codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/presentation/bloc/agent_chat_bloc.dart)) получает и обрабатывает все сообщения, включая планирование:

```dart
Future<void> _onMessageReceived(
  MessageReceivedEvent event,
  Emitter<AgentChatState> emit,
) async {
  // Добавляет сообщение в state
  emit(
    state.copyWith(
      messages: [...state.messages, event.message],
      currentAgent: newAgent,
      isLoading: false,
    ),
  );
  
  // Обрабатывает tool calls и другие типы сообщений
}
```

### 4. Форматирование сообщений планирования

**MessageModel** имеет метод для форматирования сообщений планирования:

```dart
String _formatPlanMessage() {
  switch (type) {
    case 'plan_notification':
      return '📋 План: ${content ?? ""}';
    case 'plan_update':
      final stepCount = steps?.length ?? 0;
      return '🔄 Обновление плана: $stepCount шагов';
    case 'plan_progress':
      return '⚙️ Прогресс: шаг $stepId - $status';
    default:
      return content ?? '';
  }
}
```

### 5. Состояния сессии

#### ❌ НЕ реализовано в codelab_ide:

В agent-runtime есть специальные состояния для планирования:
- `PLAN_PENDING_CONFIRMATION` - ожидание подтверждения плана
- `PLAN_EXECUTING` - выполнение плана

В codelab_ide эти состояния **не отслеживаются** на уровне UI. BLoC не имеет специальных полей для состояния планирования:

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
    // ❌ Нет полей для планирования:
    // - Option<ExecutionPlan> activePlan
    // - bool isPlanPendingConfirmation
    // - Option<Subtask> currentSubtask
  }) = _AgentChatState;
}
```

---

## Сравнение с agent-runtime

### Компоненты agent-runtime

| Компонент | Описание | Поддержка в codelab_ide |
|-----------|----------|------------------------|
| **ExecutionPlan** | Модель плана выполнения | ❌ Нет domain entity |
| **Subtask** | Модель подзадачи | ❌ Нет domain entity |
| **SubtaskStatus** | Статусы подзадач (PENDING, IN_PROGRESS, COMPLETED, FAILED, SKIPPED) | ❌ Нет enum |
| **SessionManager.set_plan()** | Сохранение плана в сессии | ❌ Нет аналога |
| **SessionManager.get_plan()** | Получение плана | ❌ Нет аналога |
| **SessionManager.mark_subtask_complete()** | Отметка подзадачи как выполненной | ❌ Нет аналога |
| **SessionManager.get_next_subtask()** | Получение следующей подзадачи | ❌ Нет аналога |
| **create_plan tool** | Инструмент для создания плана | ✅ Сообщения обрабатываются |
| **plan_notification** | Тип сообщения | ✅ Полная поддержка |
| **plan_update** | Тип сообщения | ✅ Полная поддержка |
| **plan_progress** | Тип сообщения | ✅ Полная поддержка |
| **plan_approval** | Тип сообщения | ✅ Полная поддержка |
| **Метаданные прогресса** | В StreamChunk | ✅ Передаются через metadata |

### Типы сообщений

| Тип сообщения | agent-runtime | codelab_ide | Статус |
|---------------|---------------|-------------|--------|
| `plan_notification` | ✅ | ✅ WSPlanNotification | ✅ Полная поддержка |
| `plan_update` | ✅ | ✅ WSPlanUpdate | ✅ Полная поддержка |
| `plan_progress` | ✅ | ✅ WSPlanProgress | ✅ Полная поддержка |
| `plan_approval` | ✅ | ✅ WSPlanApproval | ✅ Полная поддержка |

### Метаданные планирования

agent-runtime отправляет метаданные в StreamChunk:

```python
# При создании плана
{
    "type": "assistant_message",
    "metadata": {
        "plan_id": "plan_abc123",
        "subtask_count": 5,
        "subtasks": [...]
    }
}

# При выполнении подзадачи
{
    "type": "assistant_message",
    "metadata": {
        "subtask_id": "subtask_1",
        "subtask_status": "in_progress",
        "agent": "coder"
    }
}
```

codelab_ide **получает и сохраняет** эти метаданные в `Message.metadata`, но **не использует** их для UI.

---

## Что отсутствует в codelab_ide

### 1. Domain Entities для планирования

Нет моделей:
- `ExecutionPlan` - план выполнения
- `Subtask` - подзадача
- `SubtaskStatus` - статусы подзадач

### 2. UI компоненты

Отсутствуют виджеты для:
- ❌ Отображения плана выполнения
- ❌ Списка подзадач с прогрессом
- ❌ Индикатора текущей подзадачи
- ❌ Визуализации зависимостей между подзадачами
- ❌ Подтверждения/отклонения плана (аналог HITL для планов)

### 3. Состояния планирования в BLoC

BLoC не отслеживает:
- Активный план
- Текущую подзадачу
- Прогресс выполнения плана
- Ожидание подтверждения плана

### 4. Use Cases для планирования

Отсутствуют:
- `ApprovePlanUseCase` - подтверждение плана
- `RejectPlanUseCase` - отклонение плана
- `GetActivePlanUseCase` - получение активного плана

---

## Архитектурные различия

### agent-runtime (Python)

```
Orchestrator Agent
    ↓ (анализирует задачу, определяет сложность)
    ↓ (переключается на Architect для планирования)
Architect Agent
    ↓ (создает план через create_plan tool)
ExecutionPlan
    ↓ (сохраняется в SessionManager)
    ↓ (отправляет plan_notification для подтверждения)
User Confirmation
    ↓ (подтверждает/отклоняет план)
MultiAgentOrchestrator
    ↓ (выполняет подзадачи последовательно)
Specialized Agents (coder, debug, ask)
    ↓ (выполняют подзадачи, отправляют plan_progress)
StreamChunk с метаданными
```

### codelab_ide (Dart/Flutter)

```
WebSocket
    ↓ (получает сообщения)
WSMessage (plan_notification, plan_update, plan_progress)
    ↓ (маппинг)
Message (domain entity)
    ↓ (добавляется в state)
AgentChatBloc
    ↓ (отображается как обычное сообщение)
UI (MessageBubble)
```

**Проблема**: План обрабатывается как обычное текстовое сообщение, без специального UI.

---

## Рекомендации по интеграции

### Минимальная интеграция (быстрая)

1. **Добавить domain entities**:
   ```dart
   // lib/features/agent_chat/domain/entities/execution_plan.dart
   class ExecutionPlan {
     final String planId;
     final String sessionId;
     final String originalTask;
     final List<Subtask> subtasks;
     final int currentSubtaskIndex;
     final bool isComplete;
   }
   
   class Subtask {
     final String id;
     final String description;
     final String agent;
     final String? estimatedTime;
     final SubtaskStatus status;
     final List<String> dependencies;
   }
   
   enum SubtaskStatus {
     pending,
     inProgress,
     completed,
     failed,
     skipped,
   }
   ```

2. **Расширить AgentChatState**:
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

3. **Добавить обработку в BLoC**:
   ```dart
   Future<void> _onMessageReceived(
     MessageReceivedEvent event,
     Emitter<AgentChatState> emit,
   ) async {
     // Проверяем тип сообщения
     if (event.message.metadata.isSome()) {
       event.message.metadata.fold(
         () => null,
         (meta) {
           if (meta.containsKey('plan_id')) {
             // Обрабатываем сообщение планирования
             _handlePlanMessage(event.message, meta, emit);
           }
         },
       );
     }
     
     // ... остальная обработка
   }
   ```

4. **Создать простой UI виджет**:
   ```dart
   class PlanProgressWidget extends StatelessWidget {
     final ExecutionPlan plan;
     
     @override
     Widget build(BuildContext context) {
       return Card(
         child: Column(
           children: [
             Text('📋 План: ${plan.originalTask}'),
             LinearProgressIndicator(
               value: plan.currentSubtaskIndex / plan.subtasks.length,
             ),
             Text('Шаг ${plan.currentSubtaskIndex + 1}/${plan.subtasks.length}'),
             ...plan.subtasks.map((subtask) => 
               SubtaskTile(subtask: subtask)
             ),
           ],
         ),
       );
     }
   }
   ```

### Полная интеграция (рекомендуется)

1. **Domain Layer**:
   - Создать entities: `ExecutionPlan`, `Subtask`, `SubtaskStatus`
   - Создать use cases: `ApprovePlan`, `RejectPlan`, `GetActivePlan`

2. **Data Layer**:
   - Расширить `AgentRepository` методами для работы с планами
   - Добавить маппинг метаданных планирования

3. **Presentation Layer**:
   - Расширить `AgentChatBloc` для управления планами
   - Создать события: `PlanReceived`, `ApprovePlan`, `RejectPlan`
   - Добавить состояния планирования

4. **UI Components**:
   - `PlanOverviewWidget` - обзор плана
   - `SubtaskListWidget` - список подзадач
   - `SubtaskProgressIndicator` - индикатор прогресса
   - `PlanApprovalDialog` - диалог подтверждения плана
   - `PlanTimelineWidget` - временная шкала выполнения

5. **Интеграция с существующим HITL**:
   - Использовать похожий подход как для `ToolApprovalService`
   - Создать `PlanApprovalService` для управления подтверждениями планов

---

## Примеры использования

### Как это работает сейчас

1. Пользователь отправляет сложную задачу: "Migrate from Provider to Riverpod"
2. Orchestrator анализирует задачу и переключается на Architect Agent
3. Architect Agent создает план через `create_plan` tool
4. agent-runtime отправляет `plan_notification` через WebSocket
5. codelab_ide получает сообщение и отображает его как текст: "📋 План: Миграция на Riverpod"
6. Пользователь должен подтвердить план (но UI для этого отсутствует)
7. Подзадачи выполняются, отправляются `plan_progress` сообщения
8. Каждое сообщение отображается как отдельный текстовый пузырь

**Проблема**: Пользователь не видит структуру плана, прогресс, зависимости между задачами. Нет UI для подтверждения плана.

### Как должно работать (с полной интеграцией)

1. Пользователь отправляет задачу
2. Orchestrator переключается на Architect Agent
3. Architect Agent создает план
4. codelab_ide показывает **диалог подтверждения плана**:
   ```
   📋 План миграции на Riverpod
   
   Шаги:
   1. ✓ Добавить зависимость riverpod (2 мин)
   2. ⏳ Создать провайдеры (5 мин)
   3. ⏸️ Обновить main.dart (3 мин)
   4. ⏸️ Мигрировать виджеты (10 мин)
   5. ⏸️ Обновить тесты (5 мин)
   
   Общее время: ~25 минут
   
   [Подтвердить] [Отклонить]
   ```

5. Пользователь подтверждает план (отправляется plan_approval)
6. После подтверждения показывается **виджет прогресса**:
   ```
   📋 Миграция на Riverpod
   ████████░░░░░░░░░░░░ 40% (2/5)
   
   ✅ Добавить зависимость riverpod
   ✅ Создать провайдеры
   ⚙️ Обновить main.dart (выполняется...)
   ⏸️ Мигрировать виджеты
   ⏸️ Обновить тесты
   ```

7. Каждая подзадача обновляется в реальном времени
8. По завершении показывается итоговый отчет

---

## Совместимость протокола

### ✅ Полная совместимость на уровне протокола

codelab_ide **полностью совместим** с протоколом планирования agent-runtime:

- ✅ Все типы сообщений поддерживаются
- ✅ Сериализация/десериализация работает корректно
- ✅ Метаданные передаются и сохраняются
- ✅ WebSocket обработка функционирует

### ❌ Отсутствует UI/UX интеграция

Проблема только в том, что:
- Нет специализированных UI компонентов
- Нет логики управления планами в BLoC
- Нет domain entities для работы с планами

---

## Заключение

**codelab_ide технически поддерживает систему планирования agent-runtime на уровне протокола и моделей данных**, но **не имеет UI/UX компонентов** для полноценной работы с планами.

### Что работает:
✅ Получение сообщений планирования через WebSocket  
✅ Парсинг и десериализация всех типов сообщений  
✅ Сохранение метаданных планирования  
✅ Базовое отображение как текстовых сообщений  

### Что нужно добавить:
❌ Domain entities для планов и подзадач  
❌ UI компоненты для визуализации планов  
❌ Логика управления планами в BLoC  
❌ Диалоги подтверждения/отклонения планов  
❌ Индикаторы прогресса выполнения  

### Приоритет интеграции:
**Средний** - Система планирования работает на backend, но пользователи не получают полноценного UX. Рекомендуется добавить хотя бы минимальную визуализацию планов для улучшения пользовательского опыта.

### Оценка трудозатрат:
- **Минимальная интеграция**: 2-3 дня (базовый UI + domain entities)
- **Полная интеграция**: 1-2 недели (полный UI/UX + все компоненты)
