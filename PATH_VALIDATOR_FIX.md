# Исправление PathValidator

## Проблема

PathValidator неправильно обрабатывал путь "." (текущая директория), считая его находящимся вне workspace. Это приводило к ошибкам при попытке работы с текущей директорией проекта.

## Причины

1. **Неправильная обработка пути "."**: После преобразования "." в пустую строку и последующей нормализации, путь не корректно сравнивался с workspace root.

2. **Проблемы с каноническими путями**: Метод `_getCanonicalPath()` имел сложную логику для несуществующих файлов, что приводило к несоответствиям при проверке `_isWithinWorkspace()`.

3. **Блокировка временных директорий на macOS**: Директория `/var` была в списке запрещенных системных директорий, что блокировало работу с временными файлами в `/var/folders/`.

## Исправления

### 1. Обработка пути "." в методе `isPathSafe()`

**Файл**: [`codelab_ide/packages/codelab_core/lib/src/utils/path_validator.dart`](codelab_ide/packages/codelab_core/lib/src/utils/path_validator.dart:76-83)

```dart
// Нормализация пути
final normalizedPath = cleanPath.isEmpty ? '.' : p.normalize(cleanPath);

// Построение полного пути
// Если normalizedPath это '.', используем workspaceRoot напрямую
final fullPath = normalizedPath == '.'
    ? workspaceRoot
    : p.join(workspaceRoot, normalizedPath);
```

Теперь путь "." корректно преобразуется в workspace root.

### 2. Улучшение метода `_getCanonicalPath()`

**Файл**: [`codelab_ide/packages/codelab_core/lib/src/utils/path_validator.dart`](codelab_ide/packages/codelab_core/lib/src/utils/path_validator.dart:110-145)

Упрощена логика разрешения канонических путей для несуществующих файлов:
- Рекурсивный поиск существующей родительской директории
- Разрешение символических ссылок только для существующих частей пути
- Восстановление полного пути с учетом разрешенных символических ссылок

### 3. Улучшение метода `_isWithinWorkspace()`

**Файл**: [`codelab_ide/packages/codelab_core/lib/src/utils/path_validator.dart`](codelab_ide/packages/codelab_core/lib/src/utils/path_validator.dart:147-165)

Добавлена обработка ошибок и корректное разрешение workspace root:
- Разрешение символических ссылок для workspace root
- Fallback на нормализацию в случае ошибок
- Корректное сравнение нормализованных путей

### 4. Исключения для системных директорий

**Файл**: [`codelab_ide/packages/codelab_core/lib/src/utils/path_validator.dart`](codelab_ide/packages/codelab_core/lib/src/utils/path_validator.dart:17-23)

Добавлен список разрешенных системных директорий:
```dart
static final List<String> _allowedSystemDirs = [
  '/var/folders', // Временные директории на macOS
  '/tmp',
  '/private/tmp',
  '/private/var/folders',
];
```

Метод `_isSystemDirectory()` теперь сначала проверяет разрешенные директории, затем запрещенные.

## Тестирование

Создан полный набор тестов в [`codelab_ide/packages/codelab_core/test/utils/path_validator_test.dart`](codelab_ide/packages/codelab_core/test/utils/path_validator_test.dart):

- ✅ Путь "." корректно валидируется и указывает на workspace root
- ✅ Путь "./" корректно обрабатывается
- ✅ Относительные пути работают корректно
- ✅ Абсолютные пути блокируются
- ✅ Path traversal (..) блокируется
- ✅ Null bytes блокируются
- ✅ Очень длинные пути блокируются
- ✅ Множественные слеши нормализуются

Все 14 тестов проходят успешно.

## Влияние на другие компоненты

Исправление влияет на все компоненты, использующие PathValidator:
- [`FileSystemDatasource`](codelab_ide/packages/codelab_ai_assistant/lib/features/tool_execution/data/datasources/file_system_datasource.dart) - теперь может корректно работать с путем "."
- Все инструменты работы с файлами (list_files, read_file, write_to_file и т.д.)

## Особенности macOS

На macOS `/var` является символической ссылкой на `/private/var`. PathValidator теперь корректно обрабатывает это, разрешая символические ссылки и сравнивая нормализованные пути.
