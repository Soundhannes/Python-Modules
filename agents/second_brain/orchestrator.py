"""
SecondBrainOrchestrator - Steuert den gesamten Verarbeitungsfluss.

Flow mit Prefix-Weiche:
- ? = Query → Fragen zu Daten beantworten
- ! = Edit → Änderungen durchführen
- kein Prefix = Create → Neuen Eintrag anlegen (alter Flow)
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
from .prefix_parser import parse_prefix, PrefixType
from .query_handler import QueryHandler
from .edit_handler import EditHandler


class SecondBrainOrchestrator:
    """
    Hauptorchestrator für das Second Brain System.

    Koordiniert:
    - Prefix-Weiche (?, !, default)
    - Query-Handler für Fragen
    - Edit-Handler für Änderungen
    - Create-Flow für neue Einträge
    """

    TABLES = ['projects', 'tasks', 'people', 'ideas', 'events', 'calendar_events']

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

        # Agents für Create-Flow
        self.intent_agent = IntentAgent(db_connection)
        self.structure_agent = StructureAgent(db_connection)

        # Handler für Query/Edit
        self.query_handler = QueryHandler(db_connection)
        self.edit_handler = EditHandler(db_connection)

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

    def process(self, text: str, confirmed: bool = False, pending_action: Dict = None) -> Dict[str, Any]:
        """
        Haupteingang: Verarbeitet User-Text mit Prefix-Weiche.

        Prefixes:
        - ? = Query (Fragen stellen)
        - ! = Edit (Änderungen)
        - kein Prefix = Create (Standard)

        Args:
            text: Freitext-Eingabe vom User
            confirmed: True wenn User eine Bestätigung gegeben hat
            pending_action: Wartende Aktion bei Bestätigung

        Returns:
            Standardisiertes Ergebnis-Dict
        """
        self.logger.info(f"Eingang: {text[:100]}...")

        # Prefix parsen
        parsed = parse_prefix(text)
        self.logger.debug(f"Prefix: {parsed.type}, Text: {parsed.text[:50]}...")

        try:
            # Routing basierend auf Prefix
            if parsed.type == PrefixType.QUERY:
                return self._handle_query(parsed.text)

            elif parsed.type == PrefixType.EDIT:
                return self._handle_edit(parsed.text, confirmed, pending_action)

            else:  # CREATE (Standard)
                return self._handle_create(parsed.text)

        except Exception as e:
            self.logger.error(f"Orchestrator Fehler: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "stage": "unknown"
            }

    def _handle_query(self, text: str) -> Dict[str, Any]:
        """Verarbeitet Query (? Prefix)."""
        self.logger.info(f"Query: {text[:50]}...")

        result = self.query_handler.handle(text)

        return {
            "success": result.success,
            "intent": "query",
            "message": result.answer,
            "data": result.data,
            "error": result.error,
            "action": {"type": "query"}
        }

    def _handle_edit(self, text: str, confirmed: bool, pending_action: Dict) -> Dict[str, Any]:
        """Verarbeitet Edit (! Prefix)."""
        self.logger.info(f"Edit: {text[:50]}... (confirmed={confirmed})")

        result = self.edit_handler.handle(text, confirmed, pending_action)

        if result.needs_confirmation:
            return {
                "success": True,
                "intent": "edit",
                "needs_clarification": True,
                "question": result.confirmation_question,
                "options": [
                    {"label": "Ja", "value": "confirm"},
                    {"label": "Nein", "value": "cancel"}
                ],
                "pending_action": result.pending_action,
                "action": {"type": "edit_pending"}
            }

        # Notification senden bei Erfolg
        if result.success and self.notifier and self.telegram_chat_id:
            self.notifier.send_telegram(
                chat_id=self.telegram_chat_id,
                message=f"✏️ {result.message}",
                message_type="success"
            )

        return {
            "success": result.success,
            "intent": "edit",
            "message": result.message,
            "error": result.error,
            "action": {"type": "edit"}
        }

    def _handle_create(self, text: str) -> Dict[str, Any]:
        """Verarbeitet Create (kein Prefix) - bestehende Logik."""
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

    # ===== Bestehende Helper-Methoden =====

    def _extract_keywords(self, text: str) -> List[str]:
        """Extrahiert Keywords aus Text."""
        cleaned = re.sub(r'[^\w\säöüÄÖÜß]', ' ', text.lower())
        words = cleaned.split()
        keywords = [
            w for w in words
            if w not in self.stopwords and len(w) >= self.keyword_min_length
        ]
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
            name_col = "title" if table in ["tasks", "calendar_events"] else "name"
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
                            "data": {"name": row["name"], "notes": row["notes"]},
                            "match_score": float(row["match_score"])
                        })
                except Exception as e:
                    self.logger.warning(f"DB-Suche in {table} fehlgeschlagen: {e}")

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
            choice_options = [f"{o.get('label', o.get('table'))} ({o.get('table')})" for o in options]
            context = {
                "text": text,
                "intent_result": intent_result,
                "options": options
            }
            request_id = self.human_loop.create_choice_request(
                question=question,
                options=choice_options,
                context=context
            )

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
                query = f"""
                    UPDATE {table}
                    SET status = 'done', updated_at = NOW()
                    WHERE id = %s
                    RETURNING id
                """
                result = self.db.execute(query, (record_id,))
                action = "abgeschlossen"

            elif intent == "delete":
                query = f"UPDATE {table} SET deleted_at = NOW() WHERE id = %s AND deleted_at IS NULL RETURNING id"
                result = self.db.execute(query, (record_id,))
                action = "gelöscht"

            self._write_inbox_log(text, intent_result, record_id)

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
                "message": message,
                "action": {"type": intent, "category": table, "id": record_id}
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

            self._write_inbox_log(text, intent_result, record_id, structured)

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
                "message": message,
                "action": {"type": intent, "category": category, "id": record_id}
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

        insert_data = dict(data)
        insert_data["created_at"] = datetime.now()
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

        if person_name and table in ["tasks", "calendar_events"]:
            person = self.db.execute(
                "SELECT id FROM people WHERE LOWER(name) = LOWER(%s) AND deleted_at IS NULL",
                (person_name,)
            )

            if person:
                person_id = person[0]["id"]
            else:
                result = self.db.execute(
                    "INSERT INTO people (name, created_at, updated_at) VALUES (%s, NOW(), NOW()) RETURNING id",
                    (person_name,)
                )
                person_id = result[0]["id"]
                self.logger.info(f"Neue Person angelegt: {person_name} (#{person_id})")

            self.db.execute(
                f"UPDATE {table} SET person_id = %s WHERE id = %s",
                (person_id, record_id)
            )

        if project_name and table in ["tasks", "calendar_events"]:
            project = self.db.execute(
                "SELECT id FROM projects WHERE LOWER(name) LIKE LOWER(%s) AND deleted_at IS NULL",
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
        confidence = intent_result.get("confidence", 0)

        query = """
            INSERT INTO inbox_log
            (captured_text, intent, target_table, target_id, changes, confidence, needs_review, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        """

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
        """Verarbeitet User-Antwort auf Rückfrage."""
        import re
        
        # Request aus DB holen
        request = self.db.execute(
            "SELECT context, status FROM human_requests WHERE id = %s",
            (request_id,)
        )

        if not request:
            return {"success": False, "error": "Request nicht gefunden"}
        
        if request[0].get("status") != "pending":
            return {"success": False, "error": "Request bereits beantwortet"}

        context = request[0].get("context", {})
        if not context:
            return {"success": False, "error": "Kein Context gespeichert"}

        original_text = context.get("text", "")
        intent_result = context.get("intent_result", {})
        options = context.get("options", [])

        # Table aus Choice extrahieren: "Person Tim (people)" -> "people"
        table_match = re.search(r"\(([a-z_]+)\)$", choice)
        if not table_match:
            return {"success": False, "error": f"Konnte Tabelle nicht aus '{choice}' extrahieren"}
        
        selected_table = table_match.group(1)
        
        # Passende Option finden
        selected_option = None
        for opt in options:
            if opt.get("table") == selected_table:
                selected_option = opt
                break
        
        if not selected_option:
            return {"success": False, "error": f"Option fuer Tabelle '{selected_table}' nicht gefunden"}

        # Intent-Result mit gewaehlter Option aktualisieren
        intent_result["target"] = {
            "table": selected_table,
            "id": selected_option.get("id"),
            "label": selected_option.get("label")
        }
        intent_result["confidence"] = 1.0  # User hat bestaetigt
        
        # Request als beantwortet markieren
        self.human_loop.respond(int(request_id), choice)
        
        # Urspruengliche Aktion ausfuehren
        intent = intent_result.get("intent")
        
        if intent in ["complete", "delete"]:
            return self._execute_simple(original_text, intent_result)
        elif intent == "create":
            return self._execute_create(original_text, intent_result)
        elif intent == "edit":
            return self._handle_edit(original_text, confirmed=True)
        else:
            return {"success": False, "error": f"Unbekannter Intent: {intent}"}


def get_orchestrator(db_connection, telegram_chat_id: str = None) -> SecondBrainOrchestrator:
    """Factory-Funktion für SecondBrainOrchestrator."""
    return SecondBrainOrchestrator(db_connection, telegram_chat_id)
