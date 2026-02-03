# Phase 4: Bugfix - Infinite Loop in Plan Approval

## 🐛 Проблема

**Дата обнаружения:** 2026-02-03  
**Серьезность:** 🔴 **КРИТИЧЕСКАЯ**  
**Статус:** ✅ **ИСПРАВЛЕНО**

### Описание

После рефакторинга AgentChatBloc приложение зациклилось при обработке plan approval сообщений.

### Симптомы

```
flutter: │ 🐛 [AgentChatBloc] 📨 Message received: MessageRole.system
flutter: │ 🐛 [MessageHandlerMiddleware] 📨 Message received: MessageRole.system, content type: PlanApprovalRequiredMessageContent
flutter: │ 💡 [MessageHandlerMiddleware] 📋 Plan approval required: 2df440b3-8564-490e-a09d-e27f52f76ad4
flutter: │ 💡 [AgentChatBloc] 📋 Plan approval required
flutter: [ChatPage] BlocListener triggered: pendingPlan=present
flutter: [ChatPage] Dialog already shown for plan: 2df440b3-8564-490e-a09d-e27f52f76ad4, skipping
flutter: │ 🐛 [AgentChatBloc] 📨 Message received: MessageRole.system
flutter: │ 🐛 [MessageHandlerMiddleware] 📨 Message received: MessageRole.system, content type: PlanApprovalRequiredMessageContent
... (повторяется бесконечно)
```

### Root Cause

В методе [`_onMessageReceived`](../codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/presentation/bloc/agent_chat_bloc.dart:196) callback `onPlanApproval` вызывал `add(AgentChatEvent.messageReceived(message))`, что создавало бесконечный цикл:

```dart
// ❌ НЕПРАВИЛЬНО - создает бесконечный цикл
final newAgent = await _messageHandlerMiddleware.handleMessage(
  message: event.message,
  onPlanApproval: (message) {
    _logger.i('[AgentChatBloc] 📋 Plan approval required');
    add(AgentChatEvent.messageReceived(message)); // ← ОШИБКА!
  },
);
```

**Цикл:**
1. `_onMessageReceived` получает plan approval сообщение
2. Вызывает `messageHandlerMiddleware.handleMessage()`
3. Middleware вызывает `onPlanApproval(message)`
4. Callback вызывает `add(AgentChatEvent.messageReceived(message))`
5. Возвращаемся к шагу 1 → **бесконечный цикл**

## ✅ Решение

### Исправление

Удалил вызов `add()` из callback, так как state уже обновляется через `emit()` в конце метода:

```dart
// ✅ ПРАВИЛЬНО - без бесконечного цикла
final newAgent = await _messageHandlerMiddleware.handleMessage(
  message: event.message,
  onPlanApproval: (message) {
    _logger.i('[AgentChatBloc] 📋 Plan approval required');
    // НЕ вызываем add() здесь - это создает бесконечный цикл!
    // State будет обновлен ниже через emit
  },
);

// Обновляем state один раз
emit(
  state.copyWith(
    messages: [...state.messages, event.message],
    currentAgent: newAgent.fold(() => state.currentAgent, (agent) => agent),
    isLoading: false,
    pendingPlanApproval: isPlanApproval ? some(event.message) : state.pendingPlanApproval,
  ),
);
```

### Изменения в коде

**Файл:** [`agent_chat_bloc.dart:196-227`](../codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/presentation/bloc/agent_chat_bloc.dart:196)

**До:**
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
      add(AgentChatEvent.messageReceived(message)); // ❌ ОШИБКА
    },
  );

  final isPlanApproval = event.message.content.maybeWhen(
    planApprovalRequired: (_, __, ___, ____) => true,
    orElse: () => false,
  );

  emit(
    state.copyWith(
      messages: [...state.messages, event.message],
      currentAgent: newAgent.fold(() => state.currentAgent, (agent) => agent),
      isLoading: false,
      pendingPlanApproval: isPlanApproval ? some(event.message) : state.pendingPlanApproval,
    ),
  );
}
```

**После:**
```dart
Future<void> _onMessageReceived(
  MessageReceivedEvent event,
  Emitter<AgentChatState> emit,
) async {
  _logger.d('[AgentChatBloc] 📨 Message received: ${event.message.role}');

  // Проверяем, является ли это plan approval сообщением
  final isPlanApproval = event.message.content.maybeWhen(
    planApprovalRequired: (_, __, ___, ____) => true,
    orElse: () => false,
  );

  // Обрабатываем сообщение через MessageHandlerMiddleware
  final newAgent = await _messageHandlerMiddleware.handleMessage(
    message: event.message,
    onPlanApproval: (message) {
      _logger.i('[AgentChatBloc] 📋 Plan approval required');
      // НЕ вызываем add() здесь - это создает бесконечный цикл!
      // State будет обновлен ниже через emit
    },
  );

  // Обновляем state
  emit(
    state.copyWith(
      messages: [...state.messages, event.message],
      currentAgent: newAgent.fold(() => state.currentAgent, (agent) => agent),
      isLoading: false,
      pendingPlanApproval: isPlanApproval ? some(event.message) : state.pendingPlanApproval,
    ),
  );
}
```

## 📊 Анализ

### Почему это произошло

1. **Неправильное понимание callback**
   - Callback `onPlanApproval` предназначен только для уведомления
   - Не должен вызывать новые events

2. **Отсутствие проверки на дубликаты**
   - Не было защиты от повторной обработки того же сообщения

3. **Недостаточное тестирование**
   - Runtime тестирование не было выполнено до коммита

### Извлеченные уроки

✅ **Callbacks должны быть простыми**
- Только уведомление, без side effects
- Не вызывать `add()` из callbacks

✅ **Тестировать в runtime**
- Компиляция != работающий код
- Нужно проверять реальные сценарии

✅ **Добавить защиту от циклов**
- Проверять дубликаты events
- Добавить таймауты

## 🔍 Проверка исправления

### Ожидаемое поведение

1. Plan approval сообщение приходит **один раз**
2. State обновляется **один раз**
3. UI показывает диалог **один раз**
4. Нет повторных обработок

### Тестирование

```bash
# 1. Запустить приложение
cd codelab_ide
flutter run

# 2. Подключиться к сессии
# 3. Отправить сообщение, требующее plan approval
# 4. Проверить логи - должно быть только одно сообщение
```

**Ожидаемые логи:**
```
flutter: │ 🐛 [AgentChatBloc] 📨 Message received: MessageRole.system
flutter: │ 🐛 [MessageHandlerMiddleware] 📨 Message received: MessageRole.system, content type: PlanApprovalRequiredMessageContent
flutter: │ 💡 [MessageHandlerMiddleware] 📋 Plan approval required: <plan-id>
flutter: │ 💡 [AgentChatBloc] 📋 Plan approval required
flutter: [ChatPage] BlocListener triggered: pendingPlan=present
flutter: [ChatPage] Showing plan approval dialog for plan: <plan-id>
```

## 📝 Рекомендации

### Для будущих рефакторингов

1. **Всегда тестировать в runtime**
   - Не полагаться только на компиляцию
   - Проверять реальные сценарии

2. **Осторожно с callbacks**
   - Документировать назначение
   - Избегать side effects
   - Не вызывать `add()` из callbacks

3. **Добавлять защиту**
   - Проверки на дубликаты
   - Таймауты для операций
   - Логирование для отладки

4. **Code review**
   - Проверять на потенциальные циклы
   - Анализировать flow данных
   - Тестировать edge cases

### Улучшения для MessageHandlerMiddleware

Можно улучшить API middleware, чтобы избежать подобных ошибок:

```dart
// Вместо callback можно возвращать информацию
class MessageHandlingResult {
  final Option<String> newAgent;
  final bool isPlanApproval;
  
  const MessageHandlingResult({
    required this.newAgent,
    required this.isPlanApproval,
  });
}

Future<MessageHandlingResult> handleMessage({
  required Message message,
}) async {
  // Обработка без callbacks
  final isPlanApproval = message.content.maybeWhen(
    planApprovalRequired: (_, __, ___, ____) => true,
    orElse: () => false,
  );
  
  final newAgent = _extractAgentSwitch(message);
  
  return MessageHandlingResult(
    newAgent: newAgent,
    isPlanApproval: isPlanApproval,
  );
}
```

## ✅ Статус

- [x] Проблема идентифицирована
- [x] Root cause найден
- [x] Исправление применено
- [ ] Runtime тестирование
- [ ] Обновить тесты
- [ ] Документировать в migration guide

---

**Дата:** 2026-02-03  
**Автор:** Roo (Code Mode)  
**Статус:** ✅ Исправлено, требуется проверка
