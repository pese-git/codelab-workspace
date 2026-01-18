"""
Gateway WebSocket Client - общение с Gateway через WebSocket.

Адаптировано из codelab-ai-service/benchmark/scripts/run_poc_experiment_ws.py
Обновлено для работы с Gateway API: сначала создает сессию через HTTP,
затем подключается к WebSocket /ws/{session_id}
"""
import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional
from uuid import UUID

import httpx
import websockets

from .auth import AuthManager
from .collector import MetricsCollector
from .executor import MockToolExecutor
from .validator import TaskValidator

logger = logging.getLogger("benchmark.client")


class GatewayClient:
    """
    WebSocket клиент для общения с Gateway.
    
    Единственная точка взаимодействия с backend сервисами.
    Поддерживает Internal API Key и JWT аутентификацию.
    """
    
    def __init__(
        self,
        base_url: str,
        ws_url: str,
        auth_manager: AuthManager,
        timeout: int = 60,
        reconnect_attempts: int = 3,
        reconnect_delay: int = 5
    ):
        """
        Initialize Gateway client.
        
        Args:
            base_url: Gateway base URL (e.g., http://localhost:8000)
            ws_url: Gateway WebSocket URL base (e.g., ws://localhost:8000/ws)
            auth_manager: Authentication manager
            timeout: Message timeout in seconds
            reconnect_attempts: Number of reconnection attempts
            reconnect_delay: Delay between reconnection attempts
        """
        self.base_url = base_url
        self.ws_url = ws_url
        self.auth_manager = auth_manager
        self.timeout = timeout
        self.reconnect_attempts = reconnect_attempts
        self.reconnect_delay = reconnect_delay
        
        logger.info(f"GatewayClient initialized: {base_url}")
    
    async def _make_http_request(
        self,
        method: str,
        url: str,
        retry_on_401: bool = True,
        **kwargs
    ) -> httpx.Response:
        """
        Make HTTP request with automatic token refresh on 401.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            retry_on_401: Whether to retry with refreshed token on 401
            **kwargs: Additional arguments for httpx request
            
        Returns:
            HTTP response
            
        Raises:
            httpx.HTTPStatusError: If request fails after retry
        """
        headers = await self.auth_manager.get_headers()
        if 'headers' in kwargs:
            kwargs['headers'].update(headers)
        else:
            kwargs['headers'] = headers
        
        async with httpx.AsyncClient() as client:
            response = await client.request(method, url, **kwargs)
            
            # Handle 401 Unauthorized
            if response.status_code == 401 and retry_on_401:
                logger.warning(f"⚠️ Received 401 from {url}, refreshing token and retrying...")
                await self.auth_manager.handle_unauthorized()
                
                # Retry with new token
                headers = await self.auth_manager.get_headers()
                if 'headers' in kwargs:
                    kwargs['headers'].update(headers)
                else:
                    kwargs['headers'] = headers
                
                response = await client.request(method, url, **kwargs)
            
            response.raise_for_status()
            return response
    
    async def create_session(self) -> str:
        """
        Create new session via HTTP API.
        
        Returns:
            Session ID
        """
        response = await self._make_http_request(
            "POST",
            f"{self.base_url}/api/v1/sessions"
        )
        data = response.json()
        session_id = data['session_id']
        logger.info(f"Created session: {session_id}")
        return session_id
    
    async def get_session_metrics(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get LLM metrics for a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session metrics dictionary or None if not found
        """
        try:
            response = await self._make_http_request(
                "GET",
                f"{self.base_url}/api/v1/events/metrics/session/{session_id}"
            )
            return response.json()
                    
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.debug(f"No metrics found for session {session_id}")
                return None
            else:
                logger.warning(
                    f"Failed to get metrics for session {session_id}: "
                    f"status={e.response.status_code}"
                )
                return None
        except Exception as e:
            logger.error(f"Error fetching session metrics: {e}")
            return None
    
    async def execute_task(
        self,
        task: Dict[str, Any],
        tool_executor: MockToolExecutor,
        validator: Optional[TaskValidator],
        collector: MetricsCollector,
        task_execution_id: UUID
    ) -> bool:
        """
        Execute task via Gateway WebSocket with full tool execution loop.
        
        Args:
            task: Task definition from YAML
            tool_executor: Tool executor for local tool execution
            validator: Optional task validator
            collector: Metrics collector
            task_execution_id: Task execution ID for metrics
            
        Returns:
            True if task succeeded
        """
        task_description = task.get('description', '')
        task_id = task.get('id', 'unknown')
        task_title = task.get('title', '')
        task_category = task.get('category', 'simple')
        
        logger.info(f"🚀 Executing task {task_id}: {task_title}")
        logger.info(f"📋 Description: {task_description[:100]}...")
        
        # Adjust timeout based on task complexity
        original_timeout = self.timeout
        if task_category in ['complex', 'mixed']:
            self.timeout = 300  # 5 minutes for complex tasks
            logger.info(f"⏱️  Increased timeout to {self.timeout}s for {task_category} task")
        
        # Create session first
        session_id = await self.create_session()
        
        # Track metrics
        response_text = ""
        has_error = False
        tool_calls_count = 0
        agent_switches_count = 0
        last_write_file_time = None
        MAX_TOOL_CALLS = 100  # Prevent infinite loops
        
        try:
            # Connect to WebSocket with session_id
            ws_endpoint = f"{self.ws_url}/{session_id}"
            async with websockets.connect(ws_endpoint) as websocket:
                logger.info(f"🔌 Connected to Gateway WebSocket")
                
                # Send initial message
                await websocket.send(json.dumps({
                    "type": "user_message",
                    "content": task_description,
                    "role": "user"
                }))
                
                logger.info("📤 Sent task description to agent")
                
                # Process responses
                while True:
                    try:
                        data = await asyncio.wait_for(
                            websocket.recv(),
                            timeout=self.timeout
                        )
                        msg = json.loads(data)
                        msg_type = msg.get("type")
                        
                        if msg_type == "assistant_message":
                            token = msg.get("token", "")
                            response_text += token
                            
                            # Show progress for long responses
                            if len(response_text) % 100 == 0:
                                logger.debug(f"📝 Received {len(response_text)} characters...")
                            
                            if msg.get("is_final"):
                                logger.info(f"✅ Received final message ({len(response_text)} chars)")
                                break
                        
                        elif msg_type == "tool_call":
                            tool_calls_count += 1
                            
                            # Check tool call limit
                            if tool_calls_count > MAX_TOOL_CALLS:
                                logger.warning(f"⚠️ Reached max tool calls limit: {MAX_TOOL_CALLS}")
                                has_error = True
                                break
                            
                            call_id = msg.get("call_id")
                            tool_name = msg.get("tool_name")
                            arguments = msg.get("arguments", {})
                            
                            # Log tool call with key parameters
                            params_str = ""
                            if tool_name in ["write_file", "write_to_file"]:
                                path = arguments.get("path", "")
                                content_len = len(arguments.get("content", ""))
                                params_str = f"path={path}, content_len={content_len}"
                            elif tool_name == "read_file":
                                path = arguments.get("path", "")
                                params_str = f"path={path}"
                            elif tool_name == "execute_command":
                                command = arguments.get("command", "")
                                params_str = f"command='{command}'"
                            elif tool_name in ["search_files", "search_in_code"]:
                                pattern = arguments.get("pattern", arguments.get("regex", ""))
                                params_str = f"pattern='{pattern}'"
                            
                            logger.info(
                                f"🔧 Tool call #{tool_calls_count}: {tool_name} "
                                f"({params_str}) (call_id={call_id[:8]}...)"
                            )
                            
                            # Execute tool locally
                            start_time = time.time()
                            tool_result = await tool_executor.execute_tool(
                                tool_name, arguments
                            )
                            duration = time.time() - start_time
                            
                            # Track last write_file operation
                            if tool_name in ["write_file", "write_to_file"]:
                                last_write_file_time = time.time()
                                logger.debug(f"Tracked write_file at {last_write_file_time}")
                            
                            success_icon = "✅" if tool_result.get('success') else "❌"
                            logger.info(
                                f"{success_icon} Tool executed: {tool_name}, "
                                f"duration={duration:.2f}s"
                            )
                            
                            # Record tool call metric
                            await collector.record_tool_call(
                                task_execution_id=task_execution_id,
                                tool_name=tool_name,
                                success=tool_result.get('success', False),
                                duration_seconds=duration,
                                error=tool_result.get('error')
                            )
                            
                            # Send tool result back to Gateway
                            await websocket.send(json.dumps({
                                "type": "tool_result",
                                "call_id": call_id,
                                "result": tool_result
                            }))
                            
                            logger.debug(f"Sent tool result for {tool_name}")
                        
                        elif msg_type == "agent_switched":
                            agent_switches_count += 1
                            # Extract from metadata (new format) or root (legacy format)
                            metadata = msg.get("metadata", {})
                            from_agent = metadata.get("from_agent") or msg.get("from_agent")
                            to_agent = metadata.get("to_agent") or msg.get("to_agent")
                            reason = metadata.get("reason") or msg.get("reason", "")
                            
                            logger.info(f"🔄 Agent switched: {from_agent} → {to_agent} ({reason})")
                            
                            # Record agent switch metric (only if to_agent is not None)
                            if to_agent:
                                await collector.record_agent_switch(
                                    task_execution_id=task_execution_id,
                                    from_agent=from_agent,
                                    to_agent=to_agent,
                                    reason=reason
                                )
                            else:
                                logger.warning(f"Skipping agent_switch with to_agent=None")
                        
                        elif msg_type == "error":
                            has_error = True
                            error_msg = msg.get("content", msg.get("error", "Unknown error"))
                            logger.error(f"Error from Gateway: {error_msg}")
                            break
                    
                    except asyncio.TimeoutError:
                        logger.warning(f"Timeout waiting for response ({self.timeout}s)")
                        has_error = True
                        break
                    except websockets.ConnectionClosed:
                        logger.info("WebSocket connection closed")
                        break
            
            # Validate if enabled
            success = not has_error and len(response_text) > 0
            
            if validator and success:
                # Wait for file operations to complete if there were any write_file calls
                if last_write_file_time:
                    time_since_last_write = time.time() - last_write_file_time
                    if time_since_last_write < 2.0:
                        wait_time = 2.0 - time_since_last_write
                        logger.info(f"⏳ Waiting {wait_time:.1f}s for file operations to complete...")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.debug(f"File operations completed {time_since_last_write:.1f}s ago")
                
                logger.info("🔍 Running validation checks...")
                validation = await validator.validate_task(task)
                
                check_icon = "✅" if validation['success_rate'] >= 0.5 else "⚠️"
                logger.info(
                    f"{check_icon} Validation: {validation['passed_checks']}/"
                    f"{validation['total_checks']} passed "
                    f"({validation['success_rate']:.0%})"
                )
                
                # Record quality evaluation
                await collector.record_quality_evaluation(
                    task_execution_id=task_execution_id,
                    evaluation_type="auto_check",
                    score=validation['success_rate'],
                    passed=validation['success_rate'] >= 0.5,
                    details=validation
                )
                
                if validation['total_checks'] > 0:
                    success = validation['success_rate'] >= 0.5
            
            # Fetch LLM metrics from session
            logger.info("📊 Fetching LLM metrics from session...")
            session_metrics = await self.get_session_metrics(session_id)
            
            if session_metrics and 'requests' in session_metrics:
                llm_requests = session_metrics['requests']
                logger.info(
                    f"📈 LLM Metrics: {len(llm_requests)} requests, "
                    f"{session_metrics.get('total_tokens', 0)} tokens, "
                    f"{session_metrics.get('total_duration_ms', 0)}ms total"
                )
                
                # Record each LLM call
                for req in llm_requests:
                    if req.get('success', False):
                        await collector.record_llm_call(
                            task_execution_id=task_execution_id,
                            agent_type="agent",  # Could extract from context if needed
                            input_tokens=req.get('prompt_tokens', 0),
                            output_tokens=req.get('completion_tokens', 0),
                            model=req.get('model', 'unknown'),
                            duration_seconds=req.get('duration_ms', 0) / 1000.0
                        )
                
                logger.info(f"✅ Recorded {len(llm_requests)} LLM calls to database")
            else:
                logger.warning("⚠️ No LLM metrics found for session")
            
            result_icon = "✅" if success else "❌"
            logger.info(
                f"\n{result_icon} Task {task_id} completed: "
                f"success={success}, "
                f"tool_calls={tool_calls_count}, "
                f"agent_switches={agent_switches_count}, "
                f"response_length={len(response_text)}"
            )
            
            return success
            
        except websockets.exceptions.WebSocketException as e:
            logger.error(f"WebSocket error: {e}")
            return False
        except Exception as e:
            logger.error(f"Task execution error: {e}", exc_info=True)
            return False
        finally:
            # Restore original timeout
            self.timeout = original_timeout
    
    async def test_connection(self) -> bool:
        """
        Test connection to Gateway.
        
        Returns:
            True if connection successful
        """
        try:
            # Test HTTP endpoint (health check doesn't require auth usually)
            async with httpx.AsyncClient() as client:
                # Try /api/v1/health first (nginx), fallback to /health (direct)
                try:
                    response = await client.get(f"{self.base_url}/api/v1/health")
                    response.raise_for_status()
                    logger.info(f"✓ Gateway HTTP accessible: {self.base_url}/api/v1/health")
                except httpx.HTTPError:
                    response = await client.get(f"{self.base_url}/health")
                    response.raise_for_status()
                    logger.info(f"✓ Gateway HTTP accessible: {self.base_url}/health")
            
            # Test WebSocket by creating session and connecting (uses auth with retry)
            session_id = await self.create_session()
            ws_endpoint = f"{self.ws_url}/{session_id}"
            
            async with websockets.connect(ws_endpoint):
                logger.info(
                    f"✓ Successfully connected to Gateway WebSocket: {ws_endpoint}"
                )
                return True
                
        except Exception as e:
            logger.error(f"✗ Failed to connect to Gateway: {e}")
            return False
