# Предложение: Orchestrator с планированием задач

## Текущее состояние

Orchestrator сейчас только:
- Классифицирует задачу
- Переключается на специализированного агента
- Не планирует и не разбивает на подзадачи

## Предложение

Добавить Orchestrator возможность планирования для сложных задач.

## Архитектура

### 1. Новый инструмент: create_plan

```python
{
    "name": "create_plan",
    "description": "Create execution plan for complex task",
    "parameters": {
        "subtasks": [
            {
                "id": "subtask_1",
                "description": "Add Riverpod dependency",
                "agent": "coder",
                "estimated_time": "2 min"
            },
            {
                "id": "subtask_2",
                "description": "Create providers",
                "agent": "coder",
                "estimated_time": "5 min"
            }
        ]
    }
}
```

### 2. Обновленный промпт Orchestrator

```python
ORCHESTRATOR_PROMPT = """You are the Orchestrator Agent - the main coordinator.

For COMPLEX tasks (migrations, refactoring, multi-file changes):
1. Analyze the task and break it down into subtasks
2. Create an execution plan using create_plan tool
3. Delegate each subtask to appropriate specialist
4. Track progress and coordinate between agents

For SIMPLE tasks:
- Directly route to appropriate specialist (current behavior)

Example for complex task:
User: "Migrate from Provider to Riverpod"

Step 1: Create plan
- Subtask 1: Add riverpod dependency (Coder)
- Subtask 2: Create providers (Coder)
- Subtask 3: Update main.dart (Coder)
- Subtask 4: Migrate widgets (Coder)
- Subtask 5: Update tests (Coder)

Step 2: Execute subtasks sequentially
Step 3: Verify completion
"""
```

### 3. Хранение плана в сессии

```python
class SessionManager:
    def set_plan(self, session_id: str, plan: Dict):
        """Store execution plan for session"""
        
    def get_plan(self, session_id: str) -> Dict:
        """Get execution plan"""
        
    def mark_subtask_complete(self, session_id: str, subtask_id: str):
        """Mark subtask as completed"""
```

### 4. Обновленный multi_agent_orchestrator

```python
async def process_with_plan(session_id: str, plan: Dict):
    """Execute plan subtask by subtask"""
    for subtask in plan['subtasks']:
        # Switch to appropriate agent
        agent = get_agent(subtask['agent'])
        
        # Execute subtask
        result = await agent.process(
            session_id=session_id,
            message=subtask['description'],
            context=context
        )
        
        # Mark complete
        session_mgr.mark_subtask_complete(session_id, subtask['id'])
        
        # Continue to next subtask
```

## Преимущества

1. **Лучшая организация** - сложные задачи разбиты на шаги
2. **Отслеживание прогресса** - видно, какие подзадачи выполнены
3. **Меньше timeout** - каждая подзадача короче
4. **Лучшая специализация** - каждый агент делает свою часть
5. **Возможность паузы** - можно остановить и продолжить

## Недостатки

1. **Сложность реализации** - требует изменений в архитектуре
2. **Overhead** - дополнительные переключения между агентами
3. **Координация** - нужно передавать контекст между подзадачами

## Альтернатива (проще)

Вместо полноценного планирования, можно:

1. **Увеличить timeout** для complex задач (уже сделано: 300s)
2. **Добавить лимит tool calls** (уже сделано: 100)
3. **Улучшить промпт** - игнорировать warnings (уже сделано)
4. **Упростить задачи** - сделать их более конкретными

## Рекомендация

Для текущего POC:
- ✅ Использовать альтернативный подход (проще и быстрее)
- ✅ Увеличить timeout для complex задач
- ✅ Добавить лимит tool calls
- ✅ Улучшить промпты

Для production:
- 🔄 Реализовать полноценное планирование
- 🔄 Добавить Architect агента для планирования
- 🔄 Создать систему управления подзадачами

## Статус

Текущие улучшения (timeout, limits, prompts) достаточны для:
- ✅ 100% success на simple задачах
- ✅ Высокий success на medium задачах
- ⚠️ Complex задачи требуют планирования (будущее улучшение)
