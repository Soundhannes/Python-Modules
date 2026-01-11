import sys
sys.path.insert(0, '/opt/python-modules')
from agents.utils.logger import Logger, LogLevel, get_logger

def run_tests():
    print('Logger Tests\n' + '='*50)
    
    logger = Logger('test_automation')
    print('\n1. Instanziierung: OK')
    
    # Logging verschiedener Level
    logger.debug('Debug message', {'detail': 'test'})
    logger.info('Info message')
    logger.warning('Warning message')
    logger.error('Error message', {'code': 500})
    logger.critical('Critical message')
    print('2. Log all levels: OK')
    
    # Logs abrufen
    logs = logger.get_logs(limit=10)
    assert len(logs) >= 5
    print(f'3. Get logs: {len(logs)} entries - OK')
    
    # Nach Level filtern
    errors = logger.get_logs(level=LogLevel.ERROR)
    assert all(log.level == 'error' for log in errors)
    print(f'4. Filter by level: {len(errors)} errors - OK')
    
    # Logs löschen
    deleted = logger.clear_all()
    print(f'5. Clear all: deleted {deleted} entries - OK')
    
    # Verifizieren
    logs = logger.get_logs()
    assert len(logs) == 0
    print('6. Verify empty: OK')
    
    print('\n' + '='*50)
    print('Alle Tests bestanden!')

if __name__ == '__main__':
    run_tests()
