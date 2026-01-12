"""
DatabaseWrapper - Vereinfacht DB-Zugriffe mit execute() Methode.

Wrapped die DatabaseConnection fuer einfacheren Zugriff.
"""

from typing import Any, List, Dict, Optional, Tuple


class DatabaseWrapper:
    """
    Wrapper um DatabaseConnection fuer einfacheren Zugriff.

    Statt:
        with db.get_cursor() as cursor:
            cursor.execute(query, params)
            results = cursor.fetchall()
            db.commit()

    Einfach:
        results = db.execute(query, params)
    """

    def __init__(self, connection):
        """
        Args:
            connection: DatabaseConnection Instanz
        """
        self._conn = connection

    def _ensure_connection(self):
        """Stellt sicher dass Verbindung aktiv ist."""
        try:
            # Teste ob Verbindung noch ok
            with self._conn.get_cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception:
            # Verbindung neu aufbauen
            self._conn.reconnect()

    def execute(
        self,
        query: str,
        params: Tuple = None,
        fetch: bool = True
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Fuehrt Query aus und gibt Ergebnisse zurueck.

        Args:
            query: SQL Query
            params: Parameter-Tuple
            fetch: True = fetchall(), False = nur ausfuehren

        Returns:
            Liste von Dicts bei SELECT, None bei INSERT/UPDATE/DELETE
        """
        try:
            with self._conn.get_cursor() as cursor:
                cursor.execute(query, params)

                # Bei SELECT/RETURNING: Ergebnisse holen
                if fetch and cursor.description:
                    results = cursor.fetchall()
                    self._conn.commit()
                    return [dict(row) for row in results]

                # Bei INSERT/UPDATE/DELETE: Commit
                self._conn.commit()
                return None
        except Exception as e:
            try:
                self._conn.rollback()
            except:
                pass
            raise e

    def execute_one(
        self,
        query: str,
        params: Tuple = None
    ) -> Optional[Dict[str, Any]]:
        """
        Fuehrt Query aus und gibt erste Zeile zurueck.

        Args:
            query: SQL Query
            params: Parameter-Tuple

        Returns:
            Dict oder None
        """
        try:
            with self._conn.get_cursor() as cursor:
                cursor.execute(query, params)

                if cursor.description:
                    row = cursor.fetchone()
                    self._conn.commit()
                    return dict(row) if row else None

                self._conn.commit()
                return None
        except Exception as e:
            try:
                self._conn.rollback()
            except:
                pass
            raise e

    def commit(self):
        """Speichert Aenderungen."""
        self._conn.commit()

    def rollback(self):
        """Macht Aenderungen rueckgaengig."""
        self._conn.rollback()


def get_db_wrapper(connection) -> DatabaseWrapper:
    """Factory-Funktion fuer DatabaseWrapper."""
    return DatabaseWrapper(connection)


# Singleton fuer API-Zugriffe
_db_instance = None

def get_db() -> DatabaseWrapper:
    """
    Gibt Singleton DatabaseWrapper zurueck.
    
    Verwendet fuer API-Endpoints die keinen eigenen Connection-Pool haben.
    """
    global _db_instance
    if _db_instance is None:
        from llm.infrastructure.database import DatabaseConnection
        conn = DatabaseConnection()
        _db_instance = DatabaseWrapper(conn)
    else:
        # Sicherstellen dass Verbindung noch ok ist
        try:
            _db_instance._ensure_connection()
        except:
            # Bei Fehler: Neu aufbauen
            from llm.infrastructure.database import DatabaseConnection
            conn = DatabaseConnection()
            _db_instance = DatabaseWrapper(conn)
    return _db_instance


def reset_db():
    """Setzt DB-Verbindung zurueck (bei Fehlern)."""
    global _db_instance
    _db_instance = None
