# Task 024 - Анализ корневой причины провала

**Дата:** 2026-01-16  
**Задача:** task_024 - Исправление infinite loop  
**Статус:** ❌ ПРОВАЛЕНА

---

## 🎯 Краткое резюме

Task_024 провалилась **НЕ из-за неправильных типов сообщений в multi_agent_orchestrator.py**, а из-за **неправильной классификации задачи Orchestrator агентом**.

---

## 📋 Детали задачи

```yaml
id: task_024
category: medium
type: debug
title: "Исправление infinite loop"
description: "Найти и исправить бесконечный цикл в state management коде"
expected_agent: "Debug"
expected_files:
  - "lib/blocs/infinite_loop_bloc.dart"
```

---

## 🔍 Что произошло

### Ожидаемый сценарий:
1. Orchestrator получает задачу "Найти и исправить бесконечный цикл"
2. Классифицирует как **debug** задачу
3. Роутит на **Debug агента**
4. Debug агент анализирует код и исправляет проблему

### Фактический сценарий:
1. ✅ Orchestrator получает задачу
2. ❌ **Неправильно классифицирует как architect задачу**
3. ❌ Роутит на **Architect агента**
4. ❌ Architect выполняет задачу напрямую (без создания плана)
5. ❌ Файл `lib/blocs/infinite_loop_bloc.dart` не создается
6. ❌ Валидация провалена

### Логи подтверждают:
```
2026-01-16 15:59:29,200 - benchmark.client - INFO - 🔄 Agent switched: architect → architect
2026-01-16 15:59:33,207 - benchmark.client - INFO -    📋 Plan Used: No
2026-01-16 15:59:33,207 - benchmark.client - INFO -    Expected Agent: Debug
2026-01-16 15:59:33,207 - benchmark.client - INFO -    Actual Agent: Architect
```

---

## 🐛 Корневая причина

### Проблема #1: Неправильная классификация в Orchestrator

**Файл:** [`orchestrator_agent.py:186-310`](codelab-ai-service/agent-runtime/app/services/orchestrator_agent.py:186)

Метод `classify_task_with_llm()` использует LLM для классификации задач, но:

1. **Промпт недостаточно специфичен** для debug задач
2. **Ключевые слова "найти и исправить"** могут интерпретироваться как планирование
3. **LLM выбирает Architect** вместо Debug

### Проблема #2: Architect не создает план для debug задач

**Файл:** [`architect_agent.py:54-268`](codelab-ai-service/agent-runtime/app/agents/architect_agent.py:54)

Architect агент имеет инструмент `create_plan`, но:

1. **LLM не вызывает create_plan** для простых debug задач
2. **Architect пытается выполнить задачу напрямую** вместо делегирования
3. **Промпт Architect** говорит создавать план для "implementation tasks", но debug задача не воспринимается как таковая

---

## ✅ Что было исправлено (но не помогло)

### Исправление типов сообщений в multi_agent_orchestrator.py

**Файлы изменены:**
- [`multi_agent_orchestrator.py:270-280`](codelab-ai-service/agent-runtime/app/services/multi_agent_orchestrator.py:270) - `assistant_message` → `subtask_started`
- [`multi_agent_orchestrator.py:345-353`](codelab-ai-service/agent-runtime/app/services/multi_agent_orchestrator.py:345) - `assistant_message` → `subtask_completed`
- [`multi_agent_orchestrator.py:398-409`](codelab-ai-service/agent-runtime/app/services/multi_agent_orchestrator.py:398) - `assistant_message` → `plan_completed`

**Результат:** ✅ Исправление корректное и необходимое для случаев, когда план создается  
**Но:** ❌ Не решает проблему task_024, потому что план вообще не создается

---

## 🔧 Необходимые исправления

### Исправление #1: Улучшить классификацию в Orchestrator

**Файл:** [`orchestrator_agent.py:22-36`](codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py:22)

Улучшить промпт классификации для более точного определения debug задач:

```python
CLASSIFICATION_PROMPT_TEMPLATE = """You are a task classifier for a multi-agent system.

CRITICAL RULES:
- Tasks with "найти", "исправить", "debug", "fix", "bug" → DEBUG agent
- Tasks with "создать", "implement", "write code" → CODER agent  
- Tasks with "спроектировать", "design", "architecture" → ARCHITECT agent
- Tasks with "объяснить", "explain", "what is" → ASK agent

User request: {user_message}

Analyze and respond with JSON:
{{
  "agent": "debug|coder|architect|ask",
  "confidence": "high|medium|low",
  "reasoning": "brief explanation"
}}
"""
```

### Исправление #2: Улучшить fallback классификацию

**Файл:** [`orchestrator_agent.py:312-337`](codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py:312)

Добавить более специфичные ключевые слова для debug:

```python
def _fallback_classify(self, message: str) -> AgentType:
    message_lower = message.lower()
    
    # Debug keywords - HIGHEST PRIORITY
    if any(kw in message_lower for kw in [
        "найти", "исправить", "debug", "fix", "bug", "error", 
        "проблем", "ошибк", "crash", "infinite loop", "бесконечный цикл"
    ]):
        return AgentType.DEBUG
    
    # Coder keywords
    elif any(kw in message_lower for kw in [
        "создать", "write", "implement", "code", "refactor"
    ]):
        return AgentType.CODER
    
    # Architect keywords
    elif any(kw in message_lower for kw in [
        "спроектировать", "design", "architecture", "plan", "spec"
    ]):
        return AgentType.ARCHITECT
    
    # Ask keywords
    elif any(kw in message_lower for kw in [
        "объяснить", "explain", "what is", "how does", "help"
    ]):
        return AgentType.ASK
    
    else:
        return AgentType.CODER
```

### Исправление #3: Обновить промпт Architect

**Файл:** [`architect.py:40-49`](codelab-ai-service/agent-runtime/app/agents/prompts/architect.py:40)

Добавить явное указание НЕ обрабатывать debug задачи:

```python
⚠️ IMPORTANT: You should NOT handle:
- Debug tasks (finding/fixing bugs) → use switch_mode to "debug"
- Simple coding tasks → use switch_mode to "coder"
- Questions → use switch_mode to "ask"

If you receive a task that's not about planning/architecture:
1. Use switch_mode tool to redirect to appropriate agent
2. DO NOT attempt to solve it yourself
```

---

## 📊 Тестирование исправлений

### Тест 1: Проверить классификацию debug задач
```bash
# Запустить task_024 после исправлений
cd benchmark-standalone
uv run python main.py --task-id=task_024
```

**Ожидаемый результат:**
- Orchestrator роутит на Debug агента
- Debug агент создает файл `lib/blocs/infinite_loop_bloc.dart`
- Валидация проходит

### Тест 2: Проверить другие debug задачи
```bash
# task_003, task_008, task_012, task_016, task_020
uv run python main.py --task-id=task_003,task_008,task_012
```

### Тест 3: Проверить, что планирование работает
```bash
# Задачи, требующие планирования (complex tasks)
uv run python main.py --task-id=task_009,task_027
```

---

## 📈 Приоритеты исправлений

1. **🔴 КРИТИЧНО:** Исправить классификацию в Orchestrator (Исправление #1 и #2)
2. **🟡 ВАЖНО:** Обновить промпт Architect (Исправление #3)
3. **🟢 ПОЛЕЗНО:** Сохранить исправления типов сообщений (уже сделано)

---

## 🎓 Выводы

1. ✅ **Исправление типов сообщений было правильным**, но не решило проблему task_024
2. ❌ **Реальная проблема** - неправильная классификация задач в Orchestrator
3. 🎯 **Решение** - улучшить промпт классификации и fallback логику
4. 📝 **Важно** - тестировать не только выполнение планов, но и правильность роутинга

---

## 📎 Связанные файлы

- [`BENCHMARK_TASK_024_ANALYSIS.md`](BENCHMARK_TASK_024_ANALYSIS.md) - Первоначальный анализ
- [`multi_agent_orchestrator.py`](codelab-ai-service/agent-runtime/app/services/multi_agent_orchestrator.py) - Исправлены типы сообщений
- [`orchestrator_agent.py`](codelab-ai-service/agent-runtime/app/agents/orchestrator_agent.py) - Требует исправления классификации
- [`architect_agent.py`](codelab-ai-service/agent-runtime/app/agents/architect_agent.py) - Требует обновления промпта
