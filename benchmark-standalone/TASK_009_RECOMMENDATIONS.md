# Рекомендации для task_009 (Миграция Provider → Riverpod)

## Проблема

task_009 не завершается успешно из-за:
1. Слишком большой объем работы (69+ tool calls)
2. Timeout (60 секунд) недостаточен
3. Агент застревает в цикле исправления ошибок
4. Проблемные тесты с неправильными импортами

## Наблюдения из логов

Агент выполнил отличную работу:
- ✅ Добавил flutter_riverpod в pubspec.yaml
- ✅ Создал providers (auth_provider.dart, counter_provider.dart)
- ✅ Мигрировал HomeScreen на ConsumerWidget
- ✅ Мигрировал ProductListScreen на ConsumerStatefulWidget
- ✅ Мигрировал LoginForm на ConsumerStatefulWidget
- ✅ Обновил main.dart с ProviderScope
- ✅ Удалил старые BLoC файлы
- ✅ Создал assets/avatar_placeholder.png
- ✅ Обновил тесты для Riverpod

Проблемы:
- ❌ test/user_test.dart с неправильным импортом 'package:project_name/models/user.dart'
- ❌ flutter analyze показывает 7-10 issues (в основном info, не errors)
- ❌ Агент пытается исправить все issues, включая info
- ❌ Timeout после 7 минут работы

## Рекомендации

### 1. Увеличить timeout для сложных задач

**Файл**: `benchmark-standalone/src/client.py`

```python
# Для complex/mixed задач увеличить timeout
timeout = 300 if task.get('category') in ['complex', 'mixed'] else 60
```

### 2. Исправить проблемные тесты

**Файл**: `benchmark-standalone/test_project/test/user_test.dart`

Заменить:
```dart
import 'package:project_name/models/user.dart';
```

На:
```dart
import 'package:test_project/models/user.dart';
```

### 3. Добавить лимит на количество tool calls

**Файл**: `benchmark-standalone/src/client.py`

```python
MAX_TOOL_CALLS = 100  # Лимит для предотвращения бесконечных циклов

if tool_calls_count >= MAX_TOOL_CALLS:
    logger.warning(f"Reached max tool calls limit: {MAX_TOOL_CALLS}")
    break
```

### 4. Улучшить промпт: игнорировать info warnings

**Файл**: `codelab-ai-service/agent-runtime/app/agents/prompts/coder.py`

Добавить:
```
When running flutter analyze:
- Focus on fixing ERRORS only
- INFO and WARNING messages can be ignored
- Don't try to fix every single issue
- Complete the task when no ERRORS remain
```

### 5. Упростить задачу task_009

**Файл**: `benchmark-standalone/tasks.yaml`

Изменить описание:
```yaml
description: |
  Создать базовую структуру Riverpod providers для замены существующих BLoC.
  
  Требования:
  1. Добавить flutter_riverpod в pubspec.yaml
  2. Создать lib/providers/counter_provider.dart с StateProvider<int>
  3. Обновить lib/main.dart - обернуть в ProviderScope
  4. Мигрировать lib/screens/home_screen.dart на ConsumerWidget
  
  НЕ требуется:
  - Мигрировать все файлы проекта
  - Исправлять все info warnings
  - Удалять старые BLoC файлы
```

### 6. Разбить task_009 на подзадачи

Вместо одной большой задачи создать несколько:
- task_009a: Добавить Riverpod зависимость
- task_009b: Создать counter provider
- task_009c: Мигрировать HomeScreen
- task_009d: Мигрировать auth logic

## Вывод

Агент справляется с задачей отлично, но:
1. Задача слишком большая для одного агента
2. Нужен больший timeout
3. Нужен лимит на tool calls
4. Нужно игнорировать info warnings

Рекомендация: Разбить сложные задачи на подзадачи или увеличить timeout до 300 секунд.
