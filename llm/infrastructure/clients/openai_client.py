"""
OpenAI Client - Verbindung zu GPT.

Infrastructure Layer: Konkrete Implementierung des LLM-Interfaces.
"""

from openai import OpenAI
from typing import List, Optional

from ...domain import LLMClient, Message, LLMResponse


class OpenAIClient(LLMClient):
    """Client für OpenAI GPT API."""
    
    MODELS = [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-4",
        "gpt-3.5-turbo",
    ]
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self._client = OpenAI(api_key=api_key)
    
    def chat(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        max_tokens: int = 1024,
        system_prompt: Optional[str] = None
    ) -> LLMResponse:
        """
        Sendet Chat-Nachricht an OpenAI API.
        
        Args:
            messages: Liste von Nachrichten
            model: Modell-ID (optional, nutzt default)
            max_tokens: Maximale Antwort-Länge
            system_prompt: System-Prompt für Kontext/Anweisungen
            
        Returns:
            LLMResponse mit Antwort
        """
        use_model = model or self.default_model
        
        api_messages = []
        
        # System-Prompt als erste Message einfügen
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})
        
        # User/Assistant Messages hinzufügen
        for msg in messages:
            api_messages.append({"role": msg.role, "content": msg.content})
        
        response = self._client.chat.completions.create(
            model=use_model,
            max_tokens=max_tokens,
            messages=api_messages
        )
        
        return LLMResponse(
            content=response.choices[0].message.content,
            model=use_model,
            tokens_used=response.usage.total_tokens,
            provider=self.provider_name
        )
    
    def get_available_models(self) -> List[str]:
        return self.MODELS.copy()
    
    @property
    def provider_name(self) -> str:
        return "openai"
    
    @property
    def default_model(self) -> str:
        return "gpt-4o"
