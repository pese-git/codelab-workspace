"""
Metrics Collector - сбор и хранение метрик benchmark экспериментов.

Адаптировано из codelab-ai-service/agent-runtime/app/services/metrics_collector.py
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import (
    AgentSwitch,
    ExecutionPlan,
    Experiment,
    Hallucination,
    LLMCall,
    QualityEvaluation,
    SubtaskExecution,
    TaskExecution,
    ToolCall,
)

logger = logging.getLogger("benchmark.collector")


class MetricsCollector:
    """
    Collects and stores experiment metrics.
    
    Usage:
        collector = MetricsCollector(db_session)
        exp_id = await collector.start_experiment(mode="multi-agent")
        task_id = await collector.start_task(exp_id, "task_001", "simple", "coding", "multi-agent")
        await collector.record_llm_call(task_id, "coder", 500, 200, "gpt-4", 2.5)
        await collector.complete_task(task_id, success=True)
        await collector.complete_experiment(exp_id)
    """
    
    def __init__(self, db_session: AsyncSession):
        """
        Initialize metrics collector.
        
        Args:
            db_session: Async database session
        """
        self.db = db_session
        logger.debug("MetricsCollector initialized")
    
    async def start_experiment(
        self,
        mode: str,
        config: Optional[Dict[str, Any]] = None
    ) -> UUID:
        """
        Start new experiment.
        
        Args:
            mode: Experiment mode ('single-agent' or 'multi-agent')
            config: Optional experiment configuration
            
        Returns:
            Experiment UUID
        """
        if mode not in ("single-agent", "multi-agent"):
            raise ValueError(f"Invalid mode: {mode}")
        
        experiment = Experiment(
            mode=mode,
            started_at=datetime.now(timezone.utc),
            config=config or {}
        )
        
        self.db.add(experiment)
        await self.db.commit()
        await self.db.refresh(experiment)
        
        logger.info(f"Started experiment: id={experiment.id}, mode={mode}")
        
        return UUID(experiment.id)
    
    async def complete_experiment(self, experiment_id: UUID) -> None:
        """
        Mark experiment as completed.
        
        Args:
            experiment_id: Experiment UUID
        """
        result = await self.db.execute(
            select(Experiment).where(Experiment.id == str(experiment_id))
        )
        experiment = result.scalar_one_or_none()
        
        if not experiment:
            raise ValueError(f"Experiment not found: {experiment_id}")
        
        experiment.completed_at = datetime.now(timezone.utc)
        await self.db.commit()
        
        logger.info(f"Completed experiment: id={experiment_id}")
    
    async def start_task(
        self,
        experiment_id: UUID,
        task_id: str,
        task_category: str,
        task_type: str,
        mode: str
    ) -> UUID:
        """
        Start task execution.
        
        Args:
            experiment_id: Parent experiment UUID
            task_id: Task identifier (e.g., 'task_001')
            task_category: Task category
            task_type: Task type
            mode: Execution mode
            
        Returns:
            Task execution UUID
        """
        # Validate experiment exists
        result = await self.db.execute(
            select(Experiment).where(Experiment.id == str(experiment_id))
        )
        if not result.scalar_one_or_none():
            raise ValueError(f"Experiment not found: {experiment_id}")
        
        task_execution = TaskExecution(
            experiment_id=str(experiment_id),
            task_id=task_id,
            task_category=task_category,
            task_type=task_type,
            mode=mode,
            started_at=datetime.now(timezone.utc)
        )
        
        self.db.add(task_execution)
        await self.db.commit()
        await self.db.refresh(task_execution)
        
        logger.info(f"Started task: id={task_execution.id}, task_id={task_id}")
        
        return UUID(task_execution.id)
    
    async def complete_task(
        self,
        task_execution_id: UUID,
        success: bool,
        failure_reason: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Complete task execution.
        
        Args:
            task_execution_id: Task execution UUID
            success: Whether task completed successfully
            failure_reason: Optional reason for failure
            metrics: Optional additional metrics
        """
        result = await self.db.execute(
            select(TaskExecution).where(TaskExecution.id == str(task_execution_id))
        )
        task_execution = result.scalar_one_or_none()
        
        if not task_execution:
            raise ValueError(f"Task execution not found: {task_execution_id}")
        
        task_execution.completed_at = datetime.now(timezone.utc)
        task_execution.success = success
        task_execution.failure_reason = failure_reason
        task_execution.metrics = metrics or {}
        
        # Calculate duration
        if task_execution.started_at and task_execution.completed_at:
            started = task_execution.started_at
            completed = task_execution.completed_at
            
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            if completed.tzinfo is None:
                completed = completed.replace(tzinfo=timezone.utc)
            
            duration = (completed - started).total_seconds()
            if "duration_seconds" not in task_execution.metrics:
                task_execution.metrics["duration_seconds"] = duration
        
        await self.db.commit()
        
        logger.info(f"Completed task: id={task_execution_id}, success={success}")
    
    async def record_llm_call(
        self,
        task_execution_id: UUID,
        agent_type: str,
        input_tokens: int,
        output_tokens: int,
        model: str,
        duration_seconds: float
    ) -> UUID:
        """Record LLM API call."""
        llm_call = LLMCall(
            task_execution_id=str(task_execution_id),
            agent_type=agent_type,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=model,
            duration_seconds=duration_seconds
        )
        
        self.db.add(llm_call)
        await self.db.commit()
        await self.db.refresh(llm_call)
        
        logger.debug(f"Recorded LLM call: agent={agent_type}, tokens={input_tokens}/{output_tokens}")
        
        return UUID(llm_call.id)
    
    async def record_tool_call(
        self,
        task_execution_id: UUID,
        tool_name: str,
        success: bool,
        duration_seconds: float,
        error: Optional[str] = None
    ) -> UUID:
        """Record tool invocation."""
        tool_call = ToolCall(
            task_execution_id=str(task_execution_id),
            tool_name=tool_name,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            success=success,
            duration_seconds=duration_seconds,
            error=error
        )
        
        self.db.add(tool_call)
        await self.db.commit()
        await self.db.refresh(tool_call)
        
        logger.debug(f"Recorded tool call: tool={tool_name}, success={success}")
        
        return UUID(tool_call.id)
    
    async def record_agent_switch(
        self,
        task_execution_id: UUID,
        from_agent: Optional[str],
        to_agent: str,
        reason: str
    ) -> UUID:
        """Record agent switch (multi-agent only)."""
        agent_switch = AgentSwitch(
            task_execution_id=str(task_execution_id),
            from_agent=from_agent,
            to_agent=to_agent,
            reason=reason,
            timestamp=datetime.now(timezone.utc)
        )
        
        self.db.add(agent_switch)
        await self.db.commit()
        await self.db.refresh(agent_switch)
        
        logger.info(f"Recorded agent switch: {from_agent} → {to_agent}")
        
        return UUID(agent_switch.id)
    
    async def record_quality_evaluation(
        self,
        task_execution_id: UUID,
        evaluation_type: str,
        score: Optional[float],
        passed: bool,
        details: Optional[Dict[str, Any]] = None
    ) -> UUID:
        """Record quality evaluation."""
        if score is not None and not (0.0 <= score <= 1.0):
            raise ValueError(f"Score must be between 0.0 and 1.0, got: {score}")
        
        quality_evaluation = QualityEvaluation(
            task_execution_id=str(task_execution_id),
            evaluation_type=evaluation_type,
            score=score,
            passed=passed,
            details=details or {},
            evaluated_at=datetime.now(timezone.utc)
        )
        
        self.db.add(quality_evaluation)
        await self.db.commit()
        await self.db.refresh(quality_evaluation)
        
        logger.info(f"Recorded quality evaluation: type={evaluation_type}, passed={passed}")
        
        return UUID(quality_evaluation.id)
    
    async def record_hallucination(
        self,
        task_execution_id: UUID,
        hallucination_type: str,
        description: str
    ) -> UUID:
        """Record detected hallucination."""
        hallucination = Hallucination(
            task_execution_id=str(task_execution_id),
            hallucination_type=hallucination_type,
            description=description,
            detected_at=datetime.now(timezone.utc)
        )
        
        self.db.add(hallucination)
        await self.db.commit()
        await self.db.refresh(hallucination)
        
        logger.warning(f"Recorded hallucination: type={hallucination_type}")
        
        return UUID(hallucination.id)
    
    async def record_plan_created(
        self,
        task_execution_id: UUID,
        plan_id: str,
        original_task: str,
        subtasks: List[Dict[str, Any]]
    ) -> UUID:
        """
        Record execution plan creation.
        
        Args:
            task_execution_id: Task execution UUID
            plan_id: Plan identifier from agent-runtime
            original_task: Original user task
            subtasks: List of subtask definitions
            
        Returns:
            Execution plan UUID
        """
        execution_plan = ExecutionPlan(
            task_execution_id=str(task_execution_id),
            plan_id=plan_id,
            original_task=original_task,
            subtask_count=len(subtasks),
            created_at=datetime.now(timezone.utc),
            is_complete=False
        )
        
        self.db.add(execution_plan)
        await self.db.commit()
        await self.db.refresh(execution_plan)
        
        # Create subtask records
        for idx, subtask_data in enumerate(subtasks):
            subtask = SubtaskExecution(
                plan_id=execution_plan.id,
                subtask_id=subtask_data.get('id', f'subtask_{idx}'),
                sequence_number=idx,
                description=subtask_data.get('description', ''),
                agent=subtask_data.get('agent', 'unknown'),
                estimated_time=subtask_data.get('estimated_time'),
                status='pending',
                dependencies=subtask_data.get('dependencies', {})
            )
            self.db.add(subtask)
        
        await self.db.commit()
        
        logger.info(
            f"📋 Recorded plan creation: plan_id={plan_id}, "
            f"subtasks={len(subtasks)}, task_execution_id={task_execution_id}"
        )
        
        return UUID(execution_plan.id)
    
    async def record_subtask_started(
        self,
        task_execution_id: UUID,
        subtask_id: str,
        description: str,
        agent: str
    ) -> Optional[UUID]:
        """
        Record subtask start.
        
        Args:
            task_execution_id: Task execution UUID
            subtask_id: Subtask identifier
            description: Subtask description
            agent: Agent handling the subtask
            
        Returns:
            Subtask execution UUID or None if not found
        """
        # Find the execution plan for this task
        result = await self.db.execute(
            select(ExecutionPlan).where(
                ExecutionPlan.task_execution_id == str(task_execution_id)
            )
        )
        plan = result.scalar_one_or_none()
        
        if not plan:
            logger.warning(f"No plan found for task_execution_id={task_execution_id}")
            return None
        
        # Find the subtask
        result = await self.db.execute(
            select(SubtaskExecution).where(
                SubtaskExecution.plan_id == plan.id,
                SubtaskExecution.subtask_id == subtask_id
            )
        )
        subtask = result.scalar_one_or_none()
        
        if not subtask:
            logger.warning(f"Subtask not found: {subtask_id}")
            return None
        
        # Update subtask status
        subtask.status = 'in_progress'
        subtask.started_at = datetime.now(timezone.utc)
        
        await self.db.commit()
        
        logger.info(
            f"▶️  Recorded subtask start: subtask_id={subtask_id}, "
            f"agent={agent}, description='{description[:50]}...'"
        )
        
        return UUID(subtask.id)
    
    async def record_subtask_completed(
        self,
        task_execution_id: UUID,
        subtask_id: str,
        status: str,
        result: Optional[str] = None,
        error: Optional[str] = None
    ) -> Optional[UUID]:
        """
        Record subtask completion.
        
        Args:
            task_execution_id: Task execution UUID
            subtask_id: Subtask identifier
            status: Final status (completed, failed, skipped)
            result: Optional result message
            error: Optional error message
            
        Returns:
            Subtask execution UUID or None if not found
        """
        # Find the execution plan for this task
        result_query = await self.db.execute(
            select(ExecutionPlan).where(
                ExecutionPlan.task_execution_id == str(task_execution_id)
            )
        )
        plan = result_query.scalar_one_or_none()
        
        if not plan:
            logger.warning(f"No plan found for task_execution_id={task_execution_id}")
            return None
        
        # Find the subtask
        result_query = await self.db.execute(
            select(SubtaskExecution).where(
                SubtaskExecution.plan_id == plan.id,
                SubtaskExecution.subtask_id == subtask_id
            )
        )
        subtask = result_query.scalar_one_or_none()
        
        if not subtask:
            logger.warning(f"Subtask not found: {subtask_id}")
            return None
        
        # Update subtask
        subtask.status = status
        subtask.completed_at = datetime.now(timezone.utc)
        subtask.result = result
        subtask.error = error
        
        # Calculate duration
        if subtask.started_at and subtask.completed_at:
            started = subtask.started_at
            completed = subtask.completed_at
            
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            if completed.tzinfo is None:
                completed = completed.replace(tzinfo=timezone.utc)
            
            subtask.duration_seconds = (completed - started).total_seconds()
        
        await self.db.commit()
        
        status_icon = "✅" if status == "completed" else "❌" if status == "failed" else "⏭️"
        logger.info(
            f"{status_icon} Recorded subtask completion: subtask_id={subtask_id}, "
            f"status={status}, duration={subtask.duration_seconds:.2f}s"
        )
        
        return UUID(subtask.id)
    
    async def record_plan_completed(
        self,
        task_execution_id: UUID
    ) -> Optional[UUID]:
        """
        Mark execution plan as completed.
        
        Args:
            task_execution_id: Task execution UUID
            
        Returns:
            Execution plan UUID or None if not found
        """
        result = await self.db.execute(
            select(ExecutionPlan).where(
                ExecutionPlan.task_execution_id == str(task_execution_id)
            )
        )
        plan = result.scalar_one_or_none()
        
        if not plan:
            logger.warning(f"No plan found for task_execution_id={task_execution_id}")
            return None
        
        plan.is_complete = True
        plan.completed_at = datetime.now(timezone.utc)
        
        await self.db.commit()
        
        logger.info(f"🏁 Recorded plan completion: plan_id={plan.plan_id}")
        
        return UUID(plan.id)
    
    async def get_plan_metrics(
        self,
        task_execution_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """
        Get planning metrics for a task.
        
        Args:
            task_execution_id: Task execution UUID
            
        Returns:
            Dictionary with plan metrics or None if no plan exists
        """
        result = await self.db.execute(
            select(ExecutionPlan).where(
                ExecutionPlan.task_execution_id == str(task_execution_id)
            )
        )
        plan = result.scalar_one_or_none()
        
        if not plan:
            return None
        
        # Get all subtasks
        result = await self.db.execute(
            select(SubtaskExecution)
            .where(SubtaskExecution.plan_id == plan.id)
            .order_by(SubtaskExecution.sequence_number)
        )
        subtasks = result.scalars().all()
        
        # Calculate statistics
        total_subtasks = len(subtasks)
        completed_subtasks = sum(1 for s in subtasks if s.status == 'completed')
        failed_subtasks = sum(1 for s in subtasks if s.status == 'failed')
        skipped_subtasks = sum(1 for s in subtasks if s.status == 'skipped')
        
        # Calculate total duration
        total_duration = sum(
            s.duration_seconds for s in subtasks
            if s.duration_seconds is not None
        )
        
        # Agent distribution
        agent_counts = {}
        for s in subtasks:
            agent_counts[s.agent] = agent_counts.get(s.agent, 0) + 1
        
        return {
            "plan_id": plan.plan_id,
            "original_task": plan.original_task,
            "created_at": plan.created_at.isoformat(),
            "completed_at": plan.completed_at.isoformat() if plan.completed_at else None,
            "is_complete": plan.is_complete,
            "total_subtasks": total_subtasks,
            "completed_subtasks": completed_subtasks,
            "failed_subtasks": failed_subtasks,
            "skipped_subtasks": skipped_subtasks,
            "success_rate": completed_subtasks / total_subtasks if total_subtasks > 0 else 0.0,
            "total_duration_seconds": total_duration,
            "agent_distribution": agent_counts,
            "subtasks": [
                {
                    "subtask_id": s.subtask_id,
                    "sequence": s.sequence_number,
                    "description": s.description,
                    "agent": s.agent,
                    "estimated_time": s.estimated_time,
                    "status": s.status,
                    "duration_seconds": s.duration_seconds,
                    "error": s.error
                }
                for s in subtasks
            ]
        }
    
    async def get_experiment_summary(self, experiment_id: UUID) -> Dict[str, Any]:
        """
        Get summary statistics for an experiment.
        
        Args:
            experiment_id: Experiment UUID
            
        Returns:
            Dictionary with experiment summary statistics
        """
        result = await self.db.execute(
            select(Experiment).where(Experiment.id == str(experiment_id))
        )
        experiment = result.scalar_one_or_none()
        
        if not experiment:
            raise ValueError(f"Experiment not found: {experiment_id}")
        
        # Get task executions with LLM calls eagerly loaded (fixes N+1 query problem)
        result = await self.db.execute(
            select(TaskExecution)
            .where(TaskExecution.experiment_id == str(experiment_id))
            .options(selectinload(TaskExecution.llm_calls))
        )
        tasks = result.scalars().all()
        
        total_tasks = len(tasks)
        successful_tasks = sum(1 for t in tasks if t.success is True)
        failed_tasks = sum(1 for t in tasks if t.success is False)
        
        # Calculate total tokens from eagerly loaded LLM calls
        total_input_tokens = 0
        total_output_tokens = 0
        
        for task in tasks:
            # Access the pre-loaded llm_calls relationship
            total_input_tokens += sum(call.input_tokens for call in task.llm_calls)
            total_output_tokens += sum(call.output_tokens for call in task.llm_calls)
        
        # Calculate cost (example pricing for GPT-4)
        cost = (total_input_tokens * 0.003 + total_output_tokens * 0.015) / 1000
        
        return {
            "experiment_id": str(experiment_id),
            "mode": experiment.mode,
            "started_at": experiment.started_at.isoformat(),
            "completed_at": experiment.completed_at.isoformat() if experiment.completed_at else None,
            "total_tasks": total_tasks,
            "successful_tasks": successful_tasks,
            "failed_tasks": failed_tasks,
            "success_rate": successful_tasks / total_tasks if total_tasks > 0 else 0.0,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "estimated_cost_usd": round(cost, 4)
        }
