"""
StorageService - Flexibler Key-Value Speicher für Agents.

Bietet:
- Key-Value Speicherung mit JSON-Unterstützung
- Namespace im Konstruktor (einmal setzen, überall nutzen)
- TTL (Time-to-Live) für automatisches Aufräumen
- Bulk-Operationen

Verwendung:
    # Mit Namespace (empfohlen)
    storage = StorageService(namespace='my_automation')
    storage.set('key', 'value')
    value = storage.get('key')

    # Oder über Factory
    storage = get_storage_service('my_automation')
"""

import sys
import json
from datetime import datetime, timedelta
from typing import Optional, Any, Dict, List
from dataclasses import dataclass

sys.path.insert(0, "/opt/python-modules")
from llm.infrastructure.database import get_database


@dataclass
class StorageItem:
    """Ein gespeicherter Eintrag."""
    key: str
    value: Any
    namespace: str
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime]


class StorageService:
    """
    Flexibler Key-Value Speicher.

    Args:
        namespace: Standard-Namespace für alle Operationen (default: 'default')
    """

    TABLE_NAME = "agent_storage"

    def __init__(self, namespace: str = "default"):
        """
        Initialisiert StorageService.

        Args:
            namespace: Standard-Namespace für alle Operationen
        """
        self.namespace = namespace
        self._db = get_database()
        self._ensure_table()

    def _ensure_table(self):
        """Erstellt die Storage-Tabelle falls nicht vorhanden."""
        with self._db.get_cursor() as cursor:
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                    id SERIAL PRIMARY KEY,
                    namespace VARCHAR(100) NOT NULL DEFAULT 'default',
                    key VARCHAR(255) NOT NULL,
                    value JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    UNIQUE(namespace, key)
                )
            """)
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.TABLE_NAME}_namespace_key
                ON {self.TABLE_NAME}(namespace, key)
            """)
            self._db.commit()

    def _get_namespace(self, namespace: Optional[str]) -> str:
        """Gibt den zu verwendenden Namespace zurück."""
        return namespace if namespace is not None else self.namespace

    def _parse_value(self, value: Any) -> Any:
        """Parst einen Wert aus der DB."""
        if value is None:
            return None
        if isinstance(value, (dict, list, int, float, bool)):
            return value
        if isinstance(value, str) and value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value

    def set(
        self,
        key: str,
        value: Any,
        namespace: Optional[str] = None,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Speichert einen Wert.

        Args:
            key: Schlüssel
            value: Wert (wird als JSON gespeichert)
            namespace: Namespace (optional, nutzt self.namespace wenn None)
            ttl: Time-to-Live in Sekunden

        Returns:
            True bei Erfolg
        """
        ns = self._get_namespace(namespace)
        expires_at = None
        if ttl:
            expires_at = datetime.now() + timedelta(seconds=ttl)

        json_value = json.dumps(value)

        with self._db.get_cursor() as cursor:
            cursor.execute(f"""
                INSERT INTO {self.TABLE_NAME} (namespace, key, value, expires_at)
                VALUES (%s, %s, %s::jsonb, %s)
                ON CONFLICT (namespace, key)
                DO UPDATE SET
                    value = EXCLUDED.value,
                    updated_at = CURRENT_TIMESTAMP,
                    expires_at = EXCLUDED.expires_at
            """, (ns, key, json_value, expires_at))
            self._db.commit()
            return True

    def get(
        self,
        key: str,
        namespace: Optional[str] = None,
        default: Any = None
    ) -> Any:
        """
        Holt einen Wert.

        Args:
            key: Schlüssel
            namespace: Namespace (optional, nutzt self.namespace wenn None)
            default: Rückgabewert falls nicht gefunden

        Returns:
            Gespeicherter Wert oder default
        """
        ns = self._get_namespace(namespace)

        with self._db.get_cursor() as cursor:
            cursor.execute(f"""
                SELECT value FROM {self.TABLE_NAME}
                WHERE namespace = %s AND key = %s
                AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            """, (ns, key))
            row = cursor.fetchone()

            if row and row["value"] is not None:
                return self._parse_value(row["value"])
            return default

    def get_item(
        self,
        key: str,
        namespace: Optional[str] = None
    ) -> Optional[StorageItem]:
        """
        Holt einen Eintrag mit Metadaten.

        Args:
            key: Schlüssel
            namespace: Namespace (optional)

        Returns:
            StorageItem oder None
        """
        ns = self._get_namespace(namespace)

        with self._db.get_cursor() as cursor:
            cursor.execute(f"""
                SELECT key, value, namespace, created_at, updated_at, expires_at
                FROM {self.TABLE_NAME}
                WHERE namespace = %s AND key = %s
                AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            """, (ns, key))
            row = cursor.fetchone()

            if row:
                return StorageItem(
                    key=row["key"],
                    value=self._parse_value(row["value"]),
                    namespace=row["namespace"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    expires_at=row["expires_at"]
                )
            return None

    def delete(self, key: str, namespace: Optional[str] = None) -> bool:
        """
        Löscht einen Eintrag.

        Args:
            key: Schlüssel
            namespace: Namespace (optional)

        Returns:
            True wenn gelöscht
        """
        ns = self._get_namespace(namespace)

        with self._db.get_cursor() as cursor:
            cursor.execute(f"""
                DELETE FROM {self.TABLE_NAME}
                WHERE namespace = %s AND key = %s
            """, (ns, key))
            deleted = cursor.rowcount > 0
            self._db.commit()
            return deleted

    def exists(self, key: str, namespace: Optional[str] = None) -> bool:
        """
        Prüft ob Eintrag existiert.

        Args:
            key: Schlüssel
            namespace: Namespace (optional)

        Returns:
            True wenn vorhanden und nicht abgelaufen
        """
        ns = self._get_namespace(namespace)

        with self._db.get_cursor() as cursor:
            cursor.execute(f"""
                SELECT 1 FROM {self.TABLE_NAME}
                WHERE namespace = %s AND key = %s
                AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            """, (ns, key))
            return cursor.fetchone() is not None

    def list_keys(
        self,
        namespace: Optional[str] = None,
        prefix: Optional[str] = None
    ) -> List[str]:
        """
        Listet alle Schlüssel.

        Args:
            namespace: Namespace (optional)
            prefix: Optional - nur Keys die mit prefix beginnen

        Returns:
            Liste von Schlüsseln
        """
        ns = self._get_namespace(namespace)

        with self._db.get_cursor() as cursor:
            if prefix:
                cursor.execute(f"""
                    SELECT key FROM {self.TABLE_NAME}
                    WHERE namespace = %s AND key LIKE %s
                    AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
                    ORDER BY key
                """, (ns, f"{prefix}%"))
            else:
                cursor.execute(f"""
                    SELECT key FROM {self.TABLE_NAME}
                    WHERE namespace = %s
                    AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
                    ORDER BY key
                """, (ns,))

            return [row["key"] for row in cursor.fetchall()]

    def get_all(
        self,
        namespace: Optional[str] = None,
        prefix: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Holt alle Einträge als Dict.

        Args:
            namespace: Namespace (optional)
            prefix: Optional - nur Keys die mit prefix beginnen

        Returns:
            Dict mit key -> value
        """
        ns = self._get_namespace(namespace)

        with self._db.get_cursor() as cursor:
            if prefix:
                cursor.execute(f"""
                    SELECT key, value FROM {self.TABLE_NAME}
                    WHERE namespace = %s AND key LIKE %s
                    AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
                """, (ns, f"{prefix}%"))
            else:
                cursor.execute(f"""
                    SELECT key, value FROM {self.TABLE_NAME}
                    WHERE namespace = %s
                    AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
                """, (ns,))

            return {row["key"]: self._parse_value(row["value"]) for row in cursor.fetchall()}

    def set_many(
        self,
        items: Dict[str, Any],
        namespace: Optional[str] = None,
        ttl: Optional[int] = None
    ) -> int:
        """
        Speichert mehrere Werte auf einmal.

        Args:
            items: Dict mit key -> value
            namespace: Namespace (optional)
            ttl: Time-to-Live in Sekunden

        Returns:
            Anzahl gespeicherter Einträge
        """
        count = 0
        for key, value in items.items():
            if self.set(key, value, namespace, ttl):
                count += 1
        return count

    def delete_namespace(self, namespace: Optional[str] = None) -> int:
        """
        Löscht alle Einträge eines Namespaces.

        Args:
            namespace: Namespace (optional, nutzt self.namespace wenn None)

        Returns:
            Anzahl gelöschter Einträge
        """
        ns = self._get_namespace(namespace)

        with self._db.get_cursor() as cursor:
            cursor.execute(f"""
                DELETE FROM {self.TABLE_NAME}
                WHERE namespace = %s
            """, (ns,))
            deleted = cursor.rowcount
            self._db.commit()
            return deleted

    def cleanup_expired(self) -> int:
        """
        Löscht alle abgelaufenen Einträge.

        Returns:
            Anzahl gelöschter Einträge
        """
        with self._db.get_cursor() as cursor:
            cursor.execute(f"""
                DELETE FROM {self.TABLE_NAME}
                WHERE expires_at IS NOT NULL AND expires_at < CURRENT_TIMESTAMP
            """)
            deleted = cursor.rowcount
            self._db.commit()
            return deleted


# Cache für Instanzen pro Namespace
_storage_instances: Dict[str, StorageService] = {}


def get_storage_service(namespace: str = "default") -> StorageService:
    """
    Gibt eine StorageService-Instanz für den Namespace zurück.

    Args:
        namespace: Namespace für die Instanz

    Returns:
        StorageService-Instanz
    """
    global _storage_instances
    if namespace not in _storage_instances:
        _storage_instances[namespace] = StorageService(namespace)
    return _storage_instances[namespace]
