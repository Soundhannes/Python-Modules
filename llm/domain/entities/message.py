"""
Message Entity - Repräsentiert eine Chat-Nachricht.

Domain Layer: Reine Geschäftslogik, keine externen Abhängigkeiten.
"""

from dataclasses import dataclass


@dataclass
class Message:
    """
    Eine einzelne Nachricht im Chat.
    
    Attributes:
        role: Wer spricht? "user" oder "assistant"
        content: Der Nachrichtentext
    
    Beispiel:
        Message(role="user", content="Was ist Python?")
    """
    role: str
    content: str
