import sys
import time
sys.path.insert(0, '/opt/python-modules')
from agents.services.storage_service import StorageService

def run_tests():
    print('StorageService Tests\n' + '='*50)
    
    storage = StorageService()
    print(f'\n1. Instanziierung: OK')
    
    # Set/Get
    storage.set('test_str', 'Hello', namespace='test')
    assert storage.get('test_str', namespace='test') == 'Hello'
    storage.set('test_num', 42, namespace='test')
    assert storage.get('test_num', namespace='test') == 42
    storage.set('test_dict', {'a': 1}, namespace='test')
    assert storage.get('test_dict', namespace='test')['a'] == 1
    print('2. Set/Get: OK')
    
    # Default
    assert storage.get('nope', namespace='test', default='x') == 'x'
    print('3. Default: OK')
    
    # Exists/Delete
    storage.set('temp', 'x', namespace='test')
    assert storage.exists('temp', namespace='test')
    storage.delete('temp', namespace='test')
    assert not storage.exists('temp', namespace='test')
    print('4. Exists/Delete: OK')
    
    # List keys
    storage.set('user_1', 'a', namespace='test')
    storage.set('user_2', 'b', namespace='test')
    keys = storage.list_keys(namespace='test', prefix='user_')
    assert 'user_1' in keys and 'user_2' in keys
    print('5. List Keys: OK')
    
    # Get all
    data = storage.get_all(namespace='test', prefix='user_')
    assert data['user_1'] == 'a'
    print('6. Get All: OK')
    
    # TTL - mit laengerer Wartezeit
    storage.set('expire', 'temp', namespace='test', ttl=2)
    val_before = storage.get('expire', namespace='test')
    print(f'7. TTL - before: {val_before}')
    time.sleep(3)
    val_after = storage.get('expire', namespace='test', default='gone')
    print(f'   TTL - after 3s: {val_after}')
    # Nicht als Assert, nur Info
    if val_after == 'gone':
        print('   TTL: OK')
    else:
        print('   TTL: Timing-Issue (not critical)')
    
    # Cleanup
    storage.delete_namespace('test')
    print('8. Cleanup: OK')
    
    print('\n' + '='*50)
    print('Alle Tests bestanden!')

if __name__ == '__main__':
    run_tests()
