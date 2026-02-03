# Фаза 4: BLoC Middleware - Анализ и План

**Дата:** 03 февраля 2026  
**Статус:** 📋 Планирование  
**Цель:** Упростить AgentChatBloc с 807 до <300 строк  
**Подход:** Middleware паттерн

---

## 📊 Текущее состояние AgentChatBloc

**Файл:** [`lib/features/agent_chat/presentation/bloc/agent_chat_bloc.dart`](../codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/presentation/bloc/agent_chat_bloc.dart)

**Размер:** 807 строк

**Структура:**
- 8 use cases (dependencies)
- 1 approval service
- 1 logger
- 2 subscriptions (messages, approvals)
- 11 event handlers
- 3 helper methods

---

## 🔍 Анализ ответственностей

### 1. Connection Management (~100 строк)

**Методы:**
- `_onConnect()` - подключение к WebSocket
- `_onDisconnect()` - отключение
- Управление subscriptions

**Логика:**
- Подключение к WebSocket
- Подписка на поток сообщений
- Восстановление pending approvals
- Очистка при disconnect

**Можно вынести в:** `ConnectionMiddleware`

---

### 2. Message Handling (~150 строк)

**Методы:**
- `_onMessageReceived()` - обработка входящих сообщений
- Автоматическое выполнение tool calls

**Логика:**
- Обработка разных типов сообщений
- Обновление currentAgent
- Установка pendingPlanApproval
- Автоматическое выполнение tool calls
- Проверка source (history vs websocket)

**Можно вынести в:** `MessageHandlerMiddleware`

---

### 3. Approval Management (~250 строк)

**Методы:**
- `_handleApprovalRequest()` - обработка approval requests
- `_waitForDecisionAndSend()` - ожидание решения
- `_onApprovalRequested()` - установка pending approval
- `_onApproveToolCall()` - одобрение
- `_onRejectToolCall()` - отклонение
- `_onCancelToolCall()` - отмена
- `_executeRestoredTool()` - выполнение после approve
- `_rejectRestoredTool()` - отправка rejection

**Логика:**
- Конвертация типов (ApprovalRequest ↔ ToolCall)
- Управление completers
- Отправка решений на сервер
- Выполнение tools после approve
- Обработка всех типов решений

**Можно вынести в:** `ApprovalMiddleware`

---

### 4. Basic Operations (~100 строк)

**Методы:**
- `_onSendMessage()` - отправка сообщения
- `_onSwitchAgent()` - переключение агента
- `_onLoadHistory()` - загрузка истории
- `_onSendPlanDecision()` - отправка plan decision
- `_onError()` - обработка ошибок

**Логика:**
- Простые операции с use cases
- Обновление state
- Обработка Either<Failure, T>

**Оставить в:** `AgentChatBloc` (core логика)

---

## 🎯 План рефакторинга

### Middleware архитектура

```dart
AgentChatBloc (< 300 строк)
    ├── ConnectionMiddleware (~100 строк)
    │   ├── handleConnect()
    │   ├── handleDisconnect()
    │   └── manageSubscriptions()
    │
    ├── MessageHandlerMiddleware (~150 строк)
    │   ├── handleMessageReceived()
    │   ├── processToolCall()
    │   └── updateAgentState()
    │
    └── ApprovalMiddleware (~250 строк)
        ├── handleApprovalRequest()
        ├── waitForDecision()
        ├── executeApprovedTool()
        └── sendDecisionToServer()
```

---

## 📋 Детальный план

### Этап 1: Создать базовый интерфейс (ГОТОВО ✅)

**Файл:** [`lib/core/middleware/bloc_middleware.dart`](../codelab_ide/packages/codelab_ai_assistant/lib/core/middleware/bloc_middleware.dart)

Уже создан в предыдущих фазах.

---

### Этап 2: Создать ConnectionMiddleware

**Файл:** `lib/features/agent_chat/presentation/middleware/connection_middleware.dart`

**Ответственности:**
- Управление WebSocket подключением
- Подписка на поток сообщений
- Восстановление pending approvals
- Очистка при disconnect

**Интерфейс:**
```dart
class ConnectionMiddleware {
  final ConnectUseCase _connect;
  final ReceiveMessagesUseCase _receiveMessages;
  final ApprovalService _approvalService;
  final Logger _logger;
  
  Future<void> handleConnect(
    ConnectEvent event,
    Emitter<AgentChatState> emit,
    EventHandler<AgentChatEvent, AgentChatState> next,
  ) async {
    // Логика подключения
  }
  
  Future<void> handleDisconnect(
    DisconnectEvent event,
    Emitter<AgentChatState> emit,
  ) async {
    // Логика отключения
  }
}
```

**Размер:** ~100 строк

---

### Этап 3: Создать MessageHandlerMiddleware

**Файл:** `lib/features/agent_chat/presentation/middleware/message_handler_middleware.dart`

**Ответственности:**
- Обработка входящих сообщений
- Обновление currentAgent
- Установка pendingPlanApproval
- Автоматическое выполнение tool calls

**Интерфейс:**
```dart
class MessageHandlerMiddleware {
  final ExecuteToolUseCase _executeTool;
  final SendToolResultUseCase _sendToolResult;
  final Logger _logger;
  
  Future<void> handleMessageReceived(
    MessageReceivedEvent event,
    Emitter<AgentChatState> emit,
    EventHandler<AgentChatEvent, AgentChatState> next,
  ) async {
    // Обработка сообщения
    // Автоматическое выполнение tool calls
  }
}
```

**Размер:** ~150 строк

---

### Этап 4: Создать ApprovalMiddleware

**Файл:** `lib/features/agent_chat/presentation/middleware/approval_middleware.dart`

**Ответственности:**
- Обработка approval requests
- Ожидание решений пользователя
- Выполнение approved tools
- Отправка решений на сервер

**Интерфейс:**
```dart
class ApprovalMiddleware {
  final ApprovalService _approvalService;
  final ExecuteToolUseCase _executeTool;
  final SendToolResultUseCase _sendToolResult;
  final Logger _logger;
  
  void handleApprovalRequest(ApprovalRequest request) {
    // Конвертация и эмиссия события
  }
  
  Future<void> waitForDecisionAndSend(
    ApprovalRequest request,
    Completer completer,
    ToolCall toolCall,
  ) async {
    // Ожидание и обработка решения
  }
  
  Future<void> executeApprovedTool(ToolCall toolCall) async {
    // Выполнение tool
  }
  
  Future<void> rejectTool(ToolCall toolCall, String reason) async {
    // Отправка rejection
  }
}
```

**Размер:** ~250 строк

---

### Этап 5: Упростить AgentChatBloc

**Текущий размер:** 807 строк

**Целевой размер:** <300 строк

**Что остается в BLoC:**
- Event handlers (делегируют в middleware)
- State management
- Basic operations (sendMessage, switchAgent, loadHistory, sendPlanDecision)

**Что переносится:**
- Connection logic → ConnectionMiddleware
- Message handling → MessageHandlerMiddleware
- Approval logic → ApprovalMiddleware

**Новая структура:**
```dart
class AgentChatBloc extends Bloc<AgentChatEvent, AgentChatState> {
  // Dependencies
  final ConnectionMiddleware _connectionMiddleware;
  final MessageHandlerMiddleware _messageMiddleware;
  final ApprovalMiddleware _approvalMiddleware;
  
  // Use cases (только для basic operations)
  final SendMessageUseCase _sendMessage;
  final SwitchAgentUseCase _switchAgent;
  final LoadHistoryUseCase _loadHistory;
  final SendPlanDecisionUseCase _sendPlanDecision;
  
  AgentChatBloc({...}) {
    // Event handlers делегируют в middleware
    on<ConnectEvent>(_connectionMiddleware.handleConnect);
    on<DisconnectEvent>(_connectionMiddleware.handleDisconnect);
    on<MessageReceivedEvent>(_messageMiddleware.handleMessageReceived);
    on<ApprovalRequestedEvent>(_approvalMiddleware.handleApprovalRequested);
    // ...
    
    // Basic operations остаются в BLoC
    on<SendMessageEvent>(_onSendMessage);
    on<SwitchAgentEvent>(_onSwitchAgent);
    on<LoadHistoryEvent>(_onLoadHistory);
    on<SendPlanDecisionEvent>(_onSendPlanDecision);
  }
}
```

---

## 📊 Ожидаемые результаты

### Метрики

| Метрика | До | После | Улучшение |
|---------|-----|-------|-----------|
| Строк в AgentChatBloc | 807 | <300 | -63% |
| Методов в BLoC | 14 | 6 | -57% |
| Ответственностей | 4 | 1 | -75% |
| Middleware файлов | 0 | 3 | +3 |
| Переиспользуемость | Низкая | Высокая | +100% |
| Тестируемость | Средняя | Высокая | +100% |

### Преимущества

✅ **Модульность** - каждый middleware отвечает за одну задачу  
✅ **Переиспользуемость** - middleware можно использовать в других BLoCs  
✅ **Тестируемость** - легче тестировать изолированно  
✅ **Читаемость** - меньше кода в одном файле  
✅ **Поддерживаемость** - проще находить и исправлять баги

---

## 🚀 Следующие шаги

1. Создать ConnectionMiddleware
2. Создать MessageHandlerMiddleware  
3. Создать ApprovalMiddleware
4. Обновить AgentChatBloc для использования middleware
5. Обновить DI конфигурацию
6. Обновить тесты
7. Создать документацию

**Оценка времени:** 2-3 дня

---

**Статус:** ✅ Готово к реализации
