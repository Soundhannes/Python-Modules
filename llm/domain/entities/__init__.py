"""
Domain Entities - Die Kern-Datenstrukturen.

Exportiert:
    Message: Eine Chat-Nachricht
    LLMResponse: Eine LLM-Antwort
"""

from .message import Message
from .response import LLMResponse

__all__ = ["Message", "LLMResponse"]
