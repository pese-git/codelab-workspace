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
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        full_path.write_text(content, encoding='utf-8')
        
        logger.info(f"Created file: {path} ({len(content)} bytes)")
        return {
            "success": True,
            "message": f"File created: {path}",
            "path": path,
            "size": len(content)
        }
    
    async def _read_file(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Read file tool."""
        path = args.get('path', '')
        
        if not path:
            return {"success": False, "error": "Missing 'path' argument"}
        
        full_path = self.workspace_path / path
        
        if not full_path.exists():
            return {
                "success": False,
                "error": f"File not found: {path}"
            }
        
        try:
            content = full_path.read_text(encoding='utf-8')
            logger.debug(f"Read file: {path} ({len(content)} bytes)")
            return {
                "success": True,
                "content": content,
                "path": path,
                "size": len(content)
            }
        except Exception as e:
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
            
            logger.debug(f"Listed {len(files)} files in {path}")
            return {
                "success": True,
                "files": files,
                "count": len(files)
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error listing files: {str(e)}"
            }
    
    async def _search_in_code(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Search in code tool."""
        pattern = args.get('pattern', args.get('regex', ''))
        path = args.get('path', '.')
        file_pattern = args.get('file_pattern', '*.dart')
        
        if not pattern:
            return {"success": False, "error": "Missing 'pattern' argument"}
        
        full_path = self.workspace_path / path
        
        if not full_path.exists():
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
            
            logger.debug(f"Search found {len(results)} matches for '{pattern}'")
            return {
                "success": True,
                "results": results,
                "count": len(results),
                "pattern": pattern
            }
        except Exception as e:
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
        
        try:
            full_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created directory: {path}")
            return {
                "success": True,
                "message": f"Directory created: {path}",
                "path": path
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error creating directory: {str(e)}"
            }
