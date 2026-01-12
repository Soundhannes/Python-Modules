"""
StructureAgent - Strukturiert Text zu Datenbank-Eintraegen.

Nutzt TextPreprocessor fuer deterministische Vorverarbeitung.
Wird nur aufgerufen bei:
- intent = "create": Neue Entity strukturieren
- intent = "update": Aenderungen extrahieren
"""

from typing import Dict, Any, Optional
from datetime import datetime
from .configurable_agent import ConfigurableAgent
from ..services.text_preprocessor import get_text_preprocessor


class StructureAgent(ConfigurableAgent):
    """
    Spezialisierter Agent fuer Daten-Strukturierung.

    Laedt Konfiguration aus agent_configs mit agent_name='structure_agent'.
    Nutzt TextPreprocessor fuer Datums-/Priority-/Status-Aufloesung.
    """

    def __init__(self, db_connection):
        super().__init__("structure_agent", db_connection)
        self.preprocessor = get_text_preprocessor()

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
                data: {strukturierte Felder gemaess Entity-Schema},
                linked_entities: {person_name, project_name}
            }

            Bei UPDATE:
            {
                changes: {nur geaenderte Felder}
            }
        """
        # Vorverarbeitung mit TextPreprocessor
        cat = category or "tasks"
        context = self.preprocessor.get_context_for_prompt(text, cat)

        # Alle Template-Variablen uebergeben (fuer beide Kategorien)
        return self.execute(
            text=text,
            intent=intent,
            category=cat,
            target=target or "null",
            current_date=context["current_date"],
            resolved_due_date=context["resolved_due_date"] or "null",
            resolved_start_time=context["resolved_start_time"] or "null",
            resolved_time=context["resolved_time"] or "null",
            resolved_priority=context["resolved_priority"],
            resolved_status=context["resolved_status"]
        )


def get_structure_agent(db_connection) -> StructureAgent:
    """Factory-Funktion fuer StructureAgent."""
    return StructureAgent(db_connection)
