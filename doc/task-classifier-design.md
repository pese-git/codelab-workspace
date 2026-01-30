# Task Classifier - Детальный технический дизайн

**Версия:** 1.0  
**Дата:** 30 января 2026

---

## 1. Обзор компонента

Task Classifier определяет, является ли задача атомарной (выполняется одним агентом) или требует планирования. Это критически важный компонент, так как от его решения зависит вся архитектура обработки.

### Ответственности
- Классификация задач на атомарные/неатомарные
- Определение целевого агента
- Валидация классификации по правилам
- Fallback на keyword matching при ошибке LLM
- Метрики точности классификации

---

## 2. Структура файлов

```
app/domain/entities/
└── task_classification.py     # Pydantic модель результата

app/domain/services/
└── task_classifier.py         # Основной сервис

app/agents/prompts/
└── classification.py          # Промпт для LLM

tests/
└── test_task_classifier.py    # Тесты
```

---

## 3. Реализация компонента

### 3.1 TaskClassification Entity

```python
# app/domain/entities/task_classification.py

from typing import Literal
from pydantic import BaseModel, Field, validator

class TaskClassification(BaseModel):
    """Результат классификации задачи"""
    
    is_atomic: bool = Field(
        ...,
        description="Является ли задача атомарной (выполняется одним агентом за один шаг)"
    )
    
    agent: Literal["code", "plan", "debug", "explain"] = Field(
        ...,
        description="Целевой агент: code (Coder), plan (Architect), debug (Debug), explain (Ask)"
    )
    
    confidence: Literal["high", "medium", "low"] = Field(
        ...,
        description="Уверенность в классификации"
    )
    
    reason: str = Field(
        ...,
        description="Обоснование классификации"
    )
    
    @validator("agent")
    def validate_agent_rule(cls, agent, values):
        """
        ПРАВИЛО: Если is_atomic=false, то agent ОБЯЗАТЕЛЬНО должен быть "plan"
        
        Это критическое правило гарантирует, что сложные задачи
        всегда идут на планирование в Architect
        """
        if not values.get("is_atomic") and agent != "plan":
            raise ValueError(
                "Non-atomic tasks MUST be assigned to 'plan' (Architect) agent. "
                f"Got agent='{agent}' for is_atomic=false"
            )
        return agent
    
    def to_agent_type(self):
        """Преобразовать строку агента в AgentType"""
        mapping = {
            "code": AgentType.CODER,
            "plan": AgentType.ARCHITECT,
            "debug": AgentType.DEBUG,
            "explain": AgentType.ASK,
        }
        return mapping[self.agent]
```

### 3.2 Classification Prompt

```python
# app/agents/prompts/classification.py

CLASSIFICATION_PROMPT = """You are a task classifier in a multi-agent system.

Your job is to analyze a user's request and determine:
1. Whether it's ATOMIC (can be completed by a single agent in one step)
2. Which agent should handle it

DEFINITION OF ATOMIC TASK:
A task is ATOMIC only if ALL conditions are met:
- Single clear step with no sequencing needed
- Can be completed by ONE agent without involving other agents
- Does NOT require studying or exploring an existing project/codebase
- Does NOT involve building or implementing an application or system
- Does NOT span multiple files or components
- Does NOT require architectural, design, or planning decisions
- Can be accomplished in a single LLM call

If ANY condition is false → the task is NON-ATOMIC

ROUTING RULES:
- "code" agent (Coder): For writing, modifying, or refactoring code
  Examples: "create a function", "fix this bug", "implement feature X"
  
- "plan" agent (Architect): For analysis, design, and planning
  Examples: "design authentication system", "plan the refactoring", "analyze current architecture"
  
- "debug" agent (Debug): For troubleshooting and error investigation
  Examples: "why is this failing?", "investigate this error", "debug this issue"
  
- "explain" agent (Ask): For explanations and documentation
  Examples: "explain how X works", "what is Y?", "document this code"

CRITICAL RULE:
If is_atomic = false (non-atomic task), then agent MUST ALWAYS be "plan".
Non-atomic tasks REQUIRE Architect for decomposition into subtasks.

Respond with JSON only, no markdown or explanation:
{{
  "is_atomic": true | false,
  "agent": "code" | "plan" | "debug" | "explain",
  "confidence": "high" | "medium" | "low",
  "reason": "Brief explanation (1-2 sentences)"
}}

User request: {user_message}"""
```

### 3.3 TaskClassifier Service

```python
# app/domain/services/task_classifier.py

import json
import logging
from typing import Optional
from app.domain.entities.task_classification import TaskClassification
from app.infrastructure.llm.client import llm_proxy_client
from app.core.config import AppConfig

logger = logging.getLogger("agent-runtime.task_classifier")

class ClassificationError(Exception):
    """Ошибка при классификации"""
    pass

class TaskClassifier:
    """Классификатор задач на атомарные/неатомарные"""
    
    def __init__(self):
        self.llm_client = llm_proxy_client
        self.model = AppConfig.LLM_MODEL
        # Кэш для одинаковых запросов (опционально)
        self._cache: Dict[str, TaskClassification] = {}
    
    async def classify(self, message: str) -> TaskClassification:
        """
        Классифицировать задачу используя LLM с fallback на keyword matching
        
        Args:
            message: Сообщение пользователя
        
        Returns:
            TaskClassification с результатом
        
        Raises:
            ClassificationError: Если классификация не удалась
        """
        try:
            # Попробовать LLM классификацию
            return await self._classify_with_llm(message)
        except Exception as e:
            logger.warning(f"LLM classification failed: {e}, falling back to keyword matching")
            try:
                return self._classify_with_keywords(message)
            except Exception as fallback_error:
                logger.error(f"Both classification methods failed: {fallback_error}")
                raise ClassificationError(
                    f"Failed to classify task: {str(fallback_error)}"
                )
    
    async def _classify_with_llm(self, message: str) -> TaskClassification:
        """Классификация с использованием LLM"""
        from app.agents.prompts.classification import CLASSIFICATION_PROMPT
        
        # Подготовить промпт
        prompt = CLASSIFICATION_PROMPT.format(user_message=message)
        
        logger.debug(f"Sending classification request to LLM for message: {message[:100]}...")
        
        # Вызвать LLM
        response = await self.llm_client.chat_completion(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a task classifier. Respond with JSON only."
                },
                {"role": "user", "content": prompt}
            ],
            stream=False,
            extra_params={"temperature": 0.3}  # Низкая температура для консистентности
        )
        
        # Извлечь контент
        content = response["choices"][0]["message"]["content"]
        logger.debug(f"LLM response: {content}")
        
        # Парсить JSON
        try:
            if "```json" in content:
                # Извлечь JSON из markdown блока
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content
            
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {content}")
            raise ClassificationError(f"Invalid JSON response from LLM: {str(e)}")
        
        # Создать объект с валидацией
        try:
            classification = TaskClassification(**data)
        except ValueError as e:
            logger.error(f"Classification validation failed: {e}")
            raise ClassificationError(f"Invalid classification: {str(e)}")
        
        logger.info(
            f"LLM classification result: is_atomic={classification.is_atomic}, "
            f"agent={classification.agent}, confidence={classification.confidence}"
        )
        
        return classification
    
    def _classify_with_keywords(self, message: str) -> TaskClassification:
        """Fallback классификация с использованием keyword matching"""
        message_lower = message.lower()
        
        logger.debug("Using keyword-based classification")
        
        # Ключевые слова для разных типов задач
        code_keywords = [
            "create", "write", "implement", "add", "fix", "modify",
            "refactor", "improve", "change", "update", "delete",
            "remove", "build", "develop", "code"
        ]
        
        architect_keywords = [
            "design", "architecture", "plan", "organize", "structure",
            "schema", "blueprint", "strategy", "spec", "specification",
            "analyze", "study", "explore", "review", "audit"
        ]
        
        debug_keywords = [
            "debug", "error", "bug", "problem", "issue", "crash",
            "fail", "broken", "wrong", "investigate", "find", "trace",
            "why", "what's wrong", "not working"
        ]
        
        ask_keywords = [
            "explain", "what is", "how does", "what does", "why",
            "describe", "help", "understand", "document", "teach",
            "example", "advice", "recommend", "question"
        ]
        
        # Подсчитать совпадения
        code_score = sum(1 for kw in code_keywords if kw in message_lower)
        architect_score = sum(1 for kw in architect_keywords if kw in message_lower)
        debug_score = sum(1 for kw in debug_keywords if kw in message_lower)
        ask_score = sum(1 for kw in ask_keywords if kw in message_lower)
        
        scores = {
            "code": code_score,
            "plan": architect_score,
            "debug": debug_score,
            "explain": ask_score,
        }
        
        # Определить целевого агента (максимальный скор)
        target_agent = max(scores, key=scores.get)
        
        # Определить является ли задача атомарной
        # Эвристика: если много архитектурных слов → неатомарная
        is_atomic = architect_score <= 1
        
        # Если неатомарная, то всегда план
        if not is_atomic:
            target_agent = "plan"
        
        # Определить уверенность на основе скора
        max_score = max(scores.values())
        if max_score >= 3:
            confidence = "high"
        elif max_score >= 1:
            confidence = "medium"
        else:
            confidence = "low"
        
        reason = f"Keyword matching: {target_agent} ({scores[target_agent]} keywords)"
        
        logger.info(
            f"Keyword classification: is_atomic={is_atomic}, agent={target_agent}, "
            f"confidence={confidence}, scores={scores}"
        )
        
        # Создать объект (с валидацией)
        return TaskClassification(
            is_atomic=is_atomic,
            agent=target_agent,
            confidence=confidence,
            reason=reason
        )
    
    async def validate_classification(
        self,
        classification: TaskClassification
    ) -> tuple[bool, str]:
        """
        Валидировать классификацию по правилам
        
        Returns:
            (is_valid, error_message)
        """
        # Проверка основного правила
        if not classification.is_atomic and classification.agent != "plan":
            return False, (
                "Non-atomic tasks MUST be assigned to 'plan' agent. "
                f"Got agent='{classification.agent}'"
            )
        
        return True, ""
    
    def clear_cache(self) -> None:
        """Очистить кэш классификаций"""
        self._cache.clear()
        logger.debug("Classification cache cleared")
```

---

## 4. Интеграция в OrchestratorAgent

```python
# Пример использования в OrchestratorAgent

class OrchestratorAgent(BaseAgent):
    
    def __init__(self):
        super().__init__(...)
        self.task_classifier = TaskClassifier()
    
    async def process(self, session_id: str, message: str, ...):
        try:
            # Классифицировать задачу
            classification = await self.task_classifier.classify(message)
            
            # Валидировать (обычно пройдет благодаря Pydantic validator)
            is_valid, error_msg = await self.task_classifier.validate_classification(classification)
            if not is_valid:
                logger.error(f"Classification validation failed: {error_msg}")
                yield StreamChunk(type="error", error=error_msg)
                return
            
            # Использовать результат
            if classification.is_atomic:
                # Маршрутировать напрямую
                target_agent = classification.to_agent_type()
                yield StreamChunk(type="switch_agent", target_agent=target_agent.value)
            else:
                # Требуется планирование
                yield StreamChunk(type="switch_agent", target_agent=AgentType.ARCHITECT.value)
        
        except ClassificationError as e:
            logger.error(f"Classification error: {e}")
            yield StreamChunk(type="error", error=str(e))
```

---

## 5. Тестовые сценарии

```python
# tests/test_task_classifier.py

@pytest.mark.asyncio
async def test_atomic_coding_task():
    """Тест классификации атомарной задачи на кодирование"""
    classifier = TaskClassifier()
    
    result = await classifier.classify("Create a function to calculate fibonacci")
    
    assert result.is_atomic == True
    assert result.agent == "code"
    assert result.confidence in ["high", "medium", "low"]

@pytest.mark.asyncio
async def test_non_atomic_task():
    """Тест классификации неатомарной задачи"""
    classifier = TaskClassifier()
    
    result = await classifier.classify("Design a complete authentication system")
    
    assert result.is_atomic == False
    assert result.agent == "plan"  # ПРАВИЛО: non-atomic → plan

@pytest.mark.asyncio
async def test_rule_enforcement():
    """Тест что правило (non-atomic → plan) неразрывно"""
    classifier = TaskClassifier()
    
    # Попытка создать неатомарную задачу с не-plan агентом должна упасть
    with pytest.raises(ValueError):
        TaskClassification(
            is_atomic=False,
            agent="code",  # НАРУШЕНИЕ ПРАВИЛА!
            confidence="high",
            reason="test"
        )

@pytest.mark.asyncio
async def test_llm_fallback():
    """Тест fallback на keyword matching при ошибке LLM"""
    classifier = TaskClassifier()
    
    # Mock LLM ошибку
    with patch.object(classifier, '_classify_with_llm', side_effect=Exception("LLM error")):
        result = await classifier.classify("Create a login form")
    
    # Должен использовать fallback
    assert result is not None
    assert result.agent == "code"

def test_keyword_classification():
    """Тест keyword-based классификации"""
    classifier = TaskClassifier()
    
    result = classifier._classify_with_keywords("Design the architecture")
    
    assert result.is_atomic == False
    assert result.agent == "plan"
    assert result.confidence in ["high", "medium", "low"]
```

---

## 6. Критерии готовности

- [ ] TaskClassification Pydantic модель с валидацией
- [ ] ПРАВИЛО (non-atomic → plan) внедрено и протестировано
- [ ] LLM классификация работает
- [ ] Fallback на keyword matching работает
- [ ] Парсинг JSON из LLM ответа работает
- [ ] Unit тесты: 100% coverage
- [ ] Integration тесты с OrchestratorAgent
- [ ] Обработка ошибок правильная

---

**Статус:** 🟢 Готов к реализации
