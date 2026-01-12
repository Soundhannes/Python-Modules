"""
StructureAgent - Strukturiert Text zu Datenbank-Einträgen.

Wird nur aufgerufen bei:
- intent = "create": Neue Entity strukturieren
- intent = "update": Änderungen extrahieren
"""

from typing import Dict, Any, Optional
from datetime import datetime
from .configurable_agent import ConfigurableAgent


class StructureAgent(ConfigurableAgent):
    """
    Spezialisierter Agent für Daten-Strukturierung.

    Lädt Konfiguration aus agent_configs mit agent_name='structure_agent'.
    """

    def __init__(self, db_connection):
        super().__init__("structure_agent", db_connection)

    def structure(
        self,
        text: str,
        intent: str,
        category: Optional[str] = None,
        target: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Strukturiert Text zu Datenbank-Eintrag.

        Args:
            text: User-Eingabe
            intent: "create" oder "update"
            category: Ziel-Kategorie (people, projects, ideas, tasks, calendar_events)
            target: Bestehendes Objekt bei update {table, id, data}

        Returns:
            Bei CREATE:
            {
                data: {strukturierte Felder gemäß Entity-Schema},
                linked_entities: {person_name, project_name}
            }

            Bei UPDATE:
            {
                changes: {nur geänderte Felder}
            }
        """
        current_date = datetime.now().strftime("%Y-%m-%d")

        return self.execute(
            text=text,
            intent=intent,
            category=category or "null",
            target=target or "null",
            current_date=current_date
        )


def get_structure_agent(db_connection) -> StructureAgent:
    """Factory-Funktion für StructureAgent."""
    return StructureAgent(db_connection)
