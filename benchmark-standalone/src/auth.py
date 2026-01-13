"""
JWT Authentication module for Gateway access.

Supports both Internal API Key and JWT token authentication.
"""
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
            
            logger.info(f"✅ JWT token obtained successfully")
            logger.debug(f"Token type: {token_data.get('token_type')}")
            logger.debug(f"Expires in: {token_data.get('expires_in')}s")
            
            return self.access_token
    
    async def refresh_token_if_needed(self) -> None:
        """
        Refresh JWT token if needed.
        
        For now, just re-authenticate. In production, should use refresh_token.
        """
        if self.auth_type == "jwt":
            logger.info("🔄 Refreshing JWT token...")
            await self.authenticate_jwt()
