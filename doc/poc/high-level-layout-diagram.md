Отлично! Ниже подготовлена **High-Level Layout диаграмма Codelab IDE POC**, показывающая основные компоненты, их взаимодействие и потоки данных. Формат — **Mermaid** для документации.

---

# 🟥 **High-Level Layout Diagram — Codelab IDE POC**

```mermaid
flowchart TD
    %% ===========================
    %% User Layer
    %% ===========================
    User[User] --> ChatUI[Chat Interface]

    %% ===========================
    %% UI Layer
    %% ===========================
    ChatUI --> ChatController[Chat Controller]
    PatchUI[Patch Review UI] --> PatchController[Patch Controller]

    %% ===========================
    %% Core IDE Layer
    %% ===========================
    ChatController --> WebSocketClient[WebSocket Client]
    PatchController --> LocalToolsExecutor[Local Tools Executor]
    CommandPanel[Command Runner Panel] --> LocalToolsExecutor
    GitPanel[Git Status Panel] --> LocalToolsExecutor

    %% ===========================
    %% Local Tools
    %% ===========================
    LocalToolsExecutor --> FileOps[File Operations]
    LocalToolsExecutor --> GitOps[Git Executor]
    LocalToolsExecutor --> CommandRunner[Run Commands]

    %% ===========================
    %% WebSocket / Gateway
    %% ===========================
    WebSocketClient --> GW[Gateway Service]
    GW --> AI[AI Agent Service]
    AI --> GW
    GW --> WebSocketClient

    %% ===========================
    %% Patch Review Flow
    %% ===========================
    AI -->|apply_patch_review tool_call| PatchController
    PatchController -->|filtered_diff| AI

    %% ===========================
    %% Command Flow
    %% ===========================
    AI -->|run_command tool_call| CommandPanel
    CommandPanel -->|command_result| AI
```

---

# 🟦 **Пояснение компонентов**

### **User Layer**

* Пользовательский ввод через Chat UI
* Интерактивный выбор chunk в Patch Review UI

### **UI Layer**

* **ChatController:** управляет потоками сообщений и LLM streaming
* **PatchController:** визуализирует diff, позволяет выбирать chunk-и
* **CommandPanel / GitPanel:** отдельные панели для управления командами и Git

### **Core IDE Layer**

* **Local Tools Executor:** точка интеграции всех инструментов (файлы, git, команды)
* **FileOps:** read/write файлов
* **GitOps:** git.diff, apply_patch
* **CommandRunner:** запуск shell-команд

### **WebSocket / Gateway**

* В POC используется WebSocket для связи с AI Agent Service через Gateway
* Все tool-calls маршрутизируются через этот канал

### **Patch Review Flow**

* AI Agent генерирует diff
* IDE показывает Patch Review UI пользователю
* Пользователь выбирает chunk-и → IDE отправляет filtered diff обратно агенту

### **Command Flow**

* AI Agent может вызвать `run_command` → IDE запускает процесс локально
* Streaming stdout/stderr возвращается агенту

---

# 🟩 **Особенности POC**

1. Все git и file operations выполняются локально, без облачного хранения кода
2. Streaming LLM output отображается токен за токеном в Chat UI
3. Patch Review UI интерактивен, поддерживает выбор chunk
4. Минимальный набор инструментов: read_file, write_file, git.diff, apply_patch, run_command
5. Архитектура готова к расширению: новые tools, multi-workspace, LLM providers
