# Изменения в codelab_ide для поддержки plan_decision

## Проблема

IDE использует старое название `plan_approval`, а backend реализован с `plan_decision`.

## Необходимые изменения (только approve/reject)

### 1. Обновить AgentRepositoryImpl

#### Файл: [`lib/features/agent_chat/data/repositories/agent_repository_impl.dart`](codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/data/repositories/agent_repository_impl.dart)

**Строка 411** - изменить тип сообщения:

```dart
@override
Future<Either<Failure, Unit>> approvePlan({
  required String planId,
  Option<String> feedback = const None(),
}) async {
  try {
    final model = MessageModel(
      type: 'plan_decision',  // ← Было: 'plan_approval'
      planId: planId,
      decision: 'approve',
      feedback: feedback.toNullable(),
    );

    await _remoteDataSource.sendMessage(model);
    _activePlan = _activePlan.map((plan) => plan.approve());

    return right(unit);
  } on WebSocketException catch (e) {
    return left(Failure.network(e.message));
  } catch (e) {
    return left(Failure.server('Failed to approve plan: $e'));
  }
}
```

**Строка 437** - изменить тип сообщения:

```dart
@override
Future<Either<Failure, Unit>> rejectPlan({
  required String planId,
  required String reason,
}) async {
  try {
    final model = MessageModel(
      type: 'plan_decision',  // ← Было: 'plan_approval'
      planId: planId,
      decision: 'reject',
      feedback: reason,
    );

    await _remoteDataSource.sendMessage(model);
    _activePlan = none();

    return right(unit);
  } on WebSocketException catch (e) {
    return left(Failure.network(e.message));
  } catch (e) {
    return left(Failure.server('Failed to reject plan: $e'));
  }
}
```

## Итого

Нужно изменить **только 2 строки** в одном файле:
- Строка 411: `type: 'plan_decision'`
- Строка 437: `type: 'plan_decision'`

Это обеспечит совместимость с новым backend протоколом.

## Протокол взаимодействия

### Backend ожидает:
```json
{
  "type": "plan_decision",
  "plan_id": "plan_abc123",
  "decision": "approve|reject",
  "feedback": "..."
}
```

### IDE отправляет (после изменений):
```json
{
  "type": "plan_decision",
  "plan_id": "plan_abc123",
  "decision": "approve",
  "feedback": null
}
```

✅ Полная совместимость

## Тестирование

После внесения изменений:

1. Запустить IDE
2. Отправить сообщение: "Создай TODO приложение"
3. Дождаться `plan_notification` от Architect
4. Нажать "Подтвердить" или "Отклонить"
5. Проверить, что план выполняется/отменяется

## Функционал edit

Backend поддерживает `decision: "edit"`, но в IDE это пока не реализовано. Можно добавить позже при необходимости.
