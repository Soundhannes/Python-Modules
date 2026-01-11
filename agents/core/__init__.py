"""
Core - Basis-Klassen für Agents und Orchestrator.
"""

from .base_agent import BaseAgent, AgentResult
from .base_orchestrator import BaseOrchestrator, StepResult, OrchestrationResult

__all__ = [
    "BaseAgent",
    "AgentResult",
    "BaseOrchestrator",
    "StepResult",
    "OrchestrationResult",
]
