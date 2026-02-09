# ExecutionEngine → PlanExecutionService API Mapping

**Дата:** 2026-02-09  
**Цель:** Mapping для миграции ExecutionCoordinator

---

## API Comparison

| ExecutionEngine | PlanExecutionService | Изменения |
|-----------------|----------------------|-----------|
| `execute_plan(plan_id: str, ...)` | `start_plan_execution(plan_id: PlanId, ...)` | ✅ Переименован, typed ID |
| `get_execution_status(plan_id: str)` | `get_plan_status(plan_id: PlanId)` | ✅ Переименован, typed ID |
| `cancel_execution(plan_id: str, reason: str)` | `cancel_plan_execution(plan_id: PlanId, reason: str)` | ✅ Переименован, typed ID |

---

## Migration Strategy

### 1. ExecutionCoordinator Changes

```python
# ❌ Legacy
from app.domain.services.execution_engine import ExecutionEngine

class ExecutionCoordinator:
    def __init__(
        self,
        execution_engine: ExecutionEngine,
        plan_repository: PlanRepository
    ):
        self.execution_engine = execution_engine
        self.plan_repository = plan_repository

# ✅ New
from app.domain.execution_context.services.plan_execution_service import PlanExecutionService
from app.domain.execution_context.value_objects import PlanId

class ExecutionCoordinator:
    def __init__(
        self,
        plan_execution_service: PlanExecutionService,
        plan_repository: PlanRepository
    ):
        self._plan_execution_service = plan_execution_service
        self._plan_repository = plan_repository
```

### 2. Method Calls

```python
# ❌ Legacy
async for chunk in self.execution_engine.execute_plan(
    plan_id=plan_id,  # str
    session_id=session_id,
    session_service=session_service,
    stream_handler=stream_handler
):
    yield chunk

# ✅ New
async for chunk in self._plan_execution_service.start_plan_execution(
    plan_id=PlanId(plan_id),  # Convert str → PlanId
    session_id=session_id,
    session_service=session_service,
    stream_handler=stream_handler
):
    yield chunk
```

### 3. Status Check

```python
# ❌ Legacy
status = await self.execution_engine.get_execution_status(plan_id)

# ✅ New
status = await self._plan_execution_service.get_plan_status(PlanId(plan_id))
```

### 4. Cancellation

```python
# ❌ Legacy
result = await self.execution_engine.cancel_execution(
    plan_id=plan_id,
    reason=reason
)

# ✅ New
await self._plan_execution_service.cancel_plan_execution(
    plan_id=PlanId(plan_id),
    reason=reason
)
# Note: New method returns None, not Dict
```

---

## Key Differences

1. **Typed IDs:** `str` → `PlanId`
2. **Method names:** More explicit (`start_plan_execution` vs `execute_plan`)
3. **Return types:** `cancel_plan_execution` returns `None` instead of `Dict`
4. **Error types:** `ExecutionEngineError` → `PlanExecutionError`

---

**Status:** ✅ Ready for migration
