"""
TDD Tests fuer Google People API Provider.

Nutzt OAuth 2.0 fuer Authentifizierung.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from sync.providers.google import GoogleProvider
from sync.providers.base import Contact, ChangeSet


class TestAuthentication:
    """Tests fuer Google OAuth Authentifizierung."""

    def test_authenticate_with_refresh_token(self):
        """Authentifizierung mit bestehendem Refresh-Token."""
        provider = GoogleProvider()
        
        with patch('google.oauth2.credentials.Credentials') as mock_creds:
            mock_creds.return_value.valid = True
            mock_creds.return_value.expired = False
            
            result = provider.authenticate({
                "client_id": "client-id",
                "client_secret": "client-secret",
                "refresh_token": "refresh-token"
            })
            
            assert result is True

    def test_authenticate_missing_credentials(self):
        """Fehlende OAuth Credentials."""
        provider = GoogleProvider()
        
        with pytest.raises(ValueError, match="Missing required"):
            provider.authenticate({})

    def test_get_auth_url(self):
        """OAuth URL fuer User-Authorisierung generieren."""
        provider = GoogleProvider()
        
        with patch('google_auth_oauthlib.flow.Flow') as mock_flow:
            mock_flow.from_client_config.return_value.authorization_url.return_value = (
                "https://accounts.google.com/o/oauth2/auth?...",
                "state123"
            )
            
            url = provider.get_auth_url({
                "client_id": "client-id",
                "client_secret": "client-secret"
            })
            
            assert "accounts.google.com" in url


class TestPullContacts:
    """Tests fuer Kontakt-Abruf."""

    def test_pull_contacts_returns_list(self):
        """pull_contacts gibt Liste von Contacts zurueck."""
        provider = GoogleProvider()
        provider.credentials = Mock()
        provider.credentials.valid = True
        
        with patch('googleapiclient.discovery.build') as mock_build:
            mock_service = MagicMock()
            mock_build.return_value = mock_service
            
            # Mock People API response
            mock_service.people.return_value.connections.return_value.list.return_value.execute.return_value = {
                "connections": [
                    {
                        "resourceName": "people/c123",
                        "etag": "etag123",
                        "names": [{"givenName": "Max", "familyName": "Mustermann"}],
                        "phoneNumbers": [{"value": "+49 171 1234567"}],
                        "emailAddresses": [{"value": "max@example.de"}],
                        "metadata": {"sources": [{"updateTime": "2024-01-15T12:00:00Z"}]}
                    }
                ],
                "nextSyncToken": "token123"
            }
            
            contacts = provider.pull_contacts()
            
            assert isinstance(contacts, list)
            assert len(contacts) == 1
            assert contacts[0].first_name == "Max"
            assert contacts[0].last_name == "Mustermann"
            assert contacts[0].google_uid == "people/c123"

    def test_pull_contacts_empty(self):
        """Leeres Adressbuch."""
        provider = GoogleProvider()
        provider.credentials = Mock()
        provider.credentials.valid = True
        
        with patch('googleapiclient.discovery.build') as mock_build:
            mock_service = MagicMock()
            mock_build.return_value = mock_service
            mock_service.people.return_value.connections.return_value.list.return_value.execute.return_value = {
                "connections": []
            }
            
            contacts = provider.pull_contacts()
            
            assert contacts == []


class TestPushContact:
    """Tests fuer Kontakt-Upload."""

    def test_push_new_contact(self):
        """Neuen Kontakt erstellen."""
        provider = GoogleProvider()
        provider.credentials = Mock()
        provider.credentials.valid = True
        
        with patch('googleapiclient.discovery.build') as mock_build:
            mock_service = MagicMock()
            mock_build.return_value = mock_service
            mock_service.people.return_value.createContact.return_value.execute.return_value = {
                "resourceName": "people/c456"
            }
            
            contact = Contact(
                first_name="Neu",
                last_name="Kontakt",
                phone="+49 171 1234567"
            )
            
            uid = provider.push_contact(contact)
            
            assert uid == "people/c456"

    def test_push_update_contact(self):
        """Existierenden Kontakt aktualisieren."""
        provider = GoogleProvider()
        provider.credentials = Mock()
        provider.credentials.valid = True
        
        with patch('googleapiclient.discovery.build') as mock_build:
            mock_service = MagicMock()
            mock_build.return_value = mock_service
            mock_service.people.return_value.get.return_value.execute.return_value = {
                "resourceName": "people/c123",
                "etag": "old-etag"
            }
            mock_service.people.return_value.updateContact.return_value.execute.return_value = {
                "resourceName": "people/c123"
            }
            
            contact = Contact(
                first_name="Aktualisiert",
                last_name="Kontakt",
                google_uid="people/c123"
            )
            
            uid = provider.push_contact(contact)
            
            assert uid == "people/c123"


class TestDeleteContact:
    """Tests fuer Kontakt-Loeschung."""

    def test_delete_contact_success(self):
        """Kontakt erfolgreich loeschen."""
        provider = GoogleProvider()
        provider.credentials = Mock()
        provider.credentials.valid = True
        
        with patch('googleapiclient.discovery.build') as mock_build:
            mock_service = MagicMock()
            mock_build.return_value = mock_service
            mock_service.people.return_value.deleteContact.return_value.execute.return_value = {}
            
            result = provider.delete_contact("people/c123")
            
            assert result is True

    def test_delete_contact_not_found(self):
        """Kontakt existiert nicht."""
        provider = GoogleProvider()
        provider.credentials = Mock()
        provider.credentials.valid = True
        
        with patch('googleapiclient.discovery.build') as mock_build:
            mock_service = MagicMock()
            mock_build.return_value = mock_service
            from googleapiclient.errors import HttpError
            mock_service.people.return_value.deleteContact.return_value.execute.side_effect = HttpError(
                resp=Mock(status=404), content=b'Not found'
            )
            
            result = provider.delete_contact("people/nonexistent")
            
            assert result is False


class TestGetChangesSince:
    """Tests fuer inkrementellen Sync."""

    def test_get_changes_with_sync_token(self):
        """Inkrementeller Sync mit Token."""
        provider = GoogleProvider()
        provider.credentials = Mock()
        provider.credentials.valid = True
        
        with patch('googleapiclient.discovery.build') as mock_build:
            mock_service = MagicMock()
            mock_build.return_value = mock_service
            mock_service.people.return_value.connections.return_value.list.return_value.execute.return_value = {
                "connections": [
                    {
                        "resourceName": "people/c789",
                        "names": [{"givenName": "Neu", "familyName": "Person"}],
                        "metadata": {"deleted": False}
                    }
                ],
                "nextSyncToken": "new-token"
            }
            
            changes = provider.get_changes_since("old-token")
            
            assert isinstance(changes, ChangeSet)
            assert changes.sync_token == "new-token"
