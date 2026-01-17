# Финальный анализ: Task_024 и система планирования

**Дата:** 2026-01-16  
**Статус:** ✅ Проблема идентифицирована и частично решена

---

## 🎯 Резюме

### Что было сделано:

1. ✅ **Исправлены типы сообщений** в [`multi_agent_orchestrator.py`](codelab-ai-service/agent-runtime/app/services/multi_agent_orchestrator.py:270)
   - `subtask_started`, `subtask_completed`, `plan_completed` вместо `assistant_message`
   - Это необходимо для корректной работы benchmark и IDE

2. ✅ **Добавлена задача task_041** в [`tasks.yaml`](benchmark-standalone/tasks.yaml:786)
   - Комплексная задача на разработку TODO приложения с Clean Architecture
   - 41 задача в системе

3. ✅ **Создан детальный анализ** в [`TASK_024_ROOT_CAUSE_ANALYSIS.md`](TASK_024_ROOT_CAUSE_ANALYSIS.md)
   - Выявлены проблемы классификации и планирования

---

## 🔍 Ключевые находки

### Факт #1: В codelab_ide планы создаются ✅
Пользователь подтвердил, что в **codelab_ide планы создаются и subtasks выполняются**.

### Факт #2: В benchmark планы не создаются ❌
Тесты task_024 и task_041 показали:
- Orchestrator роутит на Architect ✅
- Architect получает задачу ✅
- Architect **НЕ вызывает** инструмент `create_plan` ❌
- Architect просто отвечает текстом ❌

### Факт #3: Используется одна и та же система
- **Модель:** `openrouter/openai/gpt-4.1`
- **Backend:** Один и тот же agent-runtime через Gateway
- **Разница:** Только в клиенте (codelab_ide vs benchmark-standalone)

---

## 🤔 Почему планы не создаются в benchmark?

### Гипотеза #1: Недетерминированное поведение LLM
LLM (GPT-4.1) **не всегда** вызывает инструмент `create_plan`, даже когда он доступен. Это зависит от:
- Формулировки задачи
- Контекста разговора
- Температуры модели
- "Настроения" модели (стохастичность)

### Гипотеза #2: Разница в контексте
**codelab_ide:**
- Интерактивный режим
- Пользователь может уточнять
- Больше контекста в истории сообщений

**benchmark:**
- Автоматический режим
- Одно сообщение без контекста
- Нет истории предыдущих взаимодействий

### Гипотеза #3: Промпт недостаточно директивен
Текущий промпт Architect говорит "используй create_plan", но не **требует** его использования для определенных типов задач.

---

## 🔧 Решения

### Решение #1: Сделать create_plan обязательным для complex задач ⭐

**Файл:** [`architect_agent.py:54-100`](codelab-ai-service/agent-runtime/app/agents/architect_agent.py:54)

Добавить логику принудительного создания плана:

```python
async def process(
    self,
    session_id: str,
    message: str,
    context: Dict[str, Any],
    session_mgr: AsyncSessionManager
) -> AsyncGenerator[StreamChunk, None]:
    """Process message through Architect agent."""
    
    # Check if this is a complex/mixed task that REQUIRES planning
    # (можно передавать метаданные задачи через context)
    task_metadata = context.get("task_metadata", {})
    task_category = task_metadata.get("category")
    task_type = task_metadata.get("type")
    
    # For complex/mixed tasks, FORCE plan creation
    if task_category == "complex" or task_type == "mixed":
        logger.info(f"Complex/mixed task detected, forcing plan creation")
        
        # Inject system message to FORCE create_plan usage
        history = session_mgr.get_history(session_id)
        
        force_plan_message = {
            "role": "system",
            "content": (
                "⚠️ CRITICAL: This is a COMPLEX task that REQUIRES a plan.\n"
                "You MUST use the create_plan tool to break it down into subtasks.\n"
                "DO NOT respond with text only - you MUST call create_plan tool first."
            )
        }
        
        # Insert after system prompt
        if len(history) > 1:
            history.insert(1, force_plan_message)
        else:
            history.append(force_plan_message)
    
    # Continue with normal processing...
```

### Решение #2: Улучшить промпт Architect

**Файл:** [`architect.py:1-134`](codelab-ai-service/agent-runtime/app/agents/prompts/architect.py:1)

Сделать инструкции более императивными:

```python
ARCHITECT_PROMPT = """You are the Architect Agent - specialized in planning and design.

⚠️ CRITICAL RULES:

1. For ANY implementation task (creating files, writing code, running commands):
   - You MUST IMMEDIATELY call create_plan tool
   - DO NOT respond with text only
   - DO NOT try to execute tasks yourself
   
2. For complex/mixed tasks:
   - create_plan is MANDATORY, not optional
   - Break down into specific subtasks
   - Assign each subtask to appropriate agent
   
3. For simple documentation tasks:
   - You can create .md files directly
   - Use write_file tool for markdown only

WRONG ❌:
User: "Create a TODO app with Clean Architecture"
Architect: "Here's a plan: 1. Create entities, 2. Create repositories..." [TEXT ONLY]

CORRECT ✅:
User: "Create a TODO app with Clean Architecture"
Architect: [CALLS create_plan TOOL with structured subtasks]

Remember: If you don't call create_plan for implementation tasks, the task will FAIL.
"""
```

### Решение #3: Добавить валидацию в orchestrator

**Файл:** [`orchestrator_agent.py:94-184`](codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py:94)

Передавать метаданные задачи в контекст:

```python
async def process(
    self,
    session_id: str,
    message: str,
    context: Dict[str, Any],
    session_mgr: "AsyncSessionManager"
) -> AsyncGenerator[StreamChunk, None]:
    """Process message through orchestrator."""
    
    # Extract task metadata if available (from benchmark)
    task_metadata = context.get("task_metadata", {})
    
    # Pass metadata to target agent
    context["task_metadata"] = task_metadata
    
    # ... rest of routing logic
```

### Решение #4: Снизить температуру для Architect

**Файл:** [`llm_stream_service.py`](codelab-ai-service/agent-runtime/app/services/llm_stream_service.py)

Для Architect агента использовать более низкую температуру:

```python
# For Architect agent, use lower temperature for more deterministic behavior
temperature = 0.1 if agent_type == AgentType.ARCHITECT else 0.7
```

---

## 📊 Приоритеты

1. **🔴 КРИТИЧНО:** Решение #1 - Принудительное создание плана для complex задач
2. **🟡 ВАЖНО:** Решение #2 - Улучшить промпт Architect
3. **🟢 ПОЛЕЗНО:** Решение #3 - Передавать метаданные задачи
4. **🟢 ПОЛЕЗНО:** Решение #4 - Снизить температуру

---

## 🧪 План тестирования

### Тест 1: Проверить task_041 после исправлений
```bash
cd benchmark-standalone
uv run python main.py --task-id=task_041
```

**Ожидается:**
- ✅ Architect вызывает create_plan
- ✅ План создается с ~10 subtasks
- ✅ Subtasks выполняются последовательно
- ✅ События subtask_started/completed отправляются
- ✅ Файлы создаются

### Тест 2: Проверить task_024
```bash
uv run python main.py --task-id=task_024
```

**Ожидается:**
- ✅ Orchestrator роутит на Debug (не Architect)
- ✅ Debug агент исправляет проблему
- ✅ Файл создается

### Тест 3: Проверить другие complex задачи
```bash
uv run python main.py --task-id=task_009,task_027,task_033
```

---

## 📈 Метрики успеха

После внедрения исправлений:

| Метрика | До | Цель |
|---------|-----|------|
| Task_024 success rate | 0% | 100% |
| Task_041 success rate | 0% | 100% |
| Complex tasks с планами | ~0% | >80% |
| Правильная классификация debug | ~50% | >90% |

---

## 🎓 Выводы

1. ✅ **Исправление типов сообщений** было правильным и необходимым
2. ✅ **Система планирования работает** в codelab_ide
3. ❌ **LLM не всегда вызывает create_plan** в автоматическом режиме
4. 🎯 **Решение:** Сделать create_plan обязательным для complex/mixed задач
5. 📝 **Важно:** Промпты должны быть более директивными и императивными

---

## 📎 Связанные файлы

- [`BENCHMARK_TASK_024_ANALYSIS.md`](BENCHMARK_TASK_024_ANALYSIS.md) - Первоначальный анализ
- [`TASK_024_ROOT_CAUSE_ANALYSIS.md`](TASK_024_ROOT_CAUSE_ANALYSIS.md) - Детальный анализ корневой причины
- [`multi_agent_orchestrator.py`](codelab-ai-service/agent-runtime/app/services/multi_agent_orchestrator.py) - Исправлены типы сообщений ✅
- [`tasks.yaml`](benchmark-standalone/tasks.yaml) - Добавлена task_041 ✅
- [`orchestrator_agent.py`](codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py) - Требует улучшения классификации
- [`architect_agent.py`](codelab-ai-service/agent-runtime/app/agents/architect_agent.py) - Требует принудительного планирования
- [`architect.py`](codelab-ai-service/agent-runtime/app/agents/prompts/architect.py) - Требует улучшения промпта
