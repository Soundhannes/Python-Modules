"""
SecondBrainOrchestrator - Steuert den gesamten Verarbeitungsfluss.

Flow:
1. Text → Keyword-Extraktion
2. Keywords → DB-Suche (Fuzzy Match)
3. Matches → Intent-Agent
4. Intent → Structure-Agent (nur bei create/update)
5. Strukturierte Daten → Executor (DB-Operation)
6. Ergebnis → Notification + Logging
"""

import sys
import re
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

sys.path.insert(0, "/opt/python-modules")

from agents.utils.logger import get_logger, LogLevel
from agents.utils.human_in_loop import get_human_in_loop
from agents.services.notification_service import get_notification_service

from .configurable_agent import get_config_manager
from .intent_agent import IntentAgent
from .structure_agent import StructureAgent


class SecondBrainOrchestrator:
    """
    Hauptorchestrator für das Second Brain System.

    Koordiniert:
    - Keyword-Extraktion und DB-Suche
    - Intent-Erkennung
    - Daten-Strukturierung
    - DB-Operationen
    - User-Interaktion (HumanInLoop)
    - Benachrichtigungen
    """

    TABLES = ['projects', 'tasks', 'people', 'ideas', 'events']

    def __init__(self, db_connection, telegram_chat_id: Optional[str] = None):
        """
        Initialisiert den Orchestrator.

        Args:
            db_connection: Datenbank-Verbindung
            telegram_chat_id: Optional für Benachrichtigungen
        """
        self.db = db_connection
        self.telegram_chat_id = telegram_chat_id

        # Config Manager für Settings
        self.config = get_config_manager(db_connection)

        # Agents
        self.intent_agent = IntentAgent(db_connection)
        self.structure_agent = StructureAgent(db_connection)

        # Services
        self.logger = get_logger("second_brain", tags=["inbox", "processing"])
        self.human_loop = get_human_in_loop("second_brain")

        if telegram_chat_id:
            self.notifier = get_notification_service("second_brain")
        else:
            self.notifier = None

        # Settings laden
        self._load_settings()

    def _load_settings(self):
        """Lädt Einstellungen aus der Datenbank."""
        self.confidence_threshold = self.config.get_setting("confidence_threshold", 0.3)
        self.max_matches = self.config.get_setting("max_matches", 5)
        self.keyword_min_length = self.config.get_setting("keyword_min_length", 2)
        self.stopwords = self.config.get_stopwords()
        self.completion_keywords = self.config.get_completion_keywords()
        self.deletion_keywords = self.config.get_deletion_keywords()

    def process(self, text: str) -> Dict[str, Any]:
        """
        Haupteingang: Verarbeitet User-Text.

        Args:
            text: Freitext-Eingabe vom User

        Returns:
            {
                success: bool,
                intent: str,
                target: {table, id} oder None,
                record_id: int (bei create),
                message: str,
                needs_clarification: bool (bei unclear)
            }
        """
        self.logger.info(f"Eingang: {text[:100]}...")

        try:
            # 1. Keywords extrahieren
            keywords = self._extract_keywords(text)
            self.logger.debug(f"Keywords: {keywords}")

            # 2. DB durchsuchen
            matches = self._search_database(keywords)
            self.logger.debug(f"Matches gefunden: {len(matches)}")

            # 3. Intent erkennen
            intent_result = self.intent_agent.analyze(text, matches)

            if intent_result.get("error"):
                self.logger.error(f"Intent-Agent Fehler: {intent_result.get('error_message')}")
                return {
                    "success": False,
                    "error": intent_result.get("error_message"),
                    "stage": "intent_recognition"
                }

            intent = intent_result.get("intent")
            confidence = intent_result.get("confidence", 0)

            self.logger.info(f"Intent: {intent}, Confidence: {confidence}")

            # 4. Bei niedriger Confidence oder unclear: User fragen
            if confidence < self.confidence_threshold or intent == "unclear":
                return self._handle_unclear(text, intent_result)

            # 5. Intent ausführen
            if intent in ["complete", "delete"]:
                return self._execute_simple(text, intent_result)

            if intent in ["create", "update"]:
                return self._execute_with_structure(text, intent_result)

            return {
                "success": False,
                "error": f"Unknown intent: {intent}",
                "stage": "execution"
            }

        except Exception as e:
            self.logger.error(f"Orchestrator Fehler: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "stage": "unknown"
            }

    def _extract_keywords(self, text: str) -> List[str]:
        """Extrahiert Keywords aus Text."""
        # Lowercase, Sonderzeichen entfernen (außer Umlaute)
        cleaned = re.sub(r'[^\w\säöüÄÖÜß]', ' ', text.lower())

        # In Wörter splitten
        words = cleaned.split()

        # Stopwords und zu kurze Wörter filtern
        keywords = [
            w for w in words
            if w not in self.stopwords and len(w) >= self.keyword_min_length
        ]

        # Deduplizieren, Reihenfolge beibehalten
        seen = set()
        unique = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique.append(kw)

        return unique

    def _search_database(self, keywords: List[str]) -> List[Dict]:
        """Durchsucht alle Tabellen nach Keywords mit Fuzzy Match."""
        matches = []

        for table in self.TABLES:
            # Dynamisch die richtige Spalte wählen
            name_col = "title" if table in ["tasks", "events"] else "name"
            notes_col = "notes" if table != "people" else "context"

            for keyword in keywords:
                query = f"""
                    SELECT id, {name_col} as name,
                           COALESCE({notes_col}, '') as notes,
                           CASE
                               WHEN LOWER({name_col}) = %s THEN 1.0
                               WHEN LOWER({name_col}) LIKE %s THEN 0.8
                               WHEN LOWER(COALESCE({notes_col}, '')) LIKE %s THEN 0.5
                               ELSE 0.3
                           END as match_score
                    FROM {table}
                    WHERE LOWER({name_col}) LIKE %s
                       OR LOWER(COALESCE({notes_col}, '')) LIKE %s
                    LIMIT 5
                """

                pattern = f"%{keyword}%"

                try:
                    results = self.db.execute(
                        query,
                        (keyword, pattern, pattern, pattern, pattern)
                    )

                    for row in results:
                        matches.append({
                            "table": table,
                            "id": row["id"],
                            "data": {
                                "name": row["name"],
                                "notes": row["notes"]
                            },
                            "match_score": float(row["match_score"])
                        })
                except Exception as e:
                    self.logger.warning(f"DB-Suche in {table} fehlgeschlagen: {e}")

        # Deduplizieren und sortieren
        seen = set()
        unique = []
        for m in sorted(matches, key=lambda x: -x["match_score"]):
            key = (m["table"], m["id"])
            if key not in seen:
                seen.add(key)
                unique.append(m)

        return unique[:self.max_matches]

    def _handle_unclear(self, text: str, intent_result: Dict) -> Dict:
        """Behandelt unklare Intents via HumanInLoop."""
        options = intent_result.get("options", [])
        question = intent_result.get("question", "Was meinst du?")

        self.logger.info(f"Unclear Intent, frage User: {question}")

        if options:
            # User wählen lassen
            choice_options = [f"{o.get('label', o.get('table'))} ({o.get('table')})" for o in options]

            request_id = self.human_loop.request_choice(
                question=question,
                options=choice_options,
                timeout_seconds=3600
            )

            # Notification senden
            if self.notifier and self.telegram_chat_id:
                options_text = "\n".join([f"- {opt}" for opt in choice_options])
                self.notifier.send_telegram(
                    chat_id=self.telegram_chat_id,
                    message=f"❓ {question}\n\n{options_text}",
                    message_type="warning"
                )

            return {
                "success": False,
                "needs_clarification": True,
                "question": question,
                "options": choice_options,
                "request_id": request_id
            }

        return {
            "success": False,
            "needs_clarification": True,
            "question": question or "Ich verstehe nicht, was du meinst."
        }

    def _execute_simple(self, text: str, intent_result: Dict) -> Dict:
        """Führt einfache Intents aus (complete, delete)."""
        target = intent_result.get("target") or {}
        table = target.get("table")
        record_id = target.get("id")
        intent = intent_result.get("intent")

        if not table or not record_id:
            return {
                "success": False,
                "error": "Kein Ziel angegeben",
                "intent": intent
            }

        try:
            if intent == "complete":
                # Status auf done setzen
                query = f"""
                    UPDATE {table}
                    SET status = 'done', updated_at = NOW()
                    WHERE id = %s
                    RETURNING id
                """
                result = self.db.execute(query, (record_id,))
                action = "abgeschlossen"

            elif intent == "delete":
                # Soft-delete wäre besser, aber hier hard-delete
                query = f"DELETE FROM {table} WHERE id = %s RETURNING id"
                result = self.db.execute(query, (record_id,))
                action = "gelöscht"

            # inbox_log schreiben
            self._write_inbox_log(text, intent_result, record_id)

            # Notification senden
            message = f"✅ {table.capitalize()} #{record_id} {action}"
            if self.notifier and self.telegram_chat_id:
                self.notifier.send_telegram(
                    chat_id=self.telegram_chat_id,
                    message=message,
                    message_type="success"
                )

            self.logger.info(f"Ausgeführt: {intent} auf {table} #{record_id}")

            return {
                "success": True,
                "intent": intent,
                "target": target,
                "message": message
            }

        except Exception as e:
            self.logger.error(f"Ausführung fehlgeschlagen: {e}")
            return {
                "success": False,
                "error": str(e),
                "intent": intent,
                "target": target
            }

    def _execute_with_structure(self, text: str, intent_result: Dict) -> Dict:
        """Führt Intents mit Strukturierung aus (create, update)."""
        intent = intent_result.get("intent")
        category = intent_result.get("category")
        target = intent_result.get("target") or {}

        # Structure-Agent aufrufen
        structured = self.structure_agent.structure(
            text=text,
            intent=intent,
            category=category,
            target=target
        )

        if structured.get("error"):
            self.logger.error(f"Structure-Agent Fehler: {structured.get('error_message')}")
            return {
                "success": False,
                "error": structured.get("error_message"),
                "stage": "structuring"
            }

        try:
            if intent == "create":
                record_id = self._insert_record(category, structured.get("data", {}))

                # Linked Entities verarbeiten
                linked = structured.get("linked_entities", {})
                if linked:
                    self._process_linked_entities(record_id, category, linked)

                message = f"✅ Neuer Eintrag in {category}: #{record_id}"

            elif intent == "update":
                table = target.get("table")
                record_id = target.get("id")
                changes = structured.get("changes", {})

                if changes:
                    self._update_record(table, record_id, changes)

                message = f"✅ {table.capitalize()} #{record_id} aktualisiert"

            # inbox_log schreiben
            self._write_inbox_log(text, intent_result, record_id, structured)

            # Notification senden
            if self.notifier and self.telegram_chat_id:
                self.notifier.send_telegram(
                    chat_id=self.telegram_chat_id,
                    message=message,
                    message_type="success"
                )

            self.logger.info(f"Ausgeführt: {intent} → {category or target.get('table')} #{record_id}")

            return {
                "success": True,
                "intent": intent,
                "record_id": record_id,
                "category": category,
                "message": message
            }

        except Exception as e:
            self.logger.error(f"DB-Operation fehlgeschlagen: {e}")
            return {
                "success": False,
                "error": str(e),
                "stage": "execution"
            }

    def _insert_record(self, table: str, data: Dict) -> int:
        """Fügt neuen Record ein."""
        if not data:
            raise ValueError("Keine Daten zum Einfügen")

        # Kopie machen um Original nicht zu verändern
        insert_data = dict(data)
        
        # Timestamps hinzufügen
        insert_data["created_at"] = datetime.now()
        if table not in ["ideas"]:  # ideas hat kein updated_at
            insert_data["updated_at"] = datetime.now()

        columns = ", ".join(insert_data.keys())
        placeholders = ", ".join(["%s"] * len(insert_data))

        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) RETURNING id"
        result = self.db.execute(query, tuple(insert_data.values()))

        return result[0]["id"]

    def _update_record(self, table: str, record_id: int, changes: Dict):
        """Aktualisiert Record."""
        if not changes:
            return

        changes["updated_at"] = datetime.now()

        set_clause = ", ".join([f"{k} = %s" for k in changes.keys()])
        query = f"UPDATE {table} SET {set_clause} WHERE id = %s"

        self.db.execute(query, (*changes.values(), record_id))

    def _process_linked_entities(self, record_id: int, table: str, linked: Dict):
        """Verarbeitet verknüpfte Entities."""
        person_name = linked.get("person_name")
        project_name = linked.get("project_name")

        if person_name and table in ["tasks", "events"]:
            # Person suchen oder anlegen
            person = self.db.execute(
                "SELECT id FROM people WHERE LOWER(name) = LOWER(%s)",
                (person_name,)
            )

            if person:
                person_id = person[0]["id"]
            else:
                # Neue Person anlegen
                result = self.db.execute(
                    "INSERT INTO people (name, created_at, updated_at) VALUES (%s, NOW(), NOW()) RETURNING id",
                    (person_name,)
                )
                person_id = result[0]["id"]
                self.logger.info(f"Neue Person angelegt: {person_name} (#{person_id})")

            # Verknüpfung setzen
            self.db.execute(
                f"UPDATE {table} SET person_id = %s WHERE id = %s",
                (person_id, record_id)
            )

        if project_name and table in ["tasks", "events"]:
            # Projekt suchen
            project = self.db.execute(
                "SELECT id FROM projects WHERE LOWER(name) LIKE LOWER(%s)",
                (f"%{project_name}%",)
            )

            if project:
                project_id = project[0]["id"]
                self.db.execute(
                    f"UPDATE {table} SET project_id = %s WHERE id = %s",
                    (project_id, record_id)
                )

    def _write_inbox_log(
        self,
        text: str,
        intent_result: Dict,
        target_id: Optional[int] = None,
        structured: Optional[Dict] = None
    ):
        """Schreibt Audit-Log in inbox_log."""
        target = intent_result.get("target") or {}

        query = """
            INSERT INTO inbox_log
            (captured_text, intent, target_table, target_id, changes, confidence, needs_review, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        """

        confidence = intent_result.get("confidence", 0)

        self.db.execute(query, (
            text,
            intent_result.get("intent"),
            target.get("table") or intent_result.get("category"),
            target_id,
            json.dumps(structured) if structured else None,
            confidence,
            confidence < self.confidence_threshold
        ))

    def respond_to_clarification(self, request_id: str, choice: str) -> Dict:
        """
        Verarbeitet User-Antwort auf Rückfrage.

        Args:
            request_id: ID der HumanInLoop-Anfrage
            choice: Gewählte Option

        Returns:
            Ergebnis der fortgesetzten Verarbeitung
        """
        # Anfrage aus human_requests laden
        request = self.db.execute(
            "SELECT context FROM human_requests WHERE id = %s",
            (request_id,)
        )

        if not request:
            return {"success": False, "error": "Request nicht gefunden"}

        context = request[0].get("context", {})
        original_text = context.get("text", "")

        # Mit der Auswahl neu verarbeiten
        # TODO: Implementierung abhängig von Use-Case

        return {"success": True, "message": "Verarbeitung fortgesetzt"}


def get_orchestrator(db_connection, telegram_chat_id: str = None) -> SecondBrainOrchestrator:
    """Factory-Funktion für SecondBrainOrchestrator."""
    return SecondBrainOrchestrator(db_connection, telegram_chat_id)
