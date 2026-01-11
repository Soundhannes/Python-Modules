"""Test: BaseOrchestrator Refactoring - Name als Parameter."""

import sys
sys.path.insert(0, '/opt/python-modules')

from agents.core.base_orchestrator import BaseOrchestrator, OrchestrationResult


def test_name_in_constructor():
    print('=== Test 1: Name im Konstruktor ===')
    
    orch = BaseOrchestrator('my_workflow')
    assert orch.name == 'my_workflow'
    assert orch.max_workers == 4  # Default
    print(f'Name: {orch.name}')
    print(f'Max Workers: {orch.max_workers}')
    print('OK\n')
    return orch


def test_name_and_workers():
    print('=== Test 2: Name und Workers ===')
    
    orch = BaseOrchestrator('heavy_workflow', max_workers=8)
    assert orch.name == 'heavy_workflow'
    assert orch.max_workers == 8
    print(f'Name: {orch.name}, Workers: {orch.max_workers}')
    print('OK\n')


def test_default_name():
    print('=== Test 3: Default Name ===')
    
    orch = BaseOrchestrator()
    assert orch.name == 'orchestrator'
    print(f'Default Name: {orch.name}')
    print('OK\n')


def test_name_in_result(orch):
    print('=== Test 4: Name im Result ===')
    
    result = orch.run_sequence([
        ('step1', lambda ctx: {'value': 1})
    ])
    
    assert result.orchestrator_name == 'my_workflow'
    print(f'Result Orchestrator Name: {result.orchestrator_name}')
    print('OK\n')


def test_sequence_with_named_orchestrator():
    print('=== Test 5: Sequence mit benanntem Orchestrator ===')
    
    orch = BaseOrchestrator('data_pipeline')
    
    result = orch.run_sequence([
        ('load', lambda ctx: {'data': [1, 2, 3]}),
        ('transform', lambda ctx: {'sum': sum(ctx['load']['data'])}),
        ('save', lambda ctx: {'saved': True})
    ])
    
    assert result.success
    assert result.orchestrator_name == 'data_pipeline'
    assert result.final_context['transform']['sum'] == 6
    print(f'Pipeline: {result.orchestrator_name}')
    print(f'Steps: {len(result.steps)}')
    print(f'Final sum: {result.final_context["transform"]["sum"]}')
    print('OK\n')


def test_backwards_compatibility():
    print('=== Test 6: Rückwärtskompatibilität ===')
    
    # Alte Nutzung: Nur max_workers (positional) - NICHT MEHR MÖGLICH
    # Stattdessen: Keyword argument
    orch = BaseOrchestrator(max_workers=2)
    assert orch.name == 'orchestrator'
    assert orch.max_workers == 2
    print('Keyword max_workers funktioniert: OK')
    
    print('OK\n')


if __name__ == '__main__':
    print('BaseOrchestrator Refactor Tests\n' + '='*50 + '\n')
    
    orch = test_name_in_constructor()
    test_name_and_workers()
    test_default_name()
    test_name_in_result(orch)
    test_sequence_with_named_orchestrator()
    test_backwards_compatibility()
    
    print('='*50)
    print('Alle Tests bestanden!')
