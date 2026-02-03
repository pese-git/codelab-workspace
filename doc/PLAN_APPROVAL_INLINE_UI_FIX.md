# Исправление черного экрана: замена диалога на встроенное окно подтверждения плана

## Проблема

После закрытия диалога утверждения плана пользователь видел черный экран без возможности продолжать общение в чате с агентом.

## Анализ первоначальной проблемы

### Логи показывали:
```
flutter: [AgentChatBloc] ✅ Plan decision sent successfully: approve
flutter: [ChatPage] BlocListener triggered: pendingPlan=null
flutter: [ConnectionMiddleware] 📨 Message received: MessageRole.system
flutter: [MessageHandlerMiddleware] 📨 Message received: MessageRole.system, content type: ErrorMessageContent
flutter: [ChatPage] BlocListener triggered: pendingPlan=null
```

### Корневая причина:
Использование модального диалога (`showDialog`) для подтверждения плана создавало проблемы:
1. Диалог блокировал весь UI
2. После закрытия диалога состояние не восстанавливалось корректно
3. `BlocListener` пытался показать диалог повторно, создавая конфликты

## Решение

Заменили модальный диалог на встроенное окно подтверждения, аналогичное tool approval.

### Изменения в архитектуре

#### 1. Удален BlocListener из [`chat_page.dart`](../codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/presentation/pages/chat_page.dart)

**Было:**
```dart
return BlocListener<AgentChatBloc, AgentChatState>(
  bloc: widget.bloc,
  listener: (context, state) {
    final pendingPlan = state.pendingPlanApproval.toNullable();
    if (pendingPlan != null) {
      pendingPlan.content.maybeWhen(
        planApprovalRequired: (approvalRequestId, planId, planSummary, content) {
          if (_currentDialogPlanId != planId) {
            _showPlanApprovalDialog(context, pendingPlan);
          }
        },
        orElse: () {},
      );
    }
  },
  child: BlocBuilder<AgentChatBloc, AgentChatState>(...),
);
```

**Стало:**
```dart
return BlocBuilder<AgentChatBloc, AgentChatState>(
  bloc: widget.bloc,
  builder: (context, state) {
    final pendingPlanApproval = state.pendingPlanApproval.toNullable();
    // ... используется в UI напрямую
  },
);
```

#### 2. Добавлено встроенное окно подтверждения плана

**Новый метод `_buildPlanApprovalButtons`:**
```dart
Widget _buildPlanApprovalButtons(BuildContext context, Message pendingPlan) {
  return pendingPlan.content.maybeWhen(
    planApprovalRequired: (approvalRequestId, planId, planSummary, content) {
      final goal = planSummary['goal'] as String? ?? 'No goal specified';
      final subtasksCount = planSummary['subtasks_count'] as int? ?? 0;
      final estimatedTime = planSummary['total_estimated_time'] as String? ?? 'Unknown';

      return Container(
        padding: AppSpacing.paddingLg,
        decoration: BoxDecoration(
          color: AppColors.info.withOpacity(0.1),
          border: Border(
            top: BorderSide(color: AppColors.info, width: 2),
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Заголовок с иконкой
            Row(
              children: [
                Icon(FluentIcons.task_manager, color: AppColors.info),
                AppSpacing.gapHorizontalSm,
                Expanded(
                  child: Text('Plan approval required', style: AppTypography.labelLarge),
                ),
              ],
            ),
            
            // Описание
            AppSpacing.gapVerticalSm,
            Text('The agent has created a plan to accomplish your request.'),
            
            // Информация о плане
            AppSpacing.gapVerticalSm,
            Container(
              padding: AppSpacing.paddingSm,
              decoration: BoxDecoration(
                color: AppColors.grey20,
                borderRadius: AppSpacing.borderRadiusXs,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Goal: $goal', style: AppTypography.bodySmall),
                  AppSpacing.gapVerticalXs,
                  Text('Subtasks: $subtasksCount • Estimated time: $estimatedTime'),
                ],
              ),
            ),
            
            // Кнопки действий
            AppSpacing.gapVerticalLg,
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                Button(
                  onPressed: () {
                    widget.bloc.add(
                      AgentChatEvent.sendPlanDecision(
                        approvalRequestId: approvalRequestId,
                        planId: planId,
                        decision: 'reject',
                        feedback: 'User rejected the plan',
                      ),
                    );
                  },
                  child: const Text('Reject'),
                ),
                AppSpacing.gapHorizontalSm,
                FilledButton(
                  onPressed: () {
                    widget.bloc.add(
                      AgentChatEvent.sendPlanDecision(
                        approvalRequestId: approvalRequestId,
                        planId: planId,
                        decision: 'approve',
                      ),
                    );
                  },
                  child: const Text('Approve'),
                ),
              ],
            ),
          ],
        ),
      );
    },
    orElse: () => const SizedBox.shrink(),
  );
}
```

#### 3. Интеграция в UI

```dart
Column(
  children: [
    ChatHeader(...),
    Expanded(child: /* Messages */),
    
    // Tool approval buttons
    if (pendingApproval != null) ...[
      Divider(...),
      _buildToolApprovalButtons(context, pendingApproval),
    ],
    
    // ✅ Plan approval buttons (новое)
    if (pendingPlanApproval != null) ...[
      Divider(...),
      _buildPlanApprovalButtons(context, pendingPlanApproval),
    ],
    
    ChatInputBar(
      enabled: !waiting && pendingApproval == null && pendingPlanApproval == null,
      ...
    ),
  ],
)
```

#### 4. Обновлен [`message_bubble.dart`](../codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/presentation/molecules/message_bubble.dart)

**Удалены:**
- Параметр `onPlanTap`
- Логика `GestureDetector` для кликабельности плана
- Текст "Нажмите для просмотра деталей"

**Обновлено:**
```dart
class MessageBubble extends StatelessWidget {
  final Message message;

  const MessageBubble({
    super.key,
    required this.message,
  });
  
  // ...
  
  planApprovalRequired: (approvalRequestId, planId, planSummary, content) {
    return '**План выполнения задачи**\n\n'
        '**Цель:** $goal\n\n'
        '**Подзадач:** $subtasksCount\n'
        '**Время:** $estimatedTime\n\n'
        '_Используйте кнопки ниже для одобрения или отклонения плана_';
  },
}
```

#### 5. Удален неиспользуемый файл

```bash
rm codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/presentation/widgets/plan_approval_dialog.dart
```

#### 6. Обновлен [`agent_chat_bloc.dart`](../codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/presentation/bloc/agent_chat_bloc.dart)

Добавлена обработка error сообщений:

```dart
Future<void> _onMessageReceived(
  MessageReceivedEvent event,
  Emitter<AgentChatState> emit,
) async {
  // Проверяем, является ли это error сообщением
  final isError = event.message.content.maybeWhen(
    error: (_) => true,
    orElse: () => false,
  );

  // Обновляем state
  emit(
    state.copyWith(
      messages: [...state.messages, event.message],
      currentAgent: newAgent.fold(() => state.currentAgent, (agent) => agent),
      isLoading: false,
      pendingPlanApproval: isPlanApproval ? some(event.message) : state.pendingPlanApproval,
      // ✅ Очищаем error state если это не error сообщение
      error: isError ? state.error : none(),
    ),
  );
}
```

## Преимущества нового подхода

### 1. **Консистентность UI**
- Plan approval теперь работает так же, как tool approval
- Единый стиль для всех типов подтверждений
- Предсказуемое поведение для пользователя

### 2. **Упрощение кода**
- Удалено ~50 строк кода (BlocListener, логика отслеживания диалогов)
- Нет необходимости в `_currentDialogPlanId`
- Нет необходимости в отдельном виджете `PlanApprovalDialog`

### 3. **Лучшая производительность**
- Нет накладных расходов на модальные диалоги
- Нет блокировки UI
- Более плавные переходы состояний

### 4. **Улучшенный UX**
- Пользователь видит контекст чата во время принятия решения
- Нет черного экрана после закрытия
- Можно прокручивать историю сообщений
- Информация о плане всегда видна

### 5. **Упрощенное управление состоянием**
- Декларативный подход вместо императивного
- Нет побочных эффектов от `BlocListener`
- Состояние полностью контролируется BLoC

## Результаты тестирования

### Проверено:
1. ✅ Отправка запроса агенту
2. ✅ Получение плана для утверждения
3. ✅ Отображение встроенного окна подтверждения
4. ✅ Утверждение плана (кнопка Approve)
5. ✅ Отклонение плана (кнопка Reject)
6. ✅ Получение error сообщений после утверждения
7. ✅ UI остается доступным для взаимодействия
8. ✅ Возможность продолжать общение с агентом

### Логи подтверждают корректную работу:
```
flutter: [AgentChatBloc] 📋 Plan approval required
flutter: [AgentChatBloc] 📤 Sending plan decision: approve for plan 8a4fe473-...
flutter: [AgentChatBloc] ✅ Plan decision sent successfully: approve
flutter: [MessageHandlerMiddleware] 📨 Message received: MessageRole.system, content type: ErrorMessageContent
```

## Измененные файлы

1. [`chat_page.dart`](../codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/presentation/pages/chat_page.dart)
   - Удален `BlocListener`
   - Удалена логика показа диалога
   - Добавлен `_buildPlanApprovalButtons`
   - Обновлен `enabled` для `ChatInputBar`

2. [`message_bubble.dart`](../codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/presentation/molecules/message_bubble.dart)
   - Удален параметр `onPlanTap`
   - Удалена логика кликабельности
   - Обновлен текст подсказки

3. [`agent_chat_bloc.dart`](../codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/presentation/bloc/agent_chat_bloc.dart)
   - Добавлена обработка error сообщений
   - Улучшено управление `error` state

4. `plan_approval_dialog.dart` - **УДАЛЕН**

## Статистика изменений

- **Удалено:** ~120 строк кода
- **Добавлено:** ~70 строк кода
- **Чистое сокращение:** ~50 строк кода
- **Файлов изменено:** 3
- **Файлов удалено:** 1

## Выводы

Замена модального диалога на встроенное окно подтверждения:
1. ✅ Решила проблему черного экрана
2. ✅ Упростила архитектуру приложения
3. ✅ Улучшила пользовательский опыт
4. ✅ Сделала код более поддерживаемым
5. ✅ Обеспечила консистентность UI

Новый подход следует принципам:
- **Single Responsibility**: каждый компонент отвечает за свою часть
- **Declarative UI**: состояние определяет UI, а не наоборот
- **Consistency**: единый стиль для всех типов подтверждений
- **Simplicity**: меньше кода, меньше сложности

## Рекомендации на будущее

1. Использовать встроенные окна подтверждения вместо модальных диалогов для всех типов взаимодействий
2. Избегать `BlocListener` для управления UI - предпочитать декларативный подход
3. Тестировать все сценарии с получением error сообщений после действий пользователя
4. Документировать паттерны UI для консистентности в команде
