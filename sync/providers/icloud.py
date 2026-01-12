"""
iCloud CardDAV Provider.

Nutzt App-spezifisches Passwort fuer Authentifizierung.
"""
import uuid
import re
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
import requests
import logging

from .base import AbstractSyncProvider, Contact, ChangeSet
from ..vcard_parser import VCardParser

logger = logging.getLogger(__name__)


class ICloudProvider(AbstractSyncProvider):
    """
    CardDAV Provider fuer iCloud.
    
    Auth: Apple ID + App-spezifisches Passwort
    """
    
    CARDDAV_URL = "https://contacts.icloud.com"
    NAMESPACES = {
        'd': 'DAV:',
        'card': 'urn:ietf:params:xml:ns:carddav'
    }
    
    def __init__(self):
        self.session: Optional[requests.Session] = None
        self.addressbook_url: Optional[str] = None
        self.vcard_parser = VCardParser()
    
    def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """
        Authentifiziert mit iCloud.
        
        Args:
            credentials: Dict mit apple_id, app_password
            
        Returns:
            True bei Erfolg
        """
        required = ['apple_id', 'app_password']
        missing = [k for k in required if k not in credentials or not credentials[k]]
        if missing:
            raise ValueError(f"Missing required credentials: {missing}")
        
        apple_id = credentials['apple_id'].strip()
        # App-Passwort: Bindestriche und Leerzeichen entfernen
        app_password = credentials['app_password'].replace('-', '').replace(' ', '').strip()
        
        logger.info(f"iCloud auth attempt for: {apple_id[:3]}***")
        logger.info(f"Password length after cleanup: {len(app_password)}")
        
        self.session = requests.Session()
        self.session.auth = (apple_id, app_password)
        self.session.headers.update({
            'User-Agent': 'DAVx5/4.3.1-ose',
            'Accept': '*/*',
        })
        
        try:
            # Erst Principal URL finden
            propfind_body = '''<?xml version="1.0" encoding="UTF-8"?>
<d:propfind xmlns:d="DAV:">
  <d:prop>
    <d:current-user-principal/>
  </d:prop>
</d:propfind>'''
            
            response = self.session.request(
                'PROPFIND',
                self.CARDDAV_URL,
                data=propfind_body,
                headers={
                    'Content-Type': 'application/xml; charset=utf-8',
                    'Depth': '0'
                },
                timeout=30
            )
            
            logger.info(f"iCloud PROPFIND status: {response.status_code}")
            logger.info(f"iCloud response headers: {dict(response.headers)}")
            
            if response.status_code == 401:
                logger.error("iCloud auth failed: 401 Unauthorized")
                return False
            
            if response.status_code not in (200, 207):
                logger.error(f"iCloud unexpected status: {response.status_code}")
                logger.error(f"Response: {response.text[:500]}")
                return False
            
            # Parse principal URL
            logger.info(f"iCloud response: {response.text[:500]}")
            self.addressbook_url = self._discover_addressbook(response)
            
            if self.addressbook_url:
                logger.info(f"iCloud addressbook URL: {self.addressbook_url}")
                return True
            else:
                logger.error("Could not discover addressbook URL")
                return False
            
        except requests.RequestException as e:
            logger.error(f"iCloud connection error: {e}")
            return False
    
    def _discover_addressbook(self, initial_response) -> Optional[str]:
        """Findet Adressbuch-URL durch CardDAV discovery."""
        try:
            root = ET.fromstring(initial_response.text)
            
            # Suche current-user-principal
            principal = root.find('.//{DAV:}current-user-principal/{DAV:}href')
            if principal is not None and principal.text:
                principal_url = principal.text
                logger.info(f"Found principal: {principal_url}")
                
                # Hole addressbook-home-set vom Principal
                if not principal_url.startswith('http'):
                    principal_url = self.CARDDAV_URL + principal_url
                
                propfind_body = '''<?xml version="1.0" encoding="UTF-8"?>
<d:propfind xmlns:d="DAV:" xmlns:card="urn:ietf:params:xml:ns:carddav">
  <d:prop>
    <card:addressbook-home-set/>
  </d:prop>
</d:propfind>'''
                
                r = self.session.request(
                    'PROPFIND',
                    principal_url,
                    data=propfind_body,
                    headers={'Content-Type': 'application/xml; charset=utf-8', 'Depth': '0'},
                    timeout=15
                )
                
                if r.status_code in (200, 207):
                    root2 = ET.fromstring(r.text)
                    home = root2.find('.//{urn:ietf:params:xml:ns:carddav}addressbook-home-set/{DAV:}href')
                    if home is not None and home.text:
                        home_url = home.text
                        if not home_url.startswith('http'):
                            home_url = self.CARDDAV_URL.rstrip('/') + home_url
                        logger.info(f"Found addressbook-home-set: {home_url}")
                        return home_url
                        
        except ET.ParseError as e:
            logger.error(f"XML parse error: {e}")
        except Exception as e:
            logger.error(f"Discovery error: {e}")
        
        return None
    
    def pull_contacts(self) -> List[Contact]:
        """Holt alle Kontakte aus iCloud."""
        if not self.session or not self.addressbook_url:
            raise RuntimeError("Not authenticated")
        
        # Erst Addressbooks im Home finden
        propfind_body = '''<?xml version="1.0" encoding="UTF-8"?>
<d:propfind xmlns:d="DAV:" xmlns:card="urn:ietf:params:xml:ns:carddav">
  <d:prop>
    <d:resourcetype/>
    <d:displayname/>
  </d:prop>
</d:propfind>'''
        
        r = self.session.request(
            'PROPFIND',
            self.addressbook_url,
            data=propfind_body,
            headers={'Content-Type': 'application/xml; charset=utf-8', 'Depth': '1'},
            timeout=30
        )
        
        if r.status_code != 207:
            logger.error(f"Failed to list addressbooks: {r.status_code}")
            return []
        
        # Finde das Addressbook
        addressbook_url = None
        try:
            root = ET.fromstring(r.text)
            for response in root.findall('.//{DAV:}response'):
                resourcetype = response.find('.//{DAV:}resourcetype')
                if resourcetype is not None:
                    if resourcetype.find('.//{urn:ietf:params:xml:ns:carddav}addressbook') is not None:
                        href = response.find('.//{DAV:}href')
                        if href is not None:
                            addressbook_url = href.text
                            if not addressbook_url.startswith('http'):
                                addressbook_url = self.CARDDAV_URL.rstrip('/') + addressbook_url
                            break
        except Exception as e:
            logger.error(f"Parse addressbooks error: {e}")
        
        if not addressbook_url:
            logger.error("No addressbook found")
            return []
        
        # Hole Kontakte
        report_body = '''<?xml version="1.0" encoding="UTF-8"?>
<card:addressbook-query xmlns:d="DAV:" xmlns:card="urn:ietf:params:xml:ns:carddav">
  <d:prop>
    <d:getetag/>
    <card:address-data/>
  </d:prop>
</card:addressbook-query>'''
        
        response = self.session.request(
            'REPORT',
            addressbook_url,
            data=report_body,
            headers={'Content-Type': 'application/xml; charset=utf-8', 'Depth': '1'},
            timeout=60
        )
        
        if response.status_code != 207:
            logger.error(f"Failed to fetch contacts: {response.status_code}")
            return []
        
        return self._parse_multistatus(response.text, 'icloud')
    
    def push_contact(self, contact: Contact) -> str:
        """Laedt Kontakt zu iCloud hoch."""
        if not self.session or not self.addressbook_url:
            raise RuntimeError("Not authenticated")
        
        uid = contact.icloud_uid or str(uuid.uuid4())
        contact.icloud_uid = uid
        
        vcard = self.vcard_parser.serialize(contact, provider="icloud")
        url = f"{self.addressbook_url}{uid}.vcf"
        
        response = self.session.request(
            'PUT',
            url,
            data=vcard,
            headers={'Content-Type': 'text/vcard; charset=utf-8'},
            timeout=15
        )
        
        if response.status_code in (201, 204):
            return uid
        
        raise RuntimeError(f"Failed to push contact: {response.status_code}")
    
    def delete_contact(self, uid: str) -> bool:
        """Loescht Kontakt in iCloud."""
        if not self.session or not self.addressbook_url:
            raise RuntimeError("Not authenticated")
        
        url = f"{self.addressbook_url}{uid}.vcf"
        response = self.session.request('DELETE', url, timeout=15)
        
        return response.status_code in (200, 204)
    
    def get_changes_since(self, sync_token: Optional[str]) -> ChangeSet:
        """Holt Aenderungen seit letztem Sync."""
        # Simplified: just pull all contacts
        contacts = self.pull_contacts()
        return ChangeSet(
            created=contacts,
            updated=[],
            deleted=[],
            sync_token=None
        )
    
    def _parse_multistatus(self, xml_text: str, provider: str) -> List[Contact]:
        """Parsed multistatus XML Response."""
        contacts = []
        
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return contacts
        
        for response in root.findall('.//{DAV:}response'):
            addr_data = response.find('.//{urn:ietf:params:xml:ns:carddav}address-data')
            if addr_data is not None and addr_data.text:
                try:
                    contact = self.vcard_parser.parse(addr_data.text)
                    uid_match = re.search(r'UID:(.+)', addr_data.text)
                    if uid_match:
                        contact.icloud_uid = uid_match.group(1).strip()
                    etag = response.find('.//{DAV:}getetag')
                    if etag is not None and etag.text:
                        contact.sync_etag = etag.text.strip('"')
                    contacts.append(contact)
                except ValueError:
                    pass
        
        return contacts
