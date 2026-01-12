"""
Edit-Handler fuer ! Aenderungen.

Verarbeitet Aenderungswuensche:
- Status aendern (unkritisch -> direkt ausfuehren)
- Termine aendern (unkritisch -> direkt ausfuehren)
- Personendaten aendern (kritisch -> Bestaetigung)
- Loeschen (kritisch -> Bestaetigung)

Nutzt TextPreprocessor fuer deterministische Datums-Aufloesung.
"""

import sys
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

sys.path.insert(0, "/opt/python-modules")

from .configurable_agent import ConfigurableAgent
from ..services.text_preprocessor import get_text_preprocessor


class EditType(Enum):
    """Typ der Aenderung."""
    CRITICAL = "critical"      # Personendaten, Loeschen -> Bestaetigung noetig
    NORMAL = "normal"          # Status, Termine -> Feedback nach Ausfuehrung


# Erlaubte Tabellen fuer Edits
ALLOWED_TABLES = ["people", "projects", "ideas", "tasks", "events", "calendar_events"]

# Kritische Operationen
CRITICAL_OPERATIONS = [
    "delete",
    "people.name",
    "people.first_name",
    "people.last_name",
    "people.phone",
    "people.email",
    "people.context",
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
    Handler fuer ! Aenderungen.
    
    Interpretiert natuerlichsprachliche Aenderungswuensche
    und fuehrt sie aus (mit/ohne Bestaetigung).
    """

    def __init__(self, db_connection):
        super().__init__("edit_agent", db_connection)
        self.preprocessor = get_text_preprocessor()

    def handle(self, instruction: str, confirmed: bool = False, pending_action: Dict = None) -> EditResult:
        """
        Verarbeitet einen Aenderungswunsch.
        
        Args:
            instruction: Der Aenderungswunsch (ohne ! Prefix)
            confirmed: True wenn User bereits bestaetigt hat
            pending_action: Die wartende Aktion bei Bestaetigung
            
        Returns:
            EditResult mit Status und ggf. Bestaetigungsfrage
        """
        if not instruction.strip() and not pending_action:
            return EditResult(
                success=False,
                message="Bitte gib an, was geaendert werden soll.",
                error="empty_instruction"
            )

        # Wenn bestaetigt und pending_action vorhanden -> ausfuehren
        if confirmed and pending_action:
            return self._execute_action(pending_action)

        # Vorverarbeitung: Datum aufloesen
        preprocess_result = self.preprocessor.preprocess(instruction)
        resolved_date = preprocess_result.resolved_date or "null"

        # LLM fragen was zu tun ist
        try:
            llm_result = self.execute(
                instruction=instruction,
                tables=json.dumps(ALLOWED_TABLES),
                today=self._get_today(),
                resolved_date=resolved_date
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
                    message="Keine gueltige Aktion erkannt.",
                    error="no_action"
                )

            # Tabellencheck
            table = action.get("table")
            if table not in ALLOWED_TABLES:
                return EditResult(
                    success=False,
                    message="Aenderungen an dieser Tabelle nicht erlaubt.",
                    error="forbidden_table"
                )

            # Pruefen ob kritisch
            is_critical = self._is_critical(action)

            if is_critical and not confirmed:
                # Bestaetigung erfragen
                return EditResult(
                    success=True,
                    message="",
                    needs_confirmation=True,
                    confirmation_question=self._build_confirmation(action, llm_result),
                    pending_action=action
                )
            else:
                # Direkt ausfuehren
                return self._execute_action(action)

        except Exception as e:
            return EditResult(
                success=False,
                message=f"Fehler: {str(e)}",
                error=str(e)
            )

    def _is_critical(self, action: Dict) -> bool:
        """Prueft ob die Aktion kritisch ist."""
        operation = action.get("operation", "")
        table = action.get("table", "")
        field = action.get("field", "")

        # Loeschen ist immer kritisch
        if operation == "delete":
            return True

        # Personendaten sind kritisch
        if table == "people" and field in ["name", "first_name", "last_name", "phone", "email", "context"]:
            return True

        return False

    def _build_confirmation(self, action: Dict, llm_result: Dict) -> str:
        """Baut die Bestaetigungsfrage."""
        operation = action.get("operation", "update")
        table = action.get("table", "")
        
        if operation == "delete":
            target = action.get("target_name", f"#{action.get('id', '?')}")
            return f"Soll '{target}' aus {table} wirklich geloescht werden?"
        
        if table == "people":
            field = action.get("field", "")
            new_value = action.get("new_value", "")
            target = action.get("target_name", "diese Person")
            return f"Soll {field} von '{target}' auf '{new_value}' geaendert werden?"
        
        return llm_result.get("confirmation_question", "Diese Aenderung durchfuehren?")

    def _execute_action(self, action: Dict) -> EditResult:
        """Fuehrt die Aktion aus."""
        operation = action.get("operation", "update")
        table = action.get("table")
        entity_id = action.get("id")

        try:
            if operation == "delete":
                self.db.execute(f"UPDATE {table} SET deleted_at = NOW() WHERE id = %s AND deleted_at IS NULL", (entity_id,))
                return EditResult(
                    success=True,
                    message=f"Eintrag #{entity_id} aus {table} geloescht."
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

                # Update ausfuehren
                self.db.execute(
                    f"UPDATE {table} SET {field} = %s, updated_at = NOW() WHERE id = %s",
                    (new_value, entity_id)
                )

                return EditResult(
                    success=True,
                    message=f"{table.capitalize()} #{entity_id}: {field} wurde geaendert."
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
                message=f"Fehler beim Ausfuehren: {str(e)}",
                error=str(e)
            )

    def _get_today(self) -> str:
        """Gibt aktuelles Datum zurueck."""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d")


def get_edit_handler(db_connection) -> EditHandler:
    """Factory-Funktion fuer EditHandler."""
    return EditHandler(db_connection)
