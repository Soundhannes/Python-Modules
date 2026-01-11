"""
LLMClient Interface - Der Vertrag für alle LLM-Clients.

Domain Layer: Definiert WAS gemacht wird, nicht WIE.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from ..entities import Message, LLMResponse


class LLMClient(ABC):
    """
    Abstrakte Basis-Klasse für LLM Clients.
    
    Definiert den Vertrag: Welche Methoden MÜSSEN existieren.
    Konkrete Klassen (AnthropicClient, etc.) erben und implementieren.
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    @abstractmethod
    def chat(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        max_tokens: int = 1024
    ) -> LLMResponse:
        """Sende Nachrichten an das LLM und erhalte eine Antwort."""
        pass
    
    @abstractmethod
    def get_available_models(self) -> List[str]:
        """Gibt alle verfügbaren Modelle dieses Providers zurück."""
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name des Providers."""
        pass
    
    @property
    @abstractmethod
    def default_model(self) -> str:
        """Das Standard-Modell dieses Providers."""
        pass
