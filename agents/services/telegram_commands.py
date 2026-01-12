"""
TelegramCommandHandler - Verarbeitet /slash-commands in Telegram.

Unterstuetzte Commands:
- /help - Zeigt verfuegbare Commands
- /status - Zeigt System-Status
- /query <text> - Fragt das Second Brain
- /tasks - Zeigt offene Aufgaben
- /today - Zeigt heutige Termine/Tasks
- /daily - Fordert Daily Report an
"""
from typing import Dict, Any, List, Optional
from datetime import datetime


class TelegramCommandHandler:
    """
    Handler fuer Telegram /commands.
    
    Parst eingehende Nachrichten und fuehrt Commands aus.
    """
    
    # Registrierte Commands mit Beschreibungen
    COMMANDS = {
        "help": "Zeigt alle verfuegbaren Befehle",
        "status": "Zeigt System-Status (offene Tasks, etc.)",
        "query": "Fragt das Second Brain (z.B. /query Projekt Alpha)",
        "tasks": "Zeigt deine offenen Aufgaben",
        "today": "Zeigt heutige Termine und Tasks",
        "daily": "Fordert den Daily Report an",
    }
    
    def __init__(self, db=None):
        """
        Args:
            db: DatabaseWrapper fuer DB-Zugriffe
        """
        self.db = db
    
    def parse_command(self, text: str) -> Dict[str, Any]:
        """
        Parst Text auf Command-Struktur.
        
        Args:
            text: Eingehende Nachricht
            
        Returns:
            {
                is_command: bool,
                command: str (wenn is_command),
                args: List[str] (wenn is_command),
                freetext: str (wenn nicht is_command)
            }
        """
        text = text.strip()
        
        if not text.startswith("/"):
            return {
                "is_command": False,
                "freetext": text
            }
        
        parts = text[1:].split()
        command = parts[0].lower() if parts else ""
        args = parts[1:] if len(parts) > 1 else []
        
        return {
            "is_command": True,
            "command": command,
            "args": args
        }
    
    def execute_command(self, command: str, args: List[str]) -> str:
        """
        Fuehrt Command aus und gibt Antwort zurueck.
        
        Args:
            command: Command-Name (ohne /)
            args: Argumente
            
        Returns:
            Antwort-Text
        """
        if command == "help":
            return self._cmd_help()
        elif command == "status":
            return self._cmd_status()
        elif command == "query":
            return self._cmd_query(args)
        elif command == "tasks":
            return self._cmd_tasks()
        elif command == "today":
            return self._cmd_today()
        elif command == "daily":
            return self._cmd_daily()
        else:
            return f"Befehl /{command} ist unbekannt. Nutze /help fuer eine Liste."
    
    def handle(self, text: str) -> Dict[str, Any]:
        """
        Haupteinstieg: Verarbeitet Nachricht.
        
        Args:
            text: Eingehende Nachricht
            
        Returns:
            {
                handled: bool,
                response: str (wenn handled)
            }
        """
        parsed = self.parse_command(text)
        
        if not parsed["is_command"]:
            return {"handled": False}
        
        response = self.execute_command(parsed["command"], parsed["args"])
        return {
            "handled": True,
            "response": response
        }
    
    def get_available_commands(self) -> List[str]:
        """Gibt Liste verfuegbarer Commands zurueck."""
        return list(self.COMMANDS.keys())
    
    # --- Command Implementations ---
    
    def _cmd_help(self) -> str:
        """Zeigt Hilfe an."""
        lines = ["<b>Verfuegbare Befehle:</b>", ""]
        for cmd, desc in self.COMMANDS.items():
            lines.append(f"/{cmd} - {desc}")
        return "\n".join(lines)
    
    def _cmd_status(self) -> str:
        """Zeigt System-Status."""
        if not self.db:
            return "Keine Datenbankverbindung."
        
        try:
            # Offene Tasks zaehlen
            tasks = self.db.execute_one("""
                SELECT COUNT(*) as count FROM tasks 
                WHERE status IN ('next', 'waiting')
            """)
            task_count = tasks.get("count", 0) if tasks else 0
            
            # Heute faellige Tasks
            overdue = self.db.execute_one("""
                SELECT COUNT(*) as count FROM tasks 
                WHERE due_date < CURRENT_DATE AND status NOT IN ('done', 'someday')
            """)
            overdue_count = overdue.get("count", 0) if overdue else 0
            
            # Heutige Termine
            events = self.db.execute_one("""
                SELECT COUNT(*) as count FROM calendar_events 
                WHERE DATE(start_time) = CURRENT_DATE
            """)
            event_count = events.get("count", 0) if events else 0
            
            lines = [
                "<b>Status:</b>",
                f"Offene Aufgaben: {task_count}",
                f"Ueberfaellig: {overdue_count}",
                f"Heutige Termine: {event_count}"
            ]
            return "\n".join(lines)
        except Exception as e:
            return f"Fehler beim Laden: {str(e)}"
    
    def _cmd_query(self, args: List[str]) -> str:
        """Fragt das Second Brain."""
        if not args:
            return "Bitte gib eine Frage an. Beispiel: /query Projekt Alpha"
        
        query_text = " ".join(args)
        
        # Hier wuerde der SecondBrain Orchestrator aufgerufen
        # Fuer jetzt: Placeholder
        return f"Suche nach: {query_text}\n(Query-Integration in Arbeit)"
    
    def _cmd_tasks(self) -> str:
        """Zeigt offene Aufgaben."""
        if not self.db:
            return "Keine Datenbankverbindung."
        
        try:
            tasks = self.db.execute("""
                SELECT title, due_date, priority
                FROM tasks
                WHERE status IN ('next', 'waiting')
                ORDER BY priority ASC, due_date ASC NULLS LAST
                LIMIT 10
            """)
            
            if not tasks:
                return "Keine offenen Aufgaben."
            
            lines = ["<b>Offene Aufgaben:</b>", ""]
            for t in tasks:
                title = t.get("title", "Unbenannt")
                due = t.get("due_date")
                due_str = f" (bis {due})" if due else ""
                lines.append(f"- {title}{due_str}")
            
            return "\n".join(lines)
        except Exception as e:
            return f"Fehler: {str(e)}"
    
    def _cmd_today(self) -> str:
        """Zeigt heutige Termine und Tasks."""
        if not self.db:
            return "Keine Datenbankverbindung."
        
        try:
            # Heutige Termine
            events = self.db.execute("""
                SELECT title, start_time
                FROM calendar_events
                WHERE DATE(start_time) = CURRENT_DATE
                ORDER BY start_time
            """)
            
            # Heute faellige Tasks
            tasks = self.db.execute("""
                SELECT title
                FROM tasks
                WHERE due_date = CURRENT_DATE AND status NOT IN ('done', 'someday')
            """)
            
            lines = [f"<b>Heute ({datetime.now().strftime('%d.%m.%Y')}):</b>", ""]
            
            if events:
                lines.append("<b>Termine:</b>")
                for e in events:
                    title = e.get("title", "Unbenannt")
                    time = e.get("start_time")
                    time_str = time.strftime("%H:%M") if time else ""
                    lines.append(f"- {time_str} {title}")
                lines.append("")
            
            if tasks:
                lines.append("<b>Faellige Aufgaben:</b>")
                for t in tasks:
                    lines.append(f"- {t.get('title', 'Unbenannt')}")
            
            if not events and not tasks:
                lines.append("Nichts geplant fuer heute.")
            
            return "\n".join(lines)
        except Exception as e:
            return f"Fehler: {str(e)}"
    
    def _cmd_daily(self) -> str:
        """Fordert Daily Report an."""
        # Hier wuerde der DailyReportAgent aufgerufen
        return "Daily Report wird generiert...\n(Report-Integration in Arbeit)"


def get_telegram_command_handler(db=None) -> TelegramCommandHandler:
    """Factory-Funktion."""
    return TelegramCommandHandler(db)
