# Анализ корневой причины проблемы выполнения плана

## Дата: 2026-02-03

## Проблема
План выполняется успешно (7/7 подзадач completed), но проект физически не создается - файлы не записываются на диск.

## Корневая причина

### 1. **LLM не вызывает инструменты при выполнении подзадач**

Из логов Docker Compose:
```
Sending assistant message: 185 chars
Sending assistant message: 177 chars
Sending assistant message: 2926 chars
```

Все ответы - только текст, **нет tool calls**.

### 2. **Промпт Coder Agent не адаптирован для контекста подзадач**

**Текущий промпт** ([`coder.py:3`](codelab-ai-service/agent-runtime/app/agents/prompts/coder.py:3)):
```python
CODER_PROMPT = """You are the Coder Agent — an EXECUTION agent specialized in writing and modifying code.

Your role is to EXECUTE assigned tasks EXACTLY as specified.
...
"""
```

**Проблема**: Промпт не содержит явных инструкций о том, что агент **ДОЛЖЕН использовать инструменты** для выполнения задачи.

### 3. **Контекст подзадачи недостаточен**

**Текущий контекст** ([`subtask_executor.py:205`](codelab-ai-service/agent-runtime/app/domain/services/subtask_executor.py:205)):
```python
def _prepare_agent_context(self, subtask: Subtask, plan) -> Dict[str, Any]:
    return {
        "subtask_id": subtask.id,
        "plan_id": plan.id,
        "plan_goal": plan.goal,
        "dependencies": dependency_results,
        "metadata": subtask.metadata,
        "execution_mode": "subtask"  # ← Это не передается в промпт!
    }
```

**Проблема**: 
- Контекст передается в `context` параметр, но **не добавляется в system prompt**
- LLM не знает, что он выполняет подзадачу в рамках плана
- LLM не видит `execution_mode: "subtask"`

### 4. **attempt_completion и ask_followup_question не нужны для подзадач**

**Текущие allowed_tools** ([`coder_agent.py:38`](codelab-ai-service/agent-runtime/app/agents/coder_agent.py:38)):
```python
allowed_tools=[
    "read_file",
    "write_file",
    "list_files",
    "search_in_code",
    "create_directory",
    "execute_command",
    "attempt_completion",      # ← Не нужен для подзадач
    "ask_followup_question"    # ← Не нужен для подзадач
]
```

**Проблема**:
- `attempt_completion` используется для завершения всей сессии, не подзадачи
- `ask_followup_question` не имеет смысла в контексте автоматического выполнения подзадач
- Из логов: `WARNING: Requested unknown tools: ['attempt_completion', 'ask_followup_question']`

## Решение

### 1. **Обновить промпт Coder Agent**

Добавить явные инструкции для режима выполнения подзадач:

```python
CODER_PROMPT = """You are the Coder Agent — an EXECUTION agent specialized in writing and modifying code.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔒 CRITICAL ROLE DEFINITION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Your role is to EXECUTE assigned tasks EXACTLY as specified.

You are NOT:
- A planner
- An architect
- A coordinator
- A decision-maker

You do NOT:
- Design architecture
- Change system structure
- Expand task scope
- Replan tasks
- Delegate tasks to other agents

You execute ONE task at a time.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ ABSOLUTE EXECUTION RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. You MUST follow the task description EXACTLY
2. You MUST NOT modify anything outside the task scope
3. You MUST NOT refactor, optimize, or improve code unless explicitly requested
4. You MUST NOT introduce new patterns, dependencies, or architectural changes unless specified
5. If something is unclear or missing — ask, do NOT assume

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛠 AVAILABLE TOOLS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- read_file
- write_file ⭐ USE THIS TO CREATE/MODIFY FILES
- list_files
- search_in_code
- create_directory ⭐ USE THIS TO CREATE DIRECTORIES
- execute_command

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔁 TOOL USAGE DISCIPLINE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- Use EXACTLY one tool per step
- Wait for the result before continuing
- Never assume tool output
- Work iteratively: tool → result → analyze → next tool

⚠️ CRITICAL: You MUST use tools to perform actions.
   DO NOT just describe what needs to be done.
   ACTUALLY DO IT using the available tools.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 WORKFLOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Read and understand the task
2. Explore the project ONLY if required
3. Execute the task precisely using tools
4. Validate result if applicable (tests, analyze)
5. Return the result (no explicit completion signal needed in subtask mode)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧠 MENTAL MODEL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Coder = Instruction Executor  
Plan = Instruction Set  
Orchestrator = Control Unit  

You execute instructions. You do not decide them.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REMEMBER:
Execute precisely.
Do not improvise.
USE TOOLS to perform actions.
"""
```

### 2. **Добавить контекст подзадачи в system prompt**

Модифицировать [`coder_agent.py:79`](codelab-ai-service/agent-runtime/app/agents/coder_agent.py:79):

```python
async def process(
    self,
    session_id: str,
    message: str,
    context: Dict[str, Any],
    session: Session,
    session_service: SessionManagementService,
    stream_handler: "IStreamHandler"
) -> AsyncGenerator[StreamChunk, None]:
    logger.info(f"Coder agent processing message for session {session_id}")
    
    # Get session history from domain entity
    history = session.get_history_for_llm()
    
    # Prepare system prompt with context
    system_prompt = self.system_prompt
    
    # Add subtask context if in subtask execution mode
    if context.get("execution_mode") == "subtask":
        subtask_context = f"""

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 SUBTASK EXECUTION MODE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You are executing a subtask as part of a larger plan.

Plan Goal: {context.get('plan_goal', 'N/A')}
Subtask ID: {context.get('subtask_id', 'N/A')}

Dependencies completed:
{self._format_dependencies(context.get('dependencies', {}))}

⚠️ CRITICAL: You MUST use tools (write_file, create_directory, etc.) to complete this subtask.
   The task description tells you WHAT to do.
   You must use tools to ACTUALLY DO IT.

DO NOT just respond with text explaining what should be done.
ACTUALLY PERFORM THE ACTIONS using the available tools.
"""
        system_prompt += subtask_context
    
    # Add system prompt at the beginning
    if history and history[0].get("role") == "system":
        history[0]["content"] = system_prompt
    else:
        history.insert(0, {"role": "system", "content": system_prompt})
    
    # ... rest of the method
```

### 3. **Удалить ненужные инструменты для режима подзадач**

Модифицировать [`coder_agent.py:38`](codelab-ai-service/agent-runtime/app/agents/coder_agent.py:38):

```python
def __init__(self):
    """Initialize Coder agent"""
    super().__init__(
        agent_type=AgentType.CODER,
        system_prompt=CODER_PROMPT,
        allowed_tools=[
            "read_file",
            "write_file",
            "list_files",
            "search_in_code",
            "create_directory",
            "execute_command"
            # Removed: attempt_completion, ask_followup_question
            # These are only for interactive mode, not subtask execution
        ]
    )
    logger.info("Coder agent initialized")
```

### 4. **Добавить helper метод для форматирования зависимостей**

```python
def _format_dependencies(self, dependencies: Dict[str, Any]) -> str:
    """Format dependency results for system prompt"""
    if not dependencies:
        return "None"
    
    lines = []
    for dep_id, dep_data in dependencies.items():
        lines.append(f"- {dep_data.get('description', 'N/A')}")
        if dep_data.get('result'):
            lines.append(f"  Result: {dep_data['result'][:100]}...")
    
    return "\n".join(lines) if lines else "None"
```

## Ожидаемый результат

После применения исправлений:

1. ✅ LLM будет явно инструктирован использовать инструменты
2. ✅ LLM будет видеть контекст подзадачи в system prompt
3. ✅ LLM будет понимать, что он в режиме "subtask execution"
4. ✅ Не будет WARNING о несуществующих инструментах
5. ✅ Файлы будут физически создаваться на диске

## Следующие шаги

1. ✅ Обновить промпт Coder Agent
2. ✅ Модифицировать метод `process()` для добавления контекста подзадачи
3. ✅ Удалить `attempt_completion` и `ask_followup_question` из `allowed_tools`
4. ✅ Добавить helper метод `_format_dependencies()`
5. ⏳ Протестировать выполнение плана
6. ⏳ Проверить, что файлы создаются физически

## Связанные документы

- [`STREAM_HANDLER_FIX.md`](STREAM_HANDLER_FIX.md) - исправление ошибки `'NoneType' object has no attribute 'handle'`
- [`PLAN_EXECUTION_TOOLS_PROBLEM.md`](PLAN_EXECUTION_TOOLS_PROBLEM.md) - первичный анализ проблемы
