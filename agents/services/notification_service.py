"""
NotificationService - Benachrichtigungen über verschiedene Kanäle.

Unterstützt:
- Telegram (Bot API)
- Webhook (HTTP POST)

Verwendung:
    notifier = NotificationService("my_automation")
    notifier.send_telegram("Nachricht")
"""

import sys
import json
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime

sys.path.insert(0, "/opt/python-modules")
from llm.infrastructure.database import get_database


@dataclass
class NotificationResult:
    """Ergebnis einer Benachrichtigung."""
    automation: str                    # Name der Automation
    success: bool
    channel: str
    message: str
    error: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class NotificationService:
    """
    Service für Benachrichtigungen.
    
    Args:
        automation: Name der Automation (für Logging/Tracking)
    
    Verwendung:
        notifier = NotificationService("my_workflow")
        result = notifier.send_telegram("Workflow abgeschlossen")
    """
    
    CONFIG_TABLE = "notification_config"
    
    def __init__(self, automation: str = "default"):
        """
        Initialisiert NotificationService.
        
        Args:
            automation: Name der Automation (für Logging/Tracking)
        """
        self.automation = automation
        self._db = get_database()
        self._ensure_table()
    
    def _ensure_table(self):
        with self._db.get_cursor() as cursor:
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.CONFIG_TABLE} (
                    id SERIAL PRIMARY KEY,
                    channel VARCHAR(50) NOT NULL UNIQUE,
                    config JSONB NOT NULL,
                    enabled BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self._db.commit()
    
    def _make_result(
        self,
        success: bool,
        channel: str,
        message: str,
        error: Optional[str] = None
    ) -> NotificationResult:
        """Erstellt ein NotificationResult."""
        return NotificationResult(
            automation=self.automation,
            success=success,
            channel=channel,
            message=message,
            error=error
        )
    
    # === Config Management ===
    
    def set_config(self, channel: str, config: Dict[str, Any], enabled: bool = True) -> bool:
        """Speichert Konfiguration für einen Kanal."""
        with self._db.get_cursor() as cursor:
            cursor.execute(f"""
                INSERT INTO {self.CONFIG_TABLE} (channel, config, enabled)
                VALUES (%s, %s::jsonb, %s)
                ON CONFLICT (channel)
                DO UPDATE SET config = EXCLUDED.config, enabled = EXCLUDED.enabled, updated_at = CURRENT_TIMESTAMP
            """, (channel, json.dumps(config), enabled))
            self._db.commit()
            return True
    
    def get_config(self, channel: str) -> Optional[Dict[str, Any]]:
        """Holt Konfiguration für einen Kanal."""
        with self._db.get_cursor() as cursor:
            cursor.execute(f"""
                SELECT config, enabled FROM {self.CONFIG_TABLE}
                WHERE channel = %s
            """, (channel,))
            row = cursor.fetchone()
            if row:
                config = row["config"]
                if isinstance(config, str):
                    config = json.loads(config)
                config["_enabled"] = row["enabled"]
                return config
            return None
    
    def delete_config(self, channel: str) -> bool:
        with self._db.get_cursor() as cursor:
            cursor.execute(f"DELETE FROM {self.CONFIG_TABLE} WHERE channel = %s", (channel,))
            deleted = cursor.rowcount > 0
            self._db.commit()
            return deleted
    
    def list_channels(self) -> List[Dict[str, Any]]:
        """Listet alle konfigurierten Kanäle."""
        with self._db.get_cursor() as cursor:
            cursor.execute(f"SELECT channel, enabled FROM {self.CONFIG_TABLE}")
            return [{"channel": row["channel"], "enabled": row["enabled"]} for row in cursor.fetchall()]
    
    # === Telegram ===
    
    def send_telegram(self, message: str, chat_id: Optional[str] = None) -> NotificationResult:
        """
        Sendet Nachricht über Telegram.
        
        Config in DB: {"bot_token": "...", "default_chat_id": "..."}
        """
        config = self.get_config("telegram")
        if not config:
            return self._make_result(False, "telegram", message, "Telegram nicht konfiguriert")
        
        if not config.get("_enabled", True):
            return self._make_result(False, "telegram", message, "Telegram deaktiviert")
        
        bot_token = config.get("bot_token")
        target_chat_id = chat_id or config.get("default_chat_id")
        
        if not bot_token or not target_chat_id:
            return self._make_result(False, "telegram", message, "Bot Token oder Chat ID fehlt")
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = json.dumps({"chat_id": target_chat_id, "text": message, "parse_mode": "HTML"}).encode()
        
        try:
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode())
                if result.get("ok"):
                    return self._make_result(True, "telegram", message)
                return self._make_result(False, "telegram", message, str(result))
        except urllib.error.URLError as e:
            return self._make_result(False, "telegram", message, str(e))
        except Exception as e:
            return self._make_result(False, "telegram", message, str(e))
    
    # === Webhook ===
    
    def send_webhook(self, url: str = None, payload: Dict[str, Any] = None, message: str = None) -> NotificationResult:
        """
        Sendet HTTP POST an Webhook URL.
        
        Config in DB: {"url": "...", "headers": {...}}
        """
        config = self.get_config("webhook") or {}
        target_url = url or config.get("url")
        
        if not target_url:
            return self._make_result(False, "webhook", str(payload), "Webhook URL fehlt")
        
        headers = {"Content-Type": "application/json"}
        headers.update(config.get("headers", {}))
        
        if payload is None:
            payload = {"message": message or "", "timestamp": datetime.now().isoformat(), "automation": self.automation}
        
        data = json.dumps(payload).encode()
        msg_preview = str(payload)[:100]
        
        try:
            req = urllib.request.Request(target_url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=10) as response:
                return self._make_result(True, "webhook", msg_preview)
        except urllib.error.URLError as e:
            return self._make_result(False, "webhook", msg_preview, str(e))
        except Exception as e:
            return self._make_result(False, "webhook", msg_preview, str(e))
    
    # === Convenience ===
    
    def notify(self, message: str, channels: List[str] = None) -> Dict[str, NotificationResult]:
        """
        Sendet Nachricht an mehrere Kanäle.
        
        Args:
            message: Nachricht
            channels: Liste von Kanälen (default: alle aktivierten)
        
        Returns:
            Dict mit Ergebnissen pro Kanal
        """
        results = {}
        
        if channels is None:
            channels = [c["channel"] for c in self.list_channels() if c["enabled"]]
        
        for channel in channels:
            if channel == "telegram":
                results["telegram"] = self.send_telegram(message)
            elif channel == "webhook":
                results["webhook"] = self.send_webhook(message=message)
        
        return results


# Cache für Instanzen pro Automation
_notification_instances: Dict[str, NotificationService] = {}


def get_notification_service(automation: str = "default") -> NotificationService:
    """
    Gibt eine NotificationService-Instanz für die Automation zurück.
    
    Args:
        automation: Name der Automation
    
    Returns:
        NotificationService-Instanz
    """
    global _notification_instances
    if automation not in _notification_instances:
        _notification_instances[automation] = NotificationService(automation)
    return _notification_instances[automation]
