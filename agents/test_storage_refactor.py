"""Test: StorageService Refactoring - Namespace im Konstruktor."""

import sys
sys.path.insert(0, '/opt/python-modules')

from agents.services.storage_service import StorageService, get_storage_service


def test_namespace_in_constructor():
    print('=== Test 1: Namespace im Konstruktor ===')
    
    storage = StorageService(namespace='test_ns')
    assert storage.namespace == 'test_ns'
    print(f'Namespace: {storage.namespace}')
    print('OK\n')
    return storage


def test_set_get_without_namespace(storage):
    print('=== Test 2: Set/Get ohne Namespace-Parameter ===')
    
    # Ohne namespace Parameter - nutzt self.namespace
    storage.set('key1', 'value1')
    result = storage.get('key1')
    
    print(f'Set/Get ohne Parameter: {result}')
    assert result == 'value1'
    print('OK\n')


def test_set_get_with_namespace(storage):
    print('=== Test 3: Set/Get mit explizitem Namespace ===')
    
    # Mit explizitem namespace - überschreibt self.namespace
    storage.set('key2', 'value2', namespace='other_ns')
    
    # Sollte NICHT im Standard-Namespace sein
    result_default = storage.get('key2')
    print(f'Im Standard-Namespace: {result_default}')
    assert result_default is None
    
    # Sollte im expliziten Namespace sein
    result_other = storage.get('key2', namespace='other_ns')
    print(f'Im expliziten Namespace: {result_other}')
    assert result_other == 'value2'
    
    print('OK\n')


def test_factory_caching():
    print('=== Test 4: Factory mit Caching ===')
    
    # Gleicher Namespace = gleiche Instanz
    s1 = get_storage_service('cache_test')
    s2 = get_storage_service('cache_test')
    assert s1 is s2
    print('Gleicher Namespace = gleiche Instanz: OK')
    
    # Anderer Namespace = andere Instanz
    s3 = get_storage_service('other_cache')
    assert s1 is not s3
    print('Anderer Namespace = andere Instanz: OK')
    
    print('OK\n')


def test_backwards_compatibility():
    print('=== Test 5: Rückwärtskompatibilität ===')
    
    # Alte Nutzung: Ohne namespace im Konstruktor
    storage = StorageService()
    assert storage.namespace == 'default'
    print(f'Default Namespace: {storage.namespace}')
    
    # Alte Nutzung: namespace bei jedem Aufruf
    storage.set('old_key', 'old_value', namespace='legacy')
    result = storage.get('old_key', namespace='legacy')
    assert result == 'old_value'
    print('Legacy-Nutzung funktioniert: OK')
    
    print('OK\n')


def test_all_methods_use_namespace():
    print('=== Test 6: Alle Methoden nutzen Namespace ===')
    
    storage = StorageService(namespace='method_test')
    
    # set/get
    storage.set('m1', 'v1')
    assert storage.get('m1') == 'v1'
    
    # exists
    assert storage.exists('m1')
    
    # list_keys
    storage.set('prefix_a', 1)
    storage.set('prefix_b', 2)
    keys = storage.list_keys(prefix='prefix_')
    assert 'prefix_a' in keys
    assert 'prefix_b' in keys
    
    # get_all
    all_data = storage.get_all(prefix='prefix_')
    assert len(all_data) == 2
    
    # set_many
    storage.set_many({'bulk1': 'a', 'bulk2': 'b'})
    assert storage.get('bulk1') == 'a'
    
    # delete
    storage.delete('m1')
    assert not storage.exists('m1')
    
    print('Alle Methoden nutzen self.namespace: OK')
    print('OK\n')


def test_cleanup():
    print('=== Test 7: Cleanup ===')
    
    # Alle Test-Namespaces löschen
    namespaces = ['test_ns', 'other_ns', 'cache_test', 'other_cache', 'legacy', 'method_test']
    
    storage = StorageService()
    for ns in namespaces:
        deleted = storage.delete_namespace(ns)
        print(f'Deleted {ns}: {deleted} items')
    
    print('OK\n')


if __name__ == '__main__':
    print('StorageService Refactor Tests\n' + '='*50 + '\n')
    
    storage = test_namespace_in_constructor()
    test_set_get_without_namespace(storage)
    test_set_get_with_namespace(storage)
    test_factory_caching()
    test_backwards_compatibility()
    test_all_methods_use_namespace()
    test_cleanup()
    
    print('='*50)
    print('Alle Tests bestanden!')
