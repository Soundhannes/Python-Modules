"""
Query-Handler für ? Fragen.

Beantwortet Fragen zu Daten aus den Entity-Tabellen:
- people, projects, ideas, tasks, events

Nutzt LLM um die Frage zu interpretieren und SQL zu generieren.
"""

import sys
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

sys.path.insert(0, "/opt/python-modules")

from .configurable_agent import ConfigurableAgent


# Erlaubte Tabellen für Queries
ALLOWED_TABLES = ["people", "projects", "ideas", "tasks", "events"]

# Schema-Info für LLM
TABLE_SCHEMAS = {
    "people": {
        "columns": ["id", "name", "context", "last_contacted_at"],
        "description": "Personen/Kontakte"
    },
    "projects": {
        "columns": ["id", "name", "status", "priority", "notes"],
        "description": "Projekte"
    },
    "ideas": {
        "columns": ["id", "name", "one_liner", "status", "priority", "tags"],
        "description": "Ideen"
    },
    "tasks": {
        "columns": ["id", "title", "due_date", "status", "priority", "project_id", "person_id", "tags"],
        "description": "Aufgaben"
    },
    "events": {
        "columns": ["id", "title", "event_date", "priority", "person_id", "project_id", "notes"],
        "description": "Termine/Events"
    }
}


@dataclass
class QueryResult:
    """Ergebnis einer Query."""
    success: bool
    answer: str
    data: Optional[List[Dict]] = None
    error: Optional[str] = None


class QueryHandler(ConfigurableAgent):
    """
    Handler für ? Fragen.
    
    Interpretiert natürlichsprachliche Fragen und
    generiert SQL-Queries für die erlaubten Tabellen.
    """

    def __init__(self, db_connection):
        super().__init__("query_agent", db_connection)

    def handle(self, question: str) -> QueryResult:
        """
        Beantwortet eine Frage.
        
        Args:
            question: Die Frage des Users (ohne ? Prefix)
            
        Returns:
            QueryResult mit Antwort oder Fehler
        """
        if not question.strip():
            return QueryResult(
                success=False,
                answer="Bitte stelle eine Frage.",
                error="empty_question"
            )

        # LLM fragen was zu tun ist
        try:
            llm_result = self.execute(
                question=question,
                tables=json.dumps(TABLE_SCHEMAS, ensure_ascii=False),
                today=self._get_today()
            )

            if llm_result.get("error"):
                return QueryResult(
                    success=False,
                    answer="Konnte die Frage nicht verstehen.",
                    error=llm_result.get("error")
                )

            # SQL ausführen wenn vorhanden
            sql = llm_result.get("sql")
            if sql:
                # Sicherheitscheck: Nur SELECT erlaubt
                if not sql.strip().upper().startswith("SELECT"):
                    return QueryResult(
                        success=False,
                        answer="Nur Lesezugriff erlaubt.",
                        error="write_attempt"
                    )

                # Tabellencheck
                sql_upper = sql.upper()
                has_allowed_table = any(t.upper() in sql_upper for t in ALLOWED_TABLES)
                has_forbidden = any(
                    t in sql_upper for t in 
                    ["AGENT_CONFIG", "SYSTEM_SETTING", "LANGUAGE_MAPPING", "API_KEY", "USER"]
                )
                
                if has_forbidden or not has_allowed_table:
                    return QueryResult(
                        success=False,
                        answer="Zugriff auf diese Daten nicht erlaubt.",
                        error="forbidden_table"
                    )

                # Query ausführen
                data = self.db.execute(sql)
                
                # Antwort formatieren
                answer = llm_result.get("answer_template", "")
                if data:
                    answer = self._format_answer(answer, data, llm_result)
                else:
                    answer = llm_result.get("no_data_answer", "Keine Daten gefunden.")

                return QueryResult(
                    success=True,
                    answer=answer,
                    data=data
                )
            else:
                # Direkte Antwort ohne SQL
                return QueryResult(
                    success=True,
                    answer=llm_result.get("answer", "Ich verstehe die Frage nicht.")
                )

        except Exception as e:
            return QueryResult(
                success=False,
                answer=f"Fehler bei der Abfrage: {str(e)}",
                error=str(e)
            )

    def _get_today(self) -> str:
        """Gibt aktuelles Datum zurück."""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d")

    def _format_answer(self, template: str, data: List[Dict], llm_result: Dict) -> str:
        """Formatiert die Antwort mit den Daten."""
        if not data:
            return template or "Keine Daten gefunden."
        
        # Einfache Formatierung: Erster Eintrag für Einzelfragen
        if len(data) == 1:
            row = data[0]
            answer = template
            for key, value in row.items():
                answer = answer.replace(f"{{{key}}}", str(value) if value else "-")
            return answer
        
        # Liste für mehrere Einträge
        if len(data) > 1:
            items = []
            for row in data[:10]:  # Max 10 Einträge
                # Hauptfeld finden (title, name)
                main = row.get("title") or row.get("name") or str(row.get("id"))
                items.append(f"• {main}")
            
            result = template + "\n" + "\n".join(items)
            if len(data) > 10:
                result += f"\n... und {len(data) - 10} weitere"
            return result
        
        return template


def get_query_handler(db_connection) -> QueryHandler:
    """Factory-Funktion für QueryHandler."""
    return QueryHandler(db_connection)
