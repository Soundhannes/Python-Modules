"""
LLMResponse Entity - Repraesentiert eine LLM-Antwort.

Domain Layer: Reine Geschaeftslogik, keine externen Abhaengigkeiten.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMResponse:
    """
    Antwort vom LLM.
    
    Attributes:
        content: Die generierte Antwort
        model: Welches Modell wurde verwendet
        tokens_used: Anzahl verbrauchter Tokens (Summe)
        provider: Der Provider ("anthropic", "openai", "google")
        thinking: Optional - Extended Thinking Block (nur Claude)
        input_tokens: Optional - Anzahl Input-Tokens
        output_tokens: Optional - Anzahl Output-Tokens
        stop_reason: Optional - Grund fuer Stop (end_turn, max_tokens, stop_sequence)
    """
    content: str
    model: str
    tokens_used: int
    provider: str
    thinking: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    stop_reason: Optional[str] = None
