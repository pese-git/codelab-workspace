# Plan Approval UI Integration - Полная интеграция ✅

## 📋 Обзор

Полная интеграция механизма Plan Approval в Flutter UI завершена. Все компоненты протестированы и готовы к использованию.

## ✅ Реализованные компоненты

### 1. Автоматический показ диалога

**Файл:** [`chat_page.dart`](../codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/presentation/pages/chat_page.dart)

Добавлен `BlocListener` который автоматически показывает диалог при получении плана от backend:

```dart
BlocListener<AgentChatBloc, AgentChatState>(
  bloc: widget.bloc,
  listener: (context, state) {
    // Автоматически показываем диалог при получении плана
    final pendingPlan = state.pendingPlanApproval.toNullable();
    if (pendingPlan != null) {
      _showPlanApprovalDialog(context, pendingPlan);
    }
  },
  child: BlocBuilder<AgentChatBloc, AgentChatState>(
    // ... остальной UI
  ),
)
```

### 2. Кликабельные сообщения с планом

**Файл:** [`message_bubble.dart`](../codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/presentation/molecules/message_bubble.dart)

Сообщения с планом теперь кликабельны и показывают диалог при нажатии:

```dart
class MessageBubble extends StatelessWidget {
  final Message message;
  final VoidCallback? onPlanTap;

  // ...

  @override
  Widget build(BuildContext context) {
    final isPlanApproval = message.content is PlanApprovalRequiredMessageContent;

    Widget bubbleContent = Container(
      // ... содержимое сообщения
    );

    // Оборачиваем в GestureDetector если это план
    if (isPlanApproval && onPlanTap != null) {
      bubbleContent = GestureDetector(
        onTap: onPlanTap,
        child: MouseRegion(
          cursor: SystemMouseCursors.click,
          child: bubbleContent,
        ),
      );
    }

    return bubbleContent;
  }
}
```

### 3. Передача callback в MessageBubble

**Файл:** [`chat_page.dart`](../codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/presentation/pages/chat_page.dart)

```dart
itemBuilder: (ctx, idx) {
  final msg = messages[idx];
  final isPlanApproval = msg.content is PlanApprovalRequiredMessageContent;
  
  return RepaintBoundary(
    child: MessageBubble(
      key: ValueKey(msg.id),
      message: msg,
      onPlanTap: isPlanApproval 
          ? () => _showPlanApprovalDialog(context, msg)
          : null,
    ),
  );
}
```

### 4. Метод показа диалога

```dart
void _showPlanApprovalDialog(BuildContext context, Message pendingPlan) {
  pendingPlan.content.maybeWhen(
    planApprovalRequired: (approvalRequestId, planId, planSummary, content) {
      showDialog(
        context: context,
        barrierDismissible: false,
        builder: (dialogContext) => PlanApprovalDialog(
          approvalRequestId: approvalRequestId,
          planId: planId,
          planSummary: planSummary,
          onDecision: (decision, feedback) {
            widget.bloc.add(
              AgentChatEvent.sendPlanDecision(
                approvalRequestId: approvalRequestId,
                planId: planId,
                decision: decision,
                feedback: feedback,
              ),
            );
            Navigator.of(dialogContext).pop();
          },
        ),
      );
    },
    orElse: () {},
  );
}
```

## 🧪 Widget тесты

**Файл:** [`plan_approval_dialog_test.dart`](../codelab_ide/packages/codelab_ai_assistant/test/features/agent_chat/presentation/widgets/plan_approval_dialog_test.dart)

Созданы комплексные widget тесты покрывающие:

### Тесты отображения
- ✅ Отображение заголовка диалога
- ✅ Отображение цели плана
- ✅ Отображение количества подзадач
- ✅ Отображение общего времени выполнения
- ✅ Отображение списка подзадач
- ✅ Отображение кнопок действий
- ✅ Отображение зависимостей подзадач

### Тесты взаимодействия
- ✅ Вызов callback при одобрении
- ✅ Вызов callback при отклонении
- ✅ Показ поля feedback при нажатии "Изменить план"
- ✅ Отправка feedback при изменении плана

### Тесты граничных случаев
- ✅ Обработка пустого planSummary

### Запуск тестов

```bash
cd codelab_ide/packages/codelab_ai_assistant
flutter test test/features/agent_chat/presentation/widgets/plan_approval_dialog_test.dart
```

## 🔄 Полный workflow

### 1. Backend отправляет план

```json
{
  "type": "plan_approval_required",
  "approval_request_id": "req-123",
  "plan_id": "plan-456",
  "plan_summary": {
    "goal": "Создать новую функцию",
    "subtasks_count": 3,
    "total_estimated_time": "2 hours",
    "subtasks": [...]
  }
}
```

### 2. Client получает и обрабатывает

1. WebSocket получает сообщение
2. `MessageModel` парсит в `Message` entity
3. `AgentChatBloc` получает сообщение через `_onMessageReceived`
4. BLoC обновляет `state.pendingPlanApproval`
5. `BlocListener` в `ChatPage` детектирует изменение
6. Автоматически показывается `PlanApprovalDialog`

### 3. User принимает решение

1. User просматривает план в диалоге
2. Нажимает "Одобрить", "Отклонить" или "Изменить план"
3. Callback вызывает `AgentChatEvent.sendPlanDecision`
4. BLoC отправляет решение через `SendPlanDecisionUseCase`
5. Repository отправляет через WebSocket на backend
6. State очищает `pendingPlanApproval`
7. Диалог закрывается

### 4. Повторный просмотр плана

1. User кликает на сообщение с планом в чате
2. `MessageBubble` вызывает `onPlanTap` callback
3. Показывается тот же `PlanApprovalDialog`
4. User может просмотреть детали (но не изменить решение)

## 📊 Структура данных

### Message Entity

```dart
@freezed
abstract class Message with _$Message {
  const factory Message({
    required String id,
    required MessageRole role,
    required MessageContent content,
    required DateTime timestamp,
    Option<Map<String, dynamic>>? metadata,
  }) = _Message;
}
```

### MessageContent - Plan Approval

```dart
@freezed
sealed class MessageContent with _$MessageContent {
  const factory MessageContent.planApprovalRequired({
    required String approvalRequestId,
    required String planId,
    required Map<String, dynamic> planSummary,
    String? content,
  }) = PlanApprovalRequiredMessageContent;
}
```

### Plan Summary Structure

```dart
{
  'goal': String,                    // Цель задачи
  'subtasks_count': int,             // Количество подзадач
  'total_estimated_time': String,    // Общее время
  'subtasks': [                      // Список подзадач
    {
      'description': String,         // Описание подзадачи
      'agent': String,               // Агент для выполнения
      'estimated_time': String,      // Время выполнения
      'dependencies': List<String>,  // Зависимости
    }
  ]
}
```

## 🎨 UI/UX особенности

### Визуальные индикаторы

1. **Сообщение с планом в чате:**
   - Желтый фон (`AppColors.warning.withOpacity(0.1)`)
   - Желтая рамка (`AppColors.warning.withOpacity(0.3)`)
   - Иконка 📋 в заголовке
   - Текст "План требует одобрения"
   - Курсор pointer при наведении

2. **Диалог плана:**
   - Иконка 🔧 для заголовка
   - Цветные карточки для метрик (подзадачи, время)
   - Нумерованные подзадачи
   - Бейджи для агента, времени и зависимостей

### Интерактивность

- **Автоматический показ:** Диалог появляется сразу при получении плана
- **Кликабельность:** Можно повторно открыть план кликнув на сообщение
- **Модальность:** Диалог блокирует взаимодействие с чатом (`barrierDismissible: false`)
- **Feedback:** Опциональное поле для комментариев при изменении плана

## 🔧 Настройка и использование

### Требования

- Flutter SDK >= 3.0.0
- fluent_ui package
- flutter_bloc package
- freezed для code generation

### Интеграция в новый экран

```dart
class MyCustomChatPage extends StatelessWidget {
  final AgentChatBloc bloc;

  @override
  Widget build(BuildContext context) {
    return BlocListener<AgentChatBloc, AgentChatState>(
      bloc: bloc,
      listener: (context, state) {
        final pendingPlan = state.pendingPlanApproval.toNullable();
        if (pendingPlan != null) {
          _showPlanDialog(context, pendingPlan);
        }
      },
      child: YourChatUI(),
    );
  }

  void _showPlanDialog(BuildContext context, Message plan) {
    plan.content.maybeWhen(
      planApprovalRequired: (reqId, planId, summary, content) {
        showDialog(
          context: context,
          builder: (_) => PlanApprovalDialog(
            approvalRequestId: reqId,
            planId: planId,
            planSummary: summary,
            onDecision: (decision, feedback) {
              bloc.add(AgentChatEvent.sendPlanDecision(
                approvalRequestId: reqId,
                planId: planId,
                decision: decision,
                feedback: feedback,
              ));
              Navigator.pop(context);
            },
          ),
        );
      },
      orElse: () {},
    );
  }
}
```

## 📝 Примеры использования

### Пример 1: Базовое использование

```dart
// В вашем BLoC listener
BlocListener<AgentChatBloc, AgentChatState>(
  listener: (context, state) {
    if (state.pendingPlanApproval.isSome()) {
      // Показать диалог
    }
  },
)
```

### Пример 2: Кастомизация диалога

```dart
PlanApprovalDialog(
  approvalRequestId: 'req-123',
  planId: 'plan-456',
  planSummary: {
    'goal': 'Custom goal',
    'subtasks_count': 5,
    'total_estimated_time': '3 hours',
    'subtasks': [...],
  },
  onDecision: (decision, feedback) {
    print('Decision: $decision');
    print('Feedback: $feedback');
  },
)
```

### Пример 3: Обработка решений

```dart
void handlePlanDecision(String decision, String? feedback) {
  switch (decision) {
    case 'approve':
      print('План одобрен');
      break;
    case 'reject':
      print('План отклонен');
      break;
    case 'modify':
      print('План требует изменений: $feedback');
      break;
  }
}
```

## 🐛 Отладка

### Логирование

BLoC логирует все события связанные с планами:

```
[AgentChatBloc] 📋 Plan approval required: plan-456
[AgentChatBloc] 📤 Sending plan decision: approve for plan plan-456
[AgentChatBloc] ✅ Plan decision sent successfully: approve
```

### Проверка состояния

```dart
// В DevTools или debug console
print(state.pendingPlanApproval.isSome()); // true если есть pending план
print(state.messages.where((m) => 
  m.content is PlanApprovalRequiredMessageContent
).length); // количество планов в истории
```

## 🚀 Следующие шаги

### Возможные улучшения

1. **Анимации:**
   - Плавное появление диалога
   - Анимация при раскрытии подзадач

2. **Дополнительные функции:**
   - Экспорт плана в PDF
   - Сохранение плана в избранное
   - История изменений плана

3. **Accessibility:**
   - Screen reader support
   - Keyboard navigation
   - High contrast mode

4. **Производительность:**
   - Lazy loading для больших списков подзадач
   - Кэширование планов

## 📚 Связанная документация

- [PLAN_APPROVAL_FULL_IMPLEMENTATION_COMPLETE.md](./PLAN_APPROVAL_FULL_IMPLEMENTATION_COMPLETE.md) - Полная реализация backend и client
- [PLAN_APPROVAL_CLIENT_IMPLEMENTATION.md](./PLAN_APPROVAL_CLIENT_IMPLEMENTATION.md) - Детали client реализации
- [PLAN_APPROVAL_COMPLETE.md](./PLAN_APPROVAL_COMPLETE.md) - Backend реализация

## ✅ Чеклист готовности

- [x] BlocListener добавлен в chat_page.dart
- [x] MessageBubble поддерживает onPlanTap callback
- [x] Автоматический показ диалога работает
- [x] Кликабельность сообщений с планом работает
- [x] Widget тесты написаны и проходят
- [x] Документация обновлена
- [x] Примеры использования добавлены
- [x] Логирование настроено
- [x] Обработка ошибок реализована

## 🎉 Заключение

Полная интеграция Plan Approval в Flutter UI завершена. Все компоненты протестированы, задокументированы и готовы к использованию в production.

Механизм обеспечивает:
- ✅ Автоматический показ планов
- ✅ Интерактивное взаимодействие
- ✅ Полную интеграцию с backend
- ✅ Отличный UX
- ✅ Покрытие тестами
- ✅ Подробную документацию
