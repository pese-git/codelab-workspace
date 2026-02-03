# Phase 4: План рефакторинга AgentChatBloc

## 📋 Обзор

Детальный план интеграции middleware компонентов в AgentChatBloc для упрощения архитектуры.

**Цель:** Уменьшить размер BLoC с 809 строк до ~300 строк (-63%) путем делегирования логики middleware.

## 🎯 Текущее состояние

### AgentChatBloc (809 строк)

**Зависимости (9 шт):**
- `SendMessageUseCase` - отправка сообщений
- `SendToolResultUseCase` - отправка результатов tool
- `ReceiveMessagesUseCase` - получение сообщений
- `SwitchAgentUseCase` - переключение агентов
- `LoadHistoryUseCase` - загрузка истории
- `ConnectUseCase` - подключение к WebSocket
- `ExecuteToolUseCase` - выполнение tool
- `SendPlanDecisionUseCase` - отправка решения по плану
- `ApprovalService` - unified approval service

**Event Handlers (14 методов):**
1. `_onSendMessage` (45 строк)
2. `_onMessageReceived` (142 строки) ⚠️ СЛОЖНЫЙ
3. `_onSwitchAgent` (24 строки)
4. `_onLoadHistory` (24 строки)
5. `_onConnect` (45 строк)
6. `_onDisconnect` (18 строк)
7. `_onError` (4 строки)
8. `_onApprovalRequested` (6 строк)
9. `_onApproveToolCall` (12 строк)
10. `_onRejectToolCall` (14 строк)
11. `_onCancelToolCall` (12 строк)
12. `_onSendPlanDecision` (34 строки)
13. `_handleApprovalRequest` (35 строк)
14. `_waitForDecisionAndSend` (72 строки) ⚠️ СЛОЖНЫЙ

**Вспомогательные методы (2 шт):**
- `_executeRestoredTool` (86 строк) ⚠️ СЛОЖНЫЙ
- `_rejectRestoredTool` (28 строк)

**Проблемы:**
- ❌ Слишком много ответственностей (нарушение SRP)
- ❌ Дублирование логики с middleware
- ❌ Сложная обработка approval requests
- ❌ Прямая работа с use cases вместо middleware

## 🏗️ Целевая архитектура

### Новый AgentChatBloc (~300 строк)

**Зависимости (6 шт):**
- `ConnectionMiddleware` - управление подключением
- `MessageHandlerMiddleware` - обработка сообщений
- `ApprovalMiddleware` - управление подтверждениями
- `SendMessageUseCase` - отправка сообщений (остается)
- `SwitchAgentUseCase` - переключение агентов (остается)
- `LoadHistoryUseCase` - загрузка истории (остается)
- `SendPlanDecisionUseCase` - отправка решения по плану (остается)
- `Logger` - логирование

**Event Handlers (6 методов):**
1. `_onSendMessage` - делегирует SendMessageUseCase
2. `_onMessageReceived` - делегирует MessageHandlerMiddleware
3. `_onSwitchAgent` - делегирует SwitchAgentUseCase
4. `_onLoadHistory` - делегирует LoadHistoryUseCase
5. `_onConnect` - делегирует ConnectionMiddleware + ApprovalMiddleware
6. `_onDisconnect` - делегирует ConnectionMiddleware + ApprovalMiddleware
7. `_onError` - простая обработка ошибок
8. `_onApprovalRequested` - обновление state
9. `_onApproveToolCall` - завершение completer
10. `_onRejectToolCall` - завершение completer
11. `_onSendPlanDecision` - делегирует SendPlanDecisionUseCase

**Удаляемые методы:**
- ❌ `_handleApprovalRequest` → ApprovalMiddleware
- ❌ `_waitForDecisionAndSend` → ApprovalMiddleware
- ❌ `_executeRestoredTool` → ApprovalMiddleware
- ❌ `_rejectRestoredTool` → ApprovalMiddleware

## 📝 План рефакторинга

### Шаг 1: Обновить конструктор (10 мин)

**Было:**
```dart
AgentChatBloc({
  required SendMessageUseCase sendMessage,
  required SendToolResultUseCase sendToolResult,
  required ReceiveMessagesUseCase receiveMessages,
  required SwitchAgentUseCase switchAgent,
  required LoadHistoryUseCase loadHistory,
  required ConnectUseCase connect,
  required ExecuteToolUseCase executeTool,
  required SendPlanDecisionUseCase sendPlanDecision,
  required ApprovalService approvalService,
  required Logger logger,
})
```

**Станет:**
```dart
AgentChatBloc({
  required ConnectionMiddleware connectionMiddleware,
  required MessageHandlerMiddleware messageHandlerMiddleware,
  required ApprovalMiddleware approvalMiddleware,
  required SendMessageUseCase sendMessage,
  required SwitchAgentUseCase switchAgent,
  required LoadHistoryUseCase loadHistory,
  required SendPlanDecisionUseCase sendPlanDecision,
  required Logger logger,
})
```

**Изменения:**
- ✅ Добавить 3 middleware
- ❌ Удалить 5 use cases (делегированы middleware)
- ❌ Удалить ApprovalService (делегирован ApprovalMiddleware)

### Шаг 2: Упростить _onConnect (20 мин)

**Было (45 строк):**
```dart
Future<void> _onConnect(ConnectEvent event, Emitter<AgentChatState> emit) async {
  emit(state.copyWith(isLoading: true, error: none()));
  
  final connectResult = await _connect(ConnectParams(sessionId: event.sessionId));
  
  await connectResult.fold(
    (failure) async {
      emit(state.copyWith(isLoading: false, error: some(failure.message)));
    },
    (_) async {
      _messageSubscription?.cancel();
      _messageSubscription = _receiveMessages(const NoParams()).listen((either) {
        either.fold(
          (failure) => add(AgentChatEvent.error(failure)),
          (message) => add(AgentChatEvent.messageReceived(message)),
        );
      });
      
      try {
        final restoredApprovals = await _approvalService.restorePendingApprovals(event.sessionId);
        _logger.i('Restored ${restoredApprovals.length} pending approvals');
      } catch (e) {
        _logger.e('Failed to restore pending approvals: $e');
      }
      
      emit(state.copyWith(isConnected: true, isLoading: false));
    },
  );
}
```

**Станет (~20 строк):**
```dart
Future<void> _onConnect(ConnectEvent event, Emitter<AgentChatState> emit) async {
  _logger.d('[AgentChatBloc] 🔌 Connecting to session: ${event.sessionId}');
  emit(state.copyWith(isLoading: true, error: none()));
  
  // Подключаемся через ConnectionMiddleware
  final result = await _connectionMiddleware.connect(
    sessionId: event.sessionId,
    onMessage: (message) => add(AgentChatEvent.messageReceived(message)),
    onError: (failure) => add(AgentChatEvent.error(failure)),
  );
  
  await result.fold(
    (failure) async {
      _logger.e('[AgentChatBloc] ❌ Failed to connect: ${failure.message}');
      emit(state.copyWith(isLoading: false, error: some(failure.message)));
    },
    (_) async {
      _logger.i('[AgentChatBloc] ✅ Connected to WebSocket');
      
      // Восстанавливаем pending approvals через ApprovalMiddleware
      await _approvalMiddleware.restorePendingApprovals(event.sessionId);
      
      emit(state.copyWith(isConnected: true, isLoading: false));
    },
  );
}
```

**Улучшения:**
- ✅ Делегирование подключения ConnectionMiddleware
- ✅ Делегирование восстановления approvals ApprovalMiddleware
- ✅ Упрощение логики: 45 → 20 строк (-56%)

### Шаг 3: Упростить _onMessageReceived (30 мин)

**Было (142 строки):**
- Логирование сообщения
- Обработка agent_switch
- Обработка plan_approval_required
- Автоматическое выполнение tool_call
- Проверка source='history'
- Извлечение requires_approval
- Выполнение tool через ExecuteToolUseCase
- Отправка результата через SendToolResultUseCase

**Станет (~25 строк):**
```dart
Future<void> _onMessageReceived(
  MessageReceivedEvent event,
  Emitter<AgentChatState> emit,
) async {
  _logger.d('[AgentChatBloc] 📨 Message received: ${event.message.role}');
  
  // Обрабатываем сообщение через MessageHandlerMiddleware
  final newAgent = await _messageHandlerMiddleware.handleMessage(
    message: event.message,
    onPlanApproval: (message) {
      _logger.i('[AgentChatBloc] 📋 Plan approval required');
      emit(state.copyWith(pendingPlanApproval: some(message)));
    },
  );
  
  // Обновляем state
  emit(
    state.copyWith(
      messages: [...state.messages, event.message],
      currentAgent: newAgent.fold(() => state.currentAgent, (agent) => agent),
      isLoading: false,
    ),
  );
}
```

**Улучшения:**
- ✅ Делегирование обработки MessageHandlerMiddleware
- ✅ Упрощение логики: 142 → 25 строк (-82%)
- ✅ Удаление дублирования с middleware

### Шаг 4: Упростить _onDisconnect (10 мин)

**Было (18 строк):**
```dart
Future<void> _onDisconnect(DisconnectEvent event, Emitter<AgentChatState> emit) async {
  _logger.d('[AgentChatBloc] 🔌 Disconnecting from chat');
  await _messageSubscription?.cancel();
  _messageSubscription = null;
  
  _approvalService.clearActiveCompleters();
  
  emit(
    state.copyWith(
      isConnected: false,
      messages: const [],
      isLoading: false,
      error: none(),
      pendingApproval: none(),
    ),
  );
  
  _logger.i('[AgentChatBloc] ✅ Disconnected from chat');
}
```

**Станет (~10 строк):**
```dart
Future<void> _onDisconnect(DisconnectEvent event, Emitter<AgentChatState> emit) async {
  _logger.d('[AgentChatBloc] 🔌 Disconnecting from chat');
  
  // Отключаемся через middleware
  await _connectionMiddleware.disconnect();
  _approvalMiddleware.clearActiveCompleters();
  
  emit(
    state.copyWith(
      isConnected: false,
      messages: const [],
      isLoading: false,
      error: none(),
      pendingApproval: none(),
      pendingPlanApproval: none(),
    ),
  );
  
  _logger.i('[AgentChatBloc] ✅ Disconnected from chat');
}
```

**Улучшения:**
- ✅ Делегирование отключения ConnectionMiddleware
- ✅ Делегирование очистки ApprovalMiddleware

### Шаг 5: Удалить устаревшие методы (10 мин)

**Удаляемые методы (221 строка):**
- ❌ `_handleApprovalRequest` (35 строк) → ApprovalMiddleware
- ❌ `_waitForDecisionAndSend` (72 строки) → ApprovalMiddleware
- ❌ `_executeRestoredTool` (86 строк) → ApprovalMiddleware
- ❌ `_rejectRestoredTool` (28 строк) → ApprovalMiddleware

**Причина удаления:**
Вся логика перенесена в ApprovalMiddleware и больше не нужна в BLoC.

### Шаг 6: Обновить инициализацию (10 мин)

**Было:**
```dart
super(AgentChatState.initial()) {
  on<SendMessageEvent>(_onSendMessage);
  on<MessageReceivedEvent>(_onMessageReceived);
  on<SwitchAgentEvent>(_onSwitchAgent);
  on<LoadHistoryEvent>(_onLoadHistory);
  on<ConnectEvent>(_onConnect);
  on<DisconnectEvent>(_onDisconnect);
  on<ErrorEvent>(_onError);
  on<ApprovalRequestedEvent>(_onApprovalRequested);
  on<ApproveToolCallEvent>(_onApproveToolCall);
  on<RejectToolCallEvent>(_onRejectToolCall);
  on<SendPlanDecisionEvent>(_onSendPlanDecision);
  
  // Подписываемся на approval requests
  _approvalSubscription = _approvalService.approvalRequests.listen((request) {
    _handleApprovalRequest(request);
  });
}
```

**Станет:**
```dart
super(AgentChatState.initial()) {
  on<SendMessageEvent>(_onSendMessage);
  on<MessageReceivedEvent>(_onMessageReceived);
  on<SwitchAgentEvent>(_onSwitchAgent);
  on<LoadHistoryEvent>(_onLoadHistory);
  on<ConnectEvent>(_onConnect);
  on<DisconnectEvent>(_onDisconnect);
  on<ErrorEvent>(_onError);
  on<ApprovalRequestedEvent>(_onApprovalRequested);
  on<ApproveToolCallEvent>(_onApproveToolCall);
  on<RejectToolCallEvent>(_onRejectToolCall);
  on<SendPlanDecisionEvent>(_onSendPlanDecision);
  
  // Подписываемся на approval requests через middleware
  _approvalMiddleware.startListening(
    onToolApproval: (request) => add(AgentChatEvent.approvalRequested(request)),
  );
}
```

**Улучшения:**
- ✅ Делегирование подписки ApprovalMiddleware
- ✅ Удаление прямой работы с ApprovalService

### Шаг 7: Обновить close() (5 мин)

**Было:**
```dart
@override
Future<void> close() async {
  _logger.d('[AgentChatBloc] 🔒 Closing bloc');
  await _messageSubscription?.cancel();
  await _approvalSubscription?.cancel();
  return super.close();
}
```

**Станет:**
```dart
@override
Future<void> close() async {
  _logger.d('[AgentChatBloc] 🔒 Closing bloc');
  await _connectionMiddleware.dispose();
  await _approvalMiddleware.dispose();
  return super.close();
}
```

**Улучшения:**
- ✅ Делегирование очистки middleware
- ✅ Удаление прямого управления subscriptions

## 📊 Ожидаемые результаты

### Метрики

| Метрика | Было | Станет | Изменение |
|---------|------|--------|-----------|
| **Строки кода** | 809 | ~300 | -509 (-63%) |
| **Зависимости** | 9 | 6 | -3 (-33%) |
| **Event handlers** | 14 | 11 | -3 (-21%) |
| **Вспомогательные методы** | 2 | 0 | -2 (-100%) |
| **Сложность (цикломатическая)** | Высокая | Низкая | ⬇️ |

### Преимущества

✅ **Упрощение архитектуры**
- Четкое разделение ответственностей (SRP)
- BLoC фокусируется только на state management
- Middleware инкапсулируют бизнес-логику

✅ **Улучшение тестируемости**
- Middleware тестируются изолированно
- BLoC тесты становятся проще
- Меньше моков в тестах

✅ **Переиспользование**
- Middleware можно использовать в других BLoC
- Единая логика обработки approvals
- Единая логика подключения

✅ **Поддерживаемость**
- Меньше кода = меньше багов
- Проще понять и модифицировать
- Легче добавлять новые фичи

## 🔄 Обратная совместимость

### API BLoC (без изменений)

**Events:** Все события остаются без изменений
**State:** Состояние остается без изменений
**UI:** Никаких изменений в UI не требуется

### Изменения только в DI

**Было:**
```dart
GetIt.I.registerFactory<AgentChatBloc>(
  () => AgentChatBloc(
    sendMessage: GetIt.I(),
    sendToolResult: GetIt.I(),
    receiveMessages: GetIt.I(),
    switchAgent: GetIt.I(),
    loadHistory: GetIt.I(),
    connect: GetIt.I(),
    executeTool: GetIt.I(),
    sendPlanDecision: GetIt.I(),
    approvalService: GetIt.I(),
    logger: GetIt.I(),
  ),
);
```

**Станет:**
```dart
GetIt.I.registerFactory<AgentChatBloc>(
  () => AgentChatBloc(
    connectionMiddleware: GetIt.I(),
    messageHandlerMiddleware: GetIt.I(),
    approvalMiddleware: GetIt.I(),
    sendMessage: GetIt.I(),
    switchAgent: GetIt.I(),
    loadHistory: GetIt.I(),
    sendPlanDecision: GetIt.I(),
    logger: GetIt.I(),
  ),
);
```

## ⏱️ Оценка времени

| Шаг | Описание | Время |
|-----|----------|-------|
| 1 | Обновить конструктор | 10 мин |
| 2 | Упростить _onConnect | 20 мин |
| 3 | Упростить _onMessageReceived | 30 мин |
| 4 | Упростить _onDisconnect | 10 мин |
| 5 | Удалить устаревшие методы | 10 мин |
| 6 | Обновить инициализацию | 10 мин |
| 7 | Обновить close() | 5 мин |
| 8 | Обновить DI bindings | 15 мин |
| 9 | Тестирование | 30 мин |
| **Итого** | | **2 часа 20 мин** |

## 🎯 Следующие шаги

1. ✅ Создать план рефакторинга (этот документ)
2. ⏳ Выполнить рефакторинг AgentChatBloc
3. ⏳ Обновить DI bindings
4. ⏳ Обновить тесты
5. ⏳ Создать migration guide
6. ⏳ Финальная документация

---

**Статус:** 📝 План готов к выполнению
**Дата:** 2026-02-03
**Автор:** Roo (Code Mode)
