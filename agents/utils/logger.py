"""
Logger - Strukturiertes Logging für Agent-Automationen.

Speichert Logs in DB für:
- Debugging
- Audit-Trail
- Performance-Analyse
- Filterung nach Tags
"""

import sys
import json
from typing import Optional, Any, Dict, List
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

sys.path.insert(0, "/opt/python-modules")
from llm.infrastructure.database import get_database


class LogLevel(Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class LogEntry:
    """Ein Log-Eintrag."""
    id: int
    automation: str
    level: str
    message: str
    data: Optional[Dict[str, Any]]
    tags: List[str]
    timestamp: datetime


class Logger:
    """
    Strukturierter Logger für Automationen.

    Args:
        automation: Name der Automation
        tags: Standard-Tags für alle Log-Einträge
        min_level: Minimales Log-Level

    Verwendung:
        logger = Logger("my_automation", tags=["production", "critical-path"])
        logger.info("Gestartet")
        logger.debug("Details", {"step": 1}, tags=["verbose"])
    """

    TABLE_NAME = "agent_logs"

    def __init__(
        self,
        automation: str = "default",
        tags: List[str] = None,
        min_level: LogLevel = LogLevel.DEBUG
    ):
        self.automation = automation
        self.default_tags = tags or []
        self.min_level = min_level
        self._db = get_database()
        self._ensure_table()
        self._level_order = ["debug", "info", "warning", "error", "critical"]

    def _ensure_table(self):
        with self._db.get_cursor() as cursor:
            # Tabelle erstellen
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                    id SERIAL PRIMARY KEY,
                    automation VARCHAR(100) NOT NULL,
                    level VARCHAR(20) NOT NULL,
                    message TEXT NOT NULL,
                    data JSONB,
                    tags JSONB DEFAULT '[]'::jsonb,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Tags-Spalte hinzufügen falls nicht vorhanden (Migration)
            cursor.execute(f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'agent_logs' AND column_name = 'tags'
                    ) THEN
                        ALTER TABLE agent_logs ADD COLUMN tags JSONB DEFAULT '[]'::jsonb;
                    END IF;
                END $$;
            """)

            # Indices
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.TABLE_NAME}_automation
                ON {self.TABLE_NAME}(automation, timestamp DESC)
            """)
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.TABLE_NAME}_level
                ON {self.TABLE_NAME}(level)
            """)
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.TABLE_NAME}_tags
                ON {self.TABLE_NAME} USING GIN (tags)
            """)
            self._db.commit()

    def _should_log(self, level: LogLevel) -> bool:
        level_idx = self._level_order.index(level.value)
        min_idx = self._level_order.index(self.min_level.value)
        return level_idx >= min_idx

    def _log(
        self,
        level: LogLevel,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        tags: List[str] = None
    ):
        if not self._should_log(level):
            return

        # Tags kombinieren: default + zusätzliche
        all_tags = list(self.default_tags)
        if tags:
            all_tags.extend(tags)
        # Duplikate entfernen, Reihenfolge beibehalten
        all_tags = list(dict.fromkeys(all_tags))

        with self._db.get_cursor() as cursor:
            cursor.execute(f"""
                INSERT INTO {self.TABLE_NAME} (automation, level, message, data, tags)
                VALUES (%s, %s, %s, %s::jsonb, %s::jsonb)
            """, (
                self.automation,
                level.value,
                message,
                json.dumps(data) if data else None,
                json.dumps(all_tags)
            ))
            self._db.commit()

    def debug(self, message: str, data: Optional[Dict[str, Any]] = None, tags: List[str] = None):
        """Loggt Debug-Nachricht."""
        self._log(LogLevel.DEBUG, message, data, tags)

    def info(self, message: str, data: Optional[Dict[str, Any]] = None, tags: List[str] = None):
        """Loggt Info-Nachricht."""
        self._log(LogLevel.INFO, message, data, tags)

    def warning(self, message: str, data: Optional[Dict[str, Any]] = None, tags: List[str] = None):
        """Loggt Warning-Nachricht."""
        self._log(LogLevel.WARNING, message, data, tags)

    def error(self, message: str, data: Optional[Dict[str, Any]] = None, tags: List[str] = None):
        """Loggt Error-Nachricht."""
        self._log(LogLevel.ERROR, message, data, tags)

    def critical(self, message: str, data: Optional[Dict[str, Any]] = None, tags: List[str] = None):
        """Loggt Critical-Nachricht."""
        self._log(LogLevel.CRITICAL, message, data, tags)

    # === Abfragen ===

    def get_logs(
        self,
        limit: int = 100,
        level: Optional[LogLevel] = None,
        since: Optional[datetime] = None,
        tags: List[str] = None
    ) -> List[LogEntry]:
        """
        Holt Logs für diese Automation.

        Args:
            limit: Maximale Anzahl
            level: Filter nach Level
            since: Filter nach Zeitpunkt
            tags: Filter nach Tags (alle müssen vorhanden sein)
        """
        with self._db.get_cursor() as cursor:
            query = f"SELECT * FROM {self.TABLE_NAME} WHERE automation = %s"
            params = [self.automation]

            if level:
                query += " AND level = %s"
                params.append(level.value)

            if since:
                query += " AND timestamp >= %s"
                params.append(since)

            if tags:
                # Alle angegebenen Tags müssen vorhanden sein
                query += " AND tags @> %s::jsonb"
                params.append(json.dumps(tags))

            query += " ORDER BY timestamp DESC LIMIT %s"
            params.append(limit)

            cursor.execute(query, params)

            return [
                LogEntry(
                    id=row["id"],
                    automation=row["automation"],
                    level=row["level"],
                    message=row["message"],
                    data=row["data"] if isinstance(row["data"], dict) else json.loads(row["data"]) if row["data"] else None,
                    tags=row["tags"] if isinstance(row["tags"], list) else json.loads(row["tags"]) if row["tags"] else [],
                    timestamp=row["timestamp"]
                )
                for row in cursor.fetchall()
            ]

    def clear_logs(self, older_than_days: int = 30) -> int:
        """Löscht alte Logs."""
        with self._db.get_cursor() as cursor:
            cursor.execute(f"""
                DELETE FROM {self.TABLE_NAME}
                WHERE automation = %s
                AND timestamp < CURRENT_TIMESTAMP - INTERVAL '%s days'
            """, (self.automation, older_than_days))
            deleted = cursor.rowcount
            self._db.commit()
            return deleted

    def clear_all(self) -> int:
        """Löscht alle Logs dieser Automation."""
        with self._db.get_cursor() as cursor:
            cursor.execute(f"DELETE FROM {self.TABLE_NAME} WHERE automation = %s", (self.automation,))
            deleted = cursor.rowcount
            self._db.commit()
            return deleted


def get_logger(automation: str = "default", tags: List[str] = None) -> Logger:
    """
    Gibt einen Logger für die Automation zurück.

    Args:
        automation: Name der Automation
        tags: Standard-Tags für alle Log-Einträge
    """
    return Logger(automation, tags=tags)
