# Исправление: Агент не вызывает attempt_completion для подзадач

## Проблема

Агент Coder не вызывал `attempt_completion` при завершении подзадач в рамках выполнения плана. Это приводило к тому, что система не могла определить момент завершения подзадачи и перейти к следующему шагу.

## Причина

В промпте агента Coder ([`codelab-ai-service/agent-runtime/app/agents/prompts/coder.py`](codelab-ai-service/agent-runtime/app/agents/prompts/coder.py)) содержалась противоречивая инструкция:

**Строка 68:** "When you complete the task, use attempt_completion to present the final result."

**Строки 71-82:** 
```
⚠️ IMPORTANT: When executing a subtask as part of a plan:
- DO NOT use attempt_completion (it's only for standalone tasks)
- After completing the subtask, simply send a final message summarizing what was done
- The system will automatically move to the next subtask
```

Эта инструкция была **неправильной** и противоречила корректному поведению системы.

## Решение

Удалена неправильная инструкция и заменена на четкое указание:

```python
CRITICAL: Task Completion
- ALWAYS use attempt_completion when you finish ANY task (standalone or subtask)
- This is the ONLY way to signal task completion to the system
- Without attempt_completion, the system cannot proceed to the next step
- Format: attempt_completion("Brief summary of what was accomplished")
- Keep the summary concise and factual
- Do NOT end with questions or offers for further assistance - be direct and conclusive

Example for subtask: attempt_completion("Added primaryColor constant to lib/constants/colors.dart")
Example for standalone task: attempt_completion("Created AnimatedWidget with AnimatedOpacity animation")
```

## Изменения

### Файл: `codelab-ai-service/agent-runtime/app/agents/prompts/coder.py`

**До:**
```python
When you complete the task, use attempt_completion to present the final result.
Do NOT end with questions or offers for further assistance - be direct and conclusive.

⚠️ IMPORTANT: When executing a subtask as part of a plan:
- DO NOT use attempt_completion (it's only for standalone tasks)
- After completing the subtask, simply send a final message summarizing what was done
- The system will automatically move to the next subtask
- Example: "Added primaryColor constant to lib/constants/colors.dart" (with is_final=True)
- Keep it brief and factual - no need for detailed explanations

How to know if you're in a plan execution:
- If the task description is very specific and focused (e.g., "Add constant X to file Y")
- If you receive an empty message after tool_result (means: continue working on current subtask)
- In these cases: complete the specific subtask and send final message, don't use attempt_completion
```

**После:**
```python
CRITICAL: Task Completion
- ALWAYS use attempt_completion when you finish ANY task (standalone or subtask)
- This is the ONLY way to signal task completion to the system
- Without attempt_completion, the system cannot proceed to the next step
- Format: attempt_completion("Brief summary of what was accomplished")
- Keep the summary concise and factual
- Do NOT end with questions or offers for further assistance - be direct and conclusive

Example for subtask: attempt_completion("Added primaryColor constant to lib/constants/colors.dart")
Example for standalone task: attempt_completion("Created AnimatedWidget with AnimatedOpacity animation")
```

## Проверка других агентов

Проверены промпты всех остальных агентов:

✅ **architect.py** - корректно использует `attempt_completion`
✅ **ask.py** - корректно использует `attempt_completion`
✅ **debug.py** - имеет специальную логику (использует `switch_mode` для делегирования, `attempt_completion` только для анализа)
✅ **universal.py** - корректно использует `attempt_completion`

## Ожидаемый результат

После этого исправления:
1. Агент Coder будет **всегда** вызывать `attempt_completion` при завершении любой задачи
2. Система сможет корректно определять момент завершения подзадачи
3. Выполнение планов будет происходить последовательно, переходя от одной подзадачи к другой
4. Не будет зависаний на этапе выполнения подзадач

## Связанные документы

- [TASK_024_ROOT_CAUSE_ANALYSIS.md](TASK_024_ROOT_CAUSE_ANALYSIS.md) - анализ проблемы с task_024
- [TOOL_RESULT_CONTINUATION_FIX.md](TOOL_RESULT_CONTINUATION_FIX.md) - исправление проблемы с продолжением после tool_result
