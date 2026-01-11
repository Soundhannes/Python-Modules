"""
Database Connection - Verwaltet PostgreSQL-Verbindungen.

Warum eine eigene Klasse?
- Verbindung wird wiederverwendet (Connection Pooling möglich)
- Zentrale Konfiguration
- Einfach zu testen (Mock möglich)
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
            raise ValueError("Keine DATABASE_URL. Setze Umgebungsvariable oder übergib connection_string.")
        
        self._connection = None
    
    def connect(self):
        """Stellt Verbindung her (falls noch nicht verbunden)."""
        if self._connection is None or self._connection.closed:
            self._connection = psycopg2.connect(self.connection_string)
        return self._connection
    
    def get_cursor(self):
        """
        Gibt einen Cursor zurück (als Context Manager).
        
        RealDictCursor: Ergebnisse als Dict statt Tuple.
        So kannst du row["provider"] statt row[0] schreiben.
        """
        conn = self.connect()
        return conn.cursor(cursor_factory=RealDictCursor)
    
    def commit(self):
        """Speichert Änderungen."""
        if self._connection:
            self._connection.commit()
    
    def rollback(self):
        """Macht Änderungen rückgängig."""
        if self._connection:
            self._connection.rollback()
    
    def close(self):
        """Schließt die Verbindung."""
        if self._connection:
            self._connection.close()
            self._connection = None


# Globale Instanz (Singleton-artig)
_db_instance: Optional[DatabaseConnection] = None


def get_database() -> DatabaseConnection:
    """
    Gibt die globale Datenbankinstanz zurück.
    
    Warum global?
    - Verbindungen sind teuer (Handshake, Auth, etc.)
    - Eine Verbindung für die ganze App reicht meist
    - Später erweiterbar zu Connection Pool
    """
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseConnection()
    return _db_instance
