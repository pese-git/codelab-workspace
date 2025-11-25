# 🟥 **Tools Specification — Codelab IDE POC**
Версия: 1.0
Статус: Единая спецификация инструментов

---

# 1. Обзор

Данный документ содержит полную спецификацию всех инструментов (tools), поддерживаемых в Codelab IDE POC. Документ является единым источником правды для всех компонентов системы.

---

# 2. Категории инструментов

## 🟦 **MVP Tools (Обязательные для POC)**

Минимальный набор инструментов, необходимый для демонстрации базовой функциональности:

### 📁 **File Operations**

| Tool Name    | Описание                        | Статус |
| ------------ | ------------------------------- | ------ |
| `read_file`  | Чтение содержимого файла        | ✅ MVP |
| `write_file` | Запись/создание файла           | ✅ MVP |

### 🔧 **Git Operations**

| Tool Name      | Описание                          | Статус |
| -------------- | --------------------------------- | ------ |
| `git.diff`     | Получение git diff для пути       | ✅ MVP |
| `apply_patch`  | Применение diff/patch             | ✅ MVP |

### 👤 **User Interaction**

| Tool Name              | Описание                           | Статус |
| ---------------------- | ---------------------------------- | ------ |
| `apply_patch_review`   | Patch Review UI с выбором chunks   | ✅ MVP |
| `prompt_user`          | Запрос подтверждения пользователя  | ✅ MVP |

---

## 🟩 **Extended Tools (Расширенные для полной версии)**

Инструменты, которые будут добавлены после успешной реализации MVP:

### 📁 **Advanced File Operations**

| Tool Name            | Описание                              | Статус      |
| -------------------- | ------------------------------------- | ----------- |
| `list_files`         | Получение дерева файлов               | 🔄 Extended |
| `search_in_project`  | Поиск по содержимому файлов           | 🔄 Extended |
| `create_directory`   | Создание директории                   | 🔄 Extended |
| `delete_file`        | Удаление файла/директории             | 🔄 Extended |
| `move_file`          | Перемещение/переименование файла      | 🔄 Extended |

### 💻 **Command Execution**

| Tool Name          | Описание                                | Статус      |
| ------------------ | --------------------------------------- | ----------- |
| `run_command`      | Выполнение shell команд                 | 🔄 Extended |
| `run_persistent`   | Запуск долгоживущих процессов           | 🔄 Extended |
| `kill_process`     | Остановка запущенного процесса          | 🔄 Extended |

### 🔧 **Advanced Git Operations**

| Tool Name        | Описание                          | Статус      |
| ---------------- | --------------------------------- | ----------- |
| `git.status`     | Получение git status              | 🔄 Extended |
| `git.log`        | История коммитов                  | 🔄 Extended |
| `git.branch`     | Управление ветками                | 🔄 Extended |
| `git.commit`     | Создание коммита                  | 🔄 Extended |

---

# 3. Детальная спецификация MVP Tools

## 3.1 `read_file`

**Описание:** Читает содержимое файла по указанному пути

**Request:**
```json
{
  "type": "tool_call",
  "tool_name": "read_file",
  "call_id": "call_001",
  "args": {
    "path": "src/auth.js"
  }
}
```

**Response:**
```json
{
  "type": "tool_result",
  "call_id": "call_001",
  "result": {
    "content": "// File content here...",
    "encoding": "utf-8"
  }
}
```

**Error Response:**
```json
{
  "type": "tool_result",
  "call_id": "call_001",
  "error": {
    "code": "FILE_NOT_FOUND",
    "message": "File not found: src/auth.js"
  }
}
```

---

## 3.2 `write_file`

**Описание:** Записывает содержимое в файл (создает, если не существует)

**Request:**
```json
{
  "type": "tool_call",
  "tool_name": "write_file",
  "call_id": "call_002",
  "args": {
    "path": "src/logger.js",
    "content": "export const log = (msg) => console.log(msg);"
  }
}
```

**Response:**
```json
{
  "type": "tool_result",
  "call_id": "call_002",
  "result": {
    "success": true,
    "bytes_written": 48
  }
}
```

---

## 3.3 `git.diff`

**Описание:** Получает git diff для указанного пути

**Request:**
```json
{
  "type": "tool_call",
  "tool_name": "git.diff",
  "call_id": "call_003",
  "args": {
    "path": ".",
    "staged": false
  }
}
```

**Response:**
```json
{
  "type": "tool_result",
  "call_id": "call_003",
  "result": {
    "diff": "diff --git a/src/auth.js b/src/auth.js\nindex 1234567..abcdefg 100644\n--- a/src/auth.js\n+++ b/src/auth.js\n@@ -1,5 +1,6 @@\n export function authenticate(user) {\n+  console.log('Authenticating user:', user.id);\n   // ... rest of the function\n }"
  }
}
```

---

## 3.4 `apply_patch`

**Описание:** Применяет diff/patch к рабочей директории

**Request:**
```json
{
  "type": "tool_call",
  "tool_name": "apply_patch",
  "call_id": "call_004",
  "args": {
    "diff": "diff --git a/src/auth.js..."
  }
}
```

**Response:**
```json
{
  "type": "tool_result",
  "call_id": "call_004",
  "result": {
    "success": true,
    "files_modified": ["src/auth.js"]
  }
}
```

---

## 3.5 `apply_patch_review`

**Описание:** Показывает Patch Review UI для интерактивного выбора изменений

**Request:**
```json
{
  "type": "tool_call",
  "tool_name": "apply_patch_review",
  "call_id": "call_005",
  "args": {
    "diff": "diff --git...",
    "message": "Review changes to authentication module"
  }
}
```

**Response:**
```json
{
  "type": "tool_result",
  "call_id": "call_005",
  "result": {
    "filtered_diff": "diff --git... (only selected chunks)",
    "action": "apply",
    "chunks_selected": [1, 3, 4],
    "chunks_total": 5
  }
}
```

---

## 3.6 `prompt_user`

**Описание:** Запрашивает подтверждение или выбор действия у пользователя

**Request:**
```json
{
  "type": "tool_call",
  "tool_name": "prompt_user",
  "call_id": "call_006",
  "args": {
    "message": "The changes will modify 5 files. Do you want to continue?",
    "actions": ["approve", "deny", "review"]
  }
}
```

**Response:**
```json
{
  "type": "tool_result",
  "call_id": "call_006",
  "result": {
    "action": "approve"
  }
}
```

---

# 4. Ограничения MVP

Детальные ограничения описаны в [system-specifications.md](./system-specifications.md#2-file-size-limits):

1. **Размер файлов:** максимум 1 МБ для read_file/write_file
2. **Размер diff:** максимум 5 МБ для git.diff/apply_patch
3. **Путь файлов:** только относительные пути внутри workspace (макс. 255 символов)
4. **Git операции:** только unstaged changes в MVP
5. **Кодировка:** только UTF-8 в MVP
6. **Сообщения:** максимум 10 МБ для WebSocket, 10,000 символов для user_message

---

# 5. План добавления Extended Tools

| Фаза | Tools                                           | Срок         |
| ---- | ---------------------------------------------- | ------------ |
| MVP  | read_file, write_file, git.diff, apply_patch, apply_patch_review, prompt_user | 2 недели |
| v1.1 | list_files, search_in_project, run_command     | +1 неделя    |
| v1.2 | git.status, git.commit, delete_file            | +1 неделя    |
| v2.0 | run_persistent, kill_process, git.branch       | +2 недели    |

---

# 6. Совместимость компонентов

Все компоненты системы должны использовать данную спецификацию:

- ✅ **Codelab IDE:** реализует локальное выполнение всех tools
- ✅ **Gateway Service:** маршрутизирует tool_call и tool_result
- ✅ **Agent Runtime Service:** генерирует tool_call на основе LLM решений
- ✅ **LLM Proxy Service:** передает информацию о доступных tools в LLM

---

# 7. Версионирование

- Версия 1.0: MVP tools only
- Версия 1.1: + базовые extended tools
- Версия 2.0: полный набор инструментов

Все изменения в спецификации должны быть обратно совместимыми или явно указывать breaking changes.
