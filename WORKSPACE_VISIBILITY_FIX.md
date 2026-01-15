# Исправление видимости Workspace при открытии проекта

## Проблема

При открытии проекта через "Open Project" в IDE workspace не становился видимым автоматически. Пользователь видел пустой экран вместо файлового дерева и редактора. Также AI ассистент не получал корректную информацию о workspace.

## Причина

Проблема была в логике обработки события открытия проекта:

1. В [`start_wizard_bloc.dart`](codelab_ide/packages/codelab_engine/lib/src/widgets/start_wizard/start_wizard_bloc.dart:108) проект устанавливался в `ProjectManagerService` даже с пустым path (когда пользователь отменял выбор)
2. В [`start_wizard_panel.dart`](codelab_ide/packages/codelab_engine/lib/src/widgets/start_wizard/start_wizard_panel.dart:36) при успешном открытии проекта вызывался callback `onAction.call('')` с пустой строкой
3. Не было проверки, что проект действительно открылся (path не пустой)
4. В [`ide_root_page.dart`](codelab_ide/apps/codelab_ide/lib/pages/ide_root_page.dart:121) callback просто устанавливал `_projectOpened = true` без дополнительных действий
5. Sidebar с файловым деревом не открывался автоматически

## Решение

### 1. Исправление в `start_wizard_bloc.dart`

**Было:**
```dart
result.match(
  (error) => emit(StartWizardState.error(error.toString())),
  (project) {
    _projectManagerService.setCurrentProject(project);
    // Инициализируем LSP для проекта
    if (project.path.isNotEmpty) {
      _lspService.initialize(project.path)
      // ...
    }
    emit(StartWizardState.opened(project));
  },
);
```

**Стало:**
```dart
result.match(
  (error) => emit(StartWizardState.error(error.toString())),
  (project) {
    // Устанавливаем проект только если он валидный (path не пустой)
    if (project.path.isNotEmpty) {
      _projectManagerService.setCurrentProject(project);
      // Инициализируем LSP для проекта
      _lspService.initialize(project.path)
      // ...
    }
    emit(StartWizardState.opened(project));
  },
);
```

**Изменения:**
- Проект устанавливается в `ProjectManagerService` только если `path` не пустой
- Это гарантирует, что AI ассистент получит корректную информацию о workspace

### 2. Исправление в `start_wizard_panel.dart`

**Было:**
```dart
listener: (context, state) async {
  if (state is ProjectOpenedState) {
    onAction.call('');
  }
```

**Стало:**
```dart
listener: (context, state) async {
  if (state is ProjectOpenedState) {
    // Проверяем, что проект действительно открыт (path не пустой)
    if (state.project.path.isNotEmpty) {
      onAction.call('project_opened');
    }
  }
```

**Изменения:**
- Добавлена проверка `state.project.path.isNotEmpty` для валидации успешного открытия
- Callback вызывается с явным значением `'project_opened'` вместо пустой строки

### 3. Исправление в `ide_root_page.dart`

**Было:**
```dart
emptySlot: engine.StartWizardPanel(
  onAction: (_) =>
      setState(() => _projectOpened = true),
),
```

**Стало:**
```dart
emptySlot: engine.StartWizardPanel(
  onAction: (action) {
    if (action == 'project_opened') {
      setState(() {
        _projectOpened = true;
        // Автоматически открываем sidebar с файловым деревом
        _sidebarVisible = true;
        _selectedSidebarIndex = 0; // Explorer
      });
    }
  },
),
```

**Изменения:**
- Добавлена проверка значения `action == 'project_opened'`
- При успешном открытии проекта автоматически:
  - Устанавливается `_projectOpened = true` (переключение на workspace view)
  - Открывается sidebar (`_sidebarVisible = true`)
  - Выбирается вкладка Explorer (`_selectedSidebarIndex = 0`)

## Результат

После исправления при открытии проекта через "Open Project":
1. ✅ Workspace становится видимым автоматически
2. ✅ Sidebar с файловым деревом открывается автоматически
3. ✅ Пользователь сразу видит структуру проекта
4. ✅ Проверяется валидность открытого проекта (непустой path)
5. ✅ AI ассистент получает корректную информацию о workspace через `ProjectManagerService`
6. ✅ Проект не устанавливается в `ProjectManagerService` если пользователь отменил выбор

## Затронутые файлы

- [`codelab_ide/packages/codelab_engine/lib/src/widgets/start_wizard/start_wizard_bloc.dart`](codelab_ide/packages/codelab_engine/lib/src/widgets/start_wizard/start_wizard_bloc.dart)
- [`codelab_ide/packages/codelab_engine/lib/src/widgets/start_wizard/start_wizard_panel.dart`](codelab_ide/packages/codelab_engine/lib/src/widgets/start_wizard/start_wizard_panel.dart)
- [`codelab_ide/apps/codelab_ide/lib/pages/ide_root_page.dart`](codelab_ide/apps/codelab_ide/lib/pages/ide_root_page.dart)

## Тестирование

Для проверки исправления:
1. Запустить IDE
2. Нажать "Open Project" в стартовом экране
3. Выбрать директорию проекта
4. Убедиться, что:
   - Workspace отображается
   - Sidebar с файловым деревом открыт
   - Файлы проекта видны в Explorer
   - AI ассистент имеет доступ к workspace (можно проверить через команды работы с файлами)
