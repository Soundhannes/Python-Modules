"""
WeeklyReportAgent - Erstellt woechentlichen Ueberblick mit Pattern-Erkennung.

Wird woechentlich Sonntag abends per Cron aufgerufen.
Sendet Report optional via Telegram.
"""

import sys
from typing import Dict, Any, List, Optional
from datetime import datetime, date, time, timedelta

sys.path.insert(0, "/opt/python-modules")

from .configurable_agent import ConfigurableAgent
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


class WeeklyReportAgent(ConfigurableAgent):
    """
    Spezialisierter Agent fuer woechentliche Reports mit Pattern-Erkennung.

    Laedt Konfiguration aus agent_configs mit agent_name='weekly_report_agent'.
    """

    def __init__(self, db_connection, telegram_chat_id: Optional[str] = None):
        super().__init__("weekly_report_agent", db_connection)

        self.telegram_chat_id = telegram_chat_id
        if telegram_chat_id:
            self.notifier = get_notification_service("weekly_report")
        else:
            self.notifier = None

    def generate(
        self,
        period_start: str,
        period_end: str,
        completed_tasks: List[Dict],
        new_tasks: List[Dict],
        open_tasks: List[Dict],
        active_projects: List[Dict],
        upcoming_calendar: List[Dict],
        patterns: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generiert woechentlichen Report.
        """
        result = self.execute(
            period_start=period_start,
            period_end=period_end,
            completed_tasks=completed_tasks,
            new_tasks=new_tasks,
            open_tasks=open_tasks,
            active_projects=active_projects,
            upcoming_calendar=upcoming_calendar,
            patterns=patterns
        )

        # Bei Erfolg: Optional via Telegram senden
        if not result.get("error") and self.notifier and self.telegram_chat_id:
            summary = result.get("summary_text", "")
            if summary:
                self.notifier.send_telegram(
                    chat_id=self.telegram_chat_id,
                    message=f"Weekly Report\n\n{summary}",
                    
                )

        return result

    def generate_from_db(self) -> Dict[str, Any]:
        """
        Generiert Report mit Daten direkt aus der Datenbank.
        """
        today = datetime.now()
        period_end = today.strftime("%Y-%m-%d")
        period_start = (today - timedelta(days=7)).strftime("%Y-%m-%d")

        completed_tasks = self.db.execute("""
            SELECT t.id, t.title, t.updated_at as completed_at, p.name as project_name
            FROM tasks t
            LEFT JOIN projects p ON t.project_id = p.id
            WHERE t.status = 'done'
              AND t.updated_at >= %s
            ORDER BY t.updated_at DESC
        """, (period_start,))

        new_tasks = self.db.execute("""
            SELECT id, title, created_at
            FROM tasks
            WHERE created_at >= %s
            ORDER BY created_at DESC
        """, (period_start,))

        open_tasks = self.db.execute("""
            SELECT id, title, due_date, priority
            FROM tasks
            WHERE status = 'open'
            ORDER BY priority ASC, due_date ASC NULLS LAST
            LIMIT 20
        """)

        active_projects = self.db.execute("""
            SELECT p.id, p.name,
                   COUNT(t.id) FILTER (WHERE t.status = 'open') as open_tasks_count
            FROM projects p
            LEFT JOIN tasks t ON t.project_id = p.id
            WHERE p.status = 'active'
            GROUP BY p.id, p.name
            ORDER BY open_tasks_count DESC
            LIMIT 10
        """)

        upcoming_calendar = self.db.execute("""
            SELECT e.id, e.title, e.start_time, p.name as person_name
            FROM calendar_events e
            LEFT JOIN people p ON e.person_id = p.id
            WHERE e.start_time >= CURRENT_DATE
              AND e.start_time < CURRENT_DATE + INTERVAL '7 days'
            ORDER BY e.start_time ASC
            LIMIT 10
        """)

        patterns = self._calculate_patterns(period_start)

        return self.generate(
            period_start=period_start,
            period_end=period_end,
            completed_tasks=_serialize_dates(completed_tasks or []),
            new_tasks=_serialize_dates(new_tasks or []),
            open_tasks=_serialize_dates(open_tasks or []),
            active_projects=_serialize_dates(active_projects or []),
            upcoming_calendar=_serialize_dates(upcoming_calendar or []),
            patterns=patterns
        )

    def _calculate_patterns(self, period_start: str) -> Dict[str, Any]:
        """Berechnet Patterns aus den Daten der letzten Woche."""

        day_counts = self.db.execute("""
            SELECT TO_CHAR(updated_at, 'Day') as day_name, COUNT(*) as count
            FROM tasks
            WHERE status = 'done' AND updated_at >= %s
            GROUP BY TO_CHAR(updated_at, 'Day')
            ORDER BY count DESC
            LIMIT 1
        """, (period_start,))

        most_active_day = day_counts[0]["day_name"].strip() if day_counts else "N/A"

        total_completed = self.db.execute("""
            SELECT COUNT(*) as count
            FROM tasks
            WHERE status = 'done' AND updated_at >= %s
        """, (period_start,))

        avg_per_day = round(total_completed[0]["count"] / 7, 1) if total_completed else 0

        people = self.db.execute("""
            SELECT DISTINCT p.name
            FROM calendar_events e
            JOIN people p ON e.person_id = p.id
            WHERE e.start_time >= %s
            LIMIT 10
        """, (period_start,))

        people_contacted = [p["name"] for p in (people or [])]

        recurring_tags = []

        return {
            "most_active_day": most_active_day,
            "avg_tasks_completed_per_day": avg_per_day,
            "recurring_tags": recurring_tags,
            "people_contacted": people_contacted
        }


def get_weekly_report_agent(db_connection, telegram_chat_id: str = None) -> WeeklyReportAgent:
    """Factory-Funktion fuer WeeklyReportAgent."""
    return WeeklyReportAgent(db_connection, telegram_chat_id)
