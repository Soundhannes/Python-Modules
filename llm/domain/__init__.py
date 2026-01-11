"""
Domain Layer - Kern-Logik ohne externe Abhängigkeiten.

Exportiert:
    Message, LLMResponse: Datenstrukturen
    LLMClient: Interface für LLM-Clients
"""

from .entities import Message, LLMResponse
from .interfaces import LLMClient

__all__ = ["Message", "LLMResponse", "LLMClient"]
