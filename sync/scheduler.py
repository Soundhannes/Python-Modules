"""
Sync-Scheduler fuer automatische Hintergrundsynchronisation.

Fuehrt Provider-Sync in konfigurierbaren Intervallen durch.
"""
import logging
import threading
import time
from datetime import datetime
from typing import Dict, Optional, Callable
import json

logger = logging.getLogger(__name__)


class SyncScheduler:
    """
    Scheduler fuer automatische Synchronisation.
    
    Fuehrt Sync fuer aktivierte Provider in konfigurierten Intervallen durch.
    """
    
    def __init__(self, db_connection, sync_service):
        """
        Initialisiert Scheduler.
        
        Args:
            db_connection: DB Connection
            sync_service: SyncService Instanz
        """
        self.db = db_connection
        self.sync_service = sync_service
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._callbacks: Dict[str, Callable] = {}
    
    def start(self) -> None:
        """Startet den Scheduler im Hintergrund."""
        if self.running:
            return
        
        self.running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Sync scheduler started")
    
    def stop(self) -> None:
        """Stoppt den Scheduler."""
        self.running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Sync scheduler stopped")
    
    def on_sync_complete(self, callback: Callable[[str, Dict], None]) -> None:
        """
        Registriert Callback fuer Sync-Completion.
        
        Args:
            callback: Funktion mit (provider_name, stats) Signatur
        """
        self._callbacks['sync_complete'] = callback
    
    def trigger_sync(self, provider_name: str) -> Dict:
        """
        Loest manuellen Sync fuer einen Provider aus.
        
        Args:
            provider_name: Name des Providers
            
        Returns:
            Sync-Statistiken
        """
        return self._sync_provider(provider_name)
    
    def _run_loop(self) -> None:
        """Haupt-Loop des Schedulers."""
        while self.running and not self._stop_event.is_set():
            try:
                self._check_and_sync()
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
            
            # 30 Sekunden warten zwischen Checks
            self._stop_event.wait(timeout=30)
    
    def _check_and_sync(self) -> None:
        """Prueft welche Provider synchronisiert werden muessen."""
        providers = self._get_active_providers()
        
        for provider in providers:
            name = provider['name']
            interval = provider['interval']
            last_sync = provider['last_sync']
            
            # Pruefen ob Sync faellig
            if self._should_sync(last_sync, interval):
                logger.info(f"Starting scheduled sync for {name}")
                stats = self._sync_provider(name)
                logger.info(f"Sync complete for {name}: {stats}")
    
    def _should_sync(self, last_sync: Optional[datetime], interval: int) -> bool:
        """Prueft ob Sync faellig ist."""
        if last_sync is None:
            return True
        
        elapsed = (datetime.now() - last_sync).total_seconds()
        return elapsed >= interval
    
    def _sync_provider(self, provider_name: str) -> Dict:
        """Fuehrt Sync fuer einen Provider durch."""
        try:
            # Credentials laden und Provider initialisieren
            credentials = self._get_provider_credentials(provider_name)
            if not credentials:
                logger.warning(f"No credentials for {provider_name}")
                return {'error': 'no_credentials'}
            
            # Provider initialisieren falls noetig
            if provider_name not in self.sync_service.providers:
                if not self.sync_service.init_provider(provider_name, credentials):
                    logger.error(f"Failed to authenticate {provider_name}")
                    return {'error': 'auth_failed'}
            
            # Sync durchfuehren
            stats = self.sync_service.sync_provider(provider_name)
            
            # Callback
            if 'sync_complete' in self._callbacks:
                self._callbacks['sync_complete'](provider_name, stats)
            
            return stats
            
        except Exception as e:
            logger.error(f"Sync failed for {provider_name}: {e}")
            return {'error': str(e)}
    
    def _get_active_providers(self) -> list:
        """Holt alle aktivierten Provider aus der DB."""
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT provider, sync_interval, last_sync
            FROM sync_config
            WHERE enabled = true
        """)
        
        providers = []
        for row in cursor.fetchall():
            providers.append({
                'name': row[0],
                'interval': row[1] or 300,
                'last_sync': row[2]
            })
        
        return providers
    
    def _get_provider_credentials(self, provider_name: str) -> Optional[Dict]:
        """Holt Credentials fuer einen Provider."""
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT credentials FROM sync_config
            WHERE provider = %s AND enabled = true
        """, (provider_name,))
        
        row = cursor.fetchone()
        if row and row[0]:
            return row[0]
        return None
    
    def get_status(self) -> Dict:
        """
        Gibt aktuellen Status aller Provider zurueck.
        
        Returns:
            Dict mit Provider-Status
        """
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT provider, enabled, last_sync, sync_interval
            FROM sync_config
        """)
        
        status = {}
        for row in cursor.fetchall():
            status[row[0]] = {
                'enabled': row[1],
                'last_sync': row[2].isoformat() if row[2] else None,
                'interval': row[3]
            }
        
        status['scheduler_running'] = self.running
        return status
