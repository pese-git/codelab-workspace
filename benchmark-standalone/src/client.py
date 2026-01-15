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
    
    async def create_session(self) -> str:
        """
        Create new session via HTTP API.
        
        Returns:
            Session ID
        """
        headers = await self.auth_manager.get_headers()
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/sessions",
                headers=headers
            )
            response.raise_for_status()
            data = response.json()
            session_id = data['session_id']
            logger.info(f"Created session: {session_id}")
            return session_id
    
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
        
        # Planning metrics
        plan_id = None
        plan_created = False
        subtasks_started = 0
        subtasks_completed = 0
        
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
                        
                        elif msg_type == "plan_notification":
                            # Plan created by Orchestrator
                            plan_created = True
                            metadata = msg.get("metadata", {})
                            plan_id = metadata.get("plan_id", "unknown")
                            subtask_count = metadata.get("subtask_count", 0)
                            subtasks = metadata.get("subtasks", [])
                            
                            logger.info("=" * 80)
                            logger.info(f"📋 EXECUTION PLAN CREATED")
                            logger.info(f"   Plan ID: {plan_id}")
                            logger.info(f"   Total Subtasks: {subtask_count}")
                            logger.info("=" * 80)
                            
                            # Log subtasks with details
                            for idx, subtask in enumerate(subtasks, 1):
                                subtask_id = subtask.get('id', f'subtask_{idx}')
                                description = subtask.get('description', 'No description')
                                agent = subtask.get('agent', 'unknown')
                                estimated_time = subtask.get('estimated_time', 'N/A')
                                dependencies = subtask.get('dependencies', [])
                                
                                logger.info(f"   {idx}. [{subtask_id}] {description}")
                                logger.info(f"      Agent: {agent} | Est. Time: {estimated_time}")
                                if dependencies:
                                    logger.info(f"      Dependencies: {', '.join(dependencies)}")
                            
                            logger.info("=" * 80)
                            
                            # Record plan creation
                            try:
                                await collector.record_plan_created(
                                    task_execution_id=task_execution_id,
                                    plan_id=plan_id,
                                    original_task=task_description,
                                    subtasks=subtasks
                                )
                            except Exception as e:
                                logger.error(f"Failed to record plan creation: {e}")
                        
                        elif msg_type == "subtask_started":
                            # Subtask execution started
                            subtasks_started += 1
                            metadata = msg.get("metadata", {})
                            subtask_id = metadata.get("subtask_id", "unknown")
                            subtask_description = metadata.get("description", "")
                            subtask_agent = metadata.get("agent", "unknown")
                            subtask_index = metadata.get("index", subtasks_started)
                            total_subtasks = metadata.get("total", "?")
                            
                            logger.info("")
                            logger.info("▶" * 40)
                            logger.info(f"▶️  SUBTASK STARTED [{subtask_index}/{total_subtasks}]")
                            logger.info(f"   ID: {subtask_id}")
                            logger.info(f"   Agent: {subtask_agent}")
                            logger.info(f"   Description: {subtask_description}")
                            logger.info("▶" * 40)
                            
                            # Record subtask start
                            try:
                                await collector.record_subtask_started(
                                    task_execution_id=task_execution_id,
                                    subtask_id=subtask_id,
                                    description=subtask_description,
                                    agent=subtask_agent
                                )
                            except Exception as e:
                                logger.error(f"Failed to record subtask start: {e}")
                        
                        elif msg_type == "subtask_completed":
                            # Subtask execution completed
                            subtasks_completed += 1
                            metadata = msg.get("metadata", {})
                            subtask_id = metadata.get("subtask_id", "unknown")
                            subtask_status = metadata.get("status", "unknown")
                            subtask_result = metadata.get("result")
                            subtask_error = metadata.get("error")
                            subtask_index = metadata.get("index", subtasks_completed)
                            total_subtasks = metadata.get("total", "?")
                            
                            # Choose icon based on status
                            if subtask_status == "completed":
                                status_icon = "✅"
                                status_color = "SUCCESS"
                            elif subtask_status == "failed":
                                status_icon = "❌"
                                status_color = "FAILED"
                            elif subtask_status == "skipped":
                                status_icon = "⏭️"
                                status_color = "SKIPPED"
                            else:
                                status_icon = "❓"
                                status_color = "UNKNOWN"
                            
                            logger.info("")
                            logger.info("◀" * 40)
                            logger.info(f"{status_icon} SUBTASK {status_color} [{subtask_index}/{total_subtasks}]")
                            logger.info(f"   ID: {subtask_id}")
                            logger.info(f"   Status: {subtask_status}")
                            if subtask_result:
                                result_preview = subtask_result[:100]
                                logger.info(f"   Result: {result_preview}{'...' if len(subtask_result) > 100 else ''}")
                            if subtask_error:
                                logger.error(f"   Error: {subtask_error}")
                            logger.info("◀" * 40)
                            
                            # Record subtask completion
                            try:
                                await collector.record_subtask_completed(
                                    task_execution_id=task_execution_id,
                                    subtask_id=subtask_id,
                                    status=subtask_status,
                                    result=subtask_result,
                                    error=subtask_error
                                )
                            except Exception as e:
                                logger.error(f"Failed to record subtask completion: {e}")
                        
                        elif msg_type == "plan_completed":
                            # Entire plan completed
                            metadata = msg.get("metadata", {})
                            completed_plan_id = metadata.get("plan_id", plan_id)
                            total_subtasks = metadata.get("total_subtasks", 0)
                            completed_count = metadata.get("completed", 0)
                            failed_count = metadata.get("failed", 0)
                            skipped_count = metadata.get("skipped", 0)
                            
                            logger.info("")
                            logger.info("🏁" * 40)
                            logger.info(f"🏁 EXECUTION PLAN COMPLETED")
                            logger.info(f"   Plan ID: {completed_plan_id}")
                            logger.info(f"   Total Subtasks: {total_subtasks}")
                            logger.info(f"   ✅ Completed: {completed_count}")
                            logger.info(f"   ❌ Failed: {failed_count}")
                            logger.info(f"   ⏭️  Skipped: {skipped_count}")
                            success_rate = (completed_count / total_subtasks * 100) if total_subtasks > 0 else 0
                            logger.info(f"   Success Rate: {success_rate:.1f}%")
                            logger.info("🏁" * 40)
                            logger.info("")
                            
                            # Record plan completion
                            try:
                                await collector.record_plan_completed(
                                    task_execution_id=task_execution_id
                                )
                            except Exception as e:
                                logger.error(f"Failed to record plan completion: {e}")
                        
                        elif msg_type == "error":
                            has_error = True
                            error_msg = msg.get("content", msg.get("error", "Unknown error"))
                            logger.error(f"❌ Error from Gateway: {error_msg}")
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
            
            # Log final summary
            result_icon = "✅" if success else "❌"
            logger.info("")
            logger.info("=" * 80)
            logger.info(f"{result_icon} TASK EXECUTION SUMMARY")
            logger.info(f"   Task ID: {task_id}")
            logger.info(f"   Title: {task_title}")
            logger.info(f"   Category: {task_category}")
            logger.info(f"   Success: {success}")
            logger.info(f"   Tool Calls: {tool_calls_count}")
            logger.info(f"   Agent Switches: {agent_switches_count}")
            logger.info(f"   Response Length: {len(response_text)} chars")
            
            if plan_created:
                logger.info(f"   📋 Plan Used: Yes (ID: {plan_id})")
                logger.info(f"   Subtasks Started: {subtasks_started}")
                logger.info(f"   Subtasks Completed: {subtasks_completed}")
            else:
                logger.info(f"   📋 Plan Used: No")
            
            logger.info("=" * 80)
            logger.info("")
            
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
            # Test HTTP endpoint
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
            
            # Test WebSocket by creating session and connecting
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
