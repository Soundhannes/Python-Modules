"""
Query-Handler fuer ? Fragen.

Drei-Stufen-Ansatz:
1. Klassifizierung (LLM): Welche Tabelle, welcher Suchtyp
2. Gezielte Query (Logik): SQL basierend auf Klassifizierung
3. Semantische Antwort (LLM): Antwort basierend auf Treffern
"""

import sys
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime

sys.path.insert(0, "/opt/python-modules")

from .configurable_agent import ConfigurableAgent


@dataclass
class QueryResult:
    """Ergebnis einer Query."""
    success: bool
    answer: str
    data: Optional[List[Dict]] = None
    found: Optional[Any] = None
    error: Optional[str] = None


class QueryClassifier(ConfigurableAgent):
    """Stufe 1: Klassifiziert die Frage."""
    
    def __init__(self, db_connection):
        super().__init__("query_classifier", db_connection)


class QueryHandler(ConfigurableAgent):
    """Handler fuer ? Fragen mit Drei-Stufen-Ansatz."""

    def __init__(self, db_connection):
        super().__init__("query_agent", db_connection)
        self.classifier = QueryClassifier(db_connection)

    def handle(self, question: str) -> QueryResult:
        """Beantwortet eine Frage."""
        if not question.strip():
            return QueryResult(
                success=False,
                answer="Bitte stelle eine Frage.",
                error="empty_question"
            )

        try:
            # === STUFE 1: Klassifizierung ===
            classify_result = self.classifier.execute(
                question=question,
                today=self._get_today()
            )
            
            if classify_result.get("error"):
                return QueryResult(
                    success=False,
                    answer="Konnte die Frage nicht verstehen.",
                    error=classify_result.get("error")
                )
            
            table = classify_result.get("table", "calendar_events")
            search_type = classify_result.get("search_type", "all")
            search_value = classify_result.get("search_value")
            
            print(f"[DEBUG] Klassifizierung: table={table}, type={search_type}, value={search_value}")
            
            # === STUFE 2: Gezielte Query ===
            sql = self._build_query(table, search_type, search_value)
            
            if not sql:
                return QueryResult(
                    success=False,
                    answer=f"Unbekannte Tabelle: {table}",
                    error="unknown_table"
                )
            
            print(f"[DEBUG] SQL: {sql}")
            
            data = self.db.execute(sql)
            
            if not data:
                return QueryResult(
                    success=True,
                    answer="Keine passenden Eintraege gefunden.",
                    data=[]
                )
            
            print(f"[DEBUG] Gefunden: {len(data)} Eintraege")
            
            # === STUFE 3: Semantische Antwort ===
            llm_result = self.execute(
                question=question,
                today=self._get_today(),
                table=table,
                data=self._format_data(data)
            )
            
            if llm_result.get("error"):
                return QueryResult(
                    success=False,
                    answer="Konnte die Frage nicht beantworten.",
                    error=llm_result.get("error")
                )
            
            return QueryResult(
                success=True,
                answer=llm_result.get("answer", "Keine Antwort."),
                data=data,
                found=llm_result.get("found")
            )

        except Exception as e:
            print(f"[ERROR] QueryHandler: {str(e)}")
            return QueryResult(
                success=False,
                answer=f"Fehler: {str(e)}",
                error=str(e)
            )

    def _build_query(self, table: str, search_type: str, search_value: str) -> Optional[str]:
        """Baut SQL-Query basierend auf Klassifizierung."""
        
        base_queries = {
            "people": "SELECT id, name, first_name, last_name, phone, email, important_dates, context FROM people WHERE deleted_at IS NULL",
            "calendar_events": "SELECT id, title, start_time, end_time, location, description FROM calendar_events WHERE 1=1",
            "tasks": "SELECT id, title, due_date, status, priority, notes FROM tasks WHERE deleted_at IS NULL",
            "projects": "SELECT id, name, status, priority, notes FROM projects WHERE deleted_at IS NULL",
            "ideas": "SELECT id, name, one_liner, status, priority FROM ideas WHERE deleted_at IS NULL"
        }
        
        if table not in base_queries:
            return None
        
        sql = base_queries[table]
        
        # Suchtyp anwenden
        if search_type == "name" and search_value:
            if table == "people":
                sql += f" AND (name ILIKE '%{search_value}%' OR first_name ILIKE '%{search_value}%' OR last_name ILIKE '%{search_value}%')"
            elif table in ["projects", "ideas"]:
                sql += f" AND name ILIKE '%{search_value}%'"
            else:
                sql += f" AND title ILIKE '%{search_value}%'"
        
        elif search_type == "date_range":
            if table == "calendar_events":
                if search_value == "next_7_days":
                    sql += " AND start_time >= CURRENT_DATE AND start_time < CURRENT_DATE + INTERVAL '7 days'"
                else:
                    sql += " AND start_time >= CURRENT_DATE AND start_time < CURRENT_DATE + INTERVAL '30 days'"
            elif table == "tasks":
                sql += " AND (due_date IS NULL OR due_date >= CURRENT_DATE)"
        
        elif search_type == "fulltext" and search_value:
            if table == "people":
                sql += f" AND (name ILIKE '%{search_value}%' OR context ILIKE '%{search_value}%')"
            elif table == "projects":
                sql += f" AND (name ILIKE '%{search_value}%' OR notes ILIKE '%{search_value}%')"
            else:
                sql += f" AND title ILIKE '%{search_value}%'"
        
        # Sortierung und Limit
        if table == "people":
            sql += " ORDER BY name ASC LIMIT 20"
        elif table == "calendar_events":
            sql += " ORDER BY start_time ASC LIMIT 20"
        elif table == "tasks":
            sql += " ORDER BY priority ASC, due_date ASC NULLS LAST LIMIT 20"
        else:
            sql += " ORDER BY name ASC LIMIT 20"
        
        return sql

    def _format_data(self, rows: List[Dict]) -> str:
        """Formatiert Daten fuer den Prompt."""
        if not rows:
            return "(keine Eintraege)"
        
        lines = []
        for row in rows:
            parts = []
            for key, value in row.items():
                if value is not None and value != "" and value != []:
                    if hasattr(value, "strftime"):
                        value = value.strftime("%d.%m.%Y %H:%M")
                    if isinstance(value, list):
                        value = json.dumps(value, ensure_ascii=False)
                    parts.append(f"{key}: {value}")
            lines.append(" | ".join(parts))
        
        return "\n".join(lines)

    def _get_today(self) -> str:
        return datetime.now().strftime("%d.%m.%Y")


def get_query_handler(db_connection) -> QueryHandler:
    return QueryHandler(db_connection)
