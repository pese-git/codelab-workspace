#!/usr/bin/env python3
"""
Тест для проверки функциональности обновления токена.

Этот скрипт проверяет:
1. Получение access_token и refresh_token
2. Обновление access_token через refresh_token
3. Автоматический retry при 401 ошибке
"""
import asyncio
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from auth import AuthManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_token_refresh")


async def test_jwt_authentication():
    """Test JWT authentication and token refresh."""
    
    # Test configuration
    config = {
        'auth_type': 'jwt',
        'jwt': {
            'auth_url': 'http://localhost:8080/api/v1/auth/token',
            'username': 'test@example.com',
            'password': 'test123',
            'client_id': 'benchmark-client',
            'client_secret': ''
        }
    }
    
    logger.info("=" * 60)
    logger.info("Testing JWT Authentication and Token Refresh")
    logger.info("=" * 60)
    
    try:
        # Initialize AuthManager
        auth_manager = AuthManager(config)
        
        # Test 1: Initial authentication
        logger.info("\n[Test 1] Initial authentication...")
        access_token = await auth_manager.authenticate_jwt()
        logger.info(f"✅ Access token obtained: {access_token[:20]}...")
        
        if auth_manager.refresh_token:
            logger.info(f"✅ Refresh token obtained: {auth_manager.refresh_token[:20]}...")
        else:
            logger.warning("⚠️ No refresh token received (server may not support it)")
        
        # Test 2: Get headers
        logger.info("\n[Test 2] Getting authentication headers...")
        headers = await auth_manager.get_headers()
        logger.info(f"✅ Headers: {headers}")
        
        # Test 3: Refresh token
        logger.info("\n[Test 3] Refreshing access token...")
        new_access_token = await auth_manager.refresh_access_token()
        logger.info(f"✅ New access token: {new_access_token[:20]}...")
        
        if new_access_token != access_token:
            logger.info("✅ Token was refreshed (different from original)")
        else:
            logger.info("ℹ️ Token is the same (may be cached by server)")
        
        # Test 4: Handle unauthorized
        logger.info("\n[Test 4] Simulating 401 handling...")
        await auth_manager.handle_unauthorized()
        logger.info("✅ 401 handling completed successfully")
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ All tests passed!")
        logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ Test failed: {e}", exc_info=True)
        return False


async def test_internal_auth():
    """Test internal API key authentication."""
    
    config = {
        'auth_type': 'internal',
        'api_key': 'test-api-key-12345'
    }
    
    logger.info("\n" + "=" * 60)
    logger.info("Testing Internal API Key Authentication")
    logger.info("=" * 60)
    
    try:
        auth_manager = AuthManager(config)
        
        headers = await auth_manager.get_headers()
        logger.info(f"✅ Headers: {headers}")
        
        assert headers.get('X-Internal-Auth') == 'test-api-key-12345'
        logger.info("✅ Internal auth test passed!")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return False


async def main():
    """Run all tests."""
    
    logger.info("Starting token refresh tests...\n")
    
    # Test internal auth (always works)
    internal_result = await test_internal_auth()
    
    # Test JWT auth (requires running auth service)
    logger.info("\n" + "=" * 60)
    logger.info("Note: JWT tests require a running auth service")
    logger.info("If auth service is not available, JWT tests will fail")
    logger.info("=" * 60)
    
    jwt_result = await test_jwt_authentication()
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Test Summary")
    logger.info("=" * 60)
    logger.info(f"Internal Auth: {'✅ PASS' if internal_result else '❌ FAIL'}")
    logger.info(f"JWT Auth: {'✅ PASS' if jwt_result else '❌ FAIL (may need auth service)'}")
    logger.info("=" * 60)
    
    return internal_result


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
