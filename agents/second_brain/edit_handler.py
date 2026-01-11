"""
Edit-Handler für ! Änderungen.

Verarbeitet Änderungswünsche:
- Status ändern (unkritisch → direkt ausführen)
- Termine ändern (unkritisch → direkt ausführen)
- Personendaten ändern (kritisch → Bestätigung)
- Löschen (kritisch → Bestätigung)
"""

import sys
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

sys.path.insert(0, "/opt/python-modules")

from .configurable_agent import ConfigurableAgent


class EditType(Enum):
    """Typ der Änderung."""
    CRITICAL = "critical"      # Personendaten, Löschen → Bestätigung nötig
    NORMAL = "normal"          # Status, Termine → Feedback nach Ausführung


# Erlaubte Tabellen für Edits
ALLOWED_TABLES = ["people", "projects", "ideas", "tasks", "events"]

# Kritische Operationen
CRITICAL_OPERATIONS = [
    "delete",
    "people.name",
    "people.context",  # Enthält oft Kontaktdaten
]


@dataclass
class EditResult:
    """Ergebnis einer Edit-Operation."""
    success: bool
    message: str
    needs_confirmation: bool = False
    confirmation_question: Optional[str] = None
    pending_action: Optional[Dict] = None
    error: Optional[str] = None


class EditHandler(ConfigurableAgent):
    """
    Handler für ! Änderungen.
    
    Interpretiert natürlichsprachliche Änderungswünsche
    und führt sie aus (mit/ohne Bestätigung).
    """

    def __init__(self, db_connection):
        super().__init__("edit_agent", db_connection)

    def handle(self, instruction: str, confirmed: bool = False, pending_action: Dict = None) -> EditResult:
        """
        Verarbeitet einen Änderungswunsch.
        
        Args:
            instruction: Der Änderungswunsch (ohne ! Prefix)
            confirmed: True wenn User bereits bestätigt hat
            pending_action: Die wartende Aktion bei Bestätigung
            
        Returns:
            EditResult mit Status und ggf. Bestätigungsfrage
        """
        if not instruction.strip() and not pending_action:
            return EditResult(
                success=False,
                message="Bitte gib an, was geändert werden soll.",
                error="empty_instruction"
            )

        # Wenn bestätigt und pending_action vorhanden → ausführen
        if confirmed and pending_action:
            return self._execute_action(pending_action)

        # LLM fragen was zu tun ist
        try:
            llm_result = self.execute(
                instruction=instruction,
                tables=json.dumps(ALLOWED_TABLES),
                today=self._get_today()
            )

            if llm_result.get("error"):
                return EditResult(
                    success=False,
                    message="Konnte die Anweisung nicht verstehen.",
                    error=llm_result.get("error")
                )

            # Action extrahieren
            action = llm_result.get("action", {})
            if not action:
                return EditResult(
                    success=False,
                    message="Keine gültige Aktion erkannt.",
                    error="no_action"
                )

            # Tabellencheck
            table = action.get("table")
            if table not in ALLOWED_TABLES:
                return EditResult(
                    success=False,
                    message="Änderungen an dieser Tabelle nicht erlaubt.",
                    error="forbidden_table"
                )

            # Prüfen ob kritisch
            is_critical = self._is_critical(action)

            if is_critical and not confirmed:
                # Bestätigung erfragen
                return EditResult(
                    success=True,
                    message="",
                    needs_confirmation=True,
                    confirmation_question=self._build_confirmation(action, llm_result),
                    pending_action=action
                )
            else:
                # Direkt ausführen
                return self._execute_action(action)

        except Exception as e:
            return EditResult(
                success=False,
                message=f"Fehler: {str(e)}",
                error=str(e)
            )

    def _is_critical(self, action: Dict) -> bool:
        """Prüft ob die Aktion kritisch ist."""
        operation = action.get("operation", "")
        table = action.get("table", "")
        field = action.get("field", "")

        # Löschen ist immer kritisch
        if operation == "delete":
            return True

        # Personendaten sind kritisch
        if table == "people" and field in ["name", "context"]:
            return True

        return False

    def _build_confirmation(self, action: Dict, llm_result: Dict) -> str:
        """Baut die Bestätigungsfrage."""
        operation = action.get("operation", "update")
        table = action.get("table", "")
        
        if operation == "delete":
            target = action.get("target_name", f"#{action.get('id', '?')}")
            return f"Soll '{target}' aus {table} wirklich gelöscht werden?"
        
        if table == "people":
            field = action.get("field", "")
            new_value = action.get("new_value", "")
            target = action.get("target_name", "diese Person")
            return f"Soll {field} von '{target}' auf '{new_value}' geändert werden?"
        
        return llm_result.get("confirmation_question", "Diese Änderung durchführen?")

    def _execute_action(self, action: Dict) -> EditResult:
        """Führt die Aktion aus."""
        operation = action.get("operation", "update")
        table = action.get("table")
        entity_id = action.get("id")

        try:
            if operation == "delete":
                self.db.execute(f"DELETE FROM {table} WHERE id = %s", (entity_id,))
                return EditResult(
                    success=True,
                    message=f"Eintrag #{entity_id} aus {table} gelöscht."
                )

            elif operation == "update":
                field = action.get("field")
                new_value = action.get("new_value")

                if not field or new_value is None:
                    return EditResult(
                        success=False,
                        message="Feld oder Wert fehlt.",
                        error="missing_field_or_value"
                    )

                # Update ausführen
                self.db.execute(
                    f"UPDATE {table} SET {field} = %s, updated_at = NOW() WHERE id = %s",
                    (new_value, entity_id)
                )

                return EditResult(
                    success=True,
                    message=f"{table.capitalize()} #{entity_id}: {field} wurde geändert."
                )

            else:
                return EditResult(
                    success=False,
                    message=f"Unbekannte Operation: {operation}",
                    error="unknown_operation"
                )

        except Exception as e:
            return EditResult(
                success=False,
                message=f"Fehler beim Ausführen: {str(e)}",
                error=str(e)
            )

    def _get_today(self) -> str:
        """Gibt aktuelles Datum zurück."""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d")


def get_edit_handler(db_connection) -> EditHandler:
    """Factory-Funktion für EditHandler."""
    return EditHandler(db_connection)
