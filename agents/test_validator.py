import sys
sys.path.insert(0, '/opt/python-modules')
from agents.utils.validator import Validator, get_validator

def run_tests():
    print('Validator Tests\n' + '='*50)
    
    v = Validator()
    print('\n1. Instanziierung: OK')
    
    # Required
    result = v.validate({}, {'name': {'required': True}})
    assert not result.valid
    assert 'Pflichtfeld fehlt' in result.errors[0]
    print('2. Required check: OK')
    
    # Type
    result = v.validate({'age': '25'}, {'age': {'type': int}})
    assert result.valid
    assert result.data['age'] == 25
    print('3. Type conversion: OK')
    
    # Min/Max für Zahlen
    result = v.validate({'age': 200}, {'age': {'type': int, 'max': 150}})
    assert not result.valid
    print('4. Min/Max number: OK')
    
    # Min/Max für Strings
    result = v.validate({'name': 'AB'}, {'name': {'type': str, 'min': 3}})
    assert not result.valid
    print('5. Min/Max string: OK')
    
    # Choices
    result = v.validate({'status': 'pending'}, {'status': {'choices': ['active', 'inactive']}})
    assert not result.valid
    print('6. Choices: OK')
    
    # Pattern
    result = v.validate({'code': 'ABC123'}, {'code': {'pattern': r'^[A-Z]{3}[0-9]{3}$'}})
    assert result.valid
    print('7. Pattern: OK')
    
    # Default
    result = v.validate({}, {'lang': {'default': 'de'}})
    assert result.valid
    assert result.data['lang'] == 'de'
    print('8. Default: OK')
    
    # Custom Validator
    v.register_validator('is_even', lambda x: x % 2 == 0)
    result = v.validate({'num': 4}, {'num': {'type': int, 'validator': 'is_even'}})
    assert result.valid
    result = v.validate({'num': 5}, {'num': {'type': int, 'validator': 'is_even'}})
    assert not result.valid
    print('9. Custom validator: OK')
    
    # Convenience methods
    assert v.validate_email('test@example.com')
    assert not v.validate_email('invalid')
    assert v.validate_url('https://example.com')
    print('10. Convenience methods: OK')
    
    # Komplexes Schema
    schema = {
        'name': {'type': str, 'required': True, 'min': 2},
        'age': {'type': int, 'min': 0, 'max': 150},
        'email': {'type': str, 'pattern': r'.*@.*'},
        'role': {'choices': ['admin', 'user'], 'default': 'user'},
    }
    result = v.validate({'name': 'Max', 'age': 25, 'email': 'max@test.de'}, schema)
    assert result.valid
    assert result.data['role'] == 'user'
    print('11. Complex schema: OK')
    
    print('\n' + '='*50)
    print('Alle Tests bestanden!')

if __name__ == '__main__':
    run_tests()
