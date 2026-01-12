"""Tests fuer AbstractSyncProvider und Contact Dataclass."""

import pytest
from datetime import datetime, date
from dataclasses import asdict

import sys
sys.path.insert(0, "/opt/python-modules")

from sync.providers.base import Contact, ChangeSet, AbstractSyncProvider


class TestContact:
    """Tests fuer Contact Dataclass."""

    def test_create_minimal_contact(self):
        """Kontakt mit Mindestangaben erstellen."""
        contact = Contact(
            first_name="Tim",
            last_name="Mueller"
        )
        assert contact.first_name == "Tim"
        assert contact.last_name == "Mueller"
        assert contact.email is None
        assert contact.phone is None

    def test_create_full_contact(self):
        """Kontakt mit allen Feldern erstellen."""
        contact = Contact(
            id=1,
            first_name="Tim",
            middle_name="Alexander",
            last_name="Mueller",
            phone="+49 211 12345",
            email="tim@example.de",
            street="Musterstr.",
            house_nr="42",
            zip="40210",
            city="Duesseldorf",
            country="Deutschland",
            important_dates=[{"type": "Geburtstag", "date": "1990-05-15"}],
            last_contact=date(2026, 1, 10),
            context="Freund",
            updated_at=datetime(2026, 1, 11, 12, 0, 0)
        )
        assert contact.id == 1
        assert contact.middle_name == "Alexander"
        assert contact.city == "Duesseldorf"
        assert len(contact.important_dates) == 1

    def test_contact_full_name(self):
        """full_name Property testen."""
        contact = Contact(first_name="Tim", last_name="Mueller")
        assert contact.full_name == "Tim Mueller"

        contact_with_middle = Contact(
            first_name="Tim",
            middle_name="Alexander",
            last_name="Mueller"
        )
        assert contact_with_middle.full_name == "Tim Alexander Mueller"

    def test_contact_to_dict(self):
        """Kontakt zu Dictionary konvertieren."""
        contact = Contact(first_name="Tim", last_name="Mueller", email="tim@example.de")
        d = asdict(contact)
        assert d["first_name"] == "Tim"
        assert d["email"] == "tim@example.de"

    def test_contact_uid_fields(self):
        """Provider-UIDs testen."""
        contact = Contact(
            first_name="Tim",
            last_name="Mueller",
            icloud_uid="ABC123",
            google_uid="people/12345",
            nextcloud_uid="uuid-xyz"
        )
        assert contact.icloud_uid == "ABC123"
        assert contact.google_uid == "people/12345"
        assert contact.nextcloud_uid == "uuid-xyz"


class TestChangeSet:
    """Tests fuer ChangeSet Dataclass."""

    def test_empty_changeset(self):
        """Leeres ChangeSet erstellen."""
        cs = ChangeSet()
        assert cs.created == []
        assert cs.updated == []
        assert cs.deleted == []
        assert cs.sync_token is None

    def test_changeset_with_contacts(self):
        """ChangeSet mit Kontakten."""
        c1 = Contact(first_name="Tim", last_name="Mueller")
        c2 = Contact(first_name="Anna", last_name="Schmidt")

        cs = ChangeSet(
            created=[c1],
            updated=[c2],
            deleted=["uid-123"],
            sync_token="token-abc"
        )
        assert len(cs.created) == 1
        assert len(cs.updated) == 1
        assert len(cs.deleted) == 1
        assert cs.sync_token == "token-abc"

    def test_changeset_has_changes(self):
        """has_changes Property testen."""
        empty = ChangeSet()
        assert empty.has_changes is False

        with_created = ChangeSet(created=[Contact(first_name="Tim", last_name="M")])
        assert with_created.has_changes is True


class TestAbstractSyncProvider:
    """Tests fuer AbstractSyncProvider Interface."""

    def test_cannot_instantiate_abstract(self):
        """Abstrakte Klasse kann nicht instanziiert werden."""
        with pytest.raises(TypeError):
            AbstractSyncProvider()

    def test_concrete_implementation(self):
        """Konkrete Implementation funktioniert."""
        class MockProvider(AbstractSyncProvider):
            def authenticate(self, credentials):
                return True

            def pull_contacts(self):
                return [Contact(first_name="Test", last_name="User")]

            def push_contact(self, contact):
                return "mock-uid-123"

            def delete_contact(self, uid):
                return True

            def get_changes_since(self, sync_token):
                return ChangeSet(sync_token="new-token")

        provider = MockProvider()
        assert provider.authenticate({}) is True
        assert len(provider.pull_contacts()) == 1
        assert provider.push_contact(Contact(first_name="A", last_name="B")) == "mock-uid-123"
        assert provider.delete_contact("uid") is True
        assert provider.get_changes_since("old").sync_token == "new-token"
