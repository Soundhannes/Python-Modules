"""
DailyReportAgent - Erstellt täglichen Fokus-Report.

Wird täglich morgens per Cron aufgerufen.
Sendet Report optional via Telegram.
"""

import sys
from datetime import datetime, date, time
from typing import Dict, Any, List, Optional

sys.path.insert(0, "/opt/python-modules")

from .configurable_agent import ConfigurableAgent, get_config_manager
from agents.services.notification_service import get_notification_service


def _serialize_dates(obj):
    """Konvertiert datetime-Objekte rekursiv zu Strings."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, time):
        return obj.strftime("%H:%M")
    elif isinstance(obj, dict):
        return {k: _serialize_dates(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_serialize_dates(item) for item in obj]
    return obj


class DailyReportAgent(ConfigurableAgent):
    """
    Spezialisierter Agent für tägliche Reports.

    Lädt Konfiguration aus agent_configs mit agent_name='daily_report_agent'.
    """

    def __init__(self, db_connection, telegram_chat_id: Optional[str] = None):
        super().__init__("daily_report_agent", db_connection)

        self.telegram_chat_id = telegram_chat_id
        if telegram_chat_id:
            self.notifier = get_notification_service("daily_report")
        else:
            self.notifier = None

    def generate(
        self,
        today: str,
        open_tasks: List[Dict],
        overdue_tasks: List[Dict],
        todays_calendar: List[Dict],
        recently_completed: List[Dict]
    ) -> Dict[str, Any]:
        """
        Generiert täglichen Report.
        """
        result = self.execute(
            today=today,
            open_tasks=open_tasks,
            overdue_tasks=overdue_tasks,
            todays_calendar=todays_calendar,
            recently_completed=recently_completed
        )

        # Bei Erfolg: Optional via Telegram senden
        if not result.get("error") and self.notifier and self.telegram_chat_id:
            summary = result.get("summary_text", "")
            if summary:
                self.notifier.send_telegram(
                    chat_id=self.telegram_chat_id,
                    message=f"Daily Report\n\n{summary}",
                    
                )

        return result

    def generate_from_db(self) -> Dict[str, Any]:
        """
        Generiert Report mit Daten direkt aus der Datenbank.
        """
        from datetime import datetime, timedelta

        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        open_tasks = self.db.execute("""
            SELECT t.id, t.title, t.due_date, t.priority, t.status,
                   p.name as project_name, pe.name as person_name
            FROM tasks t
            LEFT JOIN projects p ON t.project_id = p.id
            LEFT JOIN people pe ON t.person_id = pe.id
            WHERE t.status IN ('inbox', 'next', 'waiting')
            ORDER BY t.priority ASC, t.due_date ASC NULLS LAST
            LIMIT 20
        """)

        overdue_tasks = self.db.execute("""
            SELECT id, title, due_date, status,
                   EXTRACT(DAY FROM NOW() - due_date)::int as days_overdue
            FROM tasks
            WHERE status NOT IN ('done', 'someday') AND due_date < CURRENT_DATE
            ORDER BY due_date ASC
            LIMIT 10
        """)

        todays_calendar = self.db.execute("""
            SELECT e.id, e.title, e.start_time, p.name as person_name
            FROM calendar_events e
            LEFT JOIN people p ON e.person_id = p.id
            WHERE DATE(e.start_time) = CURRENT_DATE
            ORDER BY e.start_time ASC
        """)

        recently_completed = self.db.execute("""
            SELECT id, title, updated_at as completed_at
            FROM tasks
            WHERE status = 'done' AND DATE(updated_at) >= %s
            ORDER BY updated_at DESC
            LIMIT 5
        """, (yesterday,))

        return self.generate(
            today=today,
            open_tasks=_serialize_dates(open_tasks or []),
            overdue_tasks=_serialize_dates(overdue_tasks or []),
            todays_calendar=_serialize_dates(todays_calendar or []),
            recently_completed=_serialize_dates(recently_completed or [])
        )


def get_daily_report_agent(db_connection, telegram_chat_id: str = None) -> DailyReportAgent:
    """Factory-Funktion für DailyReportAgent."""
    return DailyReportAgent(db_connection, telegram_chat_id)
