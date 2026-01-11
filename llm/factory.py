"""
Factory - Client-Vermittler.

Zentraler Einstiegspunkt: get_client("anthropic") -> AnthropicClient

API Key Suche (in dieser Reihenfolge):
1. Direkt übergeben (api_key Parameter)
2. Aus Datenbank (api_keys Tabelle)
3. Aus Umgebungsvariable (Fallback)
"""

import os
from typing import Optional

from .domain import LLMClient
from .infrastructure import AnthropicClient, OpenAIClient, GoogleClient
from .infrastructure import get_api_key_repository


# Provider-Name -> Client-Klasse
PROVIDERS = {
    "anthropic": AnthropicClient,
    "openai": OpenAIClient,
    "google": GoogleClient,
}

# Provider -> Umgebungsvariable (Fallback)
ENV_KEYS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google": "GOOGLE_API_KEY",
}


def _get_api_key(provider: str, api_key: Optional[str] = None) -> str:
    """
    Ermittelt den API Key für einen Provider.
    
    Suchstrategie:
    1. Direkt übergeben -> verwenden
    2. In Datenbank suchen -> verwenden
    3. Umgebungsvariable -> verwenden
    4. Nichts gefunden -> Fehler
    
    Args:
        provider: Provider-Name
        api_key: Optional direkt übergebener Key
    
    Returns:
        API Key
    
    Raises:
        ValueError: Kein Key gefunden
    """
    # 1. Direkt übergeben
    if api_key:
        return api_key
    
    # 2. Aus Datenbank
    try:
        repo = get_api_key_repository()
        db_key = repo.get_key(provider)
        if db_key:
            return db_key
    except Exception:
        # DB nicht verfügbar -> weiter zu Fallback
        pass
    
    # 3. Aus Umgebungsvariable
    env_var = ENV_KEYS.get(provider)
    if env_var:
        env_key = os.getenv(env_var)
        if env_key:
            return env_key
    
    # 4. Nichts gefunden
    raise ValueError(
        f"Kein API Key für {provider}. "
        f"Optionen: 1) In DB speichern, 2) {ENV_KEYS.get(provider, 'ENV')} setzen, 3) api_key= übergeben"
    )


def get_client(provider: str, api_key: Optional[str] = None) -> LLMClient:
    """
    Erstellt einen LLM-Client für den gewünschten Provider.
    
    Args:
        provider: "anthropic", "openai" oder "google"
        api_key: API-Key (optional, sonst aus DB oder Umgebung)
    
    Returns:
        Passender LLM-Client
    
    Raises:
        ValueError: Unbekannter Provider oder kein Key
    
    Beispiel:
        client = get_client("anthropic")
        response = client.chat([Message(role="user", content="Hi!")])
    """
    provider = provider.lower()
    
    if provider not in PROVIDERS:
        available = ", ".join(PROVIDERS.keys())
        raise ValueError(f"Unbekannter Provider: {provider}. Verfügbar: {available}")
    
    # Key ermitteln (DB -> ENV -> Fehler)
    resolved_key = _get_api_key(provider, api_key)
    
    # Client erstellen
    client_class = PROVIDERS[provider]
    return client_class(resolved_key)


def list_providers() -> list:
    """Gibt alle verfügbaren Provider zurück."""
    return list(PROVIDERS.keys())


def list_configured_providers() -> list:
    """
    Gibt Provider zurück, für die ein Key konfiguriert ist.
    
    Prüft DB und Umgebungsvariablen.
    """
    configured = []
    
    for provider in PROVIDERS:
        try:
            _get_api_key(provider)
            configured.append(provider)
        except ValueError:
            pass
    
    return configured
