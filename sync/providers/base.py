"""
Base Provider - Abstrakte Klasse und Datenstrukturen fuer Sync-Provider.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, List, Dict, Any


@dataclass
class Contact:
    """Kontakt-Datenstruktur fuer Sync."""
    
    # Identifikation
    id: Optional[int] = None
    
    # Name
    first_name: str = ""
    middle_name: Optional[str] = None
    last_name: str = ""
    
    # Kontaktdaten
    phone: Optional[str] = None
    email: Optional[str] = None
    
    # Adresse
    street: Optional[str] = None
    house_nr: Optional[str] = None
    zip: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    
    # Zusatzinfos
    important_dates: List[Dict[str, str]] = field(default_factory=list)
    last_contact: Optional[date] = None
    context: Optional[str] = None
    
    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    # Provider-UIDs
    icloud_uid: Optional[str] = None
    google_uid: Optional[str] = None
    nextcloud_uid: Optional[str] = None
    sync_etag: Optional[str] = None
    
    @property
    def full_name(self) -> str:
        """Gibt den vollen Namen zurueck."""
        parts = [self.first_name]
        if self.middle_name:
            parts.append(self.middle_name)
        parts.append(self.last_name)
        return " ".join(filter(None, parts))


@dataclass
class ChangeSet:
    """Aenderungen seit letztem Sync."""
    
    created: List[Contact] = field(default_factory=list)
    updated: List[Contact] = field(default_factory=list)
    deleted: List[str] = field(default_factory=list)  # UIDs
    sync_token: Optional[str] = None
    
    @property
    def has_changes(self) -> bool:
        """Prueft ob Aenderungen vorhanden sind."""
        return bool(self.created or self.updated or self.deleted)


class AbstractSyncProvider(ABC):
    """
    Abstrakte Basisklasse fuer Sync-Provider.
    
    Jeder Provider (iCloud, Google, Nextcloud) muss diese Methoden implementieren.
    """
    
    @abstractmethod
    def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """
        Authentifiziert beim Provider.
        
        Args:
            credentials: Provider-spezifische Zugangsdaten
            
        Returns:
            True wenn erfolgreich, False sonst
        """
        pass
    
    @abstractmethod
    def pull_contacts(self) -> List[Contact]:
        """
        Holt alle Kontakte vom Provider.
        
        Returns:
            Liste aller Kontakte
        """
        pass
    
    @abstractmethod
    def push_contact(self, contact: Contact) -> str:
        """
        Erstellt oder aktualisiert einen Kontakt beim Provider.
        
        Args:
            contact: Der zu speichernde Kontakt
            
        Returns:
            UID des Kontakts beim Provider
        """
        pass
    
    @abstractmethod
    def delete_contact(self, uid: str) -> bool:
        """
        Loescht einen Kontakt beim Provider.
        
        Args:
            uid: Provider-UID des Kontakts
            
        Returns:
            True wenn erfolgreich
        """
        pass
    
    @abstractmethod
    def get_changes_since(self, sync_token: Optional[str]) -> ChangeSet:
        """
        Holt Aenderungen seit letztem Sync.
        
        Args:
            sync_token: Token vom letzten Sync (None fuer Initial-Sync)
            
        Returns:
            ChangeSet mit allen Aenderungen
        """
        pass
