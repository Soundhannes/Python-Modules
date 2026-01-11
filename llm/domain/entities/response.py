"""
LLMResponse Entity - Repräsentiert eine LLM-Antwort.

Domain Layer: Reine Geschäftslogik, keine externen Abhängigkeiten.
"""

from dataclasses import dataclass


@dataclass
class LLMResponse:
    """
    Antwort vom LLM.
    
    Attributes:
        content: Die generierte Antwort
        model: Welches Modell wurde verwendet
        tokens_used: Anzahl verbrauchter Tokens
        provider: Der Provider ("anthropic", "openai", "google")
    """
    content: str
    model: str
    tokens_used: int
    provider: str
