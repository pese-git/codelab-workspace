#!/usr/bin/env python3
"""
Report Generator Script - генерация отчетов из существующих метрик.

Usage:
    python generate_report.py --latest
    python generate_report.py --experiment-id <uuid>
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path
from uuid import UUID

import yaml

from src import (
    ReportGenerator,
    close_db,
    get_db,
    init_database,
    init_db,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("report_generator")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate benchmark report from metrics database"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.yaml"),
        help="Path to config file (default: config.yaml)"
    )
    parser.add_argument(
        "--experiment-id",
        type=str,
        help="Specific experiment ID to report on"
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Use latest experiments (one for each mode)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file path (default: reports/report_<timestamp>.md)"
    )
    
    args = parser.parse_args()
    
    if not args.experiment_id and not args.latest:
        parser.error("Must specify either --experiment-id or --latest")
    
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
        async for db in get_db():
            reporter = ReportGenerator(db)
            
            # Generate report
            experiment_id = UUID(args.experiment_id) if args.experiment_id else None
            report = await reporter.generate_report(
                experiment_id=experiment_id,
                latest=args.latest
            )
            
            # Determine output path
            if args.output:
                output_path = args.output
            else:
                output_dir = Path(config['reporting']['output_dir'])
                output_dir.mkdir(parents=True, exist_ok=True)
                import time
                output_path = output_dir / f"report_{int(time.time())}.md"
            
            # Save report
            output_path.write_text(report, encoding='utf-8')
            logger.info(f"✓ Report saved: {output_path}")
            
            # Print report
            print("\n" + report)
    
    except Exception as e:
        logger.error(f"✗ Failed to generate report: {e}", exc_info=True)
        sys.exit(1)
    
    finally:
        await close_db()
        logger.info("Database connections closed")


if __name__ == "__main__":
    asyncio.run(main())
