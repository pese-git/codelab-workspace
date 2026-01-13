#!/usr/bin/env python3
"""
Test Connection Script - проверка подключения к Gateway.

Usage:
    python test_connection.py
    python test_connection.py --ws-url ws://localhost:8000/ws
"""
import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

import httpx
import websockets
import yaml

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_connection")


async def test_gateway_connection(base_url: str, ws_url: str, gateway_config: dict) -> bool:
    """
    Test connection to Gateway WebSocket.
    
    Args:
        base_url: Gateway base URL
        ws_url: Gateway WebSocket URL base
        gateway_config: Gateway configuration dict
        
    Returns:
        True if connection successful
    """
    logger.info(f"Testing connection to Gateway: {base_url}")
    
    try:
        from src.auth import AuthManager
        
        # Initialize auth manager
        auth_manager = AuthManager(gateway_config)
        headers = await auth_manager.get_headers()
        
        # Test HTTP endpoint
        async with httpx.AsyncClient() as client:
            # Try /api/v1/health first (nginx), fallback to /health (direct)
            try:
                response = await client.get(f"{base_url}/api/v1/health")
                response.raise_for_status()
                logger.info(f"✓ Gateway HTTP accessible: {base_url}/api/v1/health")
            except httpx.HTTPError:
                response = await client.get(f"{base_url}/health")
                response.raise_for_status()
                logger.info(f"✓ Gateway HTTP accessible: {base_url}/health")
            
            # Create session
            response = await client.post(
                f"{base_url}/api/v1/sessions",
                headers=headers
            )
            response.raise_for_status()
            session_id = response.json()['session_id']
            logger.info(f"✓ Created session: {session_id}")
        
        # Test WebSocket
        ws_endpoint = f"{ws_url}/{session_id}"
        async with websockets.connect(ws_endpoint) as websocket:
            logger.info(f"✓ Successfully connected to WebSocket: {ws_endpoint}")
            
            # Send test message
            await websocket.send(json.dumps({
                "type": "user_message",
                "content": "Hello, this is a connection test",
                "role": "user"
            }))
            logger.info("✓ Sent test message")
            
            # Wait for response (with timeout)
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                msg = json.loads(response)
                logger.info(f"✓ Received response: type={msg.get('type')}")
                return True
            except asyncio.TimeoutError:
                logger.warning("⚠ Timeout waiting for response (but connection works)")
                return True
            
    except httpx.HTTPError as e:
        logger.error(f"✗ HTTP error: {e}")
        return False
    except websockets.exceptions.WebSocketException as e:
        logger.error(f"✗ WebSocket error: {e}")
        return False
    except Exception as e:
        logger.error(f"✗ Unexpected error: {e}", exc_info=True)
        return False


async def test_database(db_url: str) -> bool:
    """
    Test database connection.
    
    Args:
        db_url: Database URL
        
    Returns:
        True if database accessible
    """
    logger.info(f"Testing database: {db_url}")
    
    try:
        from src.database import close_db, get_db, init_database, init_db
        
        # Initialize database
        init_database(db_url, echo=False)
        await init_db()
        logger.info("✓ Database initialized")
        
        # Test session
        async for _db in get_db():
            logger.info("✓ Database session created")
            break
        
        # Close
        await close_db()
        logger.info("✓ Database connections closed")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Database error: {e}", exc_info=True)
        return False


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test connection to Gateway and database"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.yaml"),
        help="Path to config file (default: config.yaml)"
    )
    parser.add_argument(
        "--ws-url",
        type=str,
        help="Gateway WebSocket URL (overrides config)"
    )
    parser.add_argument(
        "--db-url",
        type=str,
        help="Database URL (overrides config)"
    )
    
    args = parser.parse_args()
    
    # Load configuration
    config = {}
    if args.config.exists():
        with open(args.config, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        logger.info(f"Loaded config from {args.config}")
    else:
        logger.warning(f"Config file not found: {args.config}, using defaults")
    
    # Get URLs
    base_url = config.get('gateway', {}).get('base_url', 'http://localhost:8000')
    ws_url = args.ws_url or config.get('gateway', {}).get('ws_url', 'ws://localhost:8000/ws')
    db_url = args.db_url or config.get('database', {}).get('url', 'sqlite:///data/metrics.db')
    gateway_config = config.get('gateway', {})
    
    logger.info("\n" + "="*60)
    logger.info("BENCHMARK STANDALONE - CONNECTION TEST")
    logger.info("="*60 + "\n")
    
    # Test Gateway connection
    logger.info("Test 1: Gateway WebSocket Connection")
    logger.info("-" * 60)
    gateway_ok = await test_gateway_connection(base_url, ws_url, gateway_config)
    
    logger.info("\n" + "-" * 60 + "\n")
    
    # Test database
    logger.info("Test 2: Database Connection")
    logger.info("-" * 60)
    db_ok = await test_database(db_url)
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("TEST SUMMARY")
    logger.info("="*60)
    logger.info(f"Gateway WebSocket: {'✓ PASS' if gateway_ok else '✗ FAIL'}")
    logger.info(f"Database: {'✓ PASS' if db_ok else '✗ FAIL'}")
    logger.info("="*60 + "\n")
    
    if gateway_ok and db_ok:
        logger.info("✓ All tests passed! Ready to run benchmark.")
        logger.info("\nNext steps:")
        logger.info("  uv run python main.py --task-id task_001")
        return 0
    else:
        logger.error("✗ Some tests failed. Please check the errors above.")
        
        if not gateway_ok:
            logger.error("\nTo start Gateway:")
            logger.error("  cd codelab-ai-service/gateway")
            logger.error("  uv run uvicorn app.main:app --host 0.0.0.0 --port 8000")
        
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
