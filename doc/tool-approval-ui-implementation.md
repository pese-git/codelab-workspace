# Реализация UI для подтверждения выполнения Tools

## Обзор

Реализована функциональность отображения кнопок "Approve"/"Reject" над полем ввода для подтверждения выполнения tool calls, требующих одобрения пользователя (HITL - Human-in-the-Loop).

## Архитектура решения

### 1. Backend (Agent Runtime)

#### Определение требования подтверждения
В [`llm_stream_service.py`](../codelab-ai-service/agent-runtime/app/services/llm_stream_service.py:111-127) добавлена логика определения, требует ли tool подтверждения:

```python
# Определяем, требуется ли подтверждение пользователя (HITL)
requires_approval = tool_call.tool_name in ["write_file", "delete_file", "move_file"]

# Для execute_command проверяем на опасные команды
if tool_call.tool_name == "execute_command":
    command = tool_call.arguments.get("command", "").lower()
    dangerous_patterns = [
        "rm -rf", "sudo", "chmod", "chown", "mkfs", 
        "dd if=", "> /dev/", ":(){ :|:& };:", "curl", "wget"
    ]
    requires_approval = any(pattern in command for pattern in dangerous_patterns)
```

#### Модель данных
В [`schemas.py`](../codelab-ai-service/agent-runtime/app/models/schemas.py:194) добавлено поле `requires_approval` в `StreamChunk`:

```python
requires_approval: Optional[bool] = Field(
    default=False, 
    description="Whether this tool requires user approval (HITL)"
)
```

### 2. Frontend (Flutter/Dart)

#### BLoC State Management

В [`ai_agent_bloc.dart`](../codelab_ide/packages/codelab_ai_assistant/lib/src/bloc/ai_agent_bloc.dart) добавлено:

**События:**
- `ApproveToolCall` - пользователь одобрил выполнение tool
- `RejectToolCall` - пользователь отклонил выполнение tool
- `ToolApprovalRequested` - получен запрос на подтверждение от `ToolApprovalService`

**Состояние:**
- Добавлено поле `pendingApproval: ToolApprovalRequest?` в `ChatState`
- Это поле содержит информацию о tool call, ожидающем подтверждения

**Обработчики:**
- `_onToolApprovalRequested` - сохраняет запрос в состояние
- `_onApproveToolCall` - завершает completer с результатом `approved`
- `_onRejectToolCall` - завершает completer с результатом `rejected`

#### UI компонент

В [`ai_assistant_panel.dart`](../codelab_ide/packages/codelab_ai_assistant/lib/src/ui/ai_assistant_panel.dart:44-117) добавлено:

**Отображение кнопок:**
```dart
if (pendingApproval != null) ...[
  _buildApprovalButtons(context, pendingApproval),
  const SizedBox(height: 8),
],
```

**Виджет кнопок подтверждения:**
- Отображается оранжевый контейнер с информацией о tool call
- Две кнопки: "Reject" (обычная) и "Approve" (FilledButton)
- Поле ввода блокируется во время ожидания подтверждения

#### Dependency Injection

В [`ai_assistant_module.dart`](../codelab_ide/packages/codelab_ai_assistant/lib/src/di/ai_assistant_module.dart:67-71) добавлен `approvalService` в конструктор `AiAgentBloc`.

## Поток данных

1. **Agent отправляет tool_call** с `requires_approval: true`
2. **Gateway** пересылает tool_call в IDE через WebSocket
3. **IDE BLoC** получает tool_call и вызывает `ToolApi.call()`
4. **ToolApi** проверяет `requiresApproval` и вызывает `approvalService.requestApproval()`
5. **ToolApprovalService** эмитирует `ToolApprovalRequest` в stream
6. **BLoC** получает запрос и обновляет состояние с `pendingApproval`
7. **UI** отображает кнопки подтверждения
8. **Пользователь** нажимает "Approve" или "Reject"
9. **UI** отправляет событие в BLoC
10. **BLoC** завершает completer с результатом
11. **ToolApi** получает результат и продолжает или отменяет выполнение
12. **BLoC** очищает `pendingApproval` из состояния

## Какие tools требуют подтверждения

- `write_file` - всегда
- `delete_file` - всегда
- `move_file` - всегда
- `execute_command` - только для опасных команд (rm -rf, sudo, и т.д.)

## Тестирование

Обновлены тесты:
- [`ai_assistant_panel_test.dart`](../codelab_ide/packages/codelab_ai_assistant/test/ui/ai_assistant_panel_test.dart) - добавлен `MockToolApprovalService`
- Все тесты обновлены для передачи `approvalService` в конструктор BLoC

## Известные проблемы

1. **Агент не вызывает write_file напрямую** - вместо этого он отвечает текстом "Пожалуйста, подтвердите...". Это проблема промпта агента, а не UI.
2. **Агент застревает в цикле** - при команде "создавай" агент бесконечно вызывает `read_file` для README.md. Это также проблема логики агента.

## Следующие шаги

1. Исправить промпт агента, чтобы он вызывал `write_file` tool напрямую
2. Добавить логику предотвращения циклов в агенте
3. Протестировать полный flow с реальным tool call, требующим подтверждения
