"""
Mock Tool Executor - локальное выполнение tools для benchmark.

Адаптировано из codelab-ai-service/benchmark/scripts/mock_tool_executor.py
"""
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger("benchmark.executor")


class MockToolExecutor:
    """
    Эмулятор выполнения tools для benchmark.
    
    Выполняет tools локально в контексте test_project,
    позволяя агентам создавать/изменять файлы для валидации.
    """
    
    def __init__(self, workspace_path: Path):
        """
        Initialize mock executor.
        
        Args:
            workspace_path: Path to test_project workspace
        """
        self.workspace_path = workspace_path
        
        if not self.workspace_path.exists():
            logger.warning(f"Workspace not found: {self.workspace_path}")
            self.workspace_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"MockToolExecutor initialized with workspace: {self.workspace_path}")
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute tool locally.
        
        Args:
            tool_name: Name of tool to execute
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        logger.debug(f"Executing tool: {tool_name}")
        
        try:
            if tool_name == "write_file" or tool_name == "write_to_file":
                return await self._write_file(arguments)
            elif tool_name == "read_file":
                return await self._read_file(arguments)
            elif tool_name == "list_files":
                return await self._list_files(arguments)
            elif tool_name == "search_files" or tool_name == "search_in_code":
                return await self._search_in_code(arguments)
            elif tool_name == "apply_diff":
                return await self._apply_diff(arguments)
            elif tool_name == "create_directory":
                return await self._create_directory(arguments)
            elif tool_name == "execute_command":
                return await self._execute_command(arguments)
            else:
                logger.warning(f"Unknown tool: {tool_name}")
                return {
                    "success": False,
                    "error": f"Tool not implemented: {tool_name}"
                }
        except Exception as e:
            logger.error(f"Tool execution error: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _write_file(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Write file tool."""
        path = args.get('path', '')
        content = args.get('content', '')
        
        if not path:
            return {"success": False, "error": "Missing 'path' argument"}
        
        full_path = self.workspace_path / path
        file_exists = full_path.exists()
        action = "Updated" if file_exists else "Created"
        
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write file and ensure it's flushed to disk
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
            f.flush()
            import os
            os.fsync(f.fileno())
        
        # Show file content preview
        lines = content.split('\n')
        preview = '\n'.join(lines[:10])
        if len(lines) > 10:
            preview += f"\n... ({len(lines) - 10} more lines)"
        
        logger.info(f"📝 {action} file: {path} ({len(content)} bytes, {len(lines)} lines)")
        logger.info(f"📄 Content preview:\n{preview}")
        
        return {
            "success": True,
            "message": f"File {action.lower()}: {path}",
            "path": path,
            "size": len(content),
            "lines": len(lines)
        }
    
    async def _read_file(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Read file tool."""
        path = args.get('path', '')
        
        if not path:
            return {"success": False, "error": "Missing 'path' argument"}
        
        full_path = self.workspace_path / path
        
        if not full_path.exists():
            logger.warning(f"📂 File not found: {path}")
            return {
                "success": False,
                "error": f"File not found: {path}"
            }
        
        try:
            content = full_path.read_text(encoding='utf-8')
            lines = content.split('\n')
            
            # Show file content preview
            preview = '\n'.join(lines[:5])
            if len(lines) > 5:
                preview += f"\n... ({len(lines) - 5} more lines)"
            
            logger.info(f"📖 Read file: {path} ({len(content)} bytes, {len(lines)} lines)")
            logger.debug(f"📄 Content preview:\n{preview}")
            
            return {
                "success": True,
                "content": content,
                "path": path,
                "size": len(content),
                "lines": len(lines)
            }
        except Exception as e:
            logger.error(f"❌ Error reading file {path}: {e}")
            return {
                "success": False,
                "error": f"Error reading file: {str(e)}"
            }
    
    async def _list_files(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List files tool."""
        path = args.get('path', '.')
        recursive = args.get('recursive', False)
        
        full_path = self.workspace_path / path
        
        if not full_path.exists():
            logger.warning(f"📂 Path not found: {path}")
            return {
                "success": False,
                "error": f"Path not found: {path}"
            }
        
        try:
            if recursive:
                files = [
                    str(p.relative_to(self.workspace_path))
                    for p in full_path.rglob('*')
                    if p.is_file()
                ]
            else:
                files = [
                    str(p.relative_to(self.workspace_path))
                    for p in full_path.iterdir()
                    if p.is_file()
                ]
            
            mode_str = "recursively" if recursive else "in"
            logger.info(f"📂 Listed {len(files)} files {mode_str} {path}")
            
            # Show first few files
            if files:
                preview = files[:5]
                logger.debug(f"📄 Files: {', '.join(preview)}" +
                           (f" ... and {len(files)-5} more" if len(files) > 5 else ""))
            
            return {
                "success": True,
                "files": files,
                "count": len(files)
            }
        except Exception as e:
            logger.error(f"❌ Error listing files in {path}: {e}")
            return {
                "success": False,
                "error": f"Error listing files: {str(e)}"
            }
    
    async def _search_in_code(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Search in code tool."""
        pattern = args.get('pattern', args.get('regex', args.get('query', '')))
        path = args.get('path', '.')
        file_pattern = args.get('file_pattern', '*.dart')
        
        if not pattern or pattern == 'False':
            logger.warning(f"Invalid search pattern: '{pattern}'")
            return {
                "success": False,
                "error": f"Invalid or missing 'pattern' argument: '{pattern}'"
            }
        
        full_path = self.workspace_path / path
        
        if not full_path.exists():
            logger.warning(f"📂 Path not found: {path}")
            return {"success": False, "error": f"Path not found: {path}"}
        
        try:
            results = []
            
            # Simple text search (not regex for simplicity)
            for file_path in full_path.rglob(file_pattern):
                if file_path.is_file():
                    try:
                        content = file_path.read_text(encoding='utf-8')
                        if pattern in content:
                            rel_path = str(file_path.relative_to(self.workspace_path))
                            results.append(rel_path)
                    except Exception:
                        pass
            
            logger.info(f"🔍 Search found {len(results)} matches for '{pattern}' in {path}")
            if results:
                logger.debug(f"📄 Matches: {', '.join(results[:3])}" +
                           (f" ... and {len(results)-3} more" if len(results) > 3 else ""))
            
            return {
                "success": True,
                "results": results,
                "count": len(results),
                "pattern": pattern
            }
        except Exception as e:
            logger.error(f"❌ Error searching in {path}: {e}")
            return {
                "success": False,
                "error": f"Error searching: {str(e)}"
            }
    
    async def _apply_diff(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Apply diff tool (simplified implementation)."""
        path = args.get('path', '')
        
        if not path:
            return {"success": False, "error": "Missing 'path' argument"}
        
        # Simplified: just acknowledge the diff
        # Real implementation would parse and apply the diff
        logger.info(f"Diff applied to: {path}")
        
        return {
            "success": True,
            "message": f"Diff applied to: {path}",
            "path": path
        }
    
    async def _create_directory(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Create directory tool."""
        path = args.get('path', '')
        
        if not path:
            return {"success": False, "error": "Missing 'path' argument"}
        
        full_path = self.workspace_path / path
        dir_exists = full_path.exists()
        action = "Already exists" if dir_exists else "Created"
        
        try:
            full_path.mkdir(parents=True, exist_ok=True)
            
            icon = "📁" if dir_exists else "✨"
            logger.info(f"{icon} {action} directory: {path}")
            
            return {
                "success": True,
                "message": f"Directory {action.lower()}: {path}",
                "path": path,
                "created": not dir_exists
            }
        except Exception as e:
            logger.error(f"❌ Error creating directory {path}: {e}")
            return {
                "success": False,
                "error": f"Error creating directory: {str(e)}"
            }
    
    async def _execute_command(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute command tool."""
        command = args.get('command', '')
        cwd = args.get('cwd', '.')
        
        if not command:
            return {"success": False, "error": "Missing 'command' argument"}
        
        # For safety, only allow specific safe commands
        safe_commands = ['dart', 'flutter', 'pub', 'analyze', 'test', 'format']
        command_parts = command.split()
        
        if not command_parts or command_parts[0] not in safe_commands:
            logger.warning(f"⚠️ Blocked unsafe command: {command}")
            return {
                "success": False,
                "error": f"Command not allowed: {command_parts[0] if command_parts else 'empty'}"
            }
        
        # Block long-running commands that don't terminate
        blocked_subcommands = ['run', 'serve', 'attach', 'drive']
        if len(command_parts) > 1 and command_parts[1] in blocked_subcommands:
            logger.warning(f"⚠️ Blocked long-running command: {command}")
            return {
                "success": False,
                "error": f"Long-running command not allowed: {command_parts[1]}"
            }
        
        try:
            import subprocess
            
            full_cwd = self.workspace_path / cwd if cwd != '.' else self.workspace_path
            
            result = subprocess.run(
                command_parts,
                cwd=str(full_cwd),
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Log command result with preview
            success_icon = "✅" if result.returncode == 0 else "❌"
            logger.info(f"{success_icon} Executed command: {command} (return_code={result.returncode})")
            
            if result.stdout:
                stdout_preview = result.stdout[:200].replace('\n', ' ')
                logger.info(f"   stdout: {stdout_preview}{'...' if len(result.stdout) > 200 else ''}")
            
            if result.stderr:
                stderr_preview = result.stderr[:200].replace('\n', ' ')
                logger.warning(f"   stderr: {stderr_preview}{'...' if len(result.stderr) > 200 else ''}")
            
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Command timed out"
            }
        except Exception as e:
            logger.error(f"❌ Error executing command {command}: {e}")
            return {
                "success": False,
                "error": f"Error executing command: {str(e)}"
            }
