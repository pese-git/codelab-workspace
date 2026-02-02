# Plan Approval - Реализация на стороне Flutter клиента

**Дата:** 2026-02-01  
**Статус:** ✅ Базовая интеграция завершена  
**Следующий шаг:** UI компонент для диалога approval

---

## 📋 Выполненные изменения

### 1. ✅ Добавлены типы WebSocket сообщений

**Файл:** [`ws_message.dart`](../codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/data/models/ws_message.dart:97-116)

```dart
const factory WSMessage.planApprovalRequired({
  String? content,
  @JsonKey(name: 'approval_request_id') required String approvalRequestId,
  @JsonKey(name: 'plan_id') required String planId,
  @JsonKey(name: 'plan_summary') required Map<String, dynamic> planSummary,
}) = WSPlanApprovalRequired;

const factory WSMessage.planDecision({
  @JsonKey(name: 'approval_request_id') required String approvalRequestId,
  @JsonKey(name: 'plan_id') required String planId,
  required String decision, // "approve", "reject", "modify"
  String? feedback,
  @JsonKey(name: 'modification_request') String? modificationRequest,
}) = WSPlanDecision;
```

**Результат:** Freezed код сгенерирован успешно ✅

---

### 2. ✅ Добавлен тип MessageContent для Plan Approval

**Файл:** [`message.dart`](../codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/domain/entities/message.dart:91-97)

```dart
/// Запрос на одобрение плана
const factory MessageContent.planApprovalRequired({
  required String approvalRequestId,
  required String planId,
  required Map<String, dynamic> planSummary,
  String? content,
}) = PlanApprovalRequiredMessageContent;
```

**Результат:** Domain entity обновлена ✅

---

### 3. ✅ Обновлен MessageMapper

**Файл:** [`message_mapper.dart`](../codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/data/mappers/message_mapper.dart)

#### Добавлена конвертация Domain → WS:
```dart
planApprovalRequired: (approvalRequestId, planId, planSummary, content) =>
  WSMessage.planApprovalRequired(
    approvalRequestId: approvalRequestId,
    planId: planId,
    planSummary: planSummary,
    content: content,
  ),
```

#### Добавлена конвертация WS → Domain:
```dart
planApprovalRequired: (content, approvalRequestId, planId, planSummary) => Message(
  id: messageId,
  role: MessageRole.system,
  content: MessageContent.planApprovalRequired(
    approvalRequestId: approvalRequestId,
    planId: planId,
    planSummary: planSummary,
    content: content,
  ),
  timestamp: timestamp,
  metadata: some({
    'approval_request_id': approvalRequestId,
    'plan_id': planId,
    'plan_summary': planSummary,
  }),
),
```

**Результат:** Маппинг настроен ✅

---

## 📊 Структура plan_summary

Согласно backend ([`orchestrator_agent.py:534`](../codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py:534)):

```dart
{
  "goal": "Create Flutter login form with validation",
  "subtasks_count": 4,
  "total_estimated_time": "20 min",
  "subtasks": [
    {
      "id": "subtask-uuid-1",
      "description": "Create login form widget",
      "agent": "coder",
      "estimated_time": "5 min",
      "dependencies": [],
      "metadata": {
        "index": 0,
        "dependency_indices": []
      }
    },
    // ... остальные subtasks
  ]
}
```

---

## 🔄 Workflow обработки Plan Approval

### Backend → Client:

1. **Backend** ([`orchestrator_agent.py:576-585`](../codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py:576-585)):
   ```python
   yield StreamChunk(
       type="plan_approval_required",
       content="Plan requires your approval before execution",
       approval_request_id=approval_request_id,
       plan_id=plan_id,
       plan_summary=plan_summary,
       metadata={"fsm_state": FSMState.PLAN_REVIEW.value}
   )
   ```

2. **Gateway** → **WebSocket** → **Client**

3. **Client Data Layer** ([`message_mapper.dart`](../codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/data/mappers/message_mapper.dart)):
   - Получает `WSMessage.planApprovalRequired`
   - Конвертирует в `Message` с `MessageContent.planApprovalRequired`

4. **Client Presentation Layer** ([`agent_chat_bloc.dart`](../codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/presentation/bloc/agent_chat_bloc.dart)):
   - Получает `Message` через `MessageReceivedEvent`
   - Добавляет в `state.messages`
   - **TODO:** Показать UI диалог для approval

### Client → Backend:

1. **User** нажимает Approve/Reject/Modify в UI

2. **Client** отправляет `WSMessage.planDecision`:
   ```dart
   WSMessage.planDecision(
     approvalRequestId: approvalRequestId,
     planId: planId,
     decision: "approve", // или "reject", "modify"
     feedback: userFeedback,
     modificationRequest: modificationText,
   )
   ```

3. **Gateway** → **Backend** ([`plan_approval_handler.py`](../codelab-ai-service/agent-runtime/app/domain/services/plan_approval_handler.py))

4. **Backend** обрабатывает решение и переходит в соответствующее FSM состояние

---

## 🎯 Следующие шаги

### 1. ⏳ Создать UI компонент для Plan Approval диалога

**Требования:**
- Показывать `plan_summary` (goal, subtasks, estimated time)
- Кнопки: Approve, Reject, Modify
- Поле для feedback/modification request
- Визуализация зависимостей между subtasks

**Пример структуры:**

```dart
// lib/features/agent_chat/presentation/widgets/plan_approval_dialog.dart

class PlanApprovalDialog extends StatelessWidget {
  final String approvalRequestId;
  final String planId;
  final Map<String, dynamic> planSummary;
  final Function(String decision, String? feedback) onDecision;

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text('📋 Plan Approval Required'),
      content: Column(
        children: [
          // Goal
          Text('Goal: ${planSummary['goal']}'),
          
          // Subtasks
          Text('Subtasks: ${planSummary['subtasks_count']}'),
          Text('Estimated Time: ${planSummary['total_estimated_time']}'),
          
          // Subtasks list
          ...planSummary['subtasks'].map((subtask) => 
            ListTile(
              title: Text(subtask['description']),
              subtitle: Text('${subtask['agent']} - ${subtask['estimated_time']}'),
            )
          ),
          
          // Feedback field
          TextField(
            decoration: InputDecoration(labelText: 'Feedback (optional)'),
            controller: feedbackController,
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => onDecision('reject', feedbackController.text),
          child: Text('❌ Reject'),
        ),
        TextButton(
          onPressed: () => onDecision('modify', feedbackController.text),
          child: Text('✏️ Modify'),
        ),
        ElevatedButton(
          onPressed: () => onDecision('approve', null),
          child: Text('✅ Approve'),
        ),
      ],
    );
  }
}
```

### 2. ⏳ Добавить обработку в AgentChatBloc

**Файл:** [`agent_chat_bloc.dart`](../codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/presentation/bloc/agent_chat_bloc.dart:296-335)

**Добавить в `_onMessageReceived`:**

```dart
// Показать Plan Approval диалог
await event.message.content.maybeWhen(
  planApprovalRequired: (approvalRequestId, planId, planSummary, content) async {
    _logger.i('📋 Plan approval required: $planId');
    
    // Показать диалог через UI
    // Можно использовать event или callback
    // Например, добавить в state:
    emit(state.copyWith(
      pendingPlanApproval: some(PlanApprovalRequest(
        approvalRequestId: approvalRequestId,
        planId: planId,
        planSummary: planSummary,
      )),
    ));
  },
  orElse: () async {},
);
```

### 3. ⏳ Добавить отправку решения на backend

**Создать Use Case:**

```dart
// lib/features/agent_chat/domain/usecases/send_plan_decision.dart

class SendPlanDecisionUseCase {
  final AgentRepository repository;

  Future<Either<Failure, void>> call(SendPlanDecisionParams params) async {
    return repository.sendPlanDecision(
      approvalRequestId: params.approvalRequestId,
      planId: params.planId,
      decision: params.decision,
      feedback: params.feedback,
      modificationRequest: params.modificationRequest,
    );
  }
}
```

**Добавить в Repository:**

```dart
// lib/features/agent_chat/data/repositories/agent_repository_impl.dart

Future<Either<Failure, void>> sendPlanDecision({
  required String approvalRequestId,
  required String planId,
  required String decision,
  String? feedback,
  String? modificationRequest,
}) async {
  try {
    final message = WSMessage.planDecision(
      approvalRequestId: approvalRequestId,
      planId: planId,
      decision: decision,
      feedback: feedback,
      modificationRequest: modificationRequest,
    );
    
    await _websocketService.send(message.toJson());
    return right(unit);
  } catch (e) {
    return left(ServerFailure(message: e.toString()));
  }
}
```

### 4. ⏳ Добавить в State

**Обновить `AgentChatState`:**

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
    required Option<PlanApprovalRequest> pendingPlanApproval, // ✅ Новое поле
  }) = _AgentChatState;
}

@freezed
class PlanApprovalRequest with _$PlanApprovalRequest {
  const factory PlanApprovalRequest({
    required String approvalRequestId,
    required String planId,
    required Map<String, dynamic> planSummary,
  }) = _PlanApprovalRequest;
}
```

### 5. ⏳ Интеграция с UI

**В Chat Screen:**

```dart
BlocListener<AgentChatBloc, AgentChatState>(
  listenWhen: (previous, current) => 
    previous.pendingPlanApproval != current.pendingPlanApproval,
  listener: (context, state) {
    state.pendingPlanApproval.fold(
      () => null,
      (planApproval) {
        // Показать диалог
        showDialog(
          context: context,
          barrierDismissible: false,
          builder: (_) => PlanApprovalDialog(
            approvalRequestId: planApproval.approvalRequestId,
            planId: planApproval.planId,
            planSummary: planApproval.planSummary,
            onDecision: (decision, feedback) {
              // Отправить решение
              context.read<AgentChatBloc>().add(
                AgentChatEvent.sendPlanDecision(
                  approvalRequestId: planApproval.approvalRequestId,
                  planId: planApproval.planId,
                  decision: decision,
                  feedback: feedback,
                ),
              );
              Navigator.of(context).pop();
            },
          ),
        );
      },
    );
  },
  child: ChatMessagesWidget(),
)
```

---

## ✅ Текущий статус

| Компонент | Статус | Файл |
|-----------|--------|------|
| WSMessage types | ✅ Готово | [`ws_message.dart`](../codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/data/models/ws_message.dart) |
| MessageContent type | ✅ Готово | [`message.dart`](../codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/domain/entities/message.dart) |
| MessageMapper | ✅ Готово | [`message_mapper.dart`](../codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/data/mappers/message_mapper.dart) |
| Freezed generation | ✅ Готово | Все `.freezed.dart` файлы |
| UI Dialog | ⏳ TODO | Нужно создать |
| BLoC integration | ⏳ TODO | Нужно добавить |
| Use Case | ⏳ TODO | Нужно создать |
| Repository method | ⏳ TODO | Нужно добавить |

---

## 🔗 Связанные документы

- [PLAN_APPROVAL_MECHANISM_ISSUE_ANALYSIS.md](PLAN_APPROVAL_MECHANISM_ISSUE_ANALYSIS.md) - Анализ проблемы на backend
- [AGENT_RUNTIME_LOGS_ANALYSIS.md](AGENT_RUNTIME_LOGS_ANALYSIS.md) - Анализ логов Docker Compose
- [UNIFIED_APPROVAL_IMPLEMENTATION_PROGRESS.md](UNIFIED_APPROVAL_IMPLEMENTATION_PROGRESS.md) - Общий прогресс approval системы

---

## 📝 Примечания

1. **Backend готов:** Все исправления на backend уже выполнены согласно отчету пользователя
2. **Формат данных согласован:** Client ожидает данные на верхнем уровне, backend отправляет именно так
3. **Clean Architecture:** Реализация следует принципам Clean Architecture с разделением на Domain, Data, Presentation слои
4. **Type Safety:** Использование Freezed обеспечивает type-safe обработку всех типов сообщений

---

## 🎯 Приоритет следующих задач

1. **Высокий:** Создать UI компонент `PlanApprovalDialog`
2. **Высокий:** Добавить обработку в `AgentChatBloc`
3. **Средний:** Создать Use Case для отправки решения
4. **Средний:** Добавить метод в Repository
5. **Низкий:** E2E тестирование с реальным backend
