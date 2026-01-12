"""
ReportDispatcher - Versendet Reports an konfigurierte Kanaele.

Liest Empfaenger aus report_channels Tabelle und versendet
Reports an alle konfigurierten Ziele.
"""
import json
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass


@dataclass
class DispatchResult:
    """Ergebnis eines Report-Versands."""
    success: bool
    channel: str
    recipient: str
    error: Optional[str] = None


class ReportDispatcher:
    """
    Dispatcher fuer Multi-Channel Report-Versand.
    
    Liest Empfaenger-Konfiguration aus DB und routet
    Reports an die konfigurierten Kanaele.
    """
    
    def __init__(self, db=None):
        """
        Args:
            db: DatabaseWrapper fuer DB-Zugriffe
        """
        self.db = db
    
    def get_recipients(self, report_type: str) -> Dict[str, List[str]]:
        """
        Holt alle Empfaenger fuer einen Report-Typ.
        
        Args:
            report_type: z.B. "daily_report", "weekly_report"
            
        Returns:
            Dict mit channel_type -> [recipient_ids]
        """
        if not self.db:
            return {}
        
        rows = self.db.execute("""
            SELECT channel_type, recipients
            FROM report_channels
            WHERE report_type = %s AND is_active = true
        """, (report_type,))
        
        if not rows:
            return {}
        
        result = {}
        for row in rows:
            channel_type = row.get("channel_type") or row[0]
            recipients = row.get("recipients") or row[1]
            
            # recipients kann JSON-String oder bereits Liste sein
            if isinstance(recipients, str):
                recipients = json.loads(recipients)
            
            result[channel_type] = recipients
        
        return result
    
    def add_recipient(
        self, 
        report_type: str, 
        channel_type: str, 
        recipient_id: str
    ) -> bool:
        """
        Fuegt Empfaenger zu Report-Kanal hinzu.
        
        Args:
            report_type: Report-Typ
            channel_type: Kanal-Typ (telegram, web, etc.)
            recipient_id: Chat-ID, Session-ID, etc.
            
        Returns:
            True bei Erfolg
        """
        if not self.db:
            return False
        
        # Pruefen ob bereits Eintrag existiert
        existing = self.db.execute_one("""
            SELECT id, recipients
            FROM report_channels
            WHERE report_type = %s AND channel_type = %s
        """, (report_type, channel_type))
        
        if existing:
            # Update existierenden Eintrag
            recipients = existing.get("recipients") or []
            if isinstance(recipients, str):
                recipients = json.loads(recipients)
            
            if recipient_id not in recipients:
                recipients.append(recipient_id)
            
            self.db.execute("""
                UPDATE report_channels
                SET recipients = %s, updated_at = NOW()
                WHERE id = %s
            """, (json.dumps(recipients), existing["id"]), fetch=False)
        else:
            # Neuen Eintrag erstellen
            self.db.execute("""
                INSERT INTO report_channels (report_type, channel_type, recipients)
                VALUES (%s, %s, %s)
            """, (report_type, channel_type, json.dumps([recipient_id])), fetch=False)
        
        return True
    
    def remove_recipient(
        self, 
        report_type: str, 
        channel_type: str, 
        recipient_id: str
    ) -> bool:
        """
        Entfernt Empfaenger von Report-Kanal.
        
        Args:
            report_type: Report-Typ
            channel_type: Kanal-Typ
            recipient_id: Zu entfernende ID
            
        Returns:
            True bei Erfolg
        """
        if not self.db:
            return False
        
        existing = self.db.execute_one("""
            SELECT id, recipients
            FROM report_channels
            WHERE report_type = %s AND channel_type = %s
        """, (report_type, channel_type))
        
        if not existing:
            return False
        
        recipients = existing.get("recipients") or []
        if isinstance(recipients, str):
            recipients = json.loads(recipients)
        
        if recipient_id in recipients:
            recipients.remove(recipient_id)
        
        self.db.execute("""
            UPDATE report_channels
            SET recipients = %s, updated_at = NOW()
            WHERE id = %s
        """, (json.dumps(recipients), existing["id"]), fetch=False)
        
        return True
    
    def get_channel_config(self, channel_type: str) -> Optional[Dict[str, Any]]:
        """
        Holt Kanal-Konfiguration (z.B. Telegram Bot-Token).
        
        Args:
            channel_type: "telegram", "web", etc.
            
        Returns:
            Config-Dict oder None
        """
        if not self.db:
            return None
        
        if channel_type == "telegram":
            return self.db.execute_one("""
                SELECT bot_token, chat_id, webhook_url
                FROM telegram_config
                WHERE is_active = true
            """)
        
        return None
    
    def format_for_channel(
        self, 
        report: Dict[str, Any], 
        channel_type: str
    ) -> Union[str, Dict]:
        """
        Formatiert Report fuer spezifischen Kanal.
        
        Args:
            report: Report-Daten
            channel_type: Ziel-Kanal
            
        Returns:
            Formatierter Text (Telegram) oder Dict (Web)
        """
        if channel_type == "telegram":
            return self._format_telegram(report)
        else:
            return report  # Web bekommt rohes Dict
    
    def _format_telegram(self, report: Dict[str, Any]) -> str:
        """Formatiert Report fuer Telegram (HTML)."""
        lines = []
        
        # Top Tasks
        top_tasks = report.get("top_3_tasks", [])
        if top_tasks:
            lines.append("<b>Top-Aufgaben:</b>")
            for i, task in enumerate(top_tasks, 1):
                title = task.get("title", "Unbenannt")
                why = task.get("why", "")
                lines.append(f"{i}. {title}")
                if why:
                    lines.append(f"   <i>{why}</i>")
            lines.append("")
        
        # Summary
        summary = report.get("summary_text", "")
        if summary:
            lines.append(summary)
        
        return "\n".join(lines) if lines else "Keine Daten."
    
    async def dispatch(
        self, 
        report_type: str, 
        report: Dict[str, Any]
    ) -> List[DispatchResult]:
        """
        Versendet Report an alle konfigurierten Empfaenger.
        
        Args:
            report_type: Report-Typ
            report: Report-Daten
            
        Returns:
            Liste von DispatchResults
        """
        results = []
        recipients = self.get_recipients(report_type)
        
        for channel_type, recipient_list in recipients.items():
            formatted = self.format_for_channel(report, channel_type)
            
            for recipient in recipient_list:
                try:
                    if channel_type == "telegram":
                        await self._send_telegram(recipient, formatted)
                        results.append(DispatchResult(
                            success=True,
                            channel="telegram",
                            recipient=recipient
                        ))
                    else:
                        # Web: Hier wuerde SSE/WebSocket verwendet
                        results.append(DispatchResult(
                            success=True,
                            channel=channel_type,
                            recipient=recipient
                        ))
                except Exception as e:
                    results.append(DispatchResult(
                        success=False,
                        channel=channel_type,
                        recipient=recipient,
                        error=str(e)
                    ))
        
        return results
    
    async def _send_telegram(self, chat_id: str, text: str):
        """Sendet Nachricht via Telegram."""
        import httpx
        
        config = self.get_channel_config("telegram")
        if not config:
            raise ValueError("Telegram nicht konfiguriert")
        
        bot_token = config.get("bot_token")
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML"
            })
            
            data = response.json()
            if not data.get("ok"):
                raise ValueError(data.get("description", "Unbekannter Fehler"))


# Singleton
_dispatcher_instance: Optional[ReportDispatcher] = None


def get_report_dispatcher(db=None) -> ReportDispatcher:
    """Factory-Funktion fuer ReportDispatcher."""
    global _dispatcher_instance
    
    if _dispatcher_instance is None:
        _dispatcher_instance = ReportDispatcher(db)
    elif db is not None and _dispatcher_instance.db is None:
        _dispatcher_instance.db = db
    
    return _dispatcher_instance
