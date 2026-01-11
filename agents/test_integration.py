"""
Integrationstest - Alle Bausteine im Zusammenspiel.
"""

import sys
sys.path.insert(0, '/opt/python-modules')

from datetime import datetime

# Core imports
from agents.core import BaseAgent, AgentResult, BaseOrchestrator, StepResult

# Services imports
from agents.services import StorageService, get_storage_service

# Utils imports
from agents.utils import Logger, get_logger, Validator, ValidationResult


def test_import_all():
    print('=== Test 1: Imports ===')
    
    from agents import BaseAgent, AgentResult
    from agents import BaseOrchestrator, StepResult, OrchestrationResult
    from agents.services import StorageService, StorageItem, get_storage_service
    from agents.services.notification_service import NotificationService, get_notification_service
    from agents.utils import Logger, LogEntry, get_logger
    from agents.utils import Validator, ValidationResult
    from agents.utils import HumanInLoop, HumanRequest, get_human_in_loop
    from agents.utils import InputCollector, FormField, FormSubmission, get_input_collector
    
    print('Alle Imports OK')
    print()
    

def test_simple_workflow():
    print('=== Test 2: Einfacher Workflow ===')
    
    logger = get_logger('integration_test')
    storage = get_storage_service()
    validator = Validator()
    
    logger.info('Workflow gestartet', {'test': 'integration'})
    
    schema = {
        'name': {'type': str, 'required': True},
        'count': {'type': int, 'required': True, 'min': 1}
    }
    
    input_data = {'name': 'Test', 'count': 5}
    result = validator.validate(input_data, schema)
    
    print(f'Validierung: {result.valid}')
    assert result.valid
    
    storage.set('workflow_input', input_data, namespace='integration_test')
    stored = storage.get('workflow_input', namespace='integration_test')
    print(f'Gespeichert: {stored}')
    assert stored['name'] == 'Test'
    
    logger.info('Workflow beendet', {'success': True})
    storage.delete_namespace('integration_test')
    
    print('Workflow OK')
    print()


def test_orchestrator_with_storage():
    print('=== Test 3: Orchestrator mit Storage ===')
    
    orchestrator = BaseOrchestrator('storage_workflow')
    storage = get_storage_service()
    logger = get_logger('orchestrator_test')
    
    def step_init(ctx):
        logger.debug('Step 1: Init')
        return {'counter': 0}
    
    def step_increment(ctx):
        init_result = ctx.get('init', {})
        counter = init_result.get('counter', 0) + 1
        storage.set('counter', counter, namespace='orch_test')
        logger.debug(f'Step 2: Counter = {counter}')
        return {'counter': counter}
    
    def step_save_result(ctx):
        final = storage.get('counter', namespace='orch_test')
        storage.set('final_result', {'value': final, 'timestamp': str(datetime.now())}, namespace='orch_test')
        logger.debug(f'Step 3: Saved final = {final}')
        return {'saved': True}
    
    result = orchestrator.run_sequence([
        ('init', step_init),
        ('increment', step_increment),
        ('save', step_save_result)
    ])
    
    print(f'Orchestrator Success: {result.success}')
    print(f'Schritte: {len(result.steps)}')
    
    final = storage.get('final_result', namespace='orch_test')
    print(f'Finales Ergebnis: {final}')
    assert result.success
    assert final['value'] == 1
    
    storage.delete_namespace('orch_test')
    print('Orchestrator OK')
    print()


def test_agent_with_logging():
    print('=== Test 4: Agent mit Logging ===')
    
    logger = get_logger('agent_test')
    agent = BaseAgent(provider='anthropic', model='claude-sonnet-4-20250514')
    
    logger.info('Agent-Aufruf gestartet')
    
    result = agent.run(
        user_prompt='Antworte nur mit dem Wort "OK"',
        max_tokens=10
    )
    
    logger.info('Agent-Aufruf beendet', {
        'success': result.success,
        'tokens': result.tokens_used
    })
    
    print(f'Agent Response: {result.response[:50]}...')
    assert result.success
    
    logs = logger.get_logs(limit=5)
    print(f'Logs gefunden: {len(logs)}')
    
    print('Agent OK')
    print()


def test_validator_with_storage():
    print('=== Test 5: Validator mit Storage ===')
    
    validator = Validator()
    storage = get_storage_service()
    
    validator.register_validator('email', validator.validate_email)
    
    test_cases = [
        {'email': 'test@example.com', 'age': 25},
        {'email': 'invalid', 'age': 'not a number'},
        {'email': 'valid@test.de', 'age': -5},
    ]
    
    schema = {
        'email': {'type': str, 'required': True, 'custom': 'email'},
        'age': {'type': int, 'required': True, 'min': 0}
    }
    
    results = []
    for i, data in enumerate(test_cases):
        result = validator.validate(data, schema)
        results.append({
            'case': i,
            'valid': result.valid,
            'errors': result.errors
        })
    
    storage.set('validation_results', results, namespace='validator_test')
    saved = storage.get('validation_results', namespace='validator_test')
    print(f'Gespeicherte Ergebnisse: {len(saved)}')
    
    assert saved[0]['valid'] == True
    assert saved[1]['valid'] == False
    assert saved[2]['valid'] == False
    
    storage.delete_namespace('validator_test')
    print('Validator OK')
    print()


def test_full_pipeline():
    print('=== Test 6: Vollständige Pipeline ===')
    
    logger = get_logger('pipeline')
    storage = get_storage_service()
    validator = Validator()
    orchestrator = BaseOrchestrator('full_pipeline')
    agent = BaseAgent(provider='anthropic', model='claude-sonnet-4-20250514')
    
    def validate_input(ctx):
        schema = {'topic': {'type': str, 'required': True}}
        result = validator.validate(ctx, schema)
        if not result.valid:
            raise ValueError(f'Validation failed: {result.errors}')
        logger.debug('Input validiert')
        return {'topic': ctx['topic']}  # Nur topic weiterreichen
    
    def generate_content(ctx):
        topic = ctx.get('validate', {}).get('topic', 'Python')
        result = agent.run(
            user_prompt=f'Nenne ein Wort das mit {topic} zu tun hat. Antworte nur mit dem Wort.',
            max_tokens=20
        )
        if not result.success:
            raise RuntimeError(f'Agent failed: {result.error}')
        
        word = result.response.strip()
        logger.debug('Content generiert', {'word': word})
        return {'topic': topic, 'generated': word}  # Flache Struktur
    
    def save_result(ctx):
        # Nur die generierten Daten speichern, nicht den ganzen Context
        gen_result = ctx.get('generate', {})
        output = {
            'topic': gen_result.get('topic'),
            'generated': gen_result.get('generated'),
            'timestamp': str(datetime.now())
        }
        storage.set('pipeline_output', output, namespace='pipeline_test')
        logger.info('Pipeline abgeschlossen')
        return {'saved': True}
    
    result = orchestrator.run_sequence([
        ('validate', validate_input),
        ('generate', generate_content),
        ('save', save_result)
    ], initial_context={'topic': 'Programmierung'})
    
    print(f'Pipeline Success: {result.success}')
    if result.error:
        print(f'Error: {result.error}')
    
    output = storage.get('pipeline_output', namespace='pipeline_test')
    print(f'Output: {output}')
    
    assert result.success, f'Pipeline failed: {result.error}'
    assert output is not None
    assert 'generated' in output
    
    storage.delete_namespace('pipeline_test')
    print('Pipeline OK')
    print()


if __name__ == '__main__':
    print('='*60)
    print('INTEGRATION TESTS - Alle Bausteine')
    print('='*60)
    print()
    
    test_import_all()
    test_simple_workflow()
    test_orchestrator_with_storage()
    test_agent_with_logging()
    test_validator_with_storage()
    test_full_pipeline()
    
    print('='*60)
    print('ALLE INTEGRATIONSTESTS BESTANDEN!')
    print('='*60)
