# План Approval - Руководство по интеграции

**Дата:** 2026-02-01  
**Статус:** 📋 Инструкции для завершения  

---

## 📋 Обзор

Документ содержит пошаговые инструкции для завершения интеграции Plan Approval в AgentChatBloc.

---

## ✅ Что уже готово

1. ✅ Backend полностью реализован
2. ✅ Domain entities созданы
3. ✅ WebSocket messages добавлены
4. ✅ PlanApprovalBloc создан
5. ✅ PlanApprovalDialog создан

---

## 🔧 Что нужно сделать

### Шаг 1: Добавить PlanApprovalBloc в AgentChatBloc

**Файл:** `codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/presentation/bloc/agent_chat_bloc.dart`

#### 1.1 Добавить зависимость

```dart
class AgentChatBloc extends Bloc<AgentChatEvent, AgentChatState> {
  // ... existing fields ...
  final ToolApprovalBloc _toolApprovalBloc;
  final PlanApprovalBloc _planApprovalBloc; // ✅ Добавить
  
  AgentChatBloc({
    // ... existing params ...
    required ToolApprovalBloc toolApprovalBloc,
    required PlanApprovalBloc planApprovalBloc, // ✅ Добавить
  })  : _toolApprovalBloc = toolApprovalBloc,
        _planApprovalBloc = planApprovalBloc, // ✅ Добавить
        super(const AgentChatState.initial()) {
    // ... existing setup ...
    _setupPlanApprovalListener(); // ✅ Добавить
  }
}
```

---

### Шаг 2: Добавить listener для PlanApprovalBloc

**Файл:** `codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/presentation/bloc/agent_chat_bloc.dart`

```dart
void _setupPlanApprovalListener() {
  _planApprovalBloc.stream.listen((planApprovalState) {
    planApprovalState.when(
      initial: () {
        // Ничего не делаем
      },
      
      requesting: (_) {
        // Dialog будет показан через BlocListener в UI
        _logger.d('Plan approval dialog should be shown');
      },
      
      approved: () async {
        // Получаем текущий request из состояния
        final currentState = _planApprovalBloc.state;
        if (currentState is! RequestingPlanApprovalState) {
          _logger.e('Cannot send approval: not in requesting state');
          return;
        }
        
        final request = currentState.request;
        _logger.i('✅ Plan approved, sending decision to backend');
        
        await _sendPlanDecision(
          approvalRequestId: request.approvalRequestId,
          decision: 'approve',
          feedback: null,
        );
      },
      
      rejected: (feedback) async {
        final currentState = _planApprovalBloc.state;
        if (currentState is! RequestingPlanApprovalState) {
          _logger.e('Cannot send rejection: not in requesting state');
          return;
        }
        
        final request = currentState.request;
        _logger.w('❌ Plan rejected, sending decision to backend');
        
        await _sendPlanDecision(
          approvalRequestId: request.approvalRequestId,
          decision: 'reject',
          feedback: feedback,
        );
      },
      
      modified: (feedback) async {
        final currentState = _planApprovalBloc.state;
        if (currentState is! RequestingPlanApprovalState) {
          _logger.e('Cannot send modification: not in requesting state');
          return;
        }
        
        final request = currentState.request;
        _logger.i('✏️ Plan modification requested, sending decision to backend');
        
        await _sendPlanDecision(
          approvalRequestId: request.approvalRequestId,
          decision: 'modify',
          feedback: feedback,
        );
      },
      
      cancelled: () async {
        final currentState = _planApprovalBloc.state;
        if (currentState is! RequestingPlanApprovalState) {
          _logger.e('Cannot send cancellation: not in requesting state');
          return;
        }
        
        final request = currentState.request;
        _logger.i('🚫 Plan approval cancelled, sending rejection to backend');
        
        await _sendPlanDecision(
          approvalRequestId: request.approvalRequestId,
          decision: 'reject',
          feedback: 'User cancelled the approval dialog',
        );
      },
      
      error: (message) {
        _logger.e('Plan approval error: $message');
        // Можно показать snackbar с ошибкой
      },
    );
  });
}
```

---

### Шаг 3: Добавить метод отправки plan_decision

**Файл:** `codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/presentation/bloc/agent_chat_bloc.dart`

```dart
Future<void> _sendPlanDecision({
  required String approvalRequestId,
  required String decision,
  String? feedback,
}) async {
  _logger.i('📤 Sending plan decision: $decision for $approvalRequestId');
  
  // Создаем WebSocket message
  final wsMessage = WSMessage.planDecision(
    approvalRequestId: approvalRequestId,
    decision: decision,
    feedback: feedback,
  );
  
  // Конвертируем в MessageModel
  final messageModel = MessageModel(
    type: 'plan_decision',
    approvalRequestId: approvalRequestId,
    metadata: {
      'decision': decision,
      if (feedback != null) 'feedback': feedback,
    },
  );
  
  // Отправляем через repository
  final result = await _sendMessage(
    SendMessageParams(message: messageModel),
  );
  
  result.fold(
    (failure) {
      _logger.e('❌ Failed to send plan decision: ${failure.message}');
      // Можно показать ошибку пользователю
    },
    (_) {
      _logger.i('✅ Plan decision sent successfully');
    },
  );
}
```

---

### Шаг 4: Добавить обработку plan_approval_required

**Файл:** `codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/presentation/bloc/agent_chat_bloc.dart`

Найти метод `_handleIncomingMessage` и добавить обработку:

```dart
Future<void> _handleIncomingMessage(Message message) async {
  message.content.when(
    // ... existing handlers ...
    
    // ✅ Добавить этот handler
    planApprovalRequired: (approvalRequestId, planId, planSummary) async {
      _logger.i('📋 Plan approval required received: $planId');
      
      // Добавляем сообщение в историю
      emit(state.copyWith(
        messages: [...state.messages, message],
      ));
      
      // Запрашиваем одобрение через PlanApprovalBloc
      _planApprovalBloc.add(
        PlanApprovalEvent.requestApproval(
          approvalRequestId: approvalRequestId,
          planId: planId,
          planSummary: planSummary,
        ),
      );
      
      _logger.d('Plan approval request dispatched to PlanApprovalBloc');
    },
    
    // ... other handlers ...
  );
}
```

---

### Шаг 5: Обновить MessageContent

**Файл:** `codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/domain/entities/message.dart`

Добавить новый вариант в `MessageContent`:

```dart
@freezed
sealed class MessageContent with _$MessageContent {
  // ... existing variants ...
  
  /// Plan approval required content
  const factory MessageContent.planApprovalRequired({
    required String approvalRequestId,
    required String planId,
    required PlanSummary planSummary,
  }) = PlanApprovalRequiredContent;
  
  // ... other variants ...
}
```

---

### Шаг 6: Обновить MessageMapper

**Файл:** `codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/data/mappers/message_mapper.dart`

Добавить маппинг для plan_approval_required:

```dart
extension MessageModelX on MessageModel {
  Message toDomain() {
    // ... existing code ...
    
    MessageContent content;
    
    switch (type) {
      // ... existing cases ...
      
      case 'plan_approval_required':
        if (approvalRequestId == null || planId == null || planSummary == null) {
          throw const ParseException('Missing required fields for plan_approval_required');
        }
        
        content = MessageContent.planApprovalRequired(
          approvalRequestId: approvalRequestId!,
          planId: planId!,
          planSummary: PlanSummary.fromJson(planSummary!),
        );
        break;
      
      // ... other cases ...
    }
    
    // ... rest of method ...
  }
}
```

---

### Шаг 7: Добавить UI integration

**Файл:** `codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/presentation/widgets/ai_assistant_panel.dart`

Добавить BlocListener для PlanApprovalBloc:

```dart
@override
Widget build(BuildContext context) {
  return MultiBlocListener(
    listeners: [
      // ... existing listeners ...
      
      // ✅ Добавить этот listener
      BlocListener<PlanApprovalBloc, PlanApprovalState>(
        listener: (context, state) {
          state.maybeWhen(
            requesting: (request) {
              // Показываем диалог одобрения плана
              showDialog(
                context: context,
                barrierDismissible: false,
                builder: (dialogContext) => PlanApprovalDialog(
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
      ),
    ],
    child: // ... existing widget tree
  );
}
```

---

### Шаг 8: Добавить PlanApprovalBloc в DI

**Файл:** `codelab_ide/packages/codelab_ai_assistant/lib/ai_assistent_module.dart`

Добавить provider для PlanApprovalBloc:

```dart
@module
abstract class AIAssistantModule {
  // ... existing providers ...
  
  @singleton
  PlanApprovalBloc providePlanApprovalBloc(Logger logger) {
    return PlanApprovalBloc(logger: logger);
  }
  
  // ... other providers ...
}
```

---

### Шаг 9: Экспортировать новые классы

**Файл:** `codelab_ide/packages/codelab_ai_assistant/lib/codelab_ai_assistant.dart`

```dart
// Plan Execution
export 'features/plan_execution/domain/entities/plan_approval.dart';
export 'features/plan_execution/presentation/bloc/plan_approval_bloc.dart';
export 'features/plan_execution/presentation/widgets/plan_approval_dialog.dart';
```

---

## 🧪 Тестирование

### Ручное тестирование

1. **Запустить backend:**
   ```bash
   cd codelab-ai-service/agent-runtime
   python -m app.main
   ```

2. **Запустить IDE:**
   ```bash
   cd codelab_ide
   fvm flutter run
   ```

3. **Отправить сложную задачу:**
   ```
   "Создай Flutter login form с валидацией и unit тестами"
   ```

4. **Ожидаемый результат:**
   - Появится диалог Plan Approval
   - Отобразится goal, subtasks, estimated time
   - Можно approve/reject/modify
   - После approve начнется выполнение

### Проверка логов

**Backend logs:**
```
Plan {plan_id} requesting user approval
Plan approval request created: plan-approval-{plan_id}
Waiting for user approval for plan {plan_id}
```

**Client logs:**
```
📋 Plan approval required received: {plan_id}
Plan approval request dispatched to PlanApprovalBloc
✅ Plan approved, sending decision to backend
📤 Sending plan decision: approve for plan-approval-{plan_id}
✅ Plan decision sent successfully
```

---

## 📝 Чеклист интеграции

### AgentChatBloc
- [ ] Добавить `PlanApprovalBloc` в конструктор
- [ ] Добавить метод `_setupPlanApprovalListener()`
- [ ] Добавить метод `_sendPlanDecision()`
- [ ] Добавить обработку в `_handleIncomingMessage()`

### MessageContent
- [ ] Добавить вариант `planApprovalRequired` в sealed class
- [ ] Обновить freezed файлы

### MessageMapper
- [ ] Добавить case для `plan_approval_required`
- [ ] Добавить маппинг в `toDomain()`

### UI Integration
- [ ] Добавить `BlocListener<PlanApprovalBloc>` в `ai_assistant_panel.dart`
- [ ] Показывать `PlanApprovalDialog` при состоянии `requesting`

### DI
- [ ] Добавить provider для `PlanApprovalBloc` в module
- [ ] Передать в `AgentChatBloc` конструктор

### Exports
- [ ] Экспортировать новые классы в `codelab_ai_assistant.dart`

### Build
- [ ] Запустить `fvm flutter pub run build_runner build --delete-conflicting-outputs`
- [ ] Проверить отсутствие ошибок компиляции

---

## 🐛 Возможные проблемы

### Проблема 1: MessageContent не имеет planApprovalRequired

**Решение:** Добавить в `message.dart`:

```dart
@freezed
sealed class MessageContent with _$MessageContent {
  const factory MessageContent.planApprovalRequired({
    required String approvalRequestId,
    required String planId,
    required PlanSummary planSummary,
  }) = PlanApprovalRequiredContent;
}
```

### Проблема 2: MessageModel не имеет полей plan approval

**Решение:** Добавить в `message_model.dart`:

```dart
@freezed
class MessageModel with _$MessageModel {
  const factory MessageModel({
    // ... existing fields ...
    
    @JsonKey(name: 'approval_request_id') String? approvalRequestId,
    @JsonKey(name: 'plan_id') String? planId,
    @JsonKey(name: 'plan_summary') Map<String, dynamic>? planSummary,
  }) = _MessageModel;
}
```

### Проблема 3: PlanApprovalBloc не инжектится

**Решение:** Проверить DI module и убедиться, что provider добавлен.

---

## 📚 Примеры кода

### Полный пример обработки в AgentChatBloc

```dart
// В _handleIncomingMessage
message.content.when(
  text: (text) async {
    // ... existing code ...
  },
  
  toolCall: (callId, toolName, arguments) async {
    // ... existing code ...
  },
  
  planApprovalRequired: (approvalRequestId, planId, planSummary) async {
    _logger.i('📋 Plan approval required: $planId');
    _logger.d('Approval request ID: $approvalRequestId');
    _logger.d('Subtasks count: ${planSummary.subtasksCount}');
    
    // Добавляем сообщение в историю
    emit(state.copyWith(
      messages: [...state.messages, message],
    ));
    
    // Запрашиваем одобрение
    _planApprovalBloc.add(
      PlanApprovalEvent.requestApproval(
        approvalRequestId: approvalRequestId,
        planId: planId,
        planSummary: planSummary,
      ),
    );
  },
  
  // ... other handlers ...
);
```

---

## ✅ Заключение

После выполнения всех шагов:

1. ✅ Plan approval будет полностью работать
2. ✅ Пользователь сможет просматривать и одобрять планы
3. ✅ FSM будет корректно переходить между состояниями
4. ✅ Планы будут выполняться только после одобрения

**Оценка времени:** 2-3 часа на интеграцию + 1-2 часа на тестирование

---

**Автор:** CodeLab Team  
**Дата:** 2026-02-01
