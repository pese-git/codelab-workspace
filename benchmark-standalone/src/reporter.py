"""
Report Generator - генерация детальных отчетов по метрикам.

Адаптировано из codelab-ai-service/benchmark/scripts/generate_metrics_report.py
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    AgentSwitch,
    Experiment,
    Hallucination,
    LLMCall,
    TaskExecution,
    ToolCall,
)

logger = logging.getLogger("benchmark.reporter")


class ReportGenerator:
    """Генератор отчетов по метрикам benchmark экспериментов."""
    
    def __init__(self, db: AsyncSession):
        """
        Initialize report generator.
        
        Args:
            db: Database session
        """
        self.db = db
    
    async def get_latest_experiments(self, limit: int = 10) -> List[Experiment]:
        """Get latest experiments."""
        result = await self.db.execute(
            select(Experiment)
            .order_by(Experiment.started_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def get_experiment_by_id(self, experiment_id: UUID) -> Optional[Experiment]:
        """Get experiment by ID."""
        result = await self.db.execute(
            select(Experiment).where(Experiment.id == str(experiment_id))
        )
        return result.scalar_one_or_none()
    
    async def calculate_experiment_stats(self, experiment: Experiment) -> Dict[str, Any]:
        """
        Calculate detailed statistics for an experiment.
        
        Args:
            experiment: Experiment object
            
        Returns:
            Dictionary with statistics
        """
        # Get task executions
        result = await self.db.execute(
            select(TaskExecution)
            .where(TaskExecution.experiment_id == experiment.id)
            .order_by(TaskExecution.started_at)
        )
        tasks = list(result.scalars().all())
        
        # Helper function to get duration
        def get_duration(task: TaskExecution) -> float:
            if task.metrics and isinstance(task.metrics, dict):
                return task.metrics.get('duration_seconds', 0) or 0
            return 0
        
        stats = {
            "experiment_id": str(experiment.id),
            "mode": experiment.mode,
            "started_at": experiment.started_at.isoformat(),
            "completed_at": experiment.completed_at.isoformat() if experiment.completed_at else None,
            "total_tasks": len(tasks),
            "successful_tasks": sum(1 for t in tasks if t.success),
            "failed_tasks": sum(1 for t in tasks if not t.success),
            "success_rate": sum(1 for t in tasks if t.success) / len(tasks) if tasks else 0,
            "total_duration": sum(get_duration(t) for t in tasks),
            "avg_task_duration": sum(get_duration(t) for t in tasks) / len(tasks) if tasks else 0,
            "total_llm_calls": 0,
            "total_tool_calls": 0,
            "total_agent_switches": 0,
            "total_hallucinations": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "estimated_cost_usd": 0,
            "tasks_by_category": {},
            "tasks_by_type": {},
        }
        
        # Collect detailed metrics
        for task in tasks:
            # Count by category and type
            category = task.task_category
            task_type = task.task_type
            
            if category not in stats["tasks_by_category"]:
                stats["tasks_by_category"][category] = {"total": 0, "successful": 0}
            stats["tasks_by_category"][category]["total"] += 1
            if task.success:
                stats["tasks_by_category"][category]["successful"] += 1
            
            if task_type not in stats["tasks_by_type"]:
                stats["tasks_by_type"][task_type] = {"total": 0, "successful": 0}
            stats["tasks_by_type"][task_type]["total"] += 1
            if task.success:
                stats["tasks_by_type"][task_type]["successful"] += 1
            
            # LLM calls
            result = await self.db.execute(
                select(LLMCall).where(LLMCall.task_execution_id == task.id)
            )
            llm_calls = list(result.scalars().all())
            stats["total_llm_calls"] += len(llm_calls)
            stats["total_input_tokens"] += sum(c.input_tokens for c in llm_calls)
            stats["total_output_tokens"] += sum(c.output_tokens for c in llm_calls)
            
            # Tool calls
            result = await self.db.execute(
                select(ToolCall).where(ToolCall.task_execution_id == task.id)
            )
            tool_calls = list(result.scalars().all())
            stats["total_tool_calls"] += len(tool_calls)
            
            # Agent switches
            result = await self.db.execute(
                select(AgentSwitch).where(AgentSwitch.task_execution_id == task.id)
            )
            agent_switches = list(result.scalars().all())
            stats["total_agent_switches"] += len(agent_switches)
            
            # Hallucinations
            result = await self.db.execute(
                select(Hallucination).where(Hallucination.task_execution_id == task.id)
            )
            hallucinations = list(result.scalars().all())
            stats["total_hallucinations"] += len(hallucinations)
        
        # Calculate cost (GPT-4 pricing)
        input_cost_per_1k = 0.03
        output_cost_per_1k = 0.06
        
        stats["estimated_cost_usd"] = (
            (stats["total_input_tokens"] / 1000) * input_cost_per_1k +
            (stats["total_output_tokens"] / 1000) * output_cost_per_1k
        )
        
        return stats
    
    def generate_markdown_report(
        self,
        single_agent_stats: Optional[Dict[str, Any]],
        multi_agent_stats: Optional[Dict[str, Any]]
    ) -> str:
        """
        Generate Markdown report from statistics.
        
        Args:
            single_agent_stats: Statistics for single-agent mode
            multi_agent_stats: Statistics for multi-agent mode
            
        Returns:
            Markdown formatted report
        """
        report = []
        
        # Header
        report.append("# Benchmark Report: Single-Agent vs Multi-Agent")
        report.append("")
        report.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        report.append("---")
        report.append("")
        
        # Executive Summary
        if single_agent_stats and multi_agent_stats:
            report.append("## Executive Summary")
            report.append("")
            
            sa_success = single_agent_stats["success_rate"]
            ma_success = multi_agent_stats["success_rate"]
            winner = "Multi-Agent" if ma_success > sa_success else "Single-Agent"
            diff = abs(ma_success - sa_success) * 100
            
            report.append(f"- **Success Rate Winner:** {winner} (+{diff:.1f}%)")
            
            sa_cost = single_agent_stats["estimated_cost_usd"]
            ma_cost = multi_agent_stats["estimated_cost_usd"]
            cost_winner = "Single-Agent" if sa_cost < ma_cost else "Multi-Agent"
            
            report.append(f"- **Cost Efficiency Winner:** {cost_winner}")
            report.append("")
        
        # Single-Agent Results
        if single_agent_stats:
            report.extend(self._format_mode_results("Single-Agent", single_agent_stats))
        
        # Multi-Agent Results
        if multi_agent_stats:
            report.extend(self._format_mode_results("Multi-Agent", multi_agent_stats))
        
        # Comparison
        if single_agent_stats and multi_agent_stats:
            report.extend(self._format_comparison(single_agent_stats, multi_agent_stats))
        
        report.append("---")
        report.append("")
        report.append("*Report generated by benchmark-standalone*")
        
        return "\n".join(report)
    
    def _format_mode_results(self, mode_name: str, stats: Dict[str, Any]) -> List[str]:
        """Format results for a single mode."""
        lines = []
        
        lines.append(f"## {mode_name} Mode Results")
        lines.append("")
        lines.append(f"**Experiment ID:** `{stats['experiment_id']}`")
        lines.append(f"**Started:** {stats['started_at']}")
        lines.append(f"**Completed:** {stats['completed_at']}")
        lines.append("")
        
        lines.append("### Overall Metrics")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Total Tasks | {stats['total_tasks']} |")
        lines.append(f"| Successful Tasks | {stats['successful_tasks']} |")
        lines.append(f"| Failed Tasks | {stats['failed_tasks']} |")
        lines.append(f"| Success Rate | {stats['success_rate']:.2%} |")
        lines.append(f"| Total Duration | {stats['total_duration']:.2f}s |")
        lines.append(f"| Avg Task Duration | {stats['avg_task_duration']:.2f}s |")
        lines.append(f"| Total LLM Calls | {stats['total_llm_calls']} |")
        lines.append(f"| Total Tool Calls | {stats['total_tool_calls']} |")
        
        if mode_name == "Multi-Agent":
            lines.append(f"| Total Agent Switches | {stats['total_agent_switches']} |")
        
        lines.append(f"| Total Hallucinations | {stats['total_hallucinations']} |")
        lines.append("")
        
        lines.append("### Token Usage")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Input Tokens | {stats['total_input_tokens']:,} |")
        lines.append(f"| Output Tokens | {stats['total_output_tokens']:,} |")
        total_tokens = stats['total_input_tokens'] + stats['total_output_tokens']
        lines.append(f"| Total Tokens | {total_tokens:,} |")
        lines.append(f"| Estimated Cost | ${stats['estimated_cost_usd']:.4f} |")
        lines.append("")
        
        return lines
    
    def _format_comparison(
        self,
        single_agent_stats: Dict[str, Any],
        multi_agent_stats: Dict[str, Any]
    ) -> List[str]:
        """Format comparison section."""
        lines = []
        
        lines.append("## Detailed Comparison")
        lines.append("")
        
        lines.append("### Success Metrics")
        lines.append("")
        lines.append("| Metric | Single-Agent | Multi-Agent | Difference |")
        lines.append("|--------|--------------|-------------|------------|")
        
        sa_success = single_agent_stats["success_rate"]
        ma_success = multi_agent_stats["success_rate"]
        diff = (ma_success - sa_success) * 100
        lines.append(f"| Success Rate | {sa_success:.2%} | {ma_success:.2%} | {diff:+.1f}% |")
        
        sa_tasks = single_agent_stats["successful_tasks"]
        ma_tasks = multi_agent_stats["successful_tasks"]
        diff_tasks = ma_tasks - sa_tasks
        lines.append(f"| Successful Tasks | {sa_tasks} | {ma_tasks} | {diff_tasks:+d} |")
        lines.append("")
        
        lines.append("### Cost Metrics")
        lines.append("")
        lines.append("| Metric | Single-Agent | Multi-Agent | Difference |")
        lines.append("|--------|--------------|-------------|------------|")
        
        sa_tokens = single_agent_stats["total_input_tokens"] + single_agent_stats["total_output_tokens"]
        ma_tokens = multi_agent_stats["total_input_tokens"] + multi_agent_stats["total_output_tokens"]
        diff_tokens = ma_tokens - sa_tokens
        lines.append(f"| Total Tokens | {sa_tokens:,} | {ma_tokens:,} | {diff_tokens:+,} |")
        
        sa_cost = single_agent_stats["estimated_cost_usd"]
        ma_cost = multi_agent_stats["estimated_cost_usd"]
        diff_cost = ma_cost - sa_cost
        lines.append(f"| Estimated Cost | ${sa_cost:.4f} | ${ma_cost:.4f} | ${diff_cost:+.4f} |")
        lines.append("")
        
        return lines
    
    async def generate_report(
        self,
        experiment_id: Optional[UUID] = None,
        latest: bool = False
    ) -> str:
        """
        Generate metrics report.
        
        Args:
            experiment_id: Specific experiment ID to report on
            latest: Use latest experiments (one for each mode)
            
        Returns:
            Markdown formatted report
        """
        single_agent_stats = None
        multi_agent_stats = None
        
        if experiment_id:
            experiment = await self.get_experiment_by_id(experiment_id)
            if not experiment:
                raise ValueError(f"Experiment not found: {experiment_id}")
            
            stats = await self.calculate_experiment_stats(experiment)
            
            if experiment.mode == "single-agent":
                single_agent_stats = stats
            else:
                multi_agent_stats = stats
        
        elif latest:
            experiments = await self.get_latest_experiments(limit=10)
            
            for exp in experiments:
                if exp.mode == "single-agent" and not single_agent_stats:
                    single_agent_stats = await self.calculate_experiment_stats(exp)
                elif exp.mode == "multi-agent" and not multi_agent_stats:
                    multi_agent_stats = await self.calculate_experiment_stats(exp)
                
                if single_agent_stats and multi_agent_stats:
                    break
        
        else:
            raise ValueError("Must specify either experiment_id or latest=True")
        
        return self.generate_markdown_report(single_agent_stats, multi_agent_stats)
