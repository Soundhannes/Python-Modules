"""
Google Client - Verbindung zu Gemini.

Infrastructure Layer: Konkrete Implementierung des LLM-Interfaces.
"""

import google.generativeai as genai
from typing import List, Optional

from ...domain import LLMClient, Message, LLMResponse


class GoogleClient(LLMClient):
    """Client für Google Gemini API."""
    
    MODELS = [
        "gemini-2.0-flash-exp",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
        "gemini-1.0-pro",
    ]
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        genai.configure(api_key=api_key)
    
    def chat(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        max_tokens: int = 1024,
        system_prompt: Optional[str] = None
    ) -> LLMResponse:
        """
        Sendet Chat-Nachricht an Google Gemini API.
        
        Args:
            messages: Liste von Nachrichten
            model: Modell-ID (optional, nutzt default)
            max_tokens: Maximale Antwort-Länge
            system_prompt: System-Prompt für Kontext/Anweisungen
            
        Returns:
            LLMResponse mit Antwort
        """
        use_model = model or self.default_model
        
        # Model mit optionalem System-Prompt erstellen
        model_kwargs = {}
        if system_prompt:
            model_kwargs["system_instruction"] = system_prompt
            
        model_instance = genai.GenerativeModel(use_model, **model_kwargs)
        
        history = []
        for msg in messages[:-1]:
            role = "model" if msg.role == "assistant" else "user"
            history.append({"role": role, "parts": [msg.content]})
        
        chat = model_instance.start_chat(history=history)
        
        last_message = messages[-1].content
        response = chat.send_message(
            last_message,
            generation_config=genai.GenerationConfig(max_output_tokens=max_tokens)
        )
        
        tokens = 0
        if hasattr(response, "usage_metadata"):
            tokens = response.usage_metadata.total_token_count
        
        return LLMResponse(
            content=response.text,
            model=use_model,
            tokens_used=tokens,
            provider=self.provider_name
        )
    
    def get_available_models(self) -> List[str]:
        return self.MODELS.copy()
    
    @property
    def provider_name(self) -> str:
        return "google"
    
    @property
    def default_model(self) -> str:
        return "gemini-1.5-flash"
