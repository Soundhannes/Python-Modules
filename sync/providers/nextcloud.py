"""
Nextcloud CardDAV Provider.

Standard CardDAV Implementierung fuer Nextcloud Adressbuecher.
"""
import uuid
import re
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
import requests

from .base import AbstractSyncProvider, Contact, ChangeSet
from ..vcard_parser import VCardParser


class NextcloudProvider(AbstractSyncProvider):
    """
    CardDAV Provider fuer Nextcloud.
    
    Endpunkt: https://{server}/remote.php/dav/addressbooks/users/{user}/contacts/
    """
    
    NAMESPACES = {
        'd': 'DAV:',
        'card': 'urn:ietf:params:xml:ns:carddav'
    }
    
    def __init__(self):
        self.session: Optional[requests.Session] = None
        self.base_url: Optional[str] = None
        self.vcard_parser = VCardParser()
    
    def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """
        Authentifiziert mit Nextcloud.
        
        Args:
            credentials: Dict mit server_url, username, password
            
        Returns:
            True bei Erfolg, False bei Fehlschlag
        """
        required = ['server_url', 'username', 'password']
        missing = [k for k in required if k not in credentials or not credentials[k]]
        if missing:
            raise ValueError(f"Missing required credentials: {missing}")
        
        server_url = credentials['server_url'].rstrip('/')
        username = credentials['username']
        password = credentials['password']
        
        self.base_url = f"{server_url}/remote.php/dav/addressbooks/users/{username}/contacts/"
        
        self.session = requests.Session()
        self.session.auth = (username, password)
        
        # Teste Verbindung mit PROPFIND
        try:
            response = self.session.request(
                'PROPFIND',
                self.base_url,
                headers={'Depth': '0'},
                timeout=10
            )
            return response.status_code in (200, 207)
        except requests.RequestException:
            return False
    
    def pull_contacts(self) -> List[Contact]:
        """
        Holt alle Kontakte aus Nextcloud.
        
        Returns:
            Liste von Contact-Objekten
        """
        if not self.session or not self.base_url:
            raise RuntimeError("Not authenticated")
        
        # REPORT request fuer alle vCards
        body = """<?xml version="1.0" encoding="UTF-8"?>
        <card:addressbook-query xmlns:d="DAV:" xmlns:card="urn:ietf:params:xml:ns:carddav">
            <d:prop>
                <d:getetag/>
                <card:address-data/>
            </d:prop>
        </card:addressbook-query>"""
        
        response = self.session.request(
            'REPORT',
            self.base_url,
            data=body,
            headers={
                'Content-Type': 'application/xml',
                'Depth': '1'
            },
            timeout=30
        )
        
        if response.status_code != 207:
            return []
        
        return self._parse_multistatus(response.text)
    
    def push_contact(self, contact: Contact) -> str:
        """
        Laedt Kontakt zu Nextcloud hoch.
        
        Args:
            contact: Contact-Objekt
            
        Returns:
            UID des Kontakts
        """
        if not self.session or not self.base_url:
            raise RuntimeError("Not authenticated")
        
        # UID generieren falls nicht vorhanden
        uid = contact.nextcloud_uid or str(uuid.uuid4())
        
        # vCard erstellen
        # Temporaer UID setzen fuer Serialisierung
        contact.nextcloud_uid = uid
        vcard = self.vcard_parser.serialize(contact, provider="nextcloud")
        
        # PUT request
        url = f"{self.base_url}{uid}.vcf"
        response = self.session.request(
            'PUT',
            url,
            data=vcard,
            headers={'Content-Type': 'text/vcard'},
            timeout=10
        )
        
        if response.status_code in (201, 204):
            return uid
        
        raise RuntimeError(f"Failed to push contact: {response.status_code}")
    
    def delete_contact(self, uid: str) -> bool:
        """
        Loescht Kontakt in Nextcloud.
        
        Args:
            uid: Nextcloud UID des Kontakts
            
        Returns:
            True bei Erfolg, False wenn nicht gefunden
        """
        if not self.session or not self.base_url:
            raise RuntimeError("Not authenticated")
        
        url = f"{self.base_url}{uid}.vcf"
        response = self.session.request('DELETE', url, timeout=10)
        
        return response.status_code in (200, 204)
    
    def get_changes_since(self, sync_token: Optional[str]) -> ChangeSet:
        """
        Holt Aenderungen seit letztem Sync.
        
        Args:
            sync_token: Token vom letzten Sync (oder None fuer vollen Sync)
            
        Returns:
            ChangeSet mit Aenderungen
        """
        if not self.session or not self.base_url:
            raise RuntimeError("Not authenticated")
        
        if sync_token is None:
            # Voller Sync
            contacts = self.pull_contacts()
            return ChangeSet(
                created=contacts,
                updated=[],
                deleted=[],
                sync_token=self._get_sync_token()
            )
        
        # Inkrementeller Sync mit sync-collection
        body = f"""<?xml version="1.0" encoding="UTF-8"?>
        <d:sync-collection xmlns:d="DAV:" xmlns:card="urn:ietf:params:xml:ns:carddav">
            <d:sync-token>{sync_token}</d:sync-token>
            <d:sync-level>1</d:sync-level>
            <d:prop>
                <d:getetag/>
                <card:address-data/>
            </d:prop>
        </d:sync-collection>"""
        
        response = self.session.request(
            'REPORT',
            self.base_url,
            data=body,
            headers={'Content-Type': 'application/xml'},
            timeout=30
        )
        
        if response.status_code != 207:
            raise RuntimeError(f"Sync failed: {response.status_code}")
        
        return self._parse_sync_response(response.text)
    
    def _parse_multistatus(self, xml_text: str) -> List[Contact]:
        """Parsed multistatus XML Response zu Contacts."""
        contacts = []
        
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return contacts
        
        for response in root.findall('.//d:response', self.NAMESPACES):
            # Finde address-data
            addr_data = response.find('.//card:address-data', self.NAMESPACES)
            if addr_data is not None and addr_data.text:
                try:
                    contact = self.vcard_parser.parse(addr_data.text)
                    # Extrahiere UID aus vCard
                    uid_match = re.search(r'UID:(.+)', addr_data.text)
                    if uid_match:
                        contact.nextcloud_uid = uid_match.group(1).strip()
                    # ETag speichern
                    etag = response.find('.//d:getetag', self.NAMESPACES)
                    if etag is not None and etag.text:
                        contact.sync_etag = etag.text.strip('"')
                    contacts.append(contact)
                except ValueError:
                    pass  # Skip invalid vCards
        
        return contacts
    
    def _parse_sync_response(self, xml_text: str) -> ChangeSet:
        """Parsed sync-collection Response."""
        created = []
        updated = []
        deleted = []
        sync_token = None
        
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return ChangeSet()
        
        # Neuen Sync-Token extrahieren
        token_elem = root.find('.//d:sync-token', self.NAMESPACES)
        if token_elem is not None:
            sync_token = token_elem.text
        
        for response in root.findall('.//d:response', self.NAMESPACES):
            href = response.find('d:href', self.NAMESPACES)
            status = response.find('.//d:status', self.NAMESPACES)
            
            if status is not None and '404' in status.text:
                # Geloeschter Kontakt
                if href is not None:
                    # UID aus href extrahieren
                    uid = href.text.rstrip('.vcf').split('/')[-1]
                    deleted.append(uid)
            else:
                # Neuer oder geaenderter Kontakt
                addr_data = response.find('.//card:address-data', self.NAMESPACES)
                if addr_data is not None and addr_data.text:
                    try:
                        contact = self.vcard_parser.parse(addr_data.text)
                        uid_match = re.search(r'UID:(.+)', addr_data.text)
                        if uid_match:
                            contact.nextcloud_uid = uid_match.group(1).strip()
                        # Alles als "created" behandeln, Unterscheidung spaeter
                        created.append(contact)
                    except ValueError:
                        pass
        
        return ChangeSet(
            created=created,
            updated=updated,
            deleted=deleted,
            sync_token=sync_token
        )
    
    def _get_sync_token(self) -> Optional[str]:
        """Holt aktuellen Sync-Token."""
        body = """<?xml version="1.0" encoding="UTF-8"?>
        <d:propfind xmlns:d="DAV:">
            <d:prop>
                <d:sync-token/>
            </d:prop>
        </d:propfind>"""
        
        response = self.session.request(
            'PROPFIND',
            self.base_url,
            data=body,
            headers={
                'Content-Type': 'application/xml',
                'Depth': '0'
            },
            timeout=10
        )
        
        if response.status_code != 207:
            return None
        
        try:
            root = ET.fromstring(response.text)
            token = root.find('.//d:sync-token', self.NAMESPACES)
            if token is not None:
                return token.text
        except ET.ParseError:
            pass
        
        return None
