# Анализ OrchestratorAgent

## Обзор

Детальный анализ текущей реализации `OrchestratorAgent` в контексте нового промпта и реальных логов работы системы.

---

## Текущая реализация

### Файл: `codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py`

**Размер:** 274 строки

### Основные компоненты:

#### 1. CLASSIFICATION_PROMPT (строки 24-68)
```python
CLASSIFICATION_PROMPT = """You are a task classifier for a multi-agent system...

Available agents:
1. **coder** - for writing, modifying, and refactoring code
2. **architect** - for planning, designing, and creating technical specifications
3. **debug** - for troubleshooting, investigating errors, and debugging
4. **ask** - for answering questions, explaining concepts, and providing documentation
5. **universal** - universal agent that can handle any task (used in single-agent mode)

Respond with ONLY a JSON object:
{
  "agent": "coder|architect|debug|ask|universal",
  "confidence": "high|medium|low",
  "reasoning": "brief explanation"
}
"""
```

**Анализ:**
- ✅ Хорошо структурирован
- ✅ Включает все агенты
- ❌ Слишком детальное описание агентов (дублирует основной промпт)
- ❌ Не учитывает концепцию "atomic vs complex tasks"

#### 2. Класс OrchestratorAgent (строки 71-274)

**Инициализация:**
```python
def __init__(self):
    super().__init__(
        agent_type=AgentType.ORCHESTRATOR,
        system_prompt=ORCHESTRATOR_PROMPT,  # ← Использует промпт
        allowed_tools=[
            "read_file",
            "list_files",
            "search_in_code"
        ]
    )
```

**Анализ:**
- ✅ Правильно использует ORCHESTRATOR_PROMPT
- ✅ Ограниченный набор инструментов (только для анализа)
- ✅ Наследуется от BaseAgent

---

## Метод process() - Основная логика

### Текущая реализация (строки 91-154):

```python
async def process(
    self,
    session_id: str,
    message: str,
    context: Dict[str, Any],
    session: "Session",
    session_service: "SessionManagementService",
    stream_handler: "IStreamHandler"
) -> AsyncGenerator[StreamChunk, None]:
    """Analyze request using LLM and determine which agent should handle it."""
    
    logger.info(f"Orchestrator analyzing request for session {session_id}")
    
    # Check if only Universal agent is available (single-agent mode)
    from app.domain.services.agent_registry import agent_router
    available_agents = agent_router.list_agents()
    
    # If only Orchestrator and Universal are registered, route to Universal
    if AgentType.UNIVERSAL in available_agents and len(available_agents) == 2:
        logger.info("Single-agent mode detected, routing to Universal agent")
        target_agent = AgentType.UNIVERSAL
        classification_info = {
            "agent": "universal",
            "confidence": "high",
            "reasoning": "Single-agent mode: only Universal agent available"
        }
    else:
        # Multi-agent mode: classify the task type using LLM
        target_agent, classification_info = await self.classify_task_with_llm(message)
    
    logger.info(
        f"Orchestrator routing to {target_agent.value} agent "
        f"for session {session_id} "
        f"(confidence: {classification_info.get('confidence', 'unknown')})"
    )
    
    # Send switch_agent chunk
    yield StreamChunk(
        type="switch_agent",
        content=f"Routing to {target_agent.value} agent",
        metadata={
            "target_agent": target_agent.value,
            "reason": classification_info.get("reasoning", f"Task classified as {target_agent.value}"),
            "confidence": classification_info.get("confidence", "medium"),
            "classification_method": "llm"
        },
        is_final=True
    )
```

### Анализ текущей логики:

#### ✅ Что работает хорошо:
1. **Single-agent mode detection** - автоматически переключается на Universal
2. **LLM-based classification** - использует LLM для умной классификации
3. **Logging** - хорошее логирование для отладки
4. **Metadata** - передает полезную информацию в switch_agent chunk

#### ❌ Что отсутствует (требуется по новому промпту):

1. **Проверка наличия плана:**
```python
# Должно быть:
if session.current_plan:
    # Execute next task from plan
    yield from self._execute_plan_task(session, ...)
else:
    # No plan - decide routing
    ...
```

2. **Управление состоянием задач:**
```python
# Должно быть:
task = plan.get_next_task()
task.status = TaskStatus.RUNNING
```

3. **Обработка завершения плана:**
```python
# Должно быть:
if plan.is_completed():
    yield from self._finalize_plan(session, plan)
```

4. **Обработка ошибок:**
```python
# Должно быть:
if task_failed:
    if self._failure_affects_plan(plan, task):
        # Escalate to Architect
    else:
        # Route to Debug
```

---

## Метод classify_task_with_llm() - LLM классификация

### Текущая реализация (строки 156-232):

```python
async def classify_task_with_llm(self, message: str) -> tuple[AgentType, Dict[str, Any]]:
    """Classify task type using LLM for more accurate routing."""
    try:
        # Prepare classification prompt
        classification_prompt = CLASSIFICATION_PROMPT.format(user_message=message)
        
        # Call LLM for classification
        response = await llm_proxy_client.chat_completion(
            model=AppConfig.LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are a task classifier. Respond only with JSON."},
                {"role": "user", "content": classification_prompt}
            ],
            stream=False,
            extra_params={"temperature": 0.3}  # Lower temperature for consistency
        )
        
        # Extract response content
        content = response["choices"][0]["message"]["content"]
        
        # Parse JSON response (with fallback for markdown code blocks)
        try:
            classification = json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code block
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
                classification = json.loads(json_str)
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
                classification = json.loads(json_str)
            else:
                raise
        
        # Extract agent type
        agent_str = classification.get("agent", "coder").lower()
        
        # Map to AgentType
        agent_mapping = {
            "coder": AgentType.CODER,
            "architect": AgentType.ARCHITECT,
            "debug": AgentType.DEBUG,
            "ask": AgentType.ASK,
            "universal": AgentType.UNIVERSAL
        }
        
        target_agent = agent_mapping.get(agent_str, AgentType.CODER)
        
        return target_agent, classification
        
    except Exception as e:
        logger.error(f"Error in LLM classification: {e}", exc_info=True)
        logger.warning("Falling back to keyword-based classification")
        
        # Fallback to simple keyword matching
        target_agent = self._fallback_classify(message)
        return target_agent, {
            "agent": target_agent.value,
            "confidence": "low",
            "reasoning": "Fallback classification due to LLM error",
            "error": str(e)
        }
```

### Анализ:

#### ✅ Сильные стороны:
1. **Robust JSON parsing** - обрабатывает markdown code blocks
2. **Error handling** - fallback на keyword matching
3. **Low temperature** - более консистентная классификация
4. **Logging** - хорошее логирование ошибок

#### ❌ Проблемы:
1. **Не учитывает atomic vs complex** - нет проверки сложности задачи
2. **Всегда возвращает один агент** - не может вернуть "нужен план"
3. **Не использует контекст сессии** - не смотрит на историю

#### 💡 Что нужно добавить:

```python
async def classify_task_with_llm(self, message: str, session: "Session") -> tuple[AgentType, Dict[str, Any], bool]:
    """
    Classify task type and determine if planning is needed.
    
    Returns:
        Tuple of (AgentType, classification_info, needs_planning)
    """
    # Обновленный промпт с проверкой сложности
    classification_prompt = """Classify the task:
    
    1. Is it atomic (single-step) or complex (multi-step)?
    2. Which agent should handle it?
    
    Respond with JSON:
    {
      "is_atomic": true|false,
      "agent": "coder|architect|debug|explain",
      "confidence": "high|medium|low",
      "reasoning": "explanation"
    }
    
    Task: {user_message}
    """
    
    # ... LLM call ...
    
    is_atomic = classification.get("is_atomic", True)
    
    if not is_atomic:
        # Complex task - needs planning
        return AgentType.ARCHITECT, classification, True
    else:
        # Atomic task - direct routing
        return target_agent, classification, False
```

---

## Метод _fallback_classify() - Keyword matching

### Текущая реализация (строки 234-259):

```python
def _fallback_classify(self, message: str) -> AgentType:
    """Fallback classification using simple keyword matching."""
    message_lower = message.lower()
    
    # Simple keyword matching as fallback
    if any(kw in message_lower for kw in ["create", "write", "implement", "fix", "code", "refactor", "modify"]):
        return AgentType.CODER
    elif any(kw in message_lower for kw in ["design", "architecture", "plan", "spec", "blueprint"]):
        return AgentType.ARCHITECT
    elif any(kw in message_lower for kw in ["debug", "error", "bug", "problem", "why", "investigate", "crash"]):
        return AgentType.DEBUG
    elif any(kw in message_lower for kw in ["explain", "what is", "how does", "help", "understand"]):
        return AgentType.ASK
    else:
        # Default to Coder
        return AgentType.CODER
```

### Анализ:

#### ✅ Хорошо:
- Простой и понятный
- Покрывает основные случаи
- Быстрый fallback

#### ❌ Проблемы:
- Не учитывает сложность задачи
- Всегда возвращает один агент
- Может ошибаться на сложных запросах

---

## Анализ логов работы

### Из предоставленных логов:

```
2026-01-29 20:53:08 - User: "Изучи текущий проект и реализу мобильное приложение"
2026-01-29 20:53:12 - Assistant: list_files(".", recursive=true)
2026-01-29 20:53:13 - Assistant: list_files("lib", recursive=true)
2026-01-29 20:53:14 - Assistant: read_file("pubspec.yaml", start_line=1, end_line=40)
... (multiple read attempts with errors)
2026-01-29 20:53:26 - Assistant: create_directory("lib", recursive=true)
```

### Наблюдения:

1. **Orchestrator не вызывался** - запрос сразу пошел к агенту (вероятно Coder или Universal)
2. **Агент пытается создать существующую директорию** - `lib` уже существует
3. **Множественные ошибки read_file** - `Invalid end_line` (файл короче, чем ожидалось)
4. **Нет переключения агентов** - весь процесс в одном агенте

### Проблемы:

1. **Orchestrator не участвует в процессе** - либо не активирован, либо сразу переключил на Universal
2. **Нет планирования** - сложная задача "реализуй мобильное приложение" не разбита на подзадачи
3. **Агент действует хаотично** - множественные попытки чтения с ошибками
4. **Нет обработки ошибок** - агент продолжает после ошибок без корректировки

---

## Соответствие новому промпту

### Требования нового промпта vs текущая реализация:

| Требование | Текущая реализация | Статус |
|------------|-------------------|--------|
| **Receive user requests** | ✅ Получает через `process()` | ✅ Есть |
| **Decide atomic vs complex** | ❌ Не проверяет сложность | ❌ Нет |
| **Route to appropriate agent** | ✅ Маршрутизирует через LLM | ✅ Есть |
| **Execute task plans** | ❌ Не управляет планами | ❌ Нет |
| **Track task status** | ❌ Нет tracking | ❌ Нет |
| **Maintain execution state** | ❌ Не хранит состояние | ❌ Нет |
| **Coordinate transitions** | ❌ Только один switch | ❌ Нет |
| **Handle task failures** | ❌ Нет обработки | ❌ Нет |
| **Escalate to Architect** | ❌ Нет эскалации | ❌ Нет |
| **Assemble final result** | ❌ Нет финализации | ❌ Нет |

**Итого:** 2 из 10 требований выполнены (20%)

---

## Критические проблемы

### 1. Отсутствие управления планами

**Проблема:** Orchestrator не знает о существовании планов

**Последствия:**
- Сложные задачи не разбиваются на подзадачи
- Нет координации между агентами
- Невозможно отследить прогресс

**Решение:**
```python
async def process(self, ...):
    # Check for existing plan
    if hasattr(session, 'current_plan') and session.current_plan:
        yield from self._execute_plan(session, ...)
    else:
        yield from self._route_task(message, session, ...)
```

### 2. Отсутствие проверки сложности задачи

**Проблема:** Все задачи обрабатываются одинаково

**Последствия:**
- Сложные задачи идут напрямую к Coder
- Нет планирования для multi-step задач
- Хаотичное выполнение

**Пример из логов:**
```
User: "Изучи текущий проект и реализуй мобильное приложение"
↓
Coder: list_files, read_file, create_directory (хаотично)
```

**Должно быть:**
```
User: "Изучи текущий проект и реализуй мобильное приложение"
↓
Orchestrator: "Complex task detected"
↓
Architect: Creates plan with subtasks
↓
Orchestrator: Executes plan step by step
```

**Решение:**
```python
async def _route_task(self, message, session):
    # Classify task
    target_agent, info, needs_planning = await self.classify_task_with_llm(message, session)
    
    if needs_planning:
        # Route to Architect for planning
        yield self._switch_to_architect("Complex task requires planning")
    else:
        # Direct routing
        yield self._switch_to_agent(target_agent, info)
```

### 3. Отсутствие отслеживания состояния

**Проблема:** Нет tracking выполнения задач

**Последствия:**
- Невозможно узнать, какие задачи выполнены
- Нет обработки ошибок
- Нет возможности возобновить после сбоя

**Решение:**
```python
class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"

async def _execute_plan(self, session, ...):
    plan = session.current_plan
    
    # Find next pending task
    next_task = plan.get_next_pending_task()
    
    if next_task:
        # Mark as running
        next_task.status = TaskStatus.RUNNING
        await session_service.update_session(session)
        
        # Route to agent
        yield self._switch_to_agent(next_task.agent, ...)
    else:
        # All tasks done
        yield from self._finalize_plan(session, plan)
```

### 4. Отсутствие обработки ошибок

**Проблема:** Нет логики для обработки сбоев задач

**Последствия:**
- Ошибки не обрабатываются
- Нет эскалации к Debug или Architect
- План может застрять

**Решение:**
```python
async def handle_task_failure(self, session, task_id, error):
    plan = session.current_plan
    task = plan.get_task(task_id)
    
    # Mark as failed
    task.status = TaskStatus.FAILED
    task.error = error
    
    # Check if failure affects plan
    if self._has_dependent_tasks(plan, task):
        # Escalate to Architect
        yield self._switch_to_architect(
            f"Task {task_id} failed, affecting plan: {error}"
        )
    else:
        # Route to Debug
        yield self._switch_to_debug(
            f"Task {task_id} failed: {error}"
        )
```

---

## Рекомендации по рефакторингу

### Приоритет 1: Базовая поддержка планов (MVP)

**Цель:** Минимальная функциональность для работы с планами

**Изменения:**
1. Добавить проверку `session.current_plan` в `process()`
2. Добавить метод `_execute_plan()` для последовательного выполнения
3. Добавить метод `_finalize_plan()` для завершения

**Код:**
```python
async def process(self, ...):
    # Check for existing plan
    if hasattr(session, 'current_plan') and session.current_plan:
        logger.info(f"Executing plan {session.current_plan.id}")
        yield from self._execute_plan(session, session_service, stream_handler)
    else:
        logger.info("No plan, routing task")
        yield from self._route_task(message, session)

async def _execute_plan(self, session, session_service, stream_handler):
    plan = session.current_plan
    
    # Find next pending task
    next_task = next(
        (t for t in plan.tasks if t.status == TaskStatus.PENDING),
        None
    )
    
    if next_task:
        # Mark as running
        next_task.status = TaskStatus.RUNNING
        await session_service.update_session(session)
        
        # Route to agent
        yield StreamChunk(
            type="switch_agent",
            content=f"Executing task: {next_task.description}",
            metadata={
                "target_agent": next_task.agent.value,
                "task_id": next_task.id,
                "plan_id": plan.id
            }
        )
    else:
        # All tasks done
        yield from self._finalize_plan(session, plan)

async def _finalize_plan(self, session, plan):
    # Clear plan
    session.current_plan = None
    
    # Send completion
    yield StreamChunk(
        type="plan_completed",
        content="All tasks completed",
        metadata={"plan_id": plan.id},
        is_final=True
    )
```

**Время:** 2-3 часа

### Приоритет 2: Проверка сложности задачи

**Цель:** Определять, нужно ли планирование

**Изменения:**
1. Обновить `CLASSIFICATION_PROMPT` с проверкой `is_atomic`
2. Обновить `classify_task_with_llm()` для возврата `needs_planning`
3. Добавить логику маршрутизации к Architect

**Код:**
```python
CLASSIFICATION_PROMPT = """Classify the task:

1. Is it atomic (single-step) or complex (multi-step)?
2. Which agent should handle it?

Atomic tasks:
- Single file changes
- Simple questions
- Direct commands

Complex tasks:
- Multi-file changes
- System design
- Feature implementations

Respond with JSON:
{
  "is_atomic": true|false,
  "agent": "code|plan|debug|explain",
  "confidence": "high|medium|low",
  "reasoning": "explanation"
}

Task: {user_message}
"""

async def classify_task_with_llm(self, message, session):
    # ... LLM call ...
    
    is_atomic = classification.get("is_atomic", True)
    agent_str = classification.get("agent", "code")
    
    # Map agent
    agent_mapping = {
        "code": AgentType.CODER,
        "plan": AgentType.ARCHITECT,
        "debug": AgentType.DEBUG,
        "explain": AgentType.ASK
    }
    
    target_agent = agent_mapping.get(agent_str, AgentType.CODER)
    
    return target_agent, classification, not is_atomic

async def _route_task(self, message, session):
    target_agent, info, needs_planning = await self.classify_task_with_llm(message, session)
    
    if needs_planning:
        # Route to Architect
        yield StreamChunk(
            type="switch_agent",
            content="Complex task requires planning",
            metadata={
                "target_agent": AgentType.ARCHITECT.value,
                "reason": "Complex task detected",
                "classification": info
            }
        )
    else:
        # Direct routing
        yield StreamChunk(
            type="switch_agent",
            content=f"Routing to {target_agent.value}",
            metadata={
                "target_agent": target_agent.value,
                "reason": info.get("reasoning"),
                "classification": info
            }
        )
```

**Время:** 2-3 часа

### Приоритет 3: Обработка ошибок

**Цель:** Обрабатывать сбои задач

**Изменения:**
1. Добавить метод `handle_task_failure()`
2. Добавить логику эскалации
3. Добавить проверку зависимостей

**Код:**
```python
async def handle_task_failure(self, session, task_id, error):
    """Handle task failure according to rules."""
    plan = session.current_plan
    
    if not plan:
        logger.warning(f"Task failure but no plan: {task_id}")
        return
    
    # Find failed task
    task = next((t for t in plan.tasks if t.id == task_id), None)
    if not task:
        logger.error(f"Task not found in plan: {task_id}")
        return
    
    # Mark as failed
    task.status = TaskStatus.FAILED
    task.error = error
    
    # Check if other tasks depend on this one
    dependent_tasks = [
        t for t in plan.tasks
        if task_id in t.dependencies
    ]
    
    if dependent_tasks:
        # Failure affects plan - escalate to Architect
        logger.info(f"Task {task_id} failure affects {len(dependent_tasks)} tasks, escalating")
        yield StreamChunk(
            type="switch_agent",
            content=f"Task failure affects plan, escalating to Architect",
            metadata={
                "target_agent": AgentType.ARCHITECT.value,
                "reason": "plan_failure",
                "failed_task": task_id,
                "error": error,
                "affected_tasks": [t.id for t in dependent_tasks]
            }
        )
    else:
        # Isolated failure - route to Debug
        logger.info(f"Task {task_id} failed, routing to Debug")
        yield StreamChunk(
            type="switch_agent",
            content=f"Routing failed task to Debug agent",
            metadata={
                "target_agent": AgentType.DEBUG.value,
                "reason": "task_failure",
                "failed_task": task_id,
                "error": error
            }
        )
```

**Время:** 2-3 часа

---

## Итоговый план действий

### Фаза 1: MVP (6-9 часов)
1. ✅ Добавить базовую поддержку планов
2. ✅ Добавить проверку сложности задачи
3. ✅ Обновить CLASSIFICATION_PROMPT

### Фаза 2: Обработка ошибок (2-3 часа)
1. ✅ Добавить `handle_task_failure()`
2. ✅ Добавить логику эскалации

### Фаза 3: Улучшения (4-6 часов)
1. ✅ Добавить параллельное выполнение независимых задач
2. ✅ Добавить детальное отслеживание прогресса
3. ✅ Добавить возможность паузы/возобновления

### Фаза 4: Тестирование (3-4 часа)
1. ✅ Unit тесты
2. ✅ Integration тесты
3. ✅ E2E тесты

**Общее время:** 15-22 часа

---

## Выводы

### Текущее состояние:
- ✅ Базовая маршрутизация работает
- ✅ LLM-based классификация реализована
- ✅ Single-agent mode поддерживается
- ❌ Управление планами отсутствует
- ❌ Отслеживание состояния отсутствует
- ❌ Обработка ошибок отсутствует

### Соответствие новому промпту: **20%**

### Критические проблемы:
1. Нет управления планами выполнения
2. Нет проверки сложности задачи
3. Нет отслеживания состояния задач
4. Нет обработки ошибок и эскалации

### Рекомендация:
Начать с MVP реализации (Фаза 1), затем итеративно добавлять функциональность.
