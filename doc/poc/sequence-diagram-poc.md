# 🟥 **Sequence Diagram — POC Codelab IDE → Gateway → AI Agent**

```mermaid
sequenceDiagram
    participant User
    participant IDE as Codelab IDE
    participant GW as Gateway
    participant Agent as AI Agent Service
    participant LLM as LLM Provider

    %% ------------------------------
    %% Step 1: User message
    %% ------------------------------
    User->>IDE: Type message "Add logging to auth.js"
    IDE->>GW: WS user_message {content: "Add logging to auth.js"}

    %% ------------------------------
    %% Step 2: Gateway → Agent
    %% ------------------------------
    GW->>Agent: Forward user_message
    Agent->>Agent: Update session context

    %% ------------------------------
    %% Step 3: Agent → LLM
    %% ------------------------------
    Agent->>LLM: Request reasoning + tool-calls
    LLM-->>Agent: Stream token output (partial reasoning)

    %% ------------------------------
    %% Step 4: LLM proposes tool-call
    %% ------------------------------
    Agent->>GW: tool_call {tool_name: "git.diff", args:{path:"."}}
    GW->>IDE: Forward tool_call

    %% ------------------------------
    %% Step 5: IDE executes tool
    %% ------------------------------
    IDE->>IDE: Execute git.diff locally
    IDE-->>GW: tool_result {diff:"diff --git ..."}
    GW-->>Agent: Forward tool_result

    %% ------------------------------
    %% Step 6: Agent continues reasoning
    %% ------------------------------
    Agent->>LLM: Continue reasoning with tool_result
    LLM-->>Agent: Stream token output (patch proposal)

    %% ------------------------------
    %% Step 7: Patch Review
    %% ------------------------------
    Agent->>GW: tool_call {tool_name:"apply_patch_review", args:{diff:"diff ..."}}
    GW->>IDE: Forward apply_patch_review
    IDE->>IDE: Show Patch Review UI
    User->>IDE: Select chunks to apply
    IDE-->>GW: tool_result {filtered_diff:"diff ..."}
    GW-->>Agent: Forward filtered_diff

    %% ------------------------------
    %% Step 8: Apply Patch
    %% ------------------------------
    Agent->>GW: tool_call {tool_name:"apply_patch", args:{diff:"filtered_diff"}}
    GW->>IDE: Forward apply_patch
    IDE->>IDE: Apply patch locally
    IDE-->>GW: tool_result {success:true}
    GW-->>Agent: Forward result

    %% ------------------------------
    %% Step 9: Final message streaming
    %% ------------------------------
    Agent->>GW: assistant_message {streaming tokens: "Logging added in auth.js..."}
    GW-->>IDE: Stream to Chat UI
    IDE->>User: Display streaming message
```

---

# 🟦 **Пояснение шагов**

1. **User → IDE:** пользователь пишет запрос в чат
2. **IDE → Gateway → Agent:** сообщение отправляется на сервер
3. **Agent → LLM:** агент формирует reasoning запрос с возможными tool-calls
4. **Tool-call git.diff:** LLM предлагает инструмент, агент отправляет в IDE
5. **IDE выполняет git.diff локально** и возвращает результат
6. **Agent продолжает reasoning** с учётом tool-result
7. **Patch Review:** пользователь выбирает chunk-и через UI, IDE отправляет обратно
8. **Apply Patch:** выбранный diff применяется локально
9. **Final message:** агент завершает ответ, IDE отображает streaming результат

---

# 🟩 **Особенности POC**

* Все Git и file operations выполняются **локально** в IDE
* LLM streaming поддерживается через WebSocket
* Patch Review UI позволяет **интерактивный выбор chunk**
* User approval (`prompt_user`) может быть добавлен в отдельный tool-call
* Схема полностью совместима с микросервисной архитектурой AI Agent