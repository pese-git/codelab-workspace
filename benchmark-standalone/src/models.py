"""
SQLAlchemy models for benchmark metrics collection.

Адаптировано из codelab-ai-service/agent-runtime/app/models/metrics.py
для использования в независимом приложении.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class Experiment(Base):
    """
    Top-level experiment tracking.
    
    Represents a complete experiment run (single-agent or multi-agent mode).
    """
    __tablename__ = "poc_experiments"
    
    # Primary key
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Experiment UUID"
    )
    
    mode: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Experiment mode: 'single-agent' or 'multi-agent'"
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
        comment="Experiment start timestamp"
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Experiment completion timestamp"
    )
    config: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Experiment configuration"
    )
    
    # Relationships
    task_executions = relationship(
        "TaskExecution",
        back_populates="experiment",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    
    __table_args__ = (
        Index('idx_poc_experiments_mode_started', 'mode', 'started_at'),
    )
    
    def __repr__(self) -> str:
        return f"<Experiment(id='{self.id}', mode='{self.mode}')>"


class TaskExecution(Base):
    """
    Individual task execution tracking.
    
    Tracks execution of a single benchmark task within an experiment.
    """
    __tablename__ = "poc_task_executions"
    
    # Primary key
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Task execution UUID"
    )
    
    experiment_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("poc_experiments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to parent experiment"
    )
    task_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Task identifier from benchmark (e.g., 'task_001')"
    )
    task_category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Task category: 'simple', 'medium', 'complex', 'specialized'"
    )
    task_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Task type: 'coding', 'architecture', 'debug', 'question', 'mixed'"
    )
    mode: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Execution mode: 'single-agent' or 'multi-agent'"
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
        comment="Task start timestamp"
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Task completion timestamp"
    )
    success: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
        index=True,
        comment="Whether task completed successfully"
    )
    failure_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for failure if task failed"
    )
    metrics: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Additional metrics (duration, iterations, etc.)"
    )
    
    # Relationships
    experiment = relationship("Experiment", back_populates="task_executions")
    llm_calls = relationship(
        "LLMCall",
        back_populates="task_execution",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    tool_calls = relationship(
        "ToolCall",
        back_populates="task_execution",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    agent_switches = relationship(
        "AgentSwitch",
        back_populates="task_execution",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    quality_evaluations = relationship(
        "QualityEvaluation",
        back_populates="task_execution",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    hallucinations = relationship(
        "Hallucination",
        back_populates="task_execution",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    execution_plan = relationship(
        "ExecutionPlan",
        back_populates="task_execution",
        uselist=False,
        cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        Index('idx_poc_task_exec_experiment_task', 'experiment_id', 'task_id'),
        Index('idx_poc_task_exec_category_type', 'task_category', 'task_type'),
        Index('idx_poc_task_exec_success', 'success'),
    )
    
    def __repr__(self) -> str:
        return f"<TaskExecution(id='{self.id}', task_id='{self.task_id}', success={self.success})>"


class LLMCall(Base):
    """LLM API call tracking."""
    __tablename__ = "poc_llm_calls"
    
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    task_execution_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("poc_task_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    task_execution = relationship("TaskExecution", back_populates="llm_calls")
    
    __table_args__ = (
        Index('idx_poc_llm_calls_task_agent', 'task_execution_id', 'agent_type'),
    )


class ToolCall(Base):
    """Tool invocation tracking."""
    __tablename__ = "poc_tool_calls"
    
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    task_execution_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("poc_task_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    task_execution = relationship("TaskExecution", back_populates="tool_calls")
    
    __table_args__ = (
        Index('idx_poc_tool_calls_task_tool', 'task_execution_id', 'tool_name'),
    )


class AgentSwitch(Base):
    """Agent switching event tracking (multi-agent only)."""
    __tablename__ = "poc_agent_switches"
    
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    task_execution_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("poc_task_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    from_agent: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    to_agent: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )
    
    task_execution = relationship("TaskExecution", back_populates="agent_switches")
    
    __table_args__ = (
        Index('idx_poc_agent_switches_agents', 'from_agent', 'to_agent'),
    )


class QualityEvaluation(Base):
    """Quality evaluation results."""
    __tablename__ = "poc_quality_evaluations"
    
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    task_execution_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("poc_task_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    evaluation_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    
    task_execution = relationship("TaskExecution", back_populates="quality_evaluations")


class Hallucination(Base):
    """Detected hallucination tracking."""
    __tablename__ = "poc_hallucinations"
    
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    task_execution_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("poc_task_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    hallucination_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )
    
    task_execution = relationship("TaskExecution", back_populates="hallucinations")


class ExecutionPlan(Base):
    """
    Execution plan tracking for complex tasks.
    
    Tracks plans created by Orchestrator agent for breaking down complex tasks.
    """
    __tablename__ = "poc_execution_plans"
    
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Execution plan UUID"
    )
    task_execution_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("poc_task_executions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Reference to parent task execution"
    )
    plan_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Plan identifier from agent-runtime"
    )
    original_task: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Original user task that triggered planning"
    )
    subtask_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total number of subtasks in plan"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
        comment="Plan creation timestamp"
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Plan completion timestamp"
    )
    is_complete: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether all subtasks are complete"
    )
    plan_metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Additional plan metadata"
    )
    
    # Relationships
    task_execution = relationship("TaskExecution", back_populates="execution_plan")
    subtasks = relationship(
        "SubtaskExecution",
        back_populates="plan",
        cascade="all, delete-orphan",
        lazy="dynamic",
        order_by="SubtaskExecution.sequence_number"
    )
    
    __table_args__ = (
        Index('idx_poc_plans_task_plan', 'task_execution_id', 'plan_id'),
        Index('idx_poc_plans_complete', 'is_complete'),
    )
    
    def __repr__(self) -> str:
        return f"<ExecutionPlan(id='{self.id}', plan_id='{self.plan_id}', subtasks={self.subtask_count})>"


class SubtaskExecution(Base):
    """
    Individual subtask execution tracking within a plan.
    
    Tracks execution of each subtask in an execution plan.
    """
    __tablename__ = "poc_subtask_executions"
    
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Subtask execution UUID"
    )
    plan_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("poc_execution_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to parent execution plan"
    )
    subtask_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Subtask identifier from agent-runtime"
    )
    sequence_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        comment="Order of subtask in plan (0-indexed)"
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Description of what needs to be done"
    )
    agent: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Agent type assigned to this subtask"
    )
    estimated_time: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Estimated time to complete (e.g., '2 min', '5 min')"
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
        comment="Current status: pending, in_progress, completed, failed, skipped"
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Subtask start timestamp"
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Subtask completion timestamp"
    )
    duration_seconds: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Actual execution duration in seconds"
    )
    result: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Result or output after completion"
    )
    error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if subtask failed"
    )
    dependencies: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="List of subtask IDs that must complete before this one"
    )
    
    # Relationships
    plan = relationship("ExecutionPlan", back_populates="subtasks")
    
    __table_args__ = (
        Index('idx_poc_subtasks_plan_seq', 'plan_id', 'sequence_number'),
        Index('idx_poc_subtasks_status', 'status'),
        Index('idx_poc_subtasks_agent', 'agent'),
    )
    
    def __repr__(self) -> str:
        return f"<SubtaskExecution(id='{self.id}', subtask_id='{self.subtask_id}', status='{self.status}')>"
