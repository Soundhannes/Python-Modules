"""
Domain Interfaces - Die Verträge/Schnittstellen.

Exportiert:
    LLMClient: Abstrakte Basis für alle LLM-Clients
"""

from .llm_client import LLMClient

__all__ = ["LLMClient"]
