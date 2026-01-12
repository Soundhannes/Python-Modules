"""
TDD Tests fuer iCloud CardDAV Provider.

Nutzt App-spezifisches Passwort fuer Authentifizierung.
"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from sync.providers.icloud import ICloudProvider
from sync.providers.base import Contact, ChangeSet


class TestAuthentication:
    """Tests fuer iCloud Authentifizierung."""

    def test_authenticate_success(self):
        """Erfolgreiche Authentifizierung mit App-Passwort."""
        provider = ICloudProvider()
        
        with patch('requests.Session') as mock_session:
            # Erste Anfrage: PROPFIND Test
            mock_response1 = Mock()
            mock_response1.status_code = 207
            mock_response1.text = """<?xml version="1.0"?>
            <d:multistatus xmlns:d="DAV:">
                <d:response>
                    <d:propstat>
                        <d:prop>
                            <d:current-user-principal>
                                <d:href>/123456/principal/</d:href>
                            </d:current-user-principal>
                        </d:prop>
                    </d:propstat>
                </d:response>
            </d:multistatus>"""
            
            # Zweite Anfrage: addressbook-home-set
            mock_response2 = Mock()
            mock_response2.status_code = 207
            mock_response2.text = """<?xml version="1.0"?>
            <d:multistatus xmlns:d="DAV:" xmlns:card="urn:ietf:params:xml:ns:carddav">
                <d:response>
                    <d:propstat>
                        <d:prop>
                            <card:addressbook-home-set>
                                <d:href>/123456/carddavhome/</d:href>
                            </card:addressbook-home-set>
                        </d:prop>
                    </d:propstat>
                </d:response>
            </d:multistatus>"""
            
            mock_session.return_value.request.side_effect = [
                mock_response1,  # First PROPFIND
                mock_response1,  # Principal discovery
                mock_response2   # Addressbook home set
            ]
            
            result = provider.authenticate({
                "apple_id": "user@icloud.com",
                "app_password": "xxxx-xxxx-xxxx-xxxx"
            })
            
            assert result is True

    def test_authenticate_failure(self):
        """Fehlgeschlagene Authentifizierung."""
        provider = ICloudProvider()
        
        with patch('requests.Session') as mock_session:
            mock_response = Mock()
            mock_response.status_code = 401
            mock_session.return_value.request.return_value = mock_response
            
            result = provider.authenticate({
                "apple_id": "user@icloud.com",
                "app_password": "wrong-password"
            })
            
            assert result is False

    def test_authenticate_missing_credentials(self):
        """Fehlende Credentials."""
        provider = ICloudProvider()
        
        with pytest.raises(ValueError, match="Missing required"):
            provider.authenticate({})


class TestDiscoverAddressbook:
    """Tests fuer Adressbuch-Discovery."""

    def test_discover_addressbook_url(self):
        """Findet CardDAV URL."""
        provider = ICloudProvider()
        provider.session = Mock()
        
        mock_response = Mock()
        mock_response.status_code = 207
        mock_response.text = """<?xml version="1.0"?>
        <d:multistatus xmlns:d="DAV:">
            <d:response>
                <d:propstat>
                    <d:prop>
                        <d:current-user-principal>
                            <d:href>/123456/principal/</d:href>
                        </d:current-user-principal>
                    </d:prop>
                </d:propstat>
            </d:response>
        </d:multistatus>"""
        
        provider.session.request.return_value = mock_response
        
        principal = provider._discover_principal()
        assert "/123456/principal/" in principal


class TestPullContacts:
    """Tests fuer Kontakt-Abruf."""

    def test_pull_contacts_returns_list(self):
        """pull_contacts gibt Liste von Contacts zurueck."""
        provider = ICloudProvider()
        provider.session = Mock()
        provider.addressbook_url = "https://contacts.icloud.com/123456/carddavhome/card/"
        
        mock_response = Mock()
        mock_response.status_code = 207
        mock_response.text = """<?xml version="1.0"?>
        <d:multistatus xmlns:d="DAV:" xmlns:card="urn:ietf:params:xml:ns:carddav">
            <d:response>
                <d:href>/123456/carddavhome/card/abc.vcf</d:href>
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
        assert contacts[0].icloud_uid == "abc-123"


class TestPushContact:
    """Tests fuer Kontakt-Upload."""

    def test_push_new_contact(self):
        """Neuen Kontakt hochladen."""
        provider = ICloudProvider()
        provider.session = Mock()
        provider.addressbook_url = "https://contacts.icloud.com/123456/carddavhome/card/"
        
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.headers = {"ETag": '"new-etag"'}
        provider.session.request.return_value = mock_response
        
        contact = Contact(
            first_name="Neu",
            last_name="Kontakt"
        )
        
        uid = provider.push_contact(contact)
        
        assert uid is not None


class TestDeleteContact:
    """Tests fuer Kontakt-Loeschung."""

    def test_delete_contact_success(self):
        """Kontakt erfolgreich loeschen."""
        provider = ICloudProvider()
        provider.session = Mock()
        provider.addressbook_url = "https://contacts.icloud.com/123456/carddavhome/card/"
        
        mock_response = Mock()
        mock_response.status_code = 204
        provider.session.request.return_value = mock_response
        
        result = provider.delete_contact("abc-123")
        
        assert result is True


class TestGetChangesSince:
    """Tests fuer Sync."""

    def test_get_changes_initial_sync(self):
        """Erster Sync ohne Token."""
        provider = ICloudProvider()
        provider.session = Mock()
        provider.addressbook_url = "https://contacts.icloud.com/123456/carddavhome/card/"
        
        mock_response = Mock()
        mock_response.status_code = 207
        mock_response.text = """<?xml version="1.0"?>
        <d:multistatus xmlns:d="DAV:" xmlns:card="urn:ietf:params:xml:ns:carddav">
            <d:response>
                <d:href>/card/abc.vcf</d:href>
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
            <d:sync-token>token-xyz</d:sync-token>
        </d:multistatus>"""
        provider.session.request.return_value = mock_response
        
        changes = provider.get_changes_since(None)
        
        assert isinstance(changes, ChangeSet)
        assert changes.sync_token == "token-xyz"
