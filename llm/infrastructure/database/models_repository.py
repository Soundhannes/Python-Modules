"""
Models Repository - Speichert verfügbare Modelle pro Provider.

Beim API Key Test werden die aktuellen Modelle vom Anbieter
abgefragt und hier gespeichert.
"""

from typing import Optional, List
from dataclasses import dataclass
from datetime import datetime
from .connection import get_database, DatabaseConnection


@dataclass
class ModelInfo:
    """Info über ein Modell."""
    provider: str
    model: str
    is_default: bool
    updated_at: datetime


class ModelsRepository:
    """
    Repository für Provider-Modelle.

    Verwendung:
        repo = ModelsRepository()
        repo.sync_models("anthropic", ["claude-3...", "claude-4..."], default="claude-4...")
        models = repo.get_models("anthropic")
    """

    def __init__(self, db: Optional[DatabaseConnection] = None):
        self._db = db or get_database()

    def get_models(self, provider: str) -> List[str]:
        """Holt alle Modelle für einen Provider."""
        with self._db.get_cursor() as cursor:
            cursor.execute(
                "SELECT model FROM provider_models WHERE provider = %s ORDER BY is_default DESC, model",
                (provider.lower(),)
            )
            rows = cursor.fetchall()
            return [row["model"] for row in rows]

    def get_default_model(self, provider: str) -> Optional[str]:
        """Holt das Default-Modell für einen Provider."""
        with self._db.get_cursor() as cursor:
            cursor.execute(
                "SELECT model FROM provider_models WHERE provider = %s AND is_default = TRUE",
                (provider.lower(),)
            )
            row = cursor.fetchone()
            return row["model"] if row else None

    def get_models_info(self, provider: str) -> List[ModelInfo]:
        """Holt alle Modell-Infos für einen Provider."""
        with self._db.get_cursor() as cursor:
            cursor.execute(
                "SELECT provider, model, is_default, updated_at FROM provider_models WHERE provider = %s ORDER BY is_default DESC, model",
                (provider.lower(),)
            )
            rows = cursor.fetchall()
            return [
                ModelInfo(
                    provider=row["provider"],
                    model=row["model"],
                    is_default=row["is_default"],
                    updated_at=row["updated_at"]
                )
                for row in rows
            ]

    def sync_models(self, provider: str, models: List[str], default: Optional[str] = None) -> bool:
        """
        Synchronisiert Modelle für einen Provider.
        Löscht alte Einträge und fügt neue ein.

        Args:
            provider: Provider-Name
            models: Liste der Modellnamen
            default: Default-Modell (optional)

        Returns:
            True bei Erfolg
        """
        provider = provider.lower()

        with self._db.get_cursor() as cursor:
            # Alte Modelle löschen
            cursor.execute(
                "DELETE FROM provider_models WHERE provider = %s",
                (provider,)
            )

            # Neue Modelle einfügen
            for model in models:
                is_default = (model == default) if default else False
                cursor.execute(
                    "INSERT INTO provider_models (provider, model, is_default) VALUES (%s, %s, %s)",
                    (provider, model, is_default)
                )

            self._db.commit()
            return True

    def delete_models(self, provider: str) -> bool:
        """Löscht alle Modelle für einen Provider."""
        with self._db.get_cursor() as cursor:
            cursor.execute(
                "DELETE FROM provider_models WHERE provider = %s",
                (provider.lower(),)
            )
            deleted = cursor.rowcount > 0
            self._db.commit()
            return deleted

    def has_models(self, provider: str) -> bool:
        """Prüft ob Modelle für Provider vorhanden sind."""
        with self._db.get_cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) as count FROM provider_models WHERE provider = %s",
                (provider.lower(),)
            )
            row = cursor.fetchone()
            return row["count"] > 0 if row else False


# Globale Instanz
_repo_instance: Optional[ModelsRepository] = None


def get_models_repository() -> ModelsRepository:
    """Gibt die globale Repository-Instanz zurück."""
    global _repo_instance
    if _repo_instance is None:
        _repo_instance = ModelsRepository()
    return _repo_instance
