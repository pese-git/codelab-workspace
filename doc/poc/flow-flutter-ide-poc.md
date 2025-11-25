
# 🟥 **POC Flutter IDE — Полная документация**

## 1. Цель POC

* Проверка **end-to-end workflow**: пользователь → IDE → Gateway → AI Agent → LLM → Tools → IDE
* Минимальный рабочий набор функций для быстрого прототипа
* Локальное выполнение всех инструментов (git, файлы, команды)
* Поддержка **token-by-token streaming** для Chat UI
* Поддержка **Patch Review** и **User Approval**

---

## 2. Архитектура POC

```mermaid
flowchart LR
User --> ChatUI[Chat Interface]
ChatUI --> ChatController[Chat Controller]
PatchUI[Patch Review UI] --> PatchController[Patch Controller]
ChatController --> WSClient[WebSocket Client]
PatchController --> LocalToolsExecutor[Local Tools Executor]
CommandPanel[Command Runner Panel] --> LocalToolsExecutor
GitPanel[Git Status Panel] --> LocalToolsExecutor
LocalToolsExecutor --> FileOps[File Operations]
LocalToolsExecutor --> GitOps[Git Executor]
LocalToolsExecutor --> CommandRunner[Run Commands]
WSClient --> GW[Gateway Service]
GW --> AI[AI Agent Service]
AI --> LLM[LLM Provider]
LLM --> AI: Stream Tokens
AI --> GW: Streaming Tokens
GW --> WSClient
WSClient --> ChatUI: Render token-by-token
AI -->|apply_patch_review tool_call| PatchController
PatchController -->|filtered_diff| AI
AI -->|run_command tool_call| CommandPanel
CommandPanel -->|command_result| AI
```

### Пояснение компонентов:

* **ChatController**: управляет потоками сообщений и streaming токенами
* **PatchController**: визуализирует diff, поддерживает выбор chunk
* **LocalToolsExecutor**: точка интеграции инструментов IDE
* **WebSocket Client**: двунаправленная связь с Gateway
* **Patch Review Flow**: выбор chunk → filtered diff → Agent
* **Command Flow**: run_command → Agent → IDE

---

## 3. Минимальные инструменты (tools)

| Tool                 | Описание                                         |
| -------------------- | ------------------------------------------------ |
| `read_file`          | Чтение файла по пути                             |
| `write_file`         | Запись файла с содержимым                        |
| `git.diff`           | Получение git diff                               |
| `apply_patch`        | Применение diff локально                         |
| `apply_patch_review` | Patch Review UI с выбором chunk                  |
| `run_command`        | Локальный запуск shell команд                    |
| `prompt_user`        | Запрос подтверждения пользователя (approve/deny) |

---

## 4. JSON схемы tool-calls

### Пример — read_file

```json
{
  "type": "tool_call",
  "tool_name": "read_file",
  "call_id": "call_001",
  "args": { "path": "src/auth.js" }
}
```

**Результат:**

```json
{
  "type": "tool_result",
  "call_id": "call_001",
  "result": { "content": "file content" }
}
```

> Аналогичные схемы есть для всех tools (`write_file`, `git.diff`, `apply_patch`, `apply_patch_review`, `run_command`, `prompt_user`).

---

## 5. Streaming сообщений (token-by-token)

### JSON контракт

```json
{
  "type": "assistant_message",
  "message_id": "msg_001",
  "token": "import",
  "is_final": false
}
```

* `type`: `"assistant_message"`
* `message_id`: уникальный ID сообщения
* `token`: один токен от LLM
* `is_final`: true, если сообщение завершено

### Пример потока:

```json
{"type": "assistant_message", "message_id": "msg_001", "token": "import", "is_final": false}
{"type": "assistant_message", "message_id": "msg_001", "token": " os", "is_final": false}
{"type": "assistant_message", "message_id": "msg_001", "token": "\n", "is_final": false}
{"type": "assistant_message", "message_id": "msg_001", "token": "# Logging added", "is_final": true}
```

### Интеграция с Flutter

```dart
StreamBuilder<AssistantToken>(
  stream: assistantTokenStream,
  builder: (context, snapshot) {
    if (snapshot.hasData) {
      chatMessages.updateCurrentMessage(snapshot.data!.token);
      return ChatMessageWidget(chatMessages.currentMessage);
    }
    return Container();
  },
);
```

---

## 6. Workflow POC

1. **User → Chat UI → WebSocket → Gateway → Agent**
   Пользователь вводит команду, отправляется на AI Agent.

2. **Agent → LLM → streaming tokens → IDE**
   AI Agent начинает reasoning и отправляет токены на Chat UI.

3. **LLM → Tool Call → IDE (локальные инструменты)**
   Например, `git.diff` или `read_file`.

4. **IDE → Tool Result → Agent → LLM**
   Результат выполнения инструмента используется AI Agent для дальнейшего reasoning.

5. **Patch Review**

   * AI Agent формирует diff
   * IDE показывает Patch Review UI
   * Пользователь выбирает chunk
   * IDE отправляет filtered diff обратно Agent

6. **Apply Patch**

   * IDE применяет diff локально
   * Подтверждает успех Agent

7. **Final streaming message**

   * AI Agent завершает reasoning
   * IDE отображает финальный ответ по токенам

---

## 7. User Approval Flow

* `prompt_user` tool позволяет запросить подтверждение пользователя.
* IDE отображает modal с `message` и `actions`.
* Пользователь выбирает действие → IDE отправляет результат обратно AI Agent.

---

## 8. Минимальные критерии готовности POC

1. WebSocket соединение с Gateway установлено.
2. Chat UI отображает streaming токены AI Agent.
3. Локальные инструменты выполняются корректно: `read_file`, `write_file`, `git.diff`, `apply_patch`.
4. Patch Review UI позволяет выбрать chunk-и.
5. User Approval (`prompt_user`) работает end-to-end.
6. Tool-call workflow интегрирован с Agent через Gateway.

---

## 9. План разработки POC (1–2 недели)

| День | Задачи                                      |
| ---- | ------------------------------------------- |
| 1–2  | Flutter Desktop skeleton + WebSocket client |
| 3–4  | Chat UI + streaming токены                  |
| 5–6  | Local tools: read_file, write_file          |
| 7    | Git tools: git.diff, apply_patch            |
| 8–9  | Patch Review UI + chunk selection           |
| 10   | prompt_user workflow                        |
| 11   | Интеграция с Gateway/Agent                  |
| 12   | E2E тестирование                            |
| 13   | UX polish, обработка ошибок                 |
| 14   | Demo + документация                         |


