# Unified Approval Architecture - Предложение по унификации

## 🎯 Проблема

Сейчас в системе существуют **два отдельных механизма подтверждения**:

1. **Tool Approval** (ToolApprovalService)
   - Подтверждение выполнения инструментов
   - Восстановление pending approvals после переподключения
   - Completer-based архитектура

2. **Plan Approval** (PlanApprovalBloc)
   - Подтверждение планов выполнения
   - Отдельная BLoC логика
   - Дублирование кода

## 🏗️ Backend Architecture (для справки)

В agent-runtime реализован **единый ApprovalManager**:

```python
# codelab-ai-service/agent-runtime/app/domain/services/approval_manager.py

class ApprovalManager:
    """Unified manager for all approval types"""
    
    async def request_approval(
        self,
        approval_type: ApprovalType,  # TOOL, PLAN, etc.
        request_data: dict,
        timeout: int = 300
    ) -> ApprovalDecision:
        """Generic approval request"""
        
    async def get_pending_approvals(
        self,
        session_id: str
    ) -> List[PendingApproval]:
        """Restore all pending approvals"""
```

## 💡 Предложение: Unified Approval Service

### Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                  UnifiedApprovalService                      │
│                                                              │
│  - Generic approval request/response handling               │
│  - Restore pending approvals (all types)                    │
│  - Type-safe approval types (Tool, Plan, etc.)              │
└─────────────────────────────────────────────────────────────┘
                         │
                         ├─────────────────┬─────────────────┐
                         ▼                 ▼                 ▼
              ┌──────────────────┐ ┌──────────────┐ ┌──────────────┐
              │ ToolApprovalBloc │ │PlanApprovalBloc│ │ Future types │
              └──────────────────┘ └──────────────┘ └──────────────┘
```

### Domain Entities

```dart
// lib/features/approval/domain/entities/approval.dart

/// Тип подтверждения
enum ApprovalType {
  tool,
  plan,
  // Будущие типы: fileOperation, dangerousCommand, etc.
}

/// Базовый запрос на подтверждение
@freezed
abstract class ApprovalRequest with _$ApprovalRequest {
  const factory ApprovalRequest({
    required String approvalRequestId,
    required ApprovalType type,
    required DateTime requestedAt,
    required int timeoutSeconds,
    required Map<String, dynamic> data, // Type-specific data
    Option<String>? context,
  }) = _ApprovalRequest;
}

/// Базовое решение
@freezed
sealed class ApprovalDecision with _$ApprovalDecision {
  const factory ApprovalDecision.approved() = ApprovalApproved;
  const factory ApprovalDecision.rejected({Option<String>? feedback}) = ApprovalRejected;
  const factory ApprovalDecision.modified({required String feedback}) = ApprovalModified;
  const factory ApprovalDecision.cancelled() = ApprovalCancelled;
}

/// Ответ на запрос
@freezed
abstract class ApprovalResponse with _$ApprovalResponse {
  const factory ApprovalResponse({
    required String approvalRequestId,
    required ApprovalType type,
    required ApprovalDecision decision,
    required DateTime respondedAt,
    required int decisionTimeMs,
  }) = _ApprovalResponse;
}
```

### Service Interface

```dart
// lib/features/approval/domain/services/approval_service.dart

abstract class ApprovalService {
  /// Запросить подтверждение (generic)
  Future<ApprovalDecision> requestApproval(ApprovalRequest request);
  
  /// Восстановить все pending approvals для сессии
  Future<List<ApprovalRequest>> restorePendingApprovals(String sessionId);
  
  /// Отправить решение на сервер
  Future<void> sendDecision(ApprovalResponse response);
  
  /// Stream всех запросов на подтверждение
  Stream<ApprovalRequest> get approvalRequests;
}
```

### Implementation

```dart
// lib/features/approval/data/services/unified_approval_service_impl.dart

class UnifiedApprovalServiceImpl implements ApprovalService {
  final GatewayApi _api;
  final Logger _logger;
  
  // Completers для ожидания решений
  final Map<String, Completer<ApprovalDecision>> _activeCompleters = {};
  
  // Stream controller для запросов
  final _requestsController = StreamController<ApprovalRequest>.broadcast();
  
  @override
  Future<ApprovalDecision> requestApproval(ApprovalRequest request) async {
    final completer = Completer<ApprovalDecision>();
    _activeCompleters[request.approvalRequestId] = completer;
    
    // Emit request для UI
    _requestsController.add(request);
    
    // Wait for decision with timeout
    return completer.future.timeout(
      Duration(seconds: request.timeoutSeconds),
      onTimeout: () => const ApprovalDecision.cancelled(),
    );
  }
  
  @override
  Future<List<ApprovalRequest>> restorePendingApprovals(String sessionId) async {
    final response = await _api.getPendingApprovals(sessionId);
    
    final requests = response.map((json) {
      final type = ApprovalType.values.byName(json['type']);
      return ApprovalRequest(
        approvalRequestId: json['approval_request_id'],
        type: type,
        requestedAt: DateTime.parse(json['requested_at']),
        timeoutSeconds: json['timeout_seconds'],
        data: json['data'],
        context: json['context'] != null ? some(json['context']) : none(),
      );
    }).toList();
    
    // Restore completers and emit requests
    for (final request in requests) {
      final completer = Completer<ApprovalDecision>();
      _activeCompleters[request.approvalRequestId] = completer;
      _requestsController.add(request);
    }
    
    return requests;
  }
  
  @override
  Future<void> sendDecision(ApprovalResponse response) async {
    await _api.sendApprovalDecision(
      approvalRequestId: response.approvalRequestId,
      type: response.type.name,
      decision: response.decision.toDecisionString(),
      feedback: response.decision.getFeedback()?.toNullable(),
    );
    
    // Complete the completer
    final completer = _activeCompleters.remove(response.approvalRequestId);
    completer?.complete(response.decision);
  }
  
  @override
  Stream<ApprovalRequest> get approvalRequests => _requestsController.stream;
}
```

### BLoC Integration

```dart
// lib/features/approval/presentation/bloc/approval_bloc.dart

/// Единый BLoC для всех типов подтверждений
class ApprovalBloc extends Bloc<ApprovalEvent, ApprovalState> {
  final UnifiedApprovalService _approvalService;
  
  ApprovalBloc({required UnifiedApprovalService approvalService})
      : _approvalService = approvalService,
        super(const ApprovalState.initial()) {
    
    // Подписываемся на запросы
    _approvalService.approvalRequests.listen((request) {
      add(ApprovalEvent.requestReceived(request));
    });
    
    on<ApprovalRequestReceivedEvent>(_onRequestReceived);
    on<ApproveEvent>(_onApprove);
    on<RejectEvent>(_onReject);
    on<ModifyEvent>(_onModify);
    on<CancelEvent>(_onCancel);
  }
  
  Future<void> _onApprove(ApproveEvent event, Emitter emit) async {
    final currentRequest = state.maybeMap(
      requesting: (state) => state.request,
      orElse: () => null,
    );
    
    if (currentRequest != null) {
      final response = ApprovalResponse(
        approvalRequestId: currentRequest.approvalRequestId,
        type: currentRequest.type,
        decision: const ApprovalDecision.approved(),
        respondedAt: DateTime.now(),
        decisionTimeMs: DateTime.now()
            .difference(currentRequest.requestedAt)
            .inMilliseconds,
      );
      
      await _approvalService.sendDecision(response);
      emit(const ApprovalState.approved());
    }
  }
  
  // Similar for reject, modify, cancel...
}
```

### AgentChatBloc Integration

```dart
class AgentChatBloc extends Bloc<AgentChatEvent, AgentChatState> {
  final UnifiedApprovalService _approvalService;
  final ApprovalBloc _approvalBloc;
  
  // Один listener для всех типов подтверждений
  void _setupApprovalListener() {
    _approvalService.approvalRequests.listen((request) {
      // Dispatch to ApprovalBloc
      _approvalBloc.add(ApprovalEvent.requestReceived(request));
    });
  }
  
  // Обработка входящих сообщений
  Future<void> _onMessageReceived(MessageReceivedEvent event, Emitter emit) async {
    // Detect approval requests from message content
    event.message.content.maybeWhen(
      toolCall: (callId, toolName, arguments) async {
        if (requiresApproval) {
          final request = ApprovalRequest(
            approvalRequestId: callId,
            type: ApprovalType.tool,
            requestedAt: DateTime.now(),
            timeoutSeconds: 300,
            data: {
              'tool_name': toolName,
              'arguments': arguments,
            },
          );
          
          final decision = await _approvalService.requestApproval(request);
          // Handle decision...
        }
      },
      planApprovalRequired: (planRequest) async {
        final request = ApprovalRequest(
          approvalRequestId: planRequest.approvalRequestId,
          type: ApprovalType.plan,
          requestedAt: planRequest.requestedAt,
          timeoutSeconds: planRequest.timeoutSeconds,
          data: {
            'plan_id': planRequest.planId,
            'plan_summary': planRequest.planSummary.toJson(),
          },
        );
        
        final decision = await _approvalService.requestApproval(request);
        // Handle decision...
      },
      orElse: () {},
    );
  }
}
```

## 📊 Сравнение подходов

### Текущий подход (Separate Services)

**Плюсы:**
- ✅ Простая реализация для каждого типа
- ✅ Изолированная логика

**Минусы:**
- ❌ Дублирование кода (restore, completers, timeouts)
- ❌ Сложность добавления новых типов подтверждений
- ❌ Разные паттерны для разных типов
- ❌ Сложность тестирования

### Unified Approach

**Плюсы:**
- ✅ Единая точка управления всеми подтверждениями
- ✅ Переиспользование логики (restore, timeouts, completers)
- ✅ Легко добавлять новые типы (просто добавить в enum)
- ✅ Единый паттерн для всех типов
- ✅ Проще тестировать
- ✅ Соответствует backend архитектуре

**Минусы:**
- ⚠️ Требует рефакторинга существующего кода
- ⚠️ Более сложная начальная реализация

## 🎯 Рекомендация

**Реализовать Unified Approval Service** по следующим причинам:

1. **Масштабируемость**: В будущем могут появиться новые типы подтверждений:
   - File operations (delete, move)
   - Dangerous commands
   - API calls
   - Database operations

2. **Консистентность**: Единый подход упрощает понимание и поддержку

3. **Соответствие backend**: Архитектура клиента будет зеркалить backend

4. **DRY принцип**: Избегаем дублирования логики

## 📝 План миграции

### Фаза 1: Создание Unified Service (1-2 дня)
1. Создать domain entities (ApprovalRequest, ApprovalDecision, etc.)
2. Создать UnifiedApprovalService interface
3. Реализовать UnifiedApprovalServiceImpl
4. Создать ApprovalBloc

### Фаза 2: Миграция Tool Approval (1 день)
1. Адаптировать ToolApprovalService к новому API
2. Обновить AgentChatBloc
3. Тестирование

### Фаза 3: Миграция Plan Approval (1 день)
1. Удалить PlanApprovalBloc (заменить на ApprovalBloc)
2. Обновить UI для работы с generic ApprovalBloc
3. Тестирование

### Фаза 4: Cleanup (0.5 дня)
1. Удалить старый код
2. Обновить документацию
3. Финальное тестирование

**Общее время: 3.5-4.5 дня**

## 🔗 Структура файлов

```
lib/features/approval/
├── domain/
│   ├── entities/
│   │   ├── approval_request.dart
│   │   ├── approval_decision.dart
│   │   └── approval_response.dart
│   └── services/
│       └── approval_service.dart
├── data/
│   └── services/
│       └── unified_approval_service_impl.dart
└── presentation/
    ├── bloc/
    │   ├── approval_bloc.dart
    │   ├── approval_event.dart
    │   └── approval_state.dart
    └── widgets/
        ├── tool_approval_dialog.dart
        ├── plan_approval_dialog.dart
        └── generic_approval_dialog.dart
```

## ✨ Заключение

Unified Approval Service - это правильный архитектурный выбор, который:
- Упрощает код
- Улучшает масштабируемость
- Соответствует backend архитектуре
- Следует принципам Clean Architecture

Рекомендую выполнить рефакторинг в ближайшее время, пока система еще не сильно разрослась.
