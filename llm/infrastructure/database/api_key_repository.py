"""
API Key Repository - Liest und schreibt API Keys aus/in die Datenbank.

Repository Pattern:
- Kapselt allen Datenbankzugriff
- Domain-Schicht weiß nicht WIE Daten gespeichert werden
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from .connection import get_database, DatabaseConnection


@dataclass
class ApiKeyInfo:
    """Info über einen API Key (ohne den Key selbst)."""
    provider: str
    valid: Optional[bool]
    created_at: datetime
    updated_at: datetime


class ApiKeyRepository:
    """
    Repository für API Keys.
    
    Verwendung:
        repo = ApiKeyRepository()
        repo.set_key("anthropic", "sk-ant-...", valid=True)
        key = repo.get_key("anthropic")
        info = repo.get_key_info("anthropic")
    """
    
    def __init__(self, db: Optional[DatabaseConnection] = None):
        self._db = db or get_database()
    
    def get_key(self, provider: str) -> Optional[str]:
        """Holt den API Key für einen Provider."""
        with self._db.get_cursor() as cursor:
            cursor.execute(
                "SELECT api_key FROM api_keys WHERE provider = %s",
                (provider.lower(),)
            )
            row = cursor.fetchone()
            return row["api_key"] if row else None
    
    def get_key_info(self, provider: str) -> Optional[ApiKeyInfo]:
        """Holt Infos über einen Key (ohne Key-Wert)."""
        with self._db.get_cursor() as cursor:
            cursor.execute(
                "SELECT provider, valid, created_at, updated_at FROM api_keys WHERE provider = %s",
                (provider.lower(),)
            )
            row = cursor.fetchone()
            if row:
                return ApiKeyInfo(
                    provider=row["provider"],
                    valid=row["valid"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"]
                )
            return None
    
    def set_key(self, provider: str, api_key: str, valid: Optional[bool] = None) -> bool:
        """
        Speichert oder aktualisiert einen API Key.
        
        Args:
            provider: Provider-Name
            api_key: Der API-Schlüssel
            valid: Validierungsstatus (optional)
        
        Returns:
            True bei Erfolg
        """
        with self._db.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO api_keys (provider, api_key, valid)
                VALUES (%s, %s, %s)
                ON CONFLICT (provider) 
                DO UPDATE SET api_key = EXCLUDED.api_key, valid = EXCLUDED.valid
            """, (provider.lower(), api_key, valid))
            self._db.commit()
            return True
    
    def update_valid(self, provider: str, valid: bool) -> bool:
        """Aktualisiert nur den valid-Status."""
        with self._db.get_cursor() as cursor:
            cursor.execute(
                "UPDATE api_keys SET valid = %s WHERE provider = %s",
                (valid, provider.lower())
            )
            updated = cursor.rowcount > 0
            self._db.commit()
            return updated
    
    def delete_key(self, provider: str) -> bool:
        """Löscht einen API Key."""
        with self._db.get_cursor() as cursor:
            cursor.execute(
                "DELETE FROM api_keys WHERE provider = %s",
                (provider.lower(),)
            )
            deleted = cursor.rowcount > 0
            self._db.commit()
            return deleted
    
    def get_all_keys(self) -> Dict[str, str]:
        """Holt alle API Keys (Provider -> Key)."""
        with self._db.get_cursor() as cursor:
            cursor.execute("SELECT provider, api_key FROM api_keys")
            rows = cursor.fetchall()
            return {row["provider"]: row["api_key"] for row in rows}
    
    def get_all_keys_info(self) -> List[ApiKeyInfo]:
        """Holt Infos über alle Keys (ohne Key-Werte)."""
        with self._db.get_cursor() as cursor:
            cursor.execute(
                "SELECT provider, valid, created_at, updated_at FROM api_keys ORDER BY provider"
            )
            rows = cursor.fetchall()
            return [
                ApiKeyInfo(
                    provider=row["provider"],
                    valid=row["valid"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"]
                )
                for row in rows
            ]
    
    def list_providers_with_keys(self) -> List[str]:
        """Gibt Liste aller Provider zurück, die einen Key haben."""
        with self._db.get_cursor() as cursor:
            cursor.execute("SELECT provider FROM api_keys")
            rows = cursor.fetchall()
            return [row["provider"] for row in rows]


# Globale Instanz
_repo_instance: Optional[ApiKeyRepository] = None


def get_api_key_repository() -> ApiKeyRepository:
    """Gibt die globale Repository-Instanz zurück."""
    global _repo_instance
    if _repo_instance is None:
        _repo_instance = ApiKeyRepository()
    return _repo_instance
