"""
DatabaseWrapper - Vereinfacht DB-Zugriffe mit execute() Methode.

Wrapped die DatabaseConnection für einfacheren Zugriff.
"""

from typing import Any, List, Dict, Optional, Tuple


class DatabaseWrapper:
    """
    Wrapper um DatabaseConnection für einfacheren Zugriff.

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

    def execute(
        self,
        query: str,
        params: Tuple = None,
        fetch: bool = True
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Führt Query aus und gibt Ergebnisse zurück.

        Args:
            query: SQL Query
            params: Parameter-Tuple
            fetch: True = fetchall(), False = nur ausführen

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
            self._conn.rollback()
            raise e

    def execute_one(
        self,
        query: str,
        params: Tuple = None
    ) -> Optional[Dict[str, Any]]:
        """
        Führt Query aus und gibt erste Zeile zurück.

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
            self._conn.rollback()
            raise e

    def commit(self):
        """Speichert Änderungen."""
        self._conn.commit()

    def rollback(self):
        """Macht Änderungen rückgängig."""
        self._conn.rollback()


def get_db_wrapper(connection) -> DatabaseWrapper:
    """Factory-Funktion für DatabaseWrapper."""
    return DatabaseWrapper(connection)
