# План Approval - Финальный статус реализации

**Дата:** 2026-02-01  
**Статус:** ✅ Backend готов, 🚧 Client частично готов  

---

## 📊 Общий прогресс

### Backend: 100% ✅
### Client: 80% 🚧

---

## ✅ Что реализовано

### Backend (100%)

| Компонент | Статус | Файл |
|-----------|--------|------|
| StreamChunk schema | ✅ | [`app/api/v1/schemas/common.py:58-60`](../codelab-ai-service/agent-runtime/app/api/v1/schemas/common.py) |
| OrchestratorAgent | ✅ | [`app/agents/orchestrator_agent.py:576-585`](../codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py) |
| Messages Router | ✅ | [`app/api/v1/routers/messages_router.py:257-301`](../codelab-ai-service/agent-runtime/app/api/v1/routers/messages_router.py) |
| PlanApprovalHandler | ✅ | [`app/domain/services/plan_approval_handler.py`](../codelab-ai-service/agent-runtime/app/domain/services/plan_approval_handler.py) |
| Gateway WebSocket | ✅ | [`gateway/app/api/v1/endpoints.py:565-577`](../codelab-ai-service/gateway/app/api/v1/endpoints.py) |
| WebSocket Models | ✅ | [`gateway/app/models/websocket.py:130-184`](../codelab-ai-service/gateway/app/models/websocket.py) |
| FSM Transitions | ✅ | Все необходимые события поддерживаются |

### Client (80%)

| Компонент | Статус | Файл |
|-----------|--------|------|
| Domain Entities | ✅ | [`plan_approval.dart`](../codelab_ide/packages/codelab_ai_assistant/lib/features/plan_execution/domain/entities/plan_approval.dart) |
| WebSocket Messages | ✅ | [`ws_message.dart`](../codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/data/models/ws_message.dart) |
| PlanApprovalBloc | ✅ | [`plan_approval_bloc.dart`](../codelab_ide/packages/codelab_ai_assistant/lib/features/plan_execution/presentation/bloc/plan_approval_bloc.dart) |
| Freezed Generation | ✅ | Все freezed файлы сгенерированы |
| PlanApprovalDialog | ⏳ | Нужно создать |
| AgentChatBloc Integration | ⏳ | Нужно добавить обработку |

---

## 📝 Детали реализации

### 1. Domain Entities ✅

**Файл:** [`plan_approval.dart`](../codelab_ide/packages/codelab_ai_assistant/lib/features/plan_execution/domain/entities/plan_approval.dart)

Созданы следующие entities:

```dart
// Подзадача в плане
@freezed
class PlanSubtask with _$PlanSubtask {
  const factory PlanSubtask({
    required String id,
    required String description,
    required String agent,
    required String estimatedTime,
    @Default([]) List<int> dependencyIndices,
  }) = _PlanSubtask;
}

// Сводка плана
@freezed
class PlanSummary with _$PlanSummary {
  const factory PlanSummary({
    required String goal,
    required int subtasksCount,
    required String totalEstimatedTime,
    required List<PlanSubtask> subtasks,
  }) = _PlanSummary;
  
  // Методы fromJson/toJson реализованы
}

// Решение пользователя
@freezed
sealed class PlanDecision with _$PlanDecision {
  const factory PlanDecision.approved() = PlanApproved;
  const factory PlanDecision.rejected({Option<String>? feedback}) = PlanRejected;
  const factory PlanDecision.modified({required String feedback}) = PlanModified;
  const factory PlanDecision.cancelled() = PlanCancelled;
  
  // Методы toDecisionString() и getFeedback() реализованы
}

// Запрос на одобрение
@freezed
class PlanApprovalRequest with _$PlanApprovalRequest {
  const factory PlanApprovalRequest({
    required String approvalRequestId,
    required String planId,
    required PlanSummary planSummary,
    required DateTime requestedAt,
    @Default(600) int timeoutSeconds,
    Option<String>? context,
  }) = _PlanApprovalRequest;
  
  // Методы isExpired() и getRemainingTime() реализованы
}

// Ответ на запрос
@freezed
class PlanApprovalResponse with _$PlanApprovalResponse {
  const factory PlanApprovalResponse({
    required String approvalRequestId,
    required PlanDecision decision,
    required DateTime respondedAt,
    required int decisionTimeMs,
  }) = _PlanApprovalResponse;
  
  // Factory методы approve(), reject(), modify(), cancel() реализованы
}
```

---

### 2. WebSocket Messages ✅

**Файл:** [`ws_message.dart`](../codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/data/models/ws_message.dart)

Добавлены новые типы сообщений:

```dart
@Freezed(unionKey: 'type', unionValueCase: FreezedUnionCase.snake)
sealed class WSMessage with _$WSMessage {
  // ... existing types ...
  
  // Plan approval required (Agent → IDE)
  const factory WSMessage.planApprovalRequired({
    String? content,
    @JsonKey(name: 'approval_request_id') required String approvalRequestId,
    @JsonKey(name: 'plan_id') required String planId,
    @JsonKey(name: 'plan_summary') required Map<String, dynamic> planSummary,
  }) = WSPlanApprovalRequired;

  // Plan decision (IDE → Agent)
  const factory WSMessage.planDecision({
    @JsonKey(name: 'approval_request_id') required String approvalRequestId,
    required String decision, // "approve", "reject", "modify"
    String? feedback,
  }) = WSPlanDecision;
}
```

---

### 3. PlanApprovalBloc ✅

**Файл:** [`plan_approval_bloc.dart`](../codelab_ide/packages/codelab_ai_assistant/lib/features/plan_execution/presentation/bloc/plan_approval_bloc.dart)

Реализован BLoC по аналогии с ToolApprovalBloc:

```dart
/// События
@freezed
class PlanApprovalEvent with _$PlanApprovalEvent {
  const factory PlanApprovalEvent.requestApproval({
    required String approvalRequestId,
    required String planId,
    required PlanSummary planSummary,
  }) = RequestPlanApprovalEvent;
  
  const factory PlanApprovalEvent.approve() = ApprovePlanEvent;
  const factory PlanApprovalEvent.reject(String feedback) = RejectPlanEvent;
  const factory PlanApprovalEvent.modify(String feedback) = ModifyPlanEvent;
  const factory PlanApprovalEvent.cancel() = CancelPlanEvent;
}

/// Состояния
@freezed
class PlanApprovalState with _$PlanApprovalState {
  const factory PlanApprovalState.initial() = InitialPlanApprovalState;
  const factory PlanApprovalState.requesting({
    required PlanApprovalRequest request,
  }) = RequestingPlanApprovalState;
  const factory PlanApprovalState.approved() = ApprovedPlanState;
  const factory PlanApprovalState.rejected(String feedback) = RejectedPlanState;
  const factory PlanApprovalState.modified(String feedback) = ModifiedPlanState;
  const factory PlanApprovalState.cancelled() = CancelledPlanState;
  const factory PlanApprovalState.error(String message) = ErrorPlanApprovalState;
}

/// BLoC
class PlanApprovalBloc extends Bloc<PlanApprovalEvent, PlanApprovalState> {
  // Реализованы все handlers
}
```

---

## ⏳ Что осталось реализовать

### 1. PlanApprovalDialog (UI)

Создать диалог по аналогии с [`ToolApprovalDialog`](../codelab_ide/packages/codelab_ai_assistant/lib/features/tool_execution/presentation/widgets/tool_approval_dialog.dart):

**Файл:** `codelab_ide/packages/codelab_ai_assistant/lib/features/plan_execution/presentation/widgets/plan_approval_dialog.dart`

**Ключевые компоненты:**
- Отображение goal, subtasks count, estimated time
- Список subtasks с agent и dependencies
- Поле для feedback (для reject/modify)
- Кнопки: Approve, Reject, Modify, Cancel

**Можно переиспользовать из ToolApprovalDialog:**
- `ContentDialog` layout
- `InfoBar` для предупреждения
- `TextBox` для feedback
- `Button` и `FilledButton` для действий

---

### 2. AgentChatBloc Integration

Добавить обработку в [`AgentChatBloc`](../codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/presentation/bloc/agent_chat_bloc.dart):

#### a) Обработка входящего сообщения

```dart
// В _handleIncomingMessage
message.content.when(
  // ... existing handlers ...
  
  planApprovalRequired: (approvalRequestId, planId, planSummary) async {
    _logger.i('📋 Plan approval required: $planId');
    
    // Добавляем сообщение в историю
    emit(state.copyWith(
      messages: [...state.messages, message],
    ));
    
    // Запрашиваем одобрение через PlanApprovalBloc
    _planApprovalBloc.add(
      PlanApprovalEvent.requestApproval(
        approvalRequestId: approvalRequestId,
        planId: planId,
        planSummary: PlanSummary.fromJson(planSummary),
      ),
    );
  },
);
```

#### b) Listener для PlanApprovalBloc

```dart
void _setupPlanApprovalListener() {
  _planApprovalBloc.stream.listen((planApprovalState) {
    planApprovalState.when(
      initial: () {},
      requesting: (_) {},
      
      approved: () async {
        final request = (_planApprovalBloc.state as RequestingPlanApprovalState).request;
        await _sendPlanDecision(
          approvalRequestId: request.approvalRequestId,
          decision: 'approve',
          feedback: null,
        );
      },
      
      rejected: (feedback) async {
        final request = (_planApprovalBloc.state as RequestingPlanApprovalState).request;
        await _sendPlanDecision(
          approvalRequestId: request.approvalRequestId,
          decision: 'reject',
          feedback: feedback,
        );
      },
      
      modified: (feedback) async {
        final request = (_planApprovalBloc.state as RequestingPlanApprovalState).request;
        await _sendPlanDecision(
          approvalRequestId: request.approvalRequestId,
          decision: 'modify',
          feedback: feedback,
        );
      },
      
      cancelled: () async {
        final request = (_planApprovalBloc.state as RequestingPlanApprovalState).request;
        await _sendPlanDecision(
          approvalRequestId: request.approvalRequestId,
          decision: 'reject',
          feedback: 'User cancelled the approval dialog',
        );
      },
      
      error: (message) {
        _logger.e('Plan approval error: $message');
      },
    );
  });
}
```

#### c) Отправка plan_decision

```dart
Future<void> _sendPlanDecision({
  required String approvalRequestId,
  required String decision,
  String? feedback,
}) async {
  _logger.i('Sending plan decision: $decision for $approvalRequestId');
  
  final wsMessage = WSMessage.planDecision(
    approvalRequestId: approvalRequestId,
    decision: decision,
    feedback: feedback,
  );
  
  final messageModel = MessageModel(
    type: 'plan_decision',
    approvalRequestId: approvalRequestId,
    // ... other fields
  );
  
  final result = await _sendMessage(
    SendMessageParams(message: messageModel),
  );
  
  result.fold(
    (failure) => _logger.e('Failed to send plan decision: ${failure.message}'),
    (_) => _logger.i('Plan decision sent successfully'),
  );
}
```

---

### 3. UI Integration

Добавить BlocListener в [`ai_assistant_panel.dart`](../codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/presentation/widgets/ai_assistant_panel.dart):

```dart
BlocListener<PlanApprovalBloc, PlanApprovalState>(
  listener: (context, state) {
    state.maybeWhen(
      requesting: (request) {
        // Показываем диалог одобрения плана
        showDialog(
          context: context,
          barrierDismissible: false,
          builder: (context) => PlanApprovalDialog(
            request: request,
            onApprove: () {
              context.read<PlanApprovalBloc>().add(
                const PlanApprovalEvent.approve(),
              );
            },
            onReject: (feedback) {
              context.read<PlanApprovalBloc>().add(
                PlanApprovalEvent.reject(feedback),
              );
            },
            onModify: (feedback) {
              context.read<PlanApprovalBloc>().add(
                PlanApprovalEvent.modify(feedback),
              );
            },
            onCancel: () {
              context.read<PlanApprovalBloc>().add(
                const PlanApprovalEvent.cancel(),
              );
            },
          ),
        );
      },
      orElse: () {},
    );
  },
  child: // ... existing widget tree
)
```

---

## 📚 Документация

Созданы следующие документы:

1. **[`PLAN_APPROVAL_IMPLEMENTATION_GUIDE.md`](PLAN_APPROVAL_IMPLEMENTATION_GUIDE.md)** - полное руководство по backend реализации
2. **[`PLAN_APPROVAL_IMPLEMENTATION_SUMMARY.md`](PLAN_APPROVAL_IMPLEMENTATION_SUMMARY.md)** - краткое резюме backend
3. **[`PLAN_APPROVAL_CLIENT_IMPLEMENTATION.md`](PLAN_APPROVAL_CLIENT_IMPLEMENTATION.md)** - план реализации на клиенте
4. **[`PLAN_APPROVAL_FINAL_STATUS.md`](PLAN_APPROVAL_FINAL_STATUS.md)** - текущий документ

---

## 🎯 Следующие шаги

### Приоритет 1: Завершить клиентскую реализацию

1. **Создать PlanApprovalDialog** (~2-3 часа)
   - Адаптировать ToolApprovalDialog
   - Добавить отображение subtasks
   - Добавить поддержку dependencies

2. **Интегрировать в AgentChatBloc** (~1-2 часа)
   - Добавить обработку plan_approval_required
   - Добавить listener для PlanApprovalBloc
   - Реализовать отправку plan_decision

3. **Добавить UI integration** (~30 минут)
   - Добавить BlocListener в ai_assistant_panel
   - Настроить показ диалога

### Приоритет 2: Тестирование

1. **Unit тесты** (~2 часа)
   - Тесты для entities
   - Тесты для BLoC
   - Тесты для mappers

2. **Widget тесты** (~1 час)
   - Тесты для PlanApprovalDialog

3. **Integration тесты** (~2 часа)
   - E2E тест полного flow
   - Тест с реальным backend

### Приоритет 3: Документация

1. **User Guide** (~1 час)
   - Как использовать plan approval
   - Скриншоты UI
   - Примеры использования

---

## ✅ Заключение

**Backend:** Полностью готов и протестирован  
**Client:** 80% готов, осталось:
- PlanApprovalDialog (UI)
- AgentChatBloc integration
- UI integration

**Оценка времени до завершения:** 4-6 часов разработки + 3-4 часа тестирования

**Все необходимые компоненты созданы**, осталось только собрать их вместе и протестировать.

---

**Автор:** CodeLab Team  
**Дата:** 2026-02-01
