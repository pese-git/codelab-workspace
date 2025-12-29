# Тестирование функциональности подтверждения tools

## Шаги для тестирования

1. Перезапустить Docker контейнеры с обновленным кодом:
   ```bash
   cd codelab-ai-service
   docker-compose down
   docker-compose up --build
   ```

2. Запустить Flutter IDE приложение

3. Отправить команду, которая должна вызвать `write_file` tool:
   ```
   Создай файл test.txt с текстом "Hello World"
   ```

4. Ожидаемое поведение:
   - Агент должен вызвать tool `write_file` с параметрами `{path: "test.txt", content: "Hello World"}`
   - Backend должен установить `requires_approval: true` для этого tool call
   - UI должен отобразить оранжевый блок с кнопками "Approve" и "Reject" над полем ввода
   - Поле ввода должно быть заблокировано
   - При нажатии "Approve" - файл должен быть создан
   - При нажатии "Reject" - операция должна быть отменена

## Текущие проблемы

### Проблема 1: Агент не вызывает write_file
**Симптом:** Агент отвечает текстом "Пожалуйста, подтвердите..." вместо вызова tool

**Причина:** Промпт агента не достаточно четко указывает, что нужно вызывать tools напрямую

**Решение:** Обновить промпт в [`prompts.py`](../codelab-ai-service/agent-runtime/app/core/agent/prompts.py) с более четкими инструкциями

### Проблема 2: Агент застревает в цикле
**Симптом:** Агент бесконечно вызывает `read_file` для одного и того же файла

**Причина:** Отсутствие логики обработки повторяющихся неудачных tool calls

**Решение:** Добавить в агент логику:
- Отслеживание количества повторных вызовов одного и того же tool
- Прекращение попыток после N неудачных вызовов
- Отправка сообщения пользователю о проблеме

## Реализованные компоненты

### Backend
- ✅ [`llm_stream_service.py`](../codelab-ai-service/agent-runtime/app/services/llm_stream_service.py) - логика определения `requires_approval`
- ✅ [`schemas.py`](../codelab-ai-service/agent-runtime/app/models/schemas.py) - поле `requires_approval` в `StreamChunk`

### Frontend
- ✅ [`ai_agent_bloc.dart`](../codelab_ide/packages/codelab_ai_assistant/lib/src/bloc/ai_agent_bloc.dart) - события и состояние для подтверждения
- ✅ [`ai_assistant_panel.dart`](../codelab_ide/packages/codelab_ai_assistant/lib/src/ui/ai_assistant_panel.dart) - UI кнопок подтверждения
- ✅ [`ai_assistant_module.dart`](../codelab_ide/packages/codelab_ai_assistant/lib/src/di/ai_assistant_module.dart) - DI для `approvalService`
- ✅ [`ai_assistant_panel_test.dart`](../codelab_ide/packages/codelab_ai_assistant/test/ui/ai_assistant_panel_test.dart) - обновлены тесты

## Демонстрация UI

Когда `pendingApproval` присутствует в состоянии, над полем ввода отображается:

```
┌─────────────────────────────────────────────────────────┐
│ Для подтверждения: Создать файл write_file с           │
│ содержимым "{path: test.txt, content: Hello World}"?    │
│                                                         │
│ Пожалуйста, подтвердите, чтобы я мог выполнить эту     │
│ операцию.                                               │
│                                                         │
│                                    [Reject]  [Approve]  │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│ Введите ваш вопрос... (заблокировано)            [📤]  │
└─────────────────────────────────────────────────────────┘
```

## Следующие шаги

1. Перезапустить Docker контейнеры
2. Протестировать с реальным `write_file` tool call
3. Исправить промпт агента для корректного вызова tools
4. Добавить логику предотвращения циклов
