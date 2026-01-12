"""
Sync-Modul fuer bidirektionale CardDAV-Synchronisation.

Provider: iCloud, Google Contacts, Nextcloud
"""

from .providers.base import AbstractSyncProvider, Contact, ChangeSet
from .providers.nextcloud import NextcloudProvider
from .providers.google import GoogleProvider
from .providers.icloud import ICloudProvider
from .vcard_parser import VCardParser
from .conflict_resolver import ConflictResolver, ConflictResult
from .service import SyncService
from .scheduler import SyncScheduler

__all__ = [
    # Base
    'AbstractSyncProvider',
    'Contact',
    'ChangeSet',
    # Providers
    'NextcloudProvider',
    'GoogleProvider',
    'ICloudProvider',
    # Parser
    'VCardParser',
    # Conflict
    'ConflictResolver',
    'ConflictResult',
    # Service
    'SyncService',
    'SyncScheduler',
]
