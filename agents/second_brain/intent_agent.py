"""
IntentAgent - Erkennt Intent aus User-Text und DB-Matches.

Intents:
- create: Neue Entity anlegen
- update: Bestehende Entity ergänzen
- complete: Entity abschließen
- delete: Entity löschen
- unclear: Mehrdeutig, User-Rückfrage nötig
"""

from typing import Dict, Any, List
from .configurable_agent import ConfigurableAgent


class IntentAgent(ConfigurableAgent):
    """
    Spezialisierter Agent für Intent-Erkennung.

    Lädt Konfiguration aus agent_configs mit agent_name='intent_agent'.
    """

    def __init__(self, db_connection):
        super().__init__("intent_agent", db_connection)

    def analyze(self, text: str, matches: List[Dict]) -> Dict[str, Any]:
        """
        Analysiert Text und Matches, erkennt Intent.

        Args:
            text: User-Eingabe
            matches: Liste von DB-Matches [{table, id, data, match_score}, ...]

        Returns:
            {
                intent: create|update|complete|delete|unclear,
                category: people|projects|ideas|tasks|events (nur bei create),
                target: {table, id} (bei update/complete/delete),
                options: [{table, id, label}, ...] (bei unclear),
                question: str (bei unclear),
                confidence: 0.0-1.0,
                reasoning: str
            }
        """
        return self.execute(
            text=text,
            matches=matches
        )


def get_intent_agent(db_connection) -> IntentAgent:
    """Factory-Funktion für IntentAgent."""
    return IntentAgent(db_connection)
