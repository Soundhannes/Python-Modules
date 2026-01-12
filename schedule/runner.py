"""
Scheduler Runner - Lädt Jobs aus DB und führt sie mit APScheduler aus.
"""
import logging
from datetime import datetime, time
from typing import Dict, Callable, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

# Job-Handler Registry
JOB_HANDLERS: Dict[str, Callable] = {}


def register_job_handler(job_name: str):
    """Decorator zum Registrieren von Job-Handlern."""
    def decorator(func: Callable):
        JOB_HANDLERS[job_name] = func
        return func
    return decorator


class SchedulerRunner:
    """Verwaltet APScheduler mit DB-basierter Konfiguration."""
    
    def __init__(self, db_connection):
        self.db = db_connection
        self.scheduler = BackgroundScheduler()
        self._loaded_jobs: Dict[str, str] = {}
    
    def start(self):
        """Startet den Scheduler und lädt Jobs aus DB."""
        self.load_jobs_from_db()
        self.scheduler.start()
        self._update_next_run_times()
        logger.info("Scheduler gestartet")
    
    def stop(self):
        """Stoppt den Scheduler."""
        self.scheduler.shutdown(wait=False)
        logger.info("Scheduler gestoppt")
    
    def _update_next_run_times(self):
        """Aktualisiert next_run Zeiten in DB nach Scheduler-Start."""
        for job_name, job_id in self._loaded_jobs.items():
            job = self.scheduler.get_job(job_id)
            if job and job.next_run_time:
                self.db.execute(
                    "UPDATE scheduled_jobs SET next_run = %s WHERE job_name = %s",
                    (job.next_run_time, job_name)
                )
    
    def load_jobs_from_db(self):
        """Lädt alle aktiven Jobs aus der Datenbank."""
        query = """
            SELECT j.id, j.job_name, j.enabled,
                   s.type, s.interval_minutes, s.time_of_day,
                   s.day_of_week, s.day_of_month
            FROM scheduled_jobs j
            LEFT JOIN schedules s ON j.schedule_id = s.id
            WHERE j.enabled = true AND s.enabled = true
        """
        jobs = self.db.execute(query)
        
        for job in jobs:
            self._add_job(job)
    
    def _add_job(self, job_row: dict):
        """Fügt einen Job zum Scheduler hinzu."""
        job_name = job_row["job_name"]
        
        if job_name not in JOB_HANDLERS:
            logger.warning(f"Kein Handler für Job: {job_name}")
            return
        
        trigger = self._create_trigger(job_row)
        if not trigger:
            return
        
        job_id = f"job_{job_row['id']}"
        self.scheduler.add_job(
            func=JOB_HANDLERS[job_name],
            trigger=trigger,
            id=job_id,
            name=job_name,
            replace_existing=True
        )
        
        self._loaded_jobs[job_name] = job_id
        logger.info(f"Job geladen: {job_name} mit Trigger {trigger}")
    
    def _create_trigger(self, job_row: dict):
        """Erstellt APScheduler Trigger basierend auf Schedule-Typ."""
        schedule_type = job_row.get("type")
        
        if schedule_type == "interval":
            minutes = job_row.get("interval_minutes", 60)
            return IntervalTrigger(minutes=minutes)
        
        elif schedule_type == "daily":
            time_of_day = job_row.get("time_of_day")
            if time_of_day:
                if isinstance(time_of_day, time):
                    hour, minute = time_of_day.hour, time_of_day.minute
                else:
                    hour, minute = map(int, str(time_of_day).split(":")[:2])
                return CronTrigger(hour=hour, minute=minute)
        
        elif schedule_type == "weekly":
            time_of_day = job_row.get("time_of_day")
            day_of_week = job_row.get("day_of_week", 0)
            if time_of_day:
                if isinstance(time_of_day, time):
                    hour, minute = time_of_day.hour, time_of_day.minute
                else:
                    hour, minute = map(int, str(time_of_day).split(":")[:2])
                return CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute)
        
        elif schedule_type == "monthly":
            time_of_day = job_row.get("time_of_day")
            day_of_month = job_row.get("day_of_month", 1)
            if time_of_day:
                if isinstance(time_of_day, time):
                    hour, minute = time_of_day.hour, time_of_day.minute
                else:
                    hour, minute = map(int, str(time_of_day).split(":")[:2])
                return CronTrigger(day=day_of_month, hour=hour, minute=minute)
        
        return None
    
    def reload_job(self, job_id: int):
        """Lädt einen einzelnen Job neu."""
        query = """
            SELECT j.id, j.job_name, j.enabled,
                   s.type, s.interval_minutes, s.time_of_day,
                   s.day_of_week, s.day_of_month, s.enabled as schedule_enabled
            FROM scheduled_jobs j
            LEFT JOIN schedules s ON j.schedule_id = s.id
            WHERE j.id = %s
        """
        result = self.db.execute(query, (job_id,))
        if result:
            job = result[0]
            old_id = self._loaded_jobs.get(job["job_name"])
            if old_id:
                try:
                    self.scheduler.remove_job(old_id)
                except:
                    pass
                del self._loaded_jobs[job["job_name"]]
            
            if job["enabled"] and job.get("schedule_enabled", True):
                self._add_job(job)
                # next_run aktualisieren
                sched_job = self.scheduler.get_job(f"job_{job['id']}")
                if sched_job and sched_job.next_run_time:
                    self.db.execute(
                        "UPDATE scheduled_jobs SET next_run = %s WHERE id = %s",
                        (sched_job.next_run_time, job["id"])
                    )
            
            logger.info(f"Job neu geladen: {job['job_name']}")
    
    def run_job_now(self, job_name: str) -> bool:
        """Führt einen Job sofort aus."""
        if job_name in JOB_HANDLERS:
            try:
                JOB_HANDLERS[job_name]()
                self.db.execute(
                    "UPDATE scheduled_jobs SET last_run = NOW(), run_count = run_count + 1 WHERE job_name = %s",
                    (job_name,)
                )
                return True
            except Exception as e:
                self.db.execute(
                    "UPDATE scheduled_jobs SET last_error = %s, error_count = error_count + 1 WHERE job_name = %s",
                    (str(e), job_name)
                )
                logger.error(f"Job {job_name} fehlgeschlagen: {e}")
                return False
        return False


_scheduler_runner: Optional[SchedulerRunner] = None


def get_scheduler_runner(db_connection=None) -> SchedulerRunner:
    """Gibt die SchedulerRunner-Instanz zurück."""
    global _scheduler_runner
    if _scheduler_runner is None and db_connection:
        _scheduler_runner = SchedulerRunner(db_connection)
    return _scheduler_runner


def init_scheduler(db_connection):
    """Initialisiert und startet den Scheduler."""
    runner = get_scheduler_runner(db_connection)
    runner.start()
    return runner
