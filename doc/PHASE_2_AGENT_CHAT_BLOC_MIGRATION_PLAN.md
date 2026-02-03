# AgentChatBloc Migration Plan - Unified Approval System

**Дата:** 03 февраля 2026  
**Файл:** [`lib/features/agent_chat/presentation/bloc/agent_chat_bloc.dart`](codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/presentation/bloc/agent_chat_bloc.dart)  
**Размер:** 690 строк  
**Цель:** Миграция с ToolApprovalService на ApprovalService

---

## 📋 Изменения

### 1. Импорты

**Удалить:**
```dart
import '../../../tool_execution/data/services/tool_approval_service_impl.dart';
```

**Добавить:**
```dart
import '../../../approval/domain/services/approval_service.dart';
import '../../../approval/domain/entities/approval_request.dart';
import '../../../approval/domain/entities/approval_response.dart';
import '../../../approval/domain/entities/approval_decision.dart';
import '../../../approval/domain/entities/approval_type.dart';
import '../../../approval/data/adapters/approval_request_adapter.dart';
```

### 2. Поля класса (строки 92-96)

**Было:**
```dart
final ToolApprovalService _approvalService;
StreamSubscription<ApprovalRequestWithCompleter>? _approvalSubscription;
```

**Стало:**
```dart
final ApprovalService _approvalService;
StreamSubscription<ApprovalRequest>? _approvalSubscription;
```

### 3. Конструктор (строки 98-142)

**Было:**
```dart
AgentChatBloc({
  // ...
  required ToolApprovalService approvalService,
  // ...
}) : _approvalService = approvalService,
     // ...
     super(AgentChatState.initial()) {
  // ...
  
  // Подписываемся на запросы подтверждения
  _approvalSubscription = _approvalService.approvalRequests.listen((request) {
    add(AgentChatEvent.approvalRequested(request));
  });

  // Устанавливаем callback для выполнения восстановленных tool
  _approvalService.onExecuteRestoredTool = _executeRestoredTool;

  // Устанавливаем callback для отправки rejection на сервер
  _approvalService.onRejectRestoredTool = _rejectRestoredTool;
}
```

**Стало:**
```dart
AgentChatBloc({
  // ...
  required ApprovalService approvalService,
  // ...
}) : _approvalService = approvalService,
     // ...
     super(AgentChatState.initial()) {
  // ...
  
  // Подписываемся на запросы подтверждения (generic)
  _approvalSubscription = _approvalService.approvalRequests.listen((request) {
    _handleApprovalRequest(request);
  });
}
```

### 4. Новый метод _handleApprovalRequest (после строки 142)

**Добавить:**
```dart
/// Обрабатывает generic approval request из unified service
void _handleApprovalRequest(ApprovalRequest request) {
  // Обрабатываем только tool approvals
  // Plan approvals обрабатываются через SendPlanDecisionEvent
  if (request.type != ApprovalType.tool) {
    _logger.d('Skipping non-tool approval: ${request.type}');
    return;
  }

  try {
    // Конвертируем ApprovalRequest в ToolCall
    final toolCall = ApprovalRequestAdapter.toToolCall(request);
    
    // Создаем legacy ToolApprovalRequest для обратной совместимости с UI
    final toolApprovalRequest = ToolApprovalRequest(
      requestId: request.approvalRequestId,
      toolCall: toolCall,
      requestedAt: request.requestedAt,
    );
    
    // Создаем completer для UI
    final completer = Completer<ApprovalDecision>();
    final requestWithCompleter = ApprovalRequestWithCompleter(
      toolApprovalRequest,
      completer,
    );
    
    // Эмитируем событие для UI
    add(AgentChatEvent.approvalRequested(requestWithCompleter));
    
    // Ожидаем решения и отправляем на сервер
    _waitForDecisionAndSend(request, completer, toolCall);
  } catch (e) {
    _logger.e('Error handling approval request: $e');
  }
}

/// Ожидает решения пользователя и отправляет на сервер
Future<void> _waitForDecisionAndSend(
  ApprovalRequest request,
  Completer<ApprovalDecision> completer,
  ToolCall toolCall,
) async {
  try {
    // Ждем решения от UI
    final decision = await completer.future;
    
    _logger.i(
      'Decision received for ${toolCall.toolName}: ${decision.toDecisionString()}',
    );
    
    // Создаем ApprovalResponse для отправки на сервер
    final response = ApprovalResponse(
      approvalRequestId: request.approvalRequestId,
      type: ApprovalType.tool,
      decision: decision,
      respondedAt: DateTime.now(),
      decisionTimeMs: DateTime.now()
          .difference(request.requestedAt)
          .inMilliseconds,
    );
    
    // Отправляем решение через unified service
    await _approvalService.sendDecision(response);
    
    // Обрабатываем решение
    await decision.when(
      approved: () async {
        // Выполняем tool после approve
        await _executeRestoredTool(toolCall);
      },
      rejected: (reason) async {
        // Отправляем rejection на сервер
        final rejectReason = reason?.fold(() => 'User rejected', (r) => r) ?? 'User rejected';
        await _rejectRestoredTool(toolCall, rejectReason);
      },
      modified: (modifiedArguments, comment) async {
        // Выполняем tool с измененными аргументами
        final modifiedToolCall = toolCall.copyWith(
          arguments: modifiedArguments,
        );
        await _executeRestoredTool(modifiedToolCall);
      },
      cancelled: () async {
        // Отправляем cancellation на сервер
        await _rejectRestoredTool(toolCall, 'User cancelled');
      },
    );
  } catch (e) {
    _logger.e('Error waiting for decision: $e');
  }
}
```

### 5. Метод _onConnect (строки 509-554)

**Было:**
```dart
// ВАЖНО: Восстанавливаем ожидающие подтверждения с сервера
try {
  await _approvalService.restorePendingApprovals(event.sessionId);
  _logger.i('Pending approvals restored successfully');
} catch (e) {
  _logger.e('Failed to restore pending approvals: $e');
  // Не блокируем подключение из-за ошибки восстановления
}
```

**Стало:**
```dart
// ВАЖНО: Восстанавливаем ожидающие подтверждения с сервера
// Unified service возвращает список восстановленных approvals
try {
  final restoredApprovals = await _approvalService.restorePendingApprovals(event.sessionId);
  _logger.i('Restored ${restoredApprovals.length} pending approvals');
  // Approvals уже эмитированы в stream через _handleApprovalRequest
} catch (e) {
  _logger.e('Failed to restore pending approvals: $e');
  // Не блокируем подключение из-за ошибки восстановления
}
```

### 6. Удалить callbacks (строки 137-141)

**Удалить полностью:**
```dart
// Устанавливаем callback для выполнения восстановленных tool
_approvalService.onExecuteRestoredTool = _executeRestoredTool;

// Устанавливаем callback для отправки rejection на сервер
_approvalService.onRejectRestoredTool = _rejectRestoredTool;
```

**Причина:** Callbacks заменены на event-driven подход через `_waitForDecisionAndSend`

---

## ✅ Что НЕ меняется

1. **Методы _executeRestoredTool и _rejectRestoredTool** (строки 144-260) - остаются без изменений
2. **Все event handlers** - остаются без изменений
3. **State и Events** - остаются без изменений
4. **UI интеграция** - остается совместимой через ApprovalRequestWithCompleter

---

## 🎯 Преимущества

✅ **Чистая архитектура** - нет callbacks, event-driven подход  
✅ **Универсальность** - готовность к plan approvals  
✅ **Меньше coupling** - нет прямой зависимости от tool-specific логики  
✅ **Лучшая тестируемость** - проще мокировать ApprovalService  
✅ **Обратная совместимость** - UI код не меняется

---

## ⚠️ Важные моменты

1. **ApprovalRequestWithCompleter** остается для UI совместимости
2. **_executeRestoredTool** и **_rejectRestoredTool** остаются без изменений
3. **Plan approvals** уже обрабатываются через SendPlanDecisionEvent
4. **Все существующие тесты** должны продолжать работать

---

**Статус:** ✅ Готово к реализации
