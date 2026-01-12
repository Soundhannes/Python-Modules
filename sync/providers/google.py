"""
Google People API Provider.

OAuth 2.0 Authentifizierung mit Google Contacts.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime

from .base import AbstractSyncProvider, Contact, ChangeSet


class GoogleProvider(AbstractSyncProvider):
    """
    Provider fuer Google People API.
    
    Scopes: https://www.googleapis.com/auth/contacts
    """
    
    SCOPES = ['https://www.googleapis.com/auth/contacts']
    
    def __init__(self):
        self.credentials = None
        self.sync_token: Optional[str] = None
    
    def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """
        Authentifiziert mit Google OAuth.
        
        Args:
            credentials: Dict mit client_id, client_secret, refresh_token
            
        Returns:
            True bei Erfolg
        """
        required = ['client_id', 'client_secret', 'refresh_token']
        missing = [k for k in required if k not in credentials or not credentials[k]]
        if missing:
            raise ValueError(f"Missing required credentials: {missing}")
        
        try:
            from google.oauth2.credentials import Credentials
            
            self.credentials = Credentials(
                token=None,
                refresh_token=credentials['refresh_token'],
                token_uri='https://oauth2.googleapis.com/token',
                client_id=credentials['client_id'],
                client_secret=credentials['client_secret'],
                scopes=self.SCOPES
            )
            
            # Refresh if expired
            if self.credentials.expired or not self.credentials.valid:
                from google.auth.transport.requests import Request
                self.credentials.refresh(Request())
            
            return self.credentials.valid
            
        except Exception:
            return False
    
    def get_auth_url(self, credentials: Dict[str, Any]) -> str:
        """
        Generiert OAuth URL fuer User-Authorisierung.
        
        Args:
            credentials: Dict mit client_id, client_secret
            
        Returns:
            Authorization URL
        """
        from google_auth_oauthlib.flow import Flow
        
        config = {
            "installed": {
                "client_id": credentials['client_id'],
                "client_secret": credentials['client_secret'],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }
        }
        
        flow = Flow.from_client_config(config, scopes=self.SCOPES)
        flow.redirect_uri = credentials.get('redirect_uri', 'urn:ietf:wg:oauth:2.0:oob')
        
        auth_url, _ = flow.authorization_url(prompt='consent')
        return auth_url
    
    def pull_contacts(self) -> List[Contact]:
        """
        Holt alle Kontakte von Google.
        
        Returns:
            Liste von Contact-Objekten
        """
        if not self.credentials or not self.credentials.valid:
            raise RuntimeError("Not authenticated")
        
        from googleapiclient.discovery import build
        
        service = build('people', 'v1', credentials=self.credentials)
        contacts = []
        next_page_token = None
        
        while True:
            results = service.people().connections().list(
                resourceName='people/me',
                pageSize=100,
                personFields='names,phoneNumbers,emailAddresses,addresses,birthdays,metadata',
                pageToken=next_page_token,
                requestSyncToken=True
            ).execute()
            
            for person in results.get('connections', []):
                contact = self._person_to_contact(person)
                if contact:
                    contacts.append(contact)
            
            # Sync token speichern
            if 'nextSyncToken' in results:
                self.sync_token = results['nextSyncToken']
            
            next_page_token = results.get('nextPageToken')
            if not next_page_token:
                break
        
        return contacts
    
    def push_contact(self, contact: Contact) -> str:
        """
        Laedt Kontakt zu Google hoch.
        
        Args:
            contact: Contact-Objekt
            
        Returns:
            resourceName des Kontakts
        """
        if not self.credentials or not self.credentials.valid:
            raise RuntimeError("Not authenticated")
        
        from googleapiclient.discovery import build
        
        service = build('people', 'v1', credentials=self.credentials)
        person = self._contact_to_person(contact)
        
        if contact.google_uid:
            # Update
            existing = service.people().get(
                resourceName=contact.google_uid,
                personFields='metadata'
            ).execute()
            
            person['etag'] = existing.get('etag')
            
            result = service.people().updateContact(
                resourceName=contact.google_uid,
                updatePersonFields='names,phoneNumbers,emailAddresses,addresses,birthdays',
                body=person
            ).execute()
        else:
            # Create
            result = service.people().createContact(body=person).execute()
        
        return result['resourceName']
    
    def delete_contact(self, uid: str) -> bool:
        """
        Loescht Kontakt in Google.
        
        Args:
            uid: Google resourceName (people/c...)
            
        Returns:
            True bei Erfolg
        """
        if not self.credentials or not self.credentials.valid:
            raise RuntimeError("Not authenticated")
        
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        
        service = build('people', 'v1', credentials=self.credentials)
        
        try:
            service.people().deleteContact(resourceName=uid).execute()
            return True
        except HttpError as e:
            if e.resp.status == 404:
                return False
            raise
    
    def get_changes_since(self, sync_token: Optional[str]) -> ChangeSet:
        """
        Holt Aenderungen seit letztem Sync.
        
        Args:
            sync_token: Token vom letzten Sync
            
        Returns:
            ChangeSet mit Aenderungen
        """
        if not self.credentials or not self.credentials.valid:
            raise RuntimeError("Not authenticated")
        
        if sync_token is None:
            contacts = self.pull_contacts()
            return ChangeSet(
                created=contacts,
                updated=[],
                deleted=[],
                sync_token=self.sync_token
            )
        
        from googleapiclient.discovery import build
        
        service = build('people', 'v1', credentials=self.credentials)
        
        created = []
        deleted = []
        
        results = service.people().connections().list(
            resourceName='people/me',
            personFields='names,phoneNumbers,emailAddresses,addresses,birthdays,metadata',
            syncToken=sync_token,
            requestSyncToken=True
        ).execute()
        
        for person in results.get('connections', []):
            metadata = person.get('metadata', {})
            if metadata.get('deleted'):
                deleted.append(person['resourceName'])
            else:
                contact = self._person_to_contact(person)
                if contact:
                    created.append(contact)
        
        return ChangeSet(
            created=created,
            updated=[],
            deleted=deleted,
            sync_token=results.get('nextSyncToken')
        )
    
    def _person_to_contact(self, person: Dict) -> Optional[Contact]:
        """Konvertiert Google Person zu Contact."""
        names = person.get('names', [])
        if not names:
            return None
        
        name = names[0]
        phones = person.get('phoneNumbers', [])
        emails = person.get('emailAddresses', [])
        addresses = person.get('addresses', [])
        birthdays = person.get('birthdays', [])
        
        contact = Contact(
            first_name=name.get('givenName', ''),
            middle_name=name.get('middleName'),
            last_name=name.get('familyName', ''),
            google_uid=person.get('resourceName'),
            sync_etag=person.get('etag')
        )
        
        if phones:
            contact.phone = phones[0].get('value')
        
        if emails:
            contact.email = emails[0].get('value')
        
        if addresses:
            addr = addresses[0]
            contact.street = addr.get('streetAddress')
            contact.city = addr.get('city')
            contact.zip = addr.get('postalCode')
            contact.country = addr.get('country')
        
        if birthdays:
            bday = birthdays[0].get('date', {})
            if bday:
                date_str = f"{bday.get('year', '0000')}-{bday.get('month', 1):02d}-{bday.get('day', 1):02d}"
                contact.important_dates.append({
                    "type": "birthday",
                    "date": date_str
                })
        
        # Update time
        metadata = person.get('metadata', {})
        sources = metadata.get('sources', [])
        if sources:
            update_time = sources[0].get('updateTime')
            if update_time:
                try:
                    contact.updated_at = datetime.fromisoformat(update_time.replace('Z', '+00:00'))
                except ValueError:
                    pass
        
        return contact
    
    def _contact_to_person(self, contact: Contact) -> Dict:
        """Konvertiert Contact zu Google Person."""
        person = {
            "names": [{
                "givenName": contact.first_name,
                "familyName": contact.last_name
            }]
        }
        
        if contact.middle_name:
            person["names"][0]["middleName"] = contact.middle_name
        
        if contact.phone:
            person["phoneNumbers"] = [{"value": contact.phone}]
        
        if contact.email:
            person["emailAddresses"] = [{"value": contact.email}]
        
        if any([contact.street, contact.city, contact.zip, contact.country]):
            person["addresses"] = [{
                "streetAddress": contact.street,
                "city": contact.city,
                "postalCode": contact.zip,
                "country": contact.country
            }]
        
        for date_entry in contact.important_dates:
            if date_entry.get("type") == "birthday":
                date_str = date_entry.get("date", "")
                if date_str:
                    parts = date_str.split("-")
                    if len(parts) == 3:
                        person["birthdays"] = [{
                            "date": {
                                "year": int(parts[0]),
                                "month": int(parts[1]),
                                "day": int(parts[2])
                            }
                        }]
        
        return person
