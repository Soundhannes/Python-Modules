"""
Agents Module - Wiederverwendbare Bausteine für LLM-Automationen.

Struktur:
    core/       - BaseAgent, BaseOrchestrator
    services/   - Storage, Notification
    utils/      - Logger, Validator, HumanInLoop, InputCollector

Verwendung:
    from agents import BaseAgent, BaseOrchestrator
    from agents.services import StorageService, NotificationService
    from agents.utils import Logger, Validator
"""

from .core import BaseAgent, AgentResult
from .core import BaseOrchestrator, StepResult, OrchestrationResult

__all__ = [
    "BaseAgent",
    "AgentResult",
    "BaseOrchestrator",
    "StepResult",
    "OrchestrationResult",
]
