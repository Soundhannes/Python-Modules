"""
Conflict Resolver fuer bidirektionale Synchronisation.

Strategie: Last-Write-Wins basierend auf updated_at Timestamp.
"""
from dataclasses import dataclass, asdict, field
from typing import Optional, Literal
from datetime import datetime
from .providers.base import Contact


@dataclass
class ConflictResult:
    """Ergebnis einer Konfliktaufloesung."""
    winner: Literal["local", "remote", "none"]
    action: Literal["push", "pull", "none"]
    contact: Contact
    reason: str = ""


class ConflictResolver:
    """
    Loest Sync-Konflikte mit Last-Write-Wins Strategie.
    
    Bei gleichem Timestamp gewinnt lokal (SSOT = Single Source of Truth).
    """
    
    def resolve(
        self,
        local: Optional[Contact],
        remote: Optional[Contact],
        provider: Optional[str] = None
    ) -> ConflictResult:
        """
        Loest Konflikt zwischen lokalem und remote Kontakt.
        
        Args:
            local: Lokaler Kontakt aus DB (oder None)
            remote: Remote Kontakt vom Provider (oder None)
            provider: Name des Providers (icloud, google, nextcloud)
            
        Returns:
            ConflictResult mit Gewinner und Aktion
        """
        # Fall 1: Nur lokal vorhanden -> push
        if local is not None and remote is None:
            return ConflictResult(
                winner="local",
                action="push",
                contact=local,
                reason="Contact only exists locally"
            )
        
        # Fall 2: Nur remote vorhanden -> pull
        if local is None and remote is not None:
            return ConflictResult(
                winner="remote",
                action="pull",
                contact=remote,
                reason="Contact only exists remotely"
            )
        
        # Fall 3: Beide None -> sollte nicht vorkommen
        if local is None and remote is None:
            raise ValueError("Both local and remote are None")
        
        # Fall 4: Beide vorhanden -> vergleiche
        # Pruefe ob Daten identisch (kein Konflikt)
        if self._are_identical(local, remote):
            return ConflictResult(
                winner="none",
                action="none",
                contact=local,
                reason="Contacts are identical"
            )
        
        # Last-Write-Wins
        local_time = local.updated_at or datetime.min
        remote_time = remote.updated_at or datetime.min
        
        if local_time >= remote_time:
            # Lokal gewinnt (auch bei Gleichstand -> SSOT)
            return ConflictResult(
                winner="local",
                action="push",
                contact=local,
                reason=f"Local is newer ({local_time} >= {remote_time})"
            )
        else:
            # Remote gewinnt -> merge UIDs
            merged = self._merge_contact(local, remote, provider)
            return ConflictResult(
                winner="remote",
                action="pull",
                contact=merged,
                reason=f"Remote is newer ({remote_time} > {local_time})"
            )
    
    def _are_identical(self, local: Contact, remote: Contact) -> bool:
        """Prueft ob relevante Felder identisch sind."""
        fields_to_compare = [
            'first_name', 'middle_name', 'last_name',
            'phone', 'email',
            'street', 'house_nr', 'zip', 'city', 'country',
            'important_dates', 'context'
        ]
        
        for field in fields_to_compare:
            if getattr(local, field, None) != getattr(remote, field, None):
                return False
        return True
    
    def _merge_contact(
        self,
        local: Contact,
        remote: Contact,
        provider: Optional[str]
    ) -> Contact:
        """
        Merged remote Daten mit lokalen Metadaten.
        
        Behaelt: lokale DB-ID, alle Provider-UIDs
        Uebernimmt: alle anderen Felder von remote
        """
        # Starte mit remote Daten
        merged_dict = asdict(remote)
        
        # Behalte lokale DB-ID
        merged_dict['id'] = local.id
        
        # Behalte alle lokalen Provider-UIDs
        if local.icloud_uid:
            merged_dict['icloud_uid'] = local.icloud_uid
        if local.google_uid:
            merged_dict['google_uid'] = local.google_uid
        if local.nextcloud_uid:
            merged_dict['nextcloud_uid'] = local.nextcloud_uid
        
        # Setze neue Provider-UID von remote
        if provider and remote:
            uid_field = f"{provider}_uid"
            remote_uid = getattr(remote, uid_field, None)
            if remote_uid:
                merged_dict[uid_field] = remote_uid
        
        return Contact(**merged_dict)
