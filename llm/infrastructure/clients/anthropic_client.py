"""
Anthropic Client - Verbindung zu Claude.

Infrastructure Layer: Konkrete Implementierung des LLM-Interfaces.
"""

import anthropic
from typing import List, Optional

from ...domain import LLMClient, Message, LLMResponse


class AnthropicClient(LLMClient):
    """Client für Anthropic Claude API."""
    
    MODELS = [
        "claude-sonnet-4-20250514",
        "claude-opus-4-20250514", 
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
        "claude-3-haiku-20240307",
    ]
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self._client = anthropic.Anthropic(api_key=api_key)
    
    def chat(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        max_tokens: int = 1024,
        system_prompt: Optional[str] = None
    ) -> LLMResponse:
        """
        Sendet Chat-Nachricht an Claude API.
        
        Args:
            messages: Liste von Nachrichten
            model: Modell-ID (optional, nutzt default)
            max_tokens: Maximale Antwort-Länge
            system_prompt: System-Prompt für Kontext/Anweisungen
            
        Returns:
            LLMResponse mit Antwort
        """
        use_model = model or self.default_model
        
        api_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
        
        # API-Aufruf mit optionalem System-Prompt
        kwargs = {
            "model": use_model,
            "max_tokens": max_tokens,
            "messages": api_messages
        }
        
        if system_prompt:
            kwargs["system"] = system_prompt
        
        response = self._client.messages.create(**kwargs)
        
        return LLMResponse(
            content=response.content[0].text,
            model=use_model,
            tokens_used=response.usage.input_tokens + response.usage.output_tokens,
            provider=self.provider_name
        )
    
    def get_available_models(self) -> List[str]:
        return self.MODELS.copy()
    
    @property
    def provider_name(self) -> str:
        return "anthropic"
    
    @property
    def default_model(self) -> str:
        return "claude-sonnet-4-20250514"
