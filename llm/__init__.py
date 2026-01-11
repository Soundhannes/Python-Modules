"""
LLM Module - Einheitliche Schnittstelle für verschiedene LLM-Provider.

Clean Architecture Struktur:
    domain/          - Entities und Interfaces
    infrastructure/  - Clients und Datenbank
    factory.py       - Client-Erstellung

API Key Suche (Reihenfolge):
    1. Direkt übergeben (api_key=...)
    2. Aus Datenbank (api_keys Tabelle)
    3. Aus Umgebungsvariable (Fallback)

Verwendung:
    from llm import get_client, Message
    
    client = get_client("anthropic")
    response = client.chat([Message(role="user", content="Hallo!")])
    print(response.content)
"""

# Domain (Kern-Logik)
from .domain import Message, LLMResponse, LLMClient

# Infrastructure (Implementierungen)
from .infrastructure import AnthropicClient, OpenAIClient, GoogleClient
from .infrastructure import ApiKeyRepository, get_api_key_repository
from .infrastructure import ModelsRepository, get_models_repository

# Factory (Einstiegspunkt)
from .factory import get_client, list_providers, list_configured_providers

__all__ = [
    # Domain
    "Message",
    "LLMResponse", 
    "LLMClient",
    # Infrastructure - Clients
    "AnthropicClient",
    "OpenAIClient",
    "GoogleClient",
    # Infrastructure - Database
    "ApiKeyRepository",
    "get_api_key_repository",
    "ModelsRepository",
    "get_models_repository",
    # Factory
    "get_client",
    "list_providers",
    "list_configured_providers",
]
