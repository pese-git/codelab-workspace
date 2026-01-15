"""
Tests for planning system integration in benchmark-standalone.

Tests the new planning functionality including:
- ExecutionPlan and SubtaskExecution models
- MetricsCollector planning methods
- Report generation with planning metrics
"""
import pytest
from datetime import datetime, timezone
from uuid import uuid4

from src.models import ExecutionPlan, SubtaskExecution, TaskExecution, Experiment
from src.collector import MetricsCollector


@pytest.mark.asyncio
async def test_execution_plan_creation(db_session):
    """Test creating an execution plan with subtasks."""
    # Create experiment and task execution
    experiment = Experiment(
        id=str(uuid4()),
        mode="multi-agent",
        started_at=datetime.now(timezone.utc)
    )
    db_session.add(experiment)
    await db_session.commit()
    
    task_execution = TaskExecution(
        id=str(uuid4()),
        experiment_id=experiment.id,
        task_id="test_task_001",
        task_category="complex",
        task_type="coding",
        mode="multi-agent",
        started_at=datetime.now(timezone.utc)
    )
    db_session.add(task_execution)
    await db_session.commit()
    
    # Create execution plan
    plan = ExecutionPlan(
        id=str(uuid4()),
        task_execution_id=task_execution.id,
        plan_id="plan_test_123",
        original_task="Migrate from Provider to Riverpod",
        subtask_count=3,
        created_at=datetime.now(timezone.utc)
    )
    db_session.add(plan)
    await db_session.commit()
    
    # Create subtasks
    subtasks_data = [
        {
            "id": "subtask_1",
            "description": "Add riverpod dependency",
            "agent": "coder",
            "estimated_time": "2 min"
        },
        {
            "id": "subtask_2",
            "description": "Create providers",
            "agent": "coder",
            "estimated_time": "5 min"
        },
        {
            "id": "subtask_3",
            "description": "Update main.dart",
            "agent": "coder",
            "estimated_time": "3 min"
        }
    ]
    
    for idx, subtask_data in enumerate(subtasks_data):
        subtask = SubtaskExecution(
            id=str(uuid4()),
            plan_id=plan.id,
            subtask_id=subtask_data["id"],
            sequence_number=idx,
            description=subtask_data["description"],
            agent=subtask_data["agent"],
            estimated_time=subtask_data["estimated_time"],
            status="pending"
        )
        db_session.add(subtask)
    
    await db_session.commit()
    
    # Verify plan was created
    assert plan.subtask_count == 3
    assert plan.is_complete is False
    
    # Verify subtasks were created
    from sqlalchemy import select
    result = await db_session.execute(
        select(SubtaskExecution).where(SubtaskExecution.plan_id == plan.id)
    )
    subtasks = list(result.scalars().all())
    assert len(subtasks) == 3
    assert all(s.status == "pending" for s in subtasks)


@pytest.mark.asyncio
async def test_collector_record_plan_created(db_session):
    """Test MetricsCollector.record_plan_created method."""
    collector = MetricsCollector(db_session)
    
    # Create experiment and task execution
    experiment_id = await collector.start_experiment(mode="multi-agent")
    task_execution_id = await collector.start_task(
        experiment_id=experiment_id,
        task_id="test_task_002",
        task_category="complex",
        task_type="coding",
        mode="multi-agent"
    )
    
    # Record plan creation
    subtasks = [
        {
            "id": "subtask_1",
            "description": "Design architecture",
            "agent": "architect",
            "estimated_time": "10 min"
        },
        {
            "id": "subtask_2",
            "description": "Implement models",
            "agent": "coder",
            "estimated_time": "15 min"
        }
    ]
    
    plan_uuid = await collector.record_plan_created(
        task_execution_id=task_execution_id,
        plan_id="plan_test_456",
        original_task="Implement authentication system",
        subtasks=subtasks
    )
    
    assert plan_uuid is not None
    
    # Verify plan was recorded
    from sqlalchemy import select
    result = await db_session.execute(
        select(ExecutionPlan).where(ExecutionPlan.id == str(plan_uuid))
    )
    plan = result.scalar_one()
    
    assert plan.plan_id == "plan_test_456"
    assert plan.subtask_count == 2
    assert plan.original_task == "Implement authentication system"


@pytest.mark.asyncio
async def test_collector_subtask_lifecycle(db_session):
    """Test subtask start and completion recording."""
    collector = MetricsCollector(db_session)
    
    # Setup
    experiment_id = await collector.start_experiment(mode="multi-agent")
    task_execution_id = await collector.start_task(
        experiment_id=experiment_id,
        task_id="test_task_003",
        task_category="complex",
        task_type="coding",
        mode="multi-agent"
    )
    
    subtasks = [
        {
            "id": "subtask_1",
            "description": "Write tests",
            "agent": "coder",
            "estimated_time": "5 min"
        }
    ]
    
    await collector.record_plan_created(
        task_execution_id=task_execution_id,
        plan_id="plan_test_789",
        original_task="Add test coverage",
        subtasks=subtasks
    )
    
    # Record subtask start
    subtask_uuid = await collector.record_subtask_started(
        task_execution_id=task_execution_id,
        subtask_id="subtask_1",
        description="Write tests",
        agent="coder"
    )
    
    assert subtask_uuid is not None
    
    # Verify subtask status is in_progress
    from sqlalchemy import select
    result = await db_session.execute(
        select(SubtaskExecution).where(SubtaskExecution.id == str(subtask_uuid))
    )
    subtask = result.scalar_one()
    assert subtask.status == "in_progress"
    assert subtask.started_at is not None
    
    # Record subtask completion
    await collector.record_subtask_completed(
        task_execution_id=task_execution_id,
        subtask_id="subtask_1",
        status="completed",
        result="Tests added successfully"
    )
    
    # Verify subtask status is completed
    await db_session.refresh(subtask)
    assert subtask.status == "completed"
    assert subtask.completed_at is not None
    assert subtask.result == "Tests added successfully"
    assert subtask.duration_seconds is not None


@pytest.mark.asyncio
async def test_collector_get_plan_metrics(db_session):
    """Test getting plan metrics."""
    collector = MetricsCollector(db_session)
    
    # Setup
    experiment_id = await collector.start_experiment(mode="multi-agent")
    task_execution_id = await collector.start_task(
        experiment_id=experiment_id,
        task_id="test_task_004",
        task_category="complex",
        task_type="mixed",
        mode="multi-agent"
    )
    
    subtasks = [
        {"id": "subtask_1", "description": "Task 1", "agent": "coder"},
        {"id": "subtask_2", "description": "Task 2", "agent": "architect"},
        {"id": "subtask_3", "description": "Task 3", "agent": "coder"}
    ]
    
    await collector.record_plan_created(
        task_execution_id=task_execution_id,
        plan_id="plan_test_metrics",
        original_task="Complex multi-step task",
        subtasks=subtasks
    )
    
    # Complete some subtasks
    await collector.record_subtask_started(
        task_execution_id=task_execution_id,
        subtask_id="subtask_1",
        description="Task 1",
        agent="coder"
    )
    await collector.record_subtask_completed(
        task_execution_id=task_execution_id,
        subtask_id="subtask_1",
        status="completed"
    )
    
    await collector.record_subtask_started(
        task_execution_id=task_execution_id,
        subtask_id="subtask_2",
        description="Task 2",
        agent="architect"
    )
    await collector.record_subtask_completed(
        task_execution_id=task_execution_id,
        subtask_id="subtask_2",
        status="failed",
        error="Architecture conflict"
    )
    
    # Get plan metrics
    metrics = await collector.get_plan_metrics(task_execution_id)
    
    assert metrics is not None
    assert metrics["plan_id"] == "plan_test_metrics"
    assert metrics["total_subtasks"] == 3
    assert metrics["completed_subtasks"] == 1
    assert metrics["failed_subtasks"] == 1
    assert metrics["success_rate"] == pytest.approx(1/3)
    assert "agent_distribution" in metrics
    assert metrics["agent_distribution"]["coder"] == 2
    assert metrics["agent_distribution"]["architect"] == 1


@pytest.mark.asyncio
async def test_plan_completion(db_session):
    """Test marking plan as completed."""
    collector = MetricsCollector(db_session)
    
    # Setup
    experiment_id = await collector.start_experiment(mode="multi-agent")
    task_execution_id = await collector.start_task(
        experiment_id=experiment_id,
        task_id="test_task_005",
        task_category="complex",
        task_type="coding",
        mode="multi-agent"
    )
    
    subtasks = [{"id": "subtask_1", "description": "Final task", "agent": "coder"}]
    
    await collector.record_plan_created(
        task_execution_id=task_execution_id,
        plan_id="plan_test_complete",
        original_task="Final test",
        subtasks=subtasks
    )
    
    # Mark plan as completed
    plan_uuid = await collector.record_plan_completed(task_execution_id)
    
    assert plan_uuid is not None
    
    # Verify plan is marked complete
    from sqlalchemy import select
    result = await db_session.execute(
        select(ExecutionPlan).where(ExecutionPlan.id == str(plan_uuid))
    )
    plan = result.scalar_one()
    
    assert plan.is_complete is True
    assert plan.completed_at is not None


# Fixture for database session (to be implemented based on your test setup)
@pytest.fixture
async def db_session():
    """Provide a database session for tests."""
    # This should be implemented based on your actual database setup
    # For now, this is a placeholder
    from src.database import get_db, init_database, init_db
    
    # Use in-memory SQLite for tests
    init_database("sqlite+aiosqlite:///:memory:", echo=False)
    await init_db()
    
    async for session in get_db():
        yield session
        break
