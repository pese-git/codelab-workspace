"""
Metrics Collector - сбор и хранение метрик benchmark экспериментов.

Адаптировано из codelab-ai-service/agent-runtime/app/services/metrics_collector.py
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import (
    AgentSwitch,
    Experiment,
    Hallucination,
    LLMCall,
    QualityEvaluation,
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
