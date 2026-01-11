"""
DailyReportAgent - Erstellt täglichen Fokus-Report.

Wird täglich morgens per Cron aufgerufen.
Sendet Report optional via Telegram.
"""

import sys
from typing import Dict, Any, List, Optional

sys.path.insert(0, "/opt/python-modules")

from .configurable_agent import ConfigurableAgent, get_config_manager
from agents.services.notification_service import get_notification_service


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
        todays_events: List[Dict],
        recently_completed: List[Dict]
    ) -> Dict[str, Any]:
        """
        Generiert täglichen Report.

        Args:
            today: Datum im Format YYYY-MM-DD
            open_tasks: [{id, title, due_date, priority, project_name}, ...]
            overdue_tasks: [{id, title, due_date, days_overdue}, ...]
            todays_events: [{id, title, event_date, person_name}, ...]
            recently_completed: [{id, title, completed_at}, ...]

        Returns:
            {
                top_3_tasks: [{id, title, why}, ...],
                avoiding: {id, title, days_overdue, suggestion},
                quick_win: {id, title, effort},
                todays_events: [{title, time, person}, ...],
                summary_text: str
            }
        """
        result = self.execute(
            today=today,
            open_tasks=open_tasks,
            overdue_tasks=overdue_tasks,
            todays_events=todays_events,
            recently_completed=recently_completed
        )

        # Bei Erfolg: Optional via Telegram senden
        if not result.get("error") and self.notifier and self.telegram_chat_id:
            summary = result.get("summary_text", "")
            if summary:
                self.notifier.send_telegram(
                    chat_id=self.telegram_chat_id,
                    message=f"📋 Daily Report\n\n{summary}",
                    message_type="info"
                )

        return result

    def generate_from_db(self) -> Dict[str, Any]:
        """
        Generiert Report mit Daten direkt aus der Datenbank.

        Convenience-Methode die alle nötigen Queries selbst macht.
        """
        from datetime import datetime, timedelta

        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        # Open Tasks
        open_tasks = self.db.execute("""
            SELECT t.id, t.title, t.due_date, t.priority, p.name as project_name
            FROM tasks t
            LEFT JOIN projects p ON t.project_id = p.id
            WHERE t.status = 'open'
            ORDER BY t.priority ASC, t.due_date ASC NULLS LAST
            LIMIT 20
        """)

        # Overdue Tasks
        overdue_tasks = self.db.execute("""
            SELECT id, title, due_date,
                   EXTRACT(DAY FROM NOW() - due_date)::int as days_overdue
            FROM tasks
            WHERE status = 'open' AND due_date < CURRENT_DATE
            ORDER BY due_date ASC
            LIMIT 10
        """)

        # Today's Events
        todays_events = self.db.execute("""
            SELECT e.id, e.title, e.event_date, p.name as person_name
            FROM events e
            LEFT JOIN people p ON e.person_id = p.id
            WHERE DATE(e.event_date) = CURRENT_DATE
            ORDER BY e.event_date ASC
        """)

        # Recently Completed
        recently_completed = self.db.execute("""
            SELECT id, title, updated_at as completed_at
            FROM tasks
            WHERE status = 'done' AND DATE(updated_at) >= %s
            ORDER BY updated_at DESC
            LIMIT 5
        """, (yesterday,))

        return self.generate(
            today=today,
            open_tasks=[dict(r) for r in open_tasks],
            overdue_tasks=[dict(r) for r in overdue_tasks],
            todays_events=[dict(r) for r in todays_events],
            recently_completed=[dict(r) for r in recently_completed]
        )


def get_daily_report_agent(db_connection, telegram_chat_id: str = None) -> DailyReportAgent:
    """Factory-Funktion für DailyReportAgent."""
    return DailyReportAgent(db_connection, telegram_chat_id)
