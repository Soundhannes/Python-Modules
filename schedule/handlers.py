"""
Job-Handler für geplante Aufgaben.

Jeder Handler wird mit @register_job_handler dekoriert.
Die DB-Connection wird vom SchedulerRunner geholt.
"""
import logging
from datetime import datetime
from schedule.runner import register_job_handler, get_scheduler_runner

logger = logging.getLogger(__name__)


def _get_db():
    """Holt DB-Connection vom SchedulerRunner."""
    runner = get_scheduler_runner()
    if runner is None:
        raise RuntimeError("SchedulerRunner nicht initialisiert")
    return runner.db


@register_job_handler("calendar_sync")
def handle_calendar_sync():
    """Synchronisiert Kalender mit iCloud."""
    logger.info("Starte Kalender-Sync...")
    
    try:
        db = _get_db()
        
        # Credentials aus sync_config holen
        config = db.execute("""
            SELECT credentials, write_calendar_id 
            FROM sync_config 
            WHERE provider = 'icloud'
        """)
        
        if not config:
            logger.warning("Keine iCloud-Konfiguration gefunden")
            return
        
        credentials = config[0]['credentials']
        write_calendar_id = config[0].get('write_calendar_id')
        
        # Provider initialisieren
        from sync.providers.icloud_calendar import ICloudCalendarProvider
        
        provider = ICloudCalendarProvider()
        if not provider.authenticate(credentials):
            logger.error("iCloud CalDAV Authentifizierung fehlgeschlagen")
            return
        
        # Kalender holen
        calendars = provider.list_calendars()
        logger.info(f"{len(calendars)} Kalender gefunden")
        
        # Alle Events der nächsten 90 Tage pullen
        from datetime import timedelta
        today = datetime.now()
        start = today.strftime("%Y%m%d")
        end = (today + timedelta(days=90)).strftime("%Y%m%d")
        
        total_events = 0
        for cal in calendars:
            events = provider.pull_events(cal, start, end)
            logger.info(f"Kalender '{cal.name}': {len(events)} Events")
            
            for event in events:
                # Event in DB upserten
                existing = db.execute(
                    "SELECT id FROM calendar_events WHERE icloud_uid = %s",
                    (event.icloud_uid,)
                )
                
                if existing:
                    db.execute("""
                        UPDATE calendar_events 
                        SET title = %s, start_time = %s, end_time = %s, 
                            location = %s, description = %s, updated_at = NOW()
                        WHERE icloud_uid = %s
                    """, (event.title, event.start_time, event.end_time, 
                           event.location, event.description, event.icloud_uid))
                else:
                    db.execute("""
                        INSERT INTO calendar_events 
                        (title, start_time, end_time, location, description, 
                         icloud_uid, calendar_id, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                    """, (event.title, event.start_time, event.end_time,
                           event.location, event.description, 
                           event.icloud_uid, write_calendar_id))
                
                total_events += 1
        
        logger.info(f"Kalender-Sync abgeschlossen: {total_events} Events synchronisiert")
        
    except Exception as e:
        logger.error(f"Kalender-Sync fehlgeschlagen: {e}", exc_info=True)


@register_job_handler("contact_sync")
def handle_contact_sync():
    """Synchronisiert Kontakte mit iCloud."""
    logger.info("Starte Kontakte-Sync...")
    
    try:
        db = _get_db()
        
        # Credentials aus sync_config holen
        config = db.execute("""
            SELECT credentials FROM sync_config WHERE provider = 'icloud'
        """)
        
        if not config:
            logger.warning("Keine iCloud-Konfiguration gefunden")
            return
        
        credentials = config[0]['credentials']
        
        # SyncService initialisieren
        from sync.service import SyncService
        
        sync_service = SyncService(db)
        
        if not sync_service.init_provider('icloud', credentials):
            logger.error("iCloud CardDAV Authentifizierung fehlgeschlagen")
            return
        
        # Sync durchführen
        stats = sync_service.sync_provider('icloud')
        
        logger.info(f"Kontakte-Sync abgeschlossen: pulled={stats['pulled']}, "
                   f"pushed={stats['pushed']}, deleted={stats['deleted']}, "
                   f"conflicts={stats['conflicts']}")
        
    except Exception as e:
        logger.error(f"Kontakte-Sync fehlgeschlagen: {e}", exc_info=True)


@register_job_handler("daily_report")
def handle_daily_report():
    """Generiert täglichen Report und sendet via Telegram."""
    logger.info("Generiere Daily Report...")
    
    try:
        db = _get_db()
        
        # Telegram Chat-ID holen
        telegram = db.execute(
            "SELECT chat_id FROM telegram_config WHERE is_active = true LIMIT 1"
        )
        chat_id = telegram[0]['chat_id'] if telegram else None
        
        # Daily Report Agent
        from agents.second_brain.daily_report_agent import get_daily_report_agent
        
        agent = get_daily_report_agent(db, telegram_chat_id=chat_id)
        result = agent.generate_from_db()
        
        if result.get('error'):
            logger.error(f"Daily Report Fehler: {result['error']}")
        else:
            logger.info("Daily Report generiert und gesendet")
        
    except Exception as e:
        logger.error(f"Daily Report fehlgeschlagen: {e}", exc_info=True)


@register_job_handler("weekly_report")
def handle_weekly_report():
    """Generiert wöchentlichen Report und sendet via Telegram."""
    logger.info("Generiere Weekly Report...")
    
    try:
        db = _get_db()
        
        # Telegram Chat-ID holen
        telegram = db.execute(
            "SELECT chat_id FROM telegram_config WHERE is_active = true LIMIT 1"
        )
        chat_id = telegram[0]['chat_id'] if telegram else None
        
        # Weekly Report Agent
        from agents.second_brain.weekly_report_agent import get_weekly_report_agent
        
        agent = get_weekly_report_agent(db, telegram_chat_id=chat_id)
        result = agent.generate_from_db()
        
        if result.get('error'):
            logger.error(f"Weekly Report Fehler: {result['error']}")
        else:
            logger.info("Weekly Report generiert und gesendet")
        
    except Exception as e:
        logger.error(f"Weekly Report fehlgeschlagen: {e}", exc_info=True)
