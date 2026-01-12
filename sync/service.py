"""
Sync-Service fuer bidirektionale Kontaktsynchronisation.

Orchestriert Provider, Conflict Resolution und DB-Operationen.
"""
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
import json

from .providers.base import AbstractSyncProvider, Contact, ChangeSet
from .providers.nextcloud import NextcloudProvider
from .providers.google import GoogleProvider
from .providers.icloud import ICloudProvider
from .conflict_resolver import ConflictResolver, ConflictResult

logger = logging.getLogger(__name__)


class SyncService:
    """
    Haupt-Sync-Service.
    
    Koordiniert Synchronisation zwischen DB und Providern.
    """
    
    PROVIDERS = {
        'nextcloud': NextcloudProvider,
        'google': GoogleProvider,
        'icloud': ICloudProvider
    }
    
    def __init__(self, db_connection):
        """
        Initialisiert Sync-Service.
        
        Args:
            db_connection: psycopg2 Connection oder Connection-Pool
        """
        self.db = db_connection
        self.resolver = ConflictResolver()
        self.providers: Dict[str, AbstractSyncProvider] = {}
    
    def init_provider(self, provider_name: str, credentials: Dict[str, Any]) -> bool:
        """
        Initialisiert und authentifiziert einen Provider.
        
        Args:
            provider_name: Name (nextcloud, google, icloud)
            credentials: Provider-spezifische Credentials
            
        Returns:
            True bei erfolgreicher Authentifizierung
        """
        if provider_name not in self.PROVIDERS:
            raise ValueError(f"Unknown provider: {provider_name}")
        
        provider_class = self.PROVIDERS[provider_name]
        provider = provider_class()
        
        if provider.authenticate(credentials):
            self.providers[provider_name] = provider
            return True
        return False
    
    def sync_provider(self, provider_name: str) -> Dict[str, int]:
        """
        Fuehrt vollstaendige Synchronisation fuer einen Provider durch.
        
        Args:
            provider_name: Name des Providers
            
        Returns:
            Dict mit Statistiken (pulled, pushed, deleted, conflicts)
        """
        if provider_name not in self.providers:
            raise ValueError(f"Provider not initialized: {provider_name}")
        
        provider = self.providers[provider_name]
        stats = {'pulled': 0, 'pushed': 0, 'deleted': 0, 'conflicts': 0}
        
        # Letzten Sync-Token holen
        sync_token = self._get_sync_token(provider_name)
        
        # Aenderungen von Remote holen
        changes = provider.get_changes_since(sync_token)
        
        # Pull: Remote -> DB
        for remote_contact in changes.created + changes.updated:
            result = self._handle_remote_contact(provider_name, remote_contact)
            if result == 'pulled':
                stats['pulled'] += 1
            elif result == 'conflict':
                stats['conflicts'] += 1
        
        # Geloeschte Kontakte verarbeiten
        for uid in changes.deleted:
            self._handle_remote_delete(provider_name, uid)
            stats['deleted'] += 1
        
        # Push: DB -> Remote (pending changes)
        pending = self._get_pending_contacts(provider_name)
        for local_contact in pending:
            try:
                uid = provider.push_contact(local_contact)
                self._update_provider_uid(local_contact.id, provider_name, uid)
                self._mark_synced(local_contact.id)
                stats['pushed'] += 1
            except Exception as e:
                logger.error(f"Failed to push contact {local_contact.id}: {e}")
        
        # Neuen Sync-Token speichern
        if changes.sync_token:
            self._save_sync_token(provider_name, changes.sync_token)
        
        # Sync-Log schreiben
        self._log_sync(provider_name, stats)
        
        return stats
    
    def _handle_remote_contact(self, provider_name: str, remote: Contact) -> str:
        """Verarbeitet einen Remote-Kontakt."""
        uid_field = f"{provider_name}_uid"
        remote_uid = getattr(remote, uid_field)
        
        # Existiert in DB?
        local = self._find_by_provider_uid(provider_name, remote_uid)
        
        if local is None:
            # Neu: In DB einfuegen
            self._insert_contact(remote, provider_name)
            return 'pulled'
        
        # Konfliktaufloesung
        result = self.resolver.resolve(local, remote, provider_name)
        
        if result.action == 'pull':
            self._update_contact(result.contact)
            return 'pulled'
        elif result.action == 'push':
            return 'conflict'  # Wird spaeter gepusht
        
        return 'none'
    
    def _handle_remote_delete(self, provider_name: str, uid: str) -> None:
        """Soft-Delete eines remote geloeschten Kontakts."""
        cursor = self.db.cursor()
        uid_field = f"{provider_name}_uid"
        
        cursor.execute(f"""
            UPDATE people 
            SET deleted_at = NOW(), sync_status = 'deleted'
            WHERE {uid_field} = %s AND deleted_at IS NULL
        """, (uid,))
        self.db.commit()
    
    def _find_by_provider_uid(self, provider_name: str, uid: str) -> Optional[Contact]:
        """Findet Kontakt anhand Provider-UID."""
        cursor = self.db.cursor()
        uid_field = f"{provider_name}_uid"
        
        cursor.execute(f"""
            SELECT id, first_name, middle_name, last_name, phone, email,
                   street, house_nr, zip, city, country, important_dates,
                   last_contact, context, created_at, updated_at,
                   icloud_uid, google_uid, nextcloud_uid, sync_etag
            FROM people 
            WHERE {uid_field} = %s AND deleted_at IS NULL
        """, (uid,))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        return Contact(
            id=row[0],
            first_name=row[1] or '',
            middle_name=row[2],
            last_name=row[3] or '',
            phone=row[4],
            email=row[5],
            street=row[6],
            house_nr=row[7],
            zip=row[8],
            city=row[9],
            country=row[10],
            important_dates=row[11] or [],
            last_contact=row[12],
            context=row[13],
            created_at=row[14],
            updated_at=row[15],
            icloud_uid=row[16],
            google_uid=row[17],
            nextcloud_uid=row[18],
            sync_etag=row[19]
        )
    
    def _insert_contact(self, contact: Contact, provider_name: str) -> int:
        """Fuegt neuen Kontakt in DB ein."""
        cursor = self.db.cursor()
        
        cursor.execute("""
            INSERT INTO people (
                first_name, middle_name, last_name, phone, email,
                street, house_nr, zip, city, country, important_dates,
                last_contact, context, icloud_uid, google_uid, nextcloud_uid,
                sync_etag, sync_status, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, 'synced', NOW(), NOW()
            ) RETURNING id
        """, (
            contact.first_name, contact.middle_name, contact.last_name,
            contact.phone, contact.email,
            contact.street, contact.house_nr, contact.zip, contact.city, contact.country,
            json.dumps(contact.important_dates),
            contact.last_contact, contact.context,
            contact.icloud_uid, contact.google_uid, contact.nextcloud_uid,
            contact.sync_etag
        ))
        
        new_id = cursor.fetchone()[0]
        self.db.commit()
        return new_id
    
    def _update_contact(self, contact: Contact) -> None:
        """Aktualisiert existierenden Kontakt."""
        cursor = self.db.cursor()
        
        cursor.execute("""
            UPDATE people SET
                first_name = %s, middle_name = %s, last_name = %s,
                phone = %s, email = %s,
                street = %s, house_nr = %s, zip = %s, city = %s, country = %s,
                important_dates = %s, last_contact = %s, context = %s,
                icloud_uid = %s, google_uid = %s, nextcloud_uid = %s,
                sync_etag = %s, sync_status = 'synced', updated_at = NOW()
            WHERE id = %s
        """, (
            contact.first_name, contact.middle_name, contact.last_name,
            contact.phone, contact.email,
            contact.street, contact.house_nr, contact.zip, contact.city, contact.country,
            json.dumps(contact.important_dates), contact.last_contact, contact.context,
            contact.icloud_uid, contact.google_uid, contact.nextcloud_uid,
            contact.sync_etag, contact.id
        ))
        self.db.commit()
    
    def _get_pending_contacts(self, provider_name: str) -> List[Contact]:
        """Holt alle Kontakte die gepusht werden muessen."""
        cursor = self.db.cursor()
        uid_field = f"{provider_name}_uid"
        
        # Kontakte ohne Provider-UID oder mit pending status
        cursor.execute(f"""
            SELECT id, first_name, middle_name, last_name, phone, email,
                   street, house_nr, zip, city, country, important_dates,
                   last_contact, context, created_at, updated_at,
                   icloud_uid, google_uid, nextcloud_uid, sync_etag
            FROM people 
            WHERE deleted_at IS NULL
              AND (sync_status = 'pending' OR {uid_field} IS NULL)
        """)
        
        contacts = []
        for row in cursor.fetchall():
            contacts.append(Contact(
                id=row[0],
                first_name=row[1] or '',
                middle_name=row[2],
                last_name=row[3] or '',
                phone=row[4],
                email=row[5],
                street=row[6],
                house_nr=row[7],
                zip=row[8],
                city=row[9],
                country=row[10],
                important_dates=row[11] or [],
                last_contact=row[12],
                context=row[13],
                created_at=row[14],
                updated_at=row[15],
                icloud_uid=row[16],
                google_uid=row[17],
                nextcloud_uid=row[18],
                sync_etag=row[19]
            ))
        
        return contacts
    
    def _update_provider_uid(self, contact_id: int, provider_name: str, uid: str) -> None:
        """Speichert Provider-UID nach erfolgreichem Push."""
        cursor = self.db.cursor()
        uid_field = f"{provider_name}_uid"
        
        cursor.execute(f"""
            UPDATE people SET {uid_field} = %s WHERE id = %s
        """, (uid, contact_id))
        self.db.commit()
    
    def _mark_synced(self, contact_id: int) -> None:
        """Markiert Kontakt als synchronisiert."""
        cursor = self.db.cursor()
        cursor.execute("""
            UPDATE people SET sync_status = 'synced' WHERE id = %s
        """, (contact_id,))
        self.db.commit()
    
    def _get_sync_token(self, provider_name: str) -> Optional[str]:
        """Holt letzten Sync-Token aus sync_config."""
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT credentials->>'sync_token' FROM sync_config
            WHERE provider = %s
        """, (provider_name,))
        row = cursor.fetchone()
        return row[0] if row else None
    
    def _save_sync_token(self, provider_name: str, token: str) -> None:
        """Speichert neuen Sync-Token."""
        cursor = self.db.cursor()
        cursor.execute("""
            UPDATE sync_config 
            SET credentials = jsonb_set(COALESCE(credentials, '{}'), '{sync_token}', %s::jsonb),
                last_sync = NOW(),
                updated_at = NOW()
            WHERE provider = %s
        """, (json.dumps(token), provider_name))
        self.db.commit()
    
    def _log_sync(self, provider_name: str, stats: Dict[str, int]) -> None:
        """Schreibt Sync-Log Eintrag."""
        cursor = self.db.cursor()
        
        for action, count in stats.items():
            if count > 0:
                cursor.execute("""
                    INSERT INTO sync_log (provider, direction, action, status, details)
                    VALUES (%s, %s, %s, 'success', %s)
                """, (
                    provider_name,
                    'sync',
                    action,
                    json.dumps({'count': count})
                ))
        
        self.db.commit()
