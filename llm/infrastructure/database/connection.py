"""
Database Connection - Verwaltet PostgreSQL-Verbindungen.

Warum eine eigene Klasse?
- Verbindung wird wiederverwendet (Connection Pooling moeglich)
- Zentrale Konfiguration
- Einfach zu testen (Mock moeglich)
"""

import os
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor


class DatabaseConnection:
    """
    Verwaltet die PostgreSQL-Verbindung.
    
    Verwendung:
        db = DatabaseConnection()
        with db.get_cursor() as cursor:
            cursor.execute("SELECT * FROM api_keys")
            rows = cursor.fetchall()
    """
    
    def __init__(self, connection_string: Optional[str] = None):
        """
        Initialisiert die Datenbankverbindung.
        
        Args:
            connection_string: PostgreSQL URL, z.B.:
                postgresql://user:pass@host:5432/dbname
                Wenn None, wird DATABASE_URL aus Umgebung gelesen.
        """
        self.connection_string = connection_string or os.getenv("DATABASE_URL")
        
        if not self.connection_string:
            raise ValueError("Keine DATABASE_URL. Setze Umgebungsvariable oder uebergib connection_string.")
        
        self._connection = None
    
    def connect(self):
        """Stellt Verbindung her (falls noch nicht verbunden)."""
        if self._connection is None or self._connection.closed:
            self._connection = psycopg2.connect(self.connection_string)
        return self._connection
    
    def get_cursor(self):
        """
        Gibt einen Cursor zurueck (als Context Manager).
        
        RealDictCursor: Ergebnisse als Dict statt Tuple.
        So kannst du row["provider"] statt row[0] schreiben.
        """
        conn = self.connect()
        return conn.cursor(cursor_factory=RealDictCursor)
    
    def commit(self):
        """Speichert Aenderungen."""
        if self._connection:
            self._connection.commit()
    
    def rollback(self):
        """Macht Aenderungen rueckgaengig."""
        if self._connection:
            self._connection.rollback()
    
    def reconnect(self):
        """Verbindung neu aufbauen."""
        self.close()
        self.connect()
    
    def close(self):
        """Schliesst die Verbindung."""
        if self._connection:
            self._connection.close()
            self._connection = None
    
    def is_healthy(self) -> bool:
        """Prueft ob Verbindung ok ist."""
        try:
            if self._connection is None or self._connection.closed:
                return False
            # Teste mit einfacher Query
            with self.get_cursor() as cursor:
                cursor.execute("SELECT 1")
            return True
        except:
            return False


# Globale Instanz (Singleton-artig)
_db_instance: Optional[DatabaseConnection] = None


def get_database() -> DatabaseConnection:
    """
    Gibt die globale Datenbankinstanz zurueck.
    
    Warum global?
    - Verbindungen sind teuer (Handshake, Auth, etc.)
    - Eine Verbindung fuer die ganze App reicht meist
    - Spaeter erweiterbar zu Connection Pool
    """
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseConnection()
    else:
        # Bei fehlgeschlagener Transaktion: Reset
        try:
            if not _db_instance.is_healthy():
                _db_instance.reconnect()
        except:
            _db_instance = DatabaseConnection()
    return _db_instance


def reset_database():
    """Setzt globale DB-Verbindung zurueck."""
    global _db_instance
    if _db_instance:
        try:
            _db_instance.close()
        except:
            pass
    _db_instance = None
