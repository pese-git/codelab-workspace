"""
JWT Authentication module for Gateway access.

Supports both Internal API Key and JWT token authentication.
"""
import asyncio
import logging
from typing import Dict, Any, Optional

import httpx

logger = logging.getLogger("benchmark.auth")


class AuthManager:
    """
    Manages authentication for Gateway API.
    
    Supports two modes:
    1. Internal API Key (X-Internal-Auth header)
    2. JWT Token (Authorization: Bearer header)
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize auth manager.
        
        Args:
            config: Gateway configuration from config.yaml
        """
        self.config = config
        self.auth_type = config.get('auth_type', 'internal')
        self.api_key = config.get('api_key')
        self.jwt_config = config.get('jwt', {})
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self._refresh_lock = asyncio.Lock()  # Prevent concurrent token refresh
        self._token_being_refreshed = False  # Track if refresh is in progress
        
        logger.info(f"AuthManager initialized: auth_type={self.auth_type}")
    
    async def get_headers(self) -> Dict[str, str]:
        """
        Get authentication headers for HTTP requests.
        
        Returns:
            Dictionary with authentication headers
        """
        if self.auth_type == "internal":
            return {"X-Internal-Auth": self.api_key}
        elif self.auth_type == "jwt":
            # Get or refresh JWT token
            if not self.access_token:
                await self.authenticate_jwt()
            return {"Authorization": f"Bearer {self.access_token}"}
        else:
            raise ValueError(f"Unknown auth_type: {self.auth_type}")
    
    async def authenticate_jwt(self) -> str:
        """
        Authenticate with OAuth2 and get JWT access token.
        
        Returns:
            Access token
        """
        auth_url = self.jwt_config.get('auth_url')
        username = self.jwt_config.get('username')
        password = self.jwt_config.get('password')
        client_id = self.jwt_config.get('client_id')
        client_secret = self.jwt_config.get('client_secret', '')
        
        if not all([auth_url, username, password, client_id]):
            raise ValueError("Missing JWT configuration (auth_url, username, password, client_id)")
        
        logger.info(f"🔐 Authenticating with OAuth2: {username}")
        
        # OAuth2 password grant
        data = {
            "grant_type": "password",
            "username": username,
            "password": password,
            "client_id": client_id,
        }
        
        if client_secret:
            data["client_secret"] = client_secret
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                auth_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data['access_token']
            self.refresh_token = token_data.get('refresh_token')
            
            logger.info(f"✅ JWT token obtained successfully")
            logger.debug(f"Token type: {token_data.get('token_type')}")
            logger.debug(f"Expires in: {token_data.get('expires_in')}s")
            if self.refresh_token:
                logger.debug(f"Refresh token available")
            
            return self.access_token
    
    async def refresh_access_token(self) -> str:
        """
        Refresh JWT access token using refresh_token.
        
        Thread-safe: Uses asyncio.Lock to prevent concurrent refresh operations.
        Double-check optimization: Queued requests reuse the token refreshed by the first request.
        
        Returns:
            New access token
            
        Raises:
            ValueError: If refresh_token is not available or refresh fails
        """
        # First check: if refresh is already in progress, wait for it
        if self._token_being_refreshed:
            async with self._refresh_lock:
                # Second check: token should be refreshed by now
                if self.access_token and not self._token_being_refreshed:
                    logger.debug("Token already refreshed by concurrent operation, reusing")
                    return self.access_token
        
        async with self._refresh_lock:
            # Double-check: another concurrent call might have just finished refreshing
            if not self._token_being_refreshed and self.access_token:
                logger.debug("Token already refreshed by concurrent operation, reusing")
                return self.access_token
            
            # Mark that refresh is in progress
            self._token_being_refreshed = True
            old_token = self.access_token
            
            try:
                if not self.refresh_token:
                    logger.warning("No refresh_token available, re-authenticating...")
                    token = await self.authenticate_jwt()
                    self._token_being_refreshed = False
                    return token
                
                auth_url = self.jwt_config.get('auth_url')
                client_id = self.jwt_config.get('client_id')
                client_secret = self.jwt_config.get('client_secret', '')
                
                if not all([auth_url, client_id]):
                    raise ValueError("Missing JWT configuration (auth_url, client_id)")
                
                logger.info("🔄 Refreshing access token using refresh_token...")
                
                # OAuth2 refresh token grant
                data = {
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                    "client_id": client_id,
                }
                
                if client_secret:
                    data["client_secret"] = client_secret
                
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            auth_url,
                            data=data,
                            headers={"Content-Type": "application/x-www-form-urlencoded"}
                        )
                        response.raise_for_status()
                        
                        token_data = response.json()
                        self.access_token = token_data['access_token']
                        # Update refresh_token if a new one is provided
                        if 'refresh_token' in token_data:
                            self.refresh_token = token_data['refresh_token']
                        
                        logger.info(f"✅ Access token refreshed successfully")
                        logger.debug(f"Expires in: {token_data.get('expires_in')}s")
                        
                        return self.access_token
                        
                except httpx.HTTPStatusError as e:
                    logger.warning(f"Failed to refresh token (status {e.response.status_code}), re-authenticating...")
                    # If refresh fails, try full re-authentication
                    return await self.authenticate_jwt()
                except Exception as e:
                    logger.error(f"Error refreshing token: {e}, re-authenticating...")
                    return await self.authenticate_jwt()
            finally:
                # Always clear the refresh flag
                self._token_being_refreshed = False
    
    async def refresh_token_if_needed(self) -> None:
        """
        Refresh JWT token if needed.
        
        Uses refresh_token if available, otherwise re-authenticates.
        """
        if self.auth_type == "jwt":
            await self.refresh_access_token()
    
    async def handle_unauthorized(self) -> None:
        """
        Handle 401 Unauthorized error by refreshing the token.
        
        Thread-safe: Multiple concurrent 401 errors will be serialized
        through the refresh lock, ensuring only one refresh operation occurs.
        
        This method should be called when a request returns 401.
        """
        if self.auth_type == "jwt":
            logger.warning("⚠️ Received 401 Unauthorized, refreshing token...")
            await self.refresh_access_token()
        else:
            logger.error("Received 401 with internal auth - check API key")
