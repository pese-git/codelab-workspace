# Execution Engine - Детальный технический дизайн

**Версия:** 1.0  
**Дата:** 30 января 2026

---

## 1. Обзор компонента

Execution Engine отвечает за исполнение планов, полученных от Architect. Он управляет жизненным циклом subtasks, обрабатывает зависимости и обработку ошибок.

### Ответственности
- Исполнение плана (итерация по subtasks)
- Разрешение зависимостей между subtasks
- Маршрутизация на целевого агента
- Обработка результатов выполнения
- Обработка ошибок и retry
- Отслеживание прогресса

---

## 2. Структура файлов

```
app/domain/services/
├── execution_engine.py          # Основной движок
├── subtask_executor.py          # Исполнитель subtask
├── dependency_resolver.py       # Разрешение зависимостей
├── progress_tracker.py          # Отслеживание прогресса
└── execution_error_handler.py   # Обработка ошибок

app/domain/entities/
└── execution_result.py          # Результат исполнения

tests/
├── test_execution_engine.py
├── test_subtask_executor.py
└── test_dependency_resolver.py
```

---

## 3. Реализация компонента

### 3.1 DependencyResolver

```python
# app/domain/services/dependency_resolver.py

import logging
from typing import List, Set
from app.domain.entities.plan import Plan, Subtask, SubtaskStatus

logger = logging.getLogger("agent-runtime.dependency_resolver")

class DependencyResolver:
    """Разрешение зависимостей между subtasks"""
    
    @staticmethod
    def get_ready_subtasks(plan: Plan) -> List[Subtask]:
        """
        Получить список subtasks готовых к исполнению
        
        Subtask готов если:
        - Статус = PENDING
        - Все его зависимости имеют статус DONE
        """
        completed_ids = {
            st.id for st in plan.subtasks
            if st.status == SubtaskStatus.DONE
        }
        
        ready = []
        for subtask in plan.subtasks:
            if subtask.is_ready(completed_ids):
                ready.append(subtask)
        
        return ready
    
    @staticmethod
    def has_cyclic_dependencies(plan: Plan) -> bool:
        """
        Проверить наличие циклических зависимостей в плане
        
        Использует DFS (Depth-First Search) для обнаружения циклов
        """
        # Построить граф зависимостей
        graph = {st.id: st.dependencies for st in plan.subtasks}
        
        def has_cycle_util(node_id: str, visited: Set[str], rec_stack: Set[str]) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)
            
            for neighbor in graph.get(node_id, []):
                if neighbor not in visited:
                    if has_cycle_util(neighbor, visited, rec_stack):
                        return True
                elif neighbor in rec_stack:
                    return True
            
            rec_stack.remove(node_id)
            return False
        
        visited = set()
        for node_id in graph.keys():
            if node_id not in visited:
                if has_cycle_util(node_id, visited, set()):
                    return True
        
        return False
    
    @staticmethod
    def validate_dependencies(plan: Plan) -> tuple[bool, str]:
        """
        Валидировать зависимости в плане
        
        Returns:
            (is_valid, error_message)
        """
        # Проверить циклические зависимости
        if DependencyResolver.has_cyclic_dependencies(plan):
            return False, "Plan contains cyclic dependencies"
        
        # Проверить что все зависимости существуют
        valid_ids = {st.id for st in plan.subtasks}
        for subtask in plan.subtasks:
            for dep_id in subtask.dependencies:
                if dep_id not in valid_ids:
                    return False, f"Dependency {dep_id} not found in plan"
        
        return True, ""
    
    @staticmethod
    def get_execution_order(plan: Plan) -> List[List[str]]:
        """
        Получить порядок исполнения subtasks по слоям
        
        Returns:
            Список слоев, где каждый слой содержит независимые subtasks
        """
        layers = []
        completed = set()
        
        while len(completed) < len(plan.subtasks):
            # Найти subtasks без зависимостей или с выполненными зависимостями
            layer = []
            for subtask in plan.subtasks:
                if subtask.id not in completed:
                    if all(dep in completed for dep in subtask.dependencies):
                        layer.append(subtask.id)
            
            if not layer:
                # Нет готовых subtasks - невозможно продолжить
                break
            
            layers.append(layer)
            completed.update(layer)
        
        return layers
```

### 3.2 SubtaskExecutor

```python
# app/domain/services/subtask_executor.py

import logging
from typing import Optional
from app.domain.entities.plan import Subtask, SubtaskStatus
from app.domain.services.agent_registry import agent_router
from app.domain.entities.agent_context import AgentType

logger = logging.getLogger("agent-runtime.subtask_executor")

class SubtaskExecutor:
    """Исполнитель отдельного subtask"""
    
    async def execute(
        self,
        session_id: str,
        subtask: Subtask,
        context: Dict[str, Any]
    ) -> str:
        """
        Исполнить subtask в целевом агенте
        
        Args:
            session_id: ID сессии
            subtask: Subtask для исполнения
            context: Контекст выполнения
        
        Returns:
            Результат выполнения
        
        Raises:
            SubtaskExecutionError: Если выполнение не удалось
        """
        try:
            # Получить целевого агента
            target_agent = agent_router.get_agent(AgentType(subtask.agent))
            
            # Начать выполнение
            subtask.start()
            
            logger.info(
                f"Starting subtask execution for session {session_id}: "
                f"subtask={subtask.id}, agent={subtask.agent}"
            )
            
            # Выполнить через агента
            result = await target_agent.execute_subtask(
                session_id=session_id,
                subtask=subtask,
                context=context
            )
            
            # Успешно завершено
            subtask.complete(result)
            
            logger.info(
                f"Subtask completed for session {session_id}: "
                f"subtask={subtask.id}"
            )
            
            return result
        
        except Exception as e:
            logger.error(
                f"Subtask execution failed for session {session_id}: "
                f"subtask={subtask.id}, error={str(e)}",
                exc_info=True
            )
            
            # Отметить как failed
            subtask.fail(str(e))
            
            raise SubtaskExecutionError(
                f"Failed to execute subtask {subtask.id}: {str(e)}"
            )
    
    async def retry(
        self,
        session_id: str,
        subtask: Subtask,
        context: Dict[str, Any],
        max_retries: int = 3
    ) -> str:
        """
        Повторить исполнение subtask с retry логикой
        
        Args:
            session_id: ID сессии
            subtask: Subtask для повтора
            context: Контекст
            max_retries: Максимальное количество попыток
        
        Returns:
            Результат выполнения
        """
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    f"Retry attempt {attempt}/{max_retries} for subtask {subtask.id}"
                )
                
                # Сбросить статус на PENDING для повтора
                subtask.status = SubtaskStatus.PENDING
                
                return await self.execute(session_id, subtask, context)
            
            except SubtaskExecutionError as e:
                if attempt == max_retries:
                    logger.error(
                        f"All retry attempts failed for subtask {subtask.id}"
                    )
                    raise
                
                logger.warning(
                    f"Retry attempt {attempt} failed, trying again..."
                )
                continue
```

### 3.3 ExecutionEngine

```python
# app/domain/services/execution_engine.py

import logging
from typing import Optional, Dict, Any
from app.domain.entities.plan import Plan, PlanStatus
from app.domain.repositories.plan_repository import PlanRepository
from app.domain.services.dependency_resolver import DependencyResolver
from app.domain.services.subtask_executor import SubtaskExecutor
from app.domain.services.progress_tracker import ProgressTracker

logger = logging.getLogger("agent-runtime.execution_engine")

class ExecutionResult:
    """Результат исполнения плана"""
    def __init__(
        self,
        plan_id: str,
        success: bool,
        completed_subtasks: int,
        failed_subtasks: int,
        error: Optional[str] = None
    ):
        self.plan_id = plan_id
        self.success = success
        self.completed_subtasks = completed_subtasks
        self.failed_subtasks = failed_subtasks
        self.error = error

class ExecutionEngine:
    """Движок для исполнения планов"""
    
    def __init__(
        self,
        plan_repository: PlanRepository,
        subtask_executor: SubtaskExecutor,
        progress_tracker: ProgressTracker
    ):
        self.plan_repository = plan_repository
        self.subtask_executor = subtask_executor
        self.progress_tracker = progress_tracker
        self.dependency_resolver = DependencyResolver()
    
    async def execute_plan(
        self,
        session_id: str,
        plan: Plan
    ) -> ExecutionResult:
        """
        Исполнить план полностью
        
        Args:
            session_id: ID сессии
            plan: План для исполнения
        
        Returns:
            ExecutionResult с информацией о результате
        """
        try:
            # Валидировать план перед исполнением
            is_valid, error_msg = self.dependency_resolver.validate_dependencies(plan)
            if not is_valid:
                logger.error(f"Invalid plan {plan.id}: {error_msg}")
                return ExecutionResult(
                    plan_id=plan.id,
                    success=False,
                    completed_subtasks=0,
                    failed_subtasks=0,
                    error=error_msg
                )
            
            # Начать исполнение
            plan.start_execution()
            await self.plan_repository.save(plan)
            
            logger.info(f"Starting plan execution for session {session_id}: plan={plan.id}")
            
            # Контекст для исполнения
            context = {
                "session_id": session_id,
                "plan_id": plan.id,
            }
            
            # Исполнять subtasks пока есть готовые
            while True:
                # Получить следующий готовый subtask
                next_subtask = plan.get_next_subtask()
                
                if not next_subtask:
                    # Проверить статус плана
                    progress = plan.get_progress()
                    
                    if progress["failed"] == 0 and progress["done"] == progress["total"]:
                        # Все выполнено успешно
                        break
                    elif progress["failed"] > 0:
                        # Есть ошибки - остановиться
                        logger.error(f"Plan has failed subtasks: {plan.id}")
                        break
                    else:
                        # Есть pending subtasks - невозможно продолжить (возможно циклические зависимости)
                        logger.warning(f"No ready subtasks but plan not complete: {plan.id}")
                        break
                
                # Исполнить subtask
                try:
                    await self.subtask_executor.execute(
                        session_id=session_id,
                        subtask=next_subtask,
                        context=context
                    )
                except Exception as e:
                    logger.error(f"Subtask execution error: {str(e)}")
                    # Subtask уже отмечен как failed в executor
                    # Можно добавить retry логику здесь
                    continue
                
                # Сохранить прогресс
                await self.plan_repository.save(plan)
                
                # Опубликовать событие прогресса
                progress = plan.get_progress()
                self.progress_tracker.update(
                    session_id=session_id,
                    plan_id=plan.id,
                    progress=progress
                )
            
            # Завершить исполнение
            progress = plan.get_progress()
            
            if progress["failed"] == 0 and progress["done"] == progress["total"]:
                plan.complete()
                success = True
                error = None
            else:
                plan.fail(f"Execution failed: {progress['failed']} failed subtasks")
                success = False
                error = f"{progress['failed']} subtasks failed"
            
            await self.plan_repository.save(plan)
            
            logger.info(
                f"Plan execution completed for session {session_id}: "
                f"plan={plan.id}, success={success}"
            )
            
            return ExecutionResult(
                plan_id=plan.id,
                success=success,
                completed_subtasks=progress["done"],
                failed_subtasks=progress["failed"],
                error=error
            )
        
        except Exception as e:
            logger.error(f"Plan execution failed: {str(e)}", exc_info=True)
            return ExecutionResult(
                plan_id=plan.id,
                success=False,
                completed_subtasks=0,
                failed_subtasks=0,
                error=str(e)
            )
    
    async def pause_execution(
        self,
        session_id: str,
        plan: Plan
    ) -> None:
        """Приостановить исполнение плана"""
        # Сохранить текущее состояние
        await self.plan_repository.save(plan)
        logger.info(f"Plan execution paused: session={session_id}, plan={plan.id}")
    
    async def resume_execution(
        self,
        session_id: str,
        plan: Plan
    ) -> ExecutionResult:
        """Возобновить исполнение плана с текущей точки"""
        logger.info(f"Resuming plan execution: session={session_id}, plan={plan.id}")
        return await self.execute_plan(session_id, plan)
```

### 3.4 ProgressTracker

```python
# app/domain/services/progress_tracker.py

import logging
from typing import Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger("agent-runtime.progress_tracker")

class ProgressTracker:
    """Отслеживание прогресса исполнения плана"""
    
    def __init__(self):
        self._progress: Dict[str, Dict[str, Any]] = {}
    
    def update(
        self,
        session_id: str,
        plan_id: str,
        progress: Dict[str, Any]
    ) -> None:
        """
        Обновить прогресс
        
        Args:
            session_id: ID сессии
            plan_id: ID плана
            progress: Данные о прогрессе (от plan.get_progress())
        """
        key = f"{session_id}:{plan_id}"
        
        self._progress[key] = {
            "session_id": session_id,
            "plan_id": plan_id,
            **progress,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        
        logger.debug(f"Progress updated: {key}, done={progress['done']}/{progress['total']}")
    
    def get_progress(
        self,
        session_id: str,
        plan_id: str
    ) -> Optional[Dict[str, Any]]:
        """Получить текущий прогресс"""
        key = f"{session_id}:{plan_id}"
        return self._progress.get(key)
    
    def get_percentage(
        self,
        session_id: str,
        plan_id: str
    ) -> float:
        """Получить процент завершения"""
        progress = self.get_progress(session_id, plan_id)
        return progress["percentage"] if progress else 0.0
```

---

## 4. Тестовые сценарии

```python
# tests/test_execution_engine.py

@pytest.mark.asyncio
async def test_simple_plan_execution():
    """Тест исполнения простого плана без зависимостей"""
    # Setup
    plan = create_test_plan_with_subtasks(count=3, dependencies=[])
    engine = create_execution_engine()
    
    # Execute
    result = await engine.execute_plan("session-1", plan)
    
    # Assert
    assert result.success == True
    assert result.completed_subtasks == 3
    assert result.failed_subtasks == 0

@pytest.mark.asyncio
async def test_plan_with_dependencies():
    """Тест исполнения плана с зависимостями"""
    # Setup: subtask_2 зависит от subtask_1
    plan = create_test_plan_with_subtasks(
        subtasks=[
            {"id": "st1", "deps": []},
            {"id": "st2", "deps": ["st1"]},
            {"id": "st3", "deps": ["st2"]},
        ]
    )
    
    # Execute
    result = await engine.execute_plan("session-1", plan)
    
    # Assert
    assert result.success == True
    # Проверить порядок исполнения

@pytest.mark.asyncio
async def test_cyclic_dependency_detection():
    """Тест обнаружения циклических зависимостей"""
    # Setup: st1 → st2 → st1 (цикл)
    plan = create_test_plan_with_subtasks(
        subtasks=[
            {"id": "st1", "deps": ["st2"]},
            {"id": "st2", "deps": ["st1"]},
        ]
    )
    
    # Execute
    result = await engine.execute_plan("session-1", plan)
    
    # Assert
    assert result.success == False
    assert "cyclic" in result.error.lower()

@pytest.mark.asyncio
async def test_subtask_failure_handling():
    """Тест обработки ошибок subtask"""
    # Setup
    plan = create_test_plan_with_subtasks(count=3)
    plan.subtasks[1].should_fail = True  # Вторая задача падает
    
    # Execute
    result = await engine.execute_plan("session-1", plan)
    
    # Assert
    assert result.success == False
    assert result.failed_subtasks == 1
    assert result.completed_subtasks == 2
```

---

## 5. Критерии готовности

- [ ] DependencyResolver разрешает зависимости
- [ ] DependencyResolver обнаруживает циклы
- [ ] SubtaskExecutor исполняет subtasks
- [ ] ExecutionEngine управляет полным workflow
- [ ] ProgressTracker отслеживает прогресс
- [ ] Обработка ошибок работает
- [ ] Unit тесты: >85% coverage
- [ ] Integration тесты с реальными agentami

---

**Статус:** 🟢 Готов к реализации
