"""
Prefix-Parser für Chat-Weiche.

Erkennt Prefix am Anfang der Nachricht:
- ? = Query (Fragen stellen)
- ! = Edit (Änderungen)
- kein Prefix = Create (Standard)
"""

from enum import Enum
from dataclasses import dataclass


class PrefixType(Enum):
    """Typ der Nachricht basierend auf Prefix."""
    QUERY = "query"    # ? - Fragen an Daten
    EDIT = "edit"      # ! - Änderungen
    CREATE = "create"  # Default - Neue Einträge


@dataclass
class ParsedInput:
    """Ergebnis des Prefix-Parsings."""
    type: PrefixType
    text: str
    original: str


def parse_prefix(text: str) -> ParsedInput:
    """
    Parst den Prefix aus der Eingabe.
    
    Args:
        text: User-Eingabe
        
    Returns:
        ParsedInput mit type, bereinigtem text und original
    """
    original = text
    text = text.strip()
    
    if not text:
        return ParsedInput(type=PrefixType.CREATE, text="", original=original)
    
    # Prüfe erstes Zeichen
    first_char = text[0]
    
    if first_char == "?":
        # Query - entferne ? und trimme
        remaining = text[1:].strip()
        return ParsedInput(type=PrefixType.QUERY, text=remaining, original=original)
    
    elif first_char == "!":
        # Edit - entferne ! und trimme
        remaining = text[1:].strip()
        return ParsedInput(type=PrefixType.EDIT, text=remaining, original=original)
    
    else:
        # Create - kein Prefix
        return ParsedInput(type=PrefixType.CREATE, text=text, original=original)
