"""
ChannelRouter - Verwaltet Channel-Kontext und Routing.

Stellt sicher dass Antworten zum gleichen Kanal zurueckgehen
wo die Anfrage herkam ("Wo gefragt, da geantwortet").
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class ChannelContext:
    """
    Kontext fuer einen Channel/Kanal.
    
    Attrs:
        channel: Kanal-Typ (web, telegram, etc.)
        channel_id: Eindeutige ID im Kanal (Session-ID, Chat-ID, etc.)
        metadata: Zusaetzliche Metadaten
    """
    channel: str = "web"
    channel_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_web(self) -> bool:
        """True wenn Web-Kanal."""
        return self.channel == "web"
    
    @property
    def is_telegram(self) -> bool:
        """True wenn Telegram-Kanal."""
        return self.channel == "telegram"


class ChannelRouter:
    """
    Router fuer Multi-Channel-Kommunikation.
    
    Verwaltet:
    - Erstellung von Channel-Kontexten
    - Routing-Entscheidungen
    - Telegram-Konfiguration (wenn DB vorhanden)
    """
    
    def __init__(self, db=None):
        """
        Args:
            db: Optional DatabaseWrapper fuer Telegram-Config
        """
        self.db = db
        self._telegram_config_cache = None
    
    def create_context(
        self, 
        channel: str = "web", 
        channel_id: Optional[str] = None,
        **metadata
    ) -> ChannelContext:
        """
        Erstellt neuen Channel-Kontext.
        
        Args:
            channel: Kanal-Typ
            channel_id: ID im Kanal
            **metadata: Zusaetzliche Daten
            
        Returns:
            ChannelContext
        """
        return ChannelContext(
            channel=channel,
            channel_id=channel_id,
            metadata=metadata
        )
    
    def get_response_target(self, ctx: ChannelContext) -> Dict[str, Any]:
        """
        Gibt Routing-Ziel fuer Antwort zurueck.
        
        Args:
            ctx: Channel-Kontext
            
        Returns:
            Dict mit Routing-Infos
        """
        if ctx.is_telegram:
            return {
                "type": "telegram",
                "chat_id": ctx.channel_id
            }
        else:
            return {
                "type": "web",
                "session_id": ctx.channel_id
            }
    
    def should_send_to_channel(self, ctx: ChannelContext, target_channel: str) -> bool:
        """
        Prueft ob Nachricht an Kanal gesendet werden soll.
        
        Regel: "Wo gefragt, da geantwortet"
        Antworten gehen nur zum Ursprungs-Kanal.
        
        Args:
            ctx: Ursprungs-Kontext
            target_channel: Ziel-Kanal
            
        Returns:
            True wenn senden, False sonst
        """
        return ctx.channel == target_channel
    
    def get_telegram_config(self) -> Optional[Dict[str, Any]]:
        """
        Holt Telegram-Konfiguration aus DB.
        
        Returns:
            Dict mit bot_token und chat_id, oder None
        """
        if not self.db:
            return None
        
        if self._telegram_config_cache:
            return self._telegram_config_cache
        
        config = self.db.execute_one("""
            SELECT bot_token, chat_id, webhook_secret
            FROM telegram_config
            WHERE is_active = true
        """)
        
        self._telegram_config_cache = config
        return config
    
    def invalidate_cache(self):
        """Leert den Config-Cache."""
        self._telegram_config_cache = None


# Singleton-Instanz
_router_instance: Optional[ChannelRouter] = None


def get_channel_router(db=None) -> ChannelRouter:
    """
    Factory-Funktion fuer ChannelRouter.
    
    Args:
        db: Optional DatabaseWrapper
        
    Returns:
        ChannelRouter-Instanz
    """
    global _router_instance
    
    if _router_instance is None:
        _router_instance = ChannelRouter(db)
    elif db is not None and _router_instance.db is None:
        _router_instance.db = db
    
    return _router_instance
