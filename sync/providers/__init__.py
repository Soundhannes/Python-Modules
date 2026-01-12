"""
Sync Provider fuer verschiedene CardDAV/Contact Services.
"""

from .base import AbstractSyncProvider, Contact, ChangeSet
from .nextcloud import NextcloudProvider
from .google import GoogleProvider
from .icloud import ICloudProvider

__all__ = [
    'AbstractSyncProvider',
    'Contact',
    'ChangeSet',
    'NextcloudProvider',
    'GoogleProvider',
    'ICloudProvider',
]
