"""
TDD Tests fuer Nextcloud CardDAV Provider.

Nutzt Mocks fuer HTTP-Requests.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from sync.providers.nextcloud import NextcloudProvider
from sync.providers.base import Contact, ChangeSet


class TestAuthentication:
    """Tests fuer Nextcloud Authentifizierung."""

    def test_authenticate_success(self):
        """Erfolgreiche Authentifizierung."""
        provider = NextcloudProvider()
        
        with patch('requests.Session') as mock_session:
            mock_response = Mock()
            mock_response.status_code = 207
            mock_session.return_value.request.return_value = mock_response
            
            result = provider.authenticate({
                "server_url": "https://cloud.example.de",
                "username": "user",
                "password": "pass"
            })
            
            assert result is True
            assert provider.base_url == "https://cloud.example.de/remote.php/dav/addressbooks/users/user/contacts/"

    def test_authenticate_failure(self):
        """Fehlgeschlagene Authentifizierung."""
        provider = NextcloudProvider()
        
        with patch('requests.Session') as mock_session:
            mock_response = Mock()
            mock_response.status_code = 401
            mock_session.return_value.request.return_value = mock_response
            
            result = provider.authenticate({
                "server_url": "https://cloud.example.de",
                "username": "user",
                "password": "wrong"
            })
            
            assert result is False

    def test_authenticate_missing_credentials(self):
        """Fehlende Credentials."""
        provider = NextcloudProvider()
        
        with pytest.raises(ValueError, match="Missing required"):
            provider.authenticate({})


class TestPullContacts:
    """Tests fuer Kontakt-Abruf."""

    def test_pull_contacts_returns_list(self):
        """pull_contacts gibt Liste von Contacts zurueck."""
        provider = NextcloudProvider()
        provider.session = Mock()
        provider.base_url = "https://cloud.example.de/remote.php/dav/addressbooks/users/user/contacts/"
        
        # Mock PROPFIND response
        mock_response = Mock()
        mock_response.status_code = 207
        mock_response.text = """<?xml version="1.0" encoding="UTF-8"?>
        <d:multistatus xmlns:d="DAV:" xmlns:card="urn:ietf:params:xml:ns:carddav">
            <d:response>
                <d:href>/remote.php/dav/addressbooks/users/user/contacts/abc.vcf</d:href>
                <d:propstat>
                    <d:prop>
                        <d:getetag>"etag123"</d:getetag>
                        <card:address-data>BEGIN:VCARD
VERSION:3.0
FN:Max Mustermann
N:Mustermann;Max;;;
UID:abc-123
END:VCARD</card:address-data>
                    </d:prop>
                </d:propstat>
            </d:response>
        </d:multistatus>"""
        provider.session.request.return_value = mock_response
        
        contacts = provider.pull_contacts()
        
        assert isinstance(contacts, list)
        assert len(contacts) == 1
        assert contacts[0].first_name == "Max"
        assert contacts[0].last_name == "Mustermann"
        assert contacts[0].nextcloud_uid == "abc-123"

    def test_pull_contacts_empty(self):
        """Leeres Adressbuch."""
        provider = NextcloudProvider()
        provider.session = Mock()
        provider.base_url = "https://cloud.example.de/remote.php/dav/addressbooks/users/user/contacts/"
        
        mock_response = Mock()
        mock_response.status_code = 207
        mock_response.text = """<?xml version="1.0"?>
        <d:multistatus xmlns:d="DAV:">
        </d:multistatus>"""
        provider.session.request.return_value = mock_response
        
        contacts = provider.pull_contacts()
        
        assert contacts == []


class TestPushContact:
    """Tests fuer Kontakt-Upload."""

    def test_push_new_contact(self):
        """Neuen Kontakt hochladen."""
        provider = NextcloudProvider()
        provider.session = Mock()
        provider.base_url = "https://cloud.example.de/remote.php/dav/addressbooks/users/user/contacts/"
        
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.headers = {"ETag": '"new-etag"'}
        provider.session.request.return_value = mock_response
        
        contact = Contact(
            first_name="Neu",
            last_name="Kontakt",
            phone="+49 171 1234567"
        )
        
        uid = provider.push_contact(contact)
        
        assert uid is not None
        assert len(uid) > 0

    def test_push_update_contact(self):
        """Existierenden Kontakt aktualisieren."""
        provider = NextcloudProvider()
        provider.session = Mock()
        provider.base_url = "https://cloud.example.de/remote.php/dav/addressbooks/users/user/contacts/"
        
        mock_response = Mock()
        mock_response.status_code = 204
        mock_response.headers = {"ETag": '"updated-etag"'}
        provider.session.request.return_value = mock_response
        
        contact = Contact(
            first_name="Aktualisiert",
            last_name="Kontakt",
            nextcloud_uid="existing-uid-123"
        )
        
        uid = provider.push_contact(contact)
        
        assert uid == "existing-uid-123"


class TestDeleteContact:
    """Tests fuer Kontakt-Loeschung."""

    def test_delete_contact_success(self):
        """Kontakt erfolgreich loeschen."""
        provider = NextcloudProvider()
        provider.session = Mock()
        provider.base_url = "https://cloud.example.de/remote.php/dav/addressbooks/users/user/contacts/"
        
        mock_response = Mock()
        mock_response.status_code = 204
        provider.session.request.return_value = mock_response
        
        result = provider.delete_contact("abc-123")
        
        assert result is True

    def test_delete_contact_not_found(self):
        """Kontakt existiert nicht."""
        provider = NextcloudProvider()
        provider.session = Mock()
        provider.base_url = "https://cloud.example.de/remote.php/dav/addressbooks/users/user/contacts/"
        
        mock_response = Mock()
        mock_response.status_code = 404
        provider.session.request.return_value = mock_response
        
        result = provider.delete_contact("non-existent")
        
        assert result is False


class TestGetChangesSince:
    """Tests fuer inkrementellen Sync."""

    def test_get_changes_initial_sync(self):
        """Erster Sync ohne Token."""
        provider = NextcloudProvider()
        provider.session = Mock()
        provider.base_url = "https://cloud.example.de/remote.php/dav/addressbooks/users/user/contacts/"
        
        # Mock sync-collection response
        mock_response = Mock()
        mock_response.status_code = 207
        mock_response.text = """<?xml version="1.0"?>
        <d:multistatus xmlns:d="DAV:" xmlns:card="urn:ietf:params:xml:ns:carddav">
            <d:response>
                <d:href>/contacts/abc.vcf</d:href>
                <d:propstat>
                    <d:prop>
                        <card:address-data>BEGIN:VCARD
VERSION:3.0
FN:Max Mustermann
N:Mustermann;Max;;;
UID:abc-123
END:VCARD</card:address-data>
                    </d:prop>
                </d:propstat>
            </d:response>
            <d:sync-token>token-123</d:sync-token>
        </d:multistatus>"""
        provider.session.request.return_value = mock_response
        
        changes = provider.get_changes_since(None)
        
        assert isinstance(changes, ChangeSet)
        assert changes.sync_token == "token-123"
