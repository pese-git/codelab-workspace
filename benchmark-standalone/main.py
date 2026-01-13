#!/usr/bin/env python3
"""
Benchmark Standalone - независимое приложение для тестирования AI-агентов.

Общается с backend через Gateway WebSocket API.

Usage:
    python main.py --task-id task_001
    python main.py --task-range 1-5
    python main.py --category simple
    python main.py --mode multi-agent --limit 10
"""
import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List
from uuid import UUID

import yaml

from src import (
    GatewayClient,
    MetricsCollector,
    MockToolExecutor,
    ReportGenerator,
    TaskValidator,
    close_db,
    get_db,
    init_database,
    init_db,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("benchmark")


class BenchmarkRunner:
    """
    Главный класс для запуска benchmark экспериментов.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize benchmark runner.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.tasks: List[Dict[str, Any]] = []
        
        # Initialize components
        self.client = GatewayClient(
            base_url=config['gateway']['base_url'],
            ws_url=config['gateway']['ws_url'],
            api_key=config['gateway']['api_key'],
            timeout=config['gateway']['timeout'],
            reconnect_attempts=config['gateway']['reconnect_attempts'],
            reconnect_delay=config['gateway']['reconnect_delay']
        )
        
        project_path = Path(config['benchmark']['test_project'])
        self.executor = MockToolExecutor(project_path)
        
        self.validator = None
        if config['benchmark']['enable_validation']:
            if project_path.exists():
                self.validator = TaskValidator(project_path)
            else:
                logger.warning(f"Test project not found: {project_path}, validation disabled")
    
    def load_tasks(self, tasks_file: Path) -> None:
        """Load tasks from YAML file."""
        logger.info(f"Loading tasks from {tasks_file}")
        
        if not tasks_file.exists():
            raise FileNotFoundError(f"Tasks file not found: {tasks_file}")
        
        with open(tasks_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        self.tasks = data.get('tasks', [])
        logger.info(f"Loaded {len(self.tasks)} tasks")
    
    def filter_tasks(self, args: argparse.Namespace) -> None:
        """Filter tasks based on command line arguments."""
        original_count = len(self.tasks)
        
        if args.task_id:
            self.tasks = [t for t in self.tasks if t['id'] == args.task_id]
            if not self.tasks:
                raise ValueError(f"Task not found: {args.task_id}")
            logger.info(f"Running single task: {args.task_id}")
        
        elif args.task_ids:
            task_ids = [tid.strip() for tid in args.task_ids.split(',')]
            self.tasks = [t for t in self.tasks if t['id'] in task_ids]
            if not self.tasks:
                raise ValueError(f"No tasks found matching: {task_ids}")
            logger.info(f"Running {len(self.tasks)} specific tasks")
        
        elif args.task_range:
            import re
            start_str, end_str = args.task_range.split('-', 1)
            start_match = re.search(r'(\d+)', start_str)
            end_match = re.search(r'(\d+)', end_str)
            
            if start_match and end_match:
                start_num = int(start_match.group(1))
                end_num = int(end_match.group(1))
                
                self.tasks = [
                    t for t in self.tasks
                    if start_num <= int(re.search(r'(\d+)', t['id']).group(1)) <= end_num
                ]
                logger.info(f"Running tasks {start_num}-{end_num} ({len(self.tasks)} tasks)")
        
        elif args.category:
            self.tasks = [t for t in self.tasks if t['category'] == args.category]
            logger.info(f"Running {len(self.tasks)} tasks with category: {args.category}")
        
        elif args.type:
            self.tasks = [t for t in self.tasks if t['type'] == args.type]
            logger.info(f"Running {len(self.tasks)} tasks with type: {args.type}")
        
        if args.limit and len(self.tasks) > args.limit:
            self.tasks = self.tasks[:args.limit]
            logger.info(f"Limited to {args.limit} tasks")
        
        if not self.tasks:
            raise ValueError("No tasks to run after filtering")
        
        if len(self.tasks) != original_count:
            logger.info(f"Filtered: {len(self.tasks)}/{original_count} tasks will be executed")
    
    async def run_experiment(self, mode: str) -> UUID:
        """
        Run experiment in specified mode.
        
        Args:
            mode: Execution mode ('single-agent' or 'multi-agent')
            
        Returns:
            Experiment UUID
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"🚀 Starting experiment in {mode} mode")
        logger.info(f"📦 Tasks to execute: {len(self.tasks)}")
        logger.info(f"{'='*60}\n")
        
        # Test connection
        logger.info("🔌 Testing Gateway connection...")
        if not await self.client.test_connection():
            raise ConnectionError("❌ Failed to connect to Gateway. Is it running?")
        logger.info("✅ Gateway connection OK\n")
        
        async for db in get_db():
            collector = MetricsCollector(db)
            
            # Start experiment
            config = {
                "mode": mode,
                "tasks_file": self.config['benchmark']['tasks_file'],
                "total_tasks": len(self.tasks),
                "gateway_url": self.config['gateway']['ws_url'],
                "started_at": time.time()
            }
            
            experiment_id = await collector.start_experiment(mode=mode, config=config)
            logger.info(f"Started experiment: {experiment_id}")
            
            # Run each task
            successful_tasks = 0
            failed_tasks = 0
            
            for i, task in enumerate(self.tasks, 1):
                logger.info(f"\n{'='*60}")
                logger.info(f"📊 Progress: [{i}/{len(self.tasks)}] ({i/len(self.tasks)*100:.0f}%)")
                logger.info(f"📝 Task: {task['id']} - {task['title']}")
                logger.info(f"🏷️  Category: {task['category']}, Type: {task['type']}")
                logger.info(f"{'='*60}\n")
                
                try:
                    # Start task
                    task_execution_id = await collector.start_task(
                        experiment_id=experiment_id,
                        task_id=task['id'],
                        task_category=task['category'],
                        task_type=task['type'],
                        mode=mode
                    )
                    
                    # Execute task via Gateway
                    start_time = time.time()
                    success = await self.client.execute_task(
                        task=task,
                        tool_executor=self.executor,
                        validator=self.validator,
                        collector=collector,
                        task_execution_id=task_execution_id
                    )
                    duration = time.time() - start_time
                    
                    # Complete task
                    await collector.complete_task(
                        task_execution_id=task_execution_id,
                        success=success,
                        metrics={"duration_seconds": duration}
                    )
                    
                    if success:
                        successful_tasks += 1
                        logger.info(f"\n✅ Task {task['id']} УСПЕШНО завершена ({duration:.2f}s)")
                    else:
                        failed_tasks += 1
                        logger.warning(f"\n❌ Task {task['id']} ПРОВАЛЕНА ({duration:.2f}s)")
                
                except Exception as e:
                    failed_tasks += 1
                    logger.error(f"\n❌ Task {task['id']} ОШИБКА: {e}")
            
            # Complete experiment
            await collector.complete_experiment(experiment_id)
            
            success_rate = successful_tasks/len(self.tasks) if self.tasks else 0
            rate_icon = "🎉" if success_rate >= 0.8 else "✅" if success_rate >= 0.5 else "⚠️"
            
            logger.info(f"\n{'='*60}")
            logger.info(f"🏁 Experiment {mode} completed")
            logger.info(f"{'='*60}")
            logger.info(f"📊 Total tasks: {len(self.tasks)}")
            logger.info(f"✅ Successful: {successful_tasks}")
            logger.info(f"❌ Failed: {failed_tasks}")
            logger.info(f"{rate_icon} Success rate: {success_rate:.2%}")
            logger.info(f"{'='*60}\n")
            
            return experiment_id


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Benchmark Standalone - тестирование AI-агентов через Gateway WebSocket"
    )
    parser.add_argument(
        "--mode",
        choices=["single-agent", "multi-agent", "both"],
        default="multi-agent",
        help="Execution mode (default: multi-agent)"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.yaml"),
        help="Path to config file (default: config.yaml)"
    )
    parser.add_argument(
        "--task-id",
        type=str,
        help="Run specific task by ID (e.g., task_001)"
    )
    parser.add_argument(
        "--task-ids",
        type=str,
        help="Run specific tasks by IDs, comma-separated (e.g., task_001,task_005)"
    )
    parser.add_argument(
        "--task-range",
        type=str,
        help="Run tasks in range (e.g., 1-10)"
    )
    parser.add_argument(
        "--category",
        choices=["simple", "medium", "complex", "specialized"],
        help="Run only tasks of specific category"
    )
    parser.add_argument(
        "--type",
        choices=["coding", "architecture", "debug", "question", "mixed"],
        help="Run only tasks of specific type"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of tasks to run"
    )
    parser.add_argument(
        "--generate-report",
        action="store_true",
        help="Generate report after experiment"
    )
    
    args = parser.parse_args()
    
    # Load configuration
    if not args.config.exists():
        logger.error(f"Config file not found: {args.config}")
        sys.exit(1)
    
    with open(args.config, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # Initialize database
    db_url = config['database']['url']
    logger.info(f"Initializing database: {db_url}")
    init_database(db_url, echo=config['database'].get('echo', False))
    await init_db()
    logger.info("✓ Database initialized")
    
    try:
        # Initialize runner
        runner = BenchmarkRunner(config)
        
        # Load and filter tasks
        tasks_file = Path(config['benchmark']['tasks_file'])
        runner.load_tasks(tasks_file)
        runner.filter_tasks(args)
        
        # Run experiment(s)
        modes_to_run = ["single-agent", "multi-agent"] if args.mode == "both" else [args.mode]
        experiment_ids = []
        
        for mode in modes_to_run:
            experiment_id = await runner.run_experiment(mode)
            experiment_ids.append(experiment_id)
        
        # Generate report if requested
        if args.generate_report and experiment_ids:
            logger.info("\nGenerating report...")
            
            async for db in get_db():
                reporter = ReportGenerator(db)
                
                # Use the last experiment_id (or latest if multiple modes)
                if len(experiment_ids) == 1:
                    report = await reporter.generate_report(experiment_id=experiment_ids[0])
                else:
                    # For both modes, use latest to get both experiments
                    report = await reporter.generate_report(latest=True)
                
                # Save report
                output_dir = Path(config['reporting']['output_dir'])
                output_dir.mkdir(parents=True, exist_ok=True)
                
                output_file = output_dir / f"report_{int(time.time())}.md"
                output_file.write_text(report, encoding='utf-8')
                
                logger.info(f"✓ Report saved: {output_file}")
                
                # Print report
                print("\n" + report)
        
        logger.info("\n✓ Benchmark completed successfully")
    
    except Exception as e:
        logger.error(f"✗ Benchmark failed: {e}", exc_info=True)
        sys.exit(1)
    
    finally:
        await close_db()
        logger.info("Database connections closed")


if __name__ == "__main__":
    asyncio.run(main())
