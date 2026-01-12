"""
TDD Tests fuer Conflict Resolver.

Strategie: Last-Write-Wins basierend auf updated_at.
"""
import pytest
from datetime import datetime, timedelta
from sync.providers.base import Contact
from sync.conflict_resolver import ConflictResolver, ConflictResult


class TestLastWriteWins:
    """Tests fuer Last-Write-Wins Konfliktaufloesung."""

    def test_local_newer_wins(self):
        """Lokaler Kontakt ist neuer -> lokal gewinnt."""
        now = datetime.now()
        
        local = Contact(
            id=1,
            first_name="Max",
            last_name="Mustermann",
            updated_at=now
        )
        remote = Contact(
            first_name="Max",
            last_name="Mueller",  # Aenderung
            updated_at=now - timedelta(hours=1)
        )
        
        resolver = ConflictResolver()
        result = resolver.resolve(local, remote)
        
        assert result.winner == "local"
        assert result.contact.last_name == "Mustermann"
        assert result.action == "push"  # Push lokal zu Remote

    def test_remote_newer_wins(self):
        """Remote Kontakt ist neuer -> remote gewinnt."""
        now = datetime.now()
        
        local = Contact(
            id=1,
            first_name="Max",
            last_name="Mustermann",
            updated_at=now - timedelta(hours=1)
        )
        remote = Contact(
            first_name="Max",
            last_name="Mueller",  # Aenderung
            updated_at=now
        )
        
        resolver = ConflictResolver()
        result = resolver.resolve(local, remote)
        
        assert result.winner == "remote"
        assert result.contact.last_name == "Mueller"
        assert result.action == "pull"  # Pull von Remote

    def test_same_timestamp_prefers_local(self):
        """Bei gleichem Timestamp gewinnt lokal (SSOT)."""
        now = datetime.now()
        
        local = Contact(
            id=1,
            first_name="Max",
            last_name="Mustermann",
            updated_at=now
        )
        remote = Contact(
            first_name="Max",
            last_name="Mueller",
            updated_at=now
        )
        
        resolver = ConflictResolver()
        result = resolver.resolve(local, remote)
        
        assert result.winner == "local"

    def test_no_conflict_if_identical(self):
        """Keine Aenderung wenn Daten identisch."""
        now = datetime.now()
        
        local = Contact(
            id=1,
            first_name="Max",
            last_name="Mustermann",
            updated_at=now
        )
        remote = Contact(
            first_name="Max",
            last_name="Mustermann",
            updated_at=now - timedelta(hours=1)
        )
        
        resolver = ConflictResolver()
        result = resolver.resolve(local, remote)
        
        assert result.action == "none"  # Nichts zu tun


class TestNewContacts:
    """Tests fuer neue Kontakte (nur auf einer Seite vorhanden)."""

    def test_local_only_needs_push(self):
        """Lokaler Kontakt ohne Remote -> push."""
        local = Contact(
            id=1,
            first_name="Neu",
            last_name="Kontakt",
            updated_at=datetime.now()
        )
        
        resolver = ConflictResolver()
        result = resolver.resolve(local, None)
        
        assert result.action == "push"
        assert result.contact == local

    def test_remote_only_needs_pull(self):
        """Remote Kontakt ohne Lokal -> pull."""
        remote = Contact(
            first_name="Neu",
            last_name="Remote",
            updated_at=datetime.now(),
            nextcloud_uid="remote-123"
        )
        
        resolver = ConflictResolver()
        result = resolver.resolve(None, remote)
        
        assert result.action == "pull"
        assert result.contact == remote


class TestMergeFields:
    """Tests fuer Feld-Merge bei Konflikt."""

    def test_preserves_provider_uids(self):
        """Provider UIDs werden nicht ueberschrieben."""
        now = datetime.now()
        
        local = Contact(
            id=1,
            first_name="Max",
            last_name="Mustermann",
            updated_at=now - timedelta(hours=1),
            icloud_uid="icloud-123",
            google_uid="google-456"
        )
        remote = Contact(
            first_name="Max",
            last_name="Mueller",
            updated_at=now,
            nextcloud_uid="nextcloud-789"
        )
        
        resolver = ConflictResolver()
        result = resolver.resolve(local, remote, provider="nextcloud")
        
        # Remote gewinnt aber lokale UIDs bleiben
        assert result.contact.last_name == "Mueller"
        assert result.contact.icloud_uid == "icloud-123"
        assert result.contact.google_uid == "google-456"
        assert result.contact.nextcloud_uid == "nextcloud-789"

    def test_preserves_local_id(self):
        """Lokale DB-ID wird immer beibehalten."""
        now = datetime.now()
        
        local = Contact(
            id=42,
            first_name="Max",
            last_name="Alt",
            updated_at=now - timedelta(hours=1)
        )
        remote = Contact(
            first_name="Max",
            last_name="Neu",
            updated_at=now
        )
        
        resolver = ConflictResolver()
        result = resolver.resolve(local, remote)
        
        assert result.contact.id == 42


class TestConflictResult:
    """Tests fuer ConflictResult Dataclass."""

    def test_result_has_required_fields(self):
        """ConflictResult hat alle notwendigen Felder."""
        contact = Contact(first_name="Test", last_name="Person")
        result = ConflictResult(
            winner="local",
            action="push",
            contact=contact,
            reason="Local is newer"
        )
        
        assert result.winner == "local"
        assert result.action == "push"
        assert result.contact == contact
        assert result.reason == "Local is newer"
