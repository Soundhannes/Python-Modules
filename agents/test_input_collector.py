"""Test-Skript für InputCollector."""

import sys
sys.path.insert(0, '/opt/python-modules')

from agents.utils.input_collector import InputCollector, FormField, get_input_collector


def test_instanziierung():
    print('=== Test 1: Instanziierung ===')
    collector = InputCollector()
    print(f'Table: {collector.TABLE_NAME}')
    print('OK\n')
    return collector


def test_create_form(collector):
    print('=== Test 2: Create Form ===')
    
    fields = [
        FormField(name='name', label='Name', field_type='text', required=True),
        FormField(name='email', label='E-Mail', field_type='email', required=True),
        FormField(name='age', label='Alter', field_type='number', required=False),
    ]
    
    form_id = collector.create_form('test_form', fields)
    print(f'Created form with ID: {form_id}')
    assert form_id is not None
    assert form_id > 0
    
    print('OK\n')
    return form_id


def test_get_pending_forms(collector, form_id):
    print('=== Test 3: Get Pending Forms ===')
    
    pending = collector.get_pending_forms()
    print(f'Pending forms: {len(pending)}')
    
    # Unser Form sollte dabei sein
    our_form = [f for f in pending if f.id == form_id]
    assert len(our_form) == 1
    print(f'Found our form: {our_form[0].form_name}')
    
    print('OK\n')


def test_submit_valid(collector, form_id):
    print('=== Test 4: Submit Valid Data ===')
    
    data = {
        'name': 'Max Mustermann',
        'email': 'max@example.com',
        'age': 30
    }
    
    success, errors = collector.submit(form_id, data)
    print(f'Success: {success}')
    print(f'Errors: {errors}')
    assert success
    assert len(errors) == 0
    
    print('OK\n')


def test_submit_invalid(collector):
    print('=== Test 5: Submit Invalid Data ===')
    
    # Neues Formular erstellen
    fields = [
        FormField(name='email', label='E-Mail', field_type='email', required=True),
    ]
    form_id = collector.create_form('test_invalid', fields)
    
    # Ungültige E-Mail
    data = {'email': 'not-an-email'}
    success, errors = collector.submit(form_id, data)
    
    print(f'Success: {success}')
    print(f'Errors: {errors}')
    assert not success
    assert len(errors) > 0
    assert any('E-Mail' in e for e in errors)
    
    print('OK\n')


def test_submit_missing_required(collector):
    print('=== Test 6: Submit Missing Required Field ===')
    
    fields = [
        FormField(name='required_field', label='Pflichtfeld', field_type='text', required=True),
        FormField(name='optional_field', label='Optional', field_type='text', required=False),
    ]
    form_id = collector.create_form('test_required', fields)
    
    # Nur optionales Feld
    data = {'optional_field': 'some value'}
    success, errors = collector.submit(form_id, data)
    
    print(f'Success: {success}')
    print(f'Errors: {errors}')
    assert not success
    assert any('Pflichtfeld' in e for e in errors)
    
    print('OK\n')


def test_choices_validation(collector):
    print('=== Test 7: Choices Validation ===')
    
    fields = [
        FormField(
            name='color', 
            label='Farbe', 
            field_type='select', 
            required=True,
            choices=['rot', 'grün', 'blau']
        ),
    ]
    form_id = collector.create_form('test_choices', fields)
    
    # Gültige Auswahl
    data = {'color': 'rot'}
    success, errors = collector.submit(form_id, data)
    print(f'Valid choice - Success: {success}')
    assert success
    
    # Ungültige Auswahl
    form_id2 = collector.create_form('test_choices2', fields)
    data2 = {'color': 'gelb'}
    success2, errors2 = collector.submit(form_id2, data2)
    print(f'Invalid choice - Success: {success2}, Errors: {errors2}')
    assert not success2
    
    print('OK\n')


def test_collect_timeout(collector):
    print('=== Test 8: Collect with Timeout ===')
    
    fields = [
        FormField(name='quick', label='Schnell', field_type='text', required=True),
    ]
    
    # Sehr kurzer Timeout (1 Sekunde)
    result = collector.collect('timeout_test', fields, timeout=1)
    print(f'Result after timeout: {result}')
    assert result is None  # Timeout sollte None zurückgeben
    
    print('OK\n')


def test_cleanup(collector):
    print('=== Test 9: Cleanup ===')
    
    # Alle Test-Forms löschen
    from agents.utils.input_collector import get_database
    db = get_database()
    with db.get_cursor() as cursor:
        cursor.execute("""
            DELETE FROM input_forms 
            WHERE form_name LIKE 'test%' OR form_name LIKE 'timeout%'
        """)
        deleted = cursor.rowcount
        db.commit()
    
    print(f'Deleted {deleted} test forms')
    print('OK\n')


if __name__ == '__main__':
    print('InputCollector Tests\n' + '='*50 + '\n')
    
    collector = test_instanziierung()
    form_id = test_create_form(collector)
    test_get_pending_forms(collector, form_id)
    test_submit_valid(collector, form_id)
    test_submit_invalid(collector)
    test_submit_missing_required(collector)
    test_choices_validation(collector)
    test_collect_timeout(collector)
    test_cleanup(collector)
    
    print('='*50)
    print('Alle Tests bestanden!')
