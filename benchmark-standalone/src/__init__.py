"""
Benchmark Standalone - независимое приложение для тестирования AI-агентов.

Общается с backend через Gateway WebSocket API.
"""
from .auth import AuthManager
from .client import GatewayClient
from .collector import MetricsCollector
from .database import close_db, get_db, init_database, init_db
from .executor import MockToolExecutor
from .models import (
    AgentSwitch,
    Base,
    Experiment,
    Hallucination,
    LLMCall,
    QualityEvaluation,
    TaskExecution,
    ToolCall,
)
from .reporter import ReportGenerator
from .validator import TaskValidator

__version__ = "1.0.0"

__all__ = [
    "AuthManager",
    "GatewayClient",
    "MetricsCollector",
    "MockToolExecutor",
    "TaskValidator",
    "ReportGenerator",
    "init_database",
    "init_db",
    "get_db",
    "close_db",
    "Base",
    "Experiment",
    "TaskExecution",
    "LLMCall",
    "ToolCall",
    "AgentSwitch",
    "QualityEvaluation",
    "Hallucination",
]
