import sys
sys.path.insert(0, '/opt/python-modules')
from agents.services.notification_service import NotificationService

def run_tests():
    print('NotificationService Tests\n' + '='*50)
    
    notifier = NotificationService()
    print('\n1. Instanziierung: OK')
    
    # Config setzen
    notifier.set_config('telegram', {'bot_token': 'test_token', 'default_chat_id': '12345'}, enabled=True)
    print('2. Set Config: OK')
    
    # Config lesen
    config = notifier.get_config('telegram')
    assert config['bot_token'] == 'test_token'
    assert config['default_chat_id'] == '12345'
    print('3. Get Config: OK')
    
    # List channels
    channels = notifier.list_channels()
    assert any(c['channel'] == 'telegram' for c in channels)
    print('4. List Channels: OK')
    
    # Telegram ohne echten Token (erwartet Fehler)
    result = notifier.send_telegram('Test')
    print(f'5. Telegram (fake token): success={result.success}, error={result.error[:50] if result.error else None}...')
    # Sollte fehlschlagen da Token ungültig
    
    # Webhook ohne URL (erwartet Fehler)
    result = notifier.send_webhook(message='Test')
    assert not result.success
    print(f'6. Webhook (no URL): success={result.success} - OK')
    
    # Config löschen
    notifier.delete_config('telegram')
    assert notifier.get_config('telegram') is None
    print('7. Delete Config: OK')
    
    print('\n' + '='*50)
    print('Alle Tests bestanden!')

if __name__ == '__main__':
    run_tests()
