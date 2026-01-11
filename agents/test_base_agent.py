"""Test-Skript für BaseAgent."""

import sys
sys.path.insert(0, '/opt/python-modules')

from agents import BaseAgent, AgentResult

def test_instanziierung():
    print('=== Test 1: Instanziierung ===')
    agent = BaseAgent(provider='anthropic')
    print(f'Provider: {agent.provider}')
    print(f'Default max_tokens: {agent.default_max_tokens}')
    print(f'Default temperature: {agent.default_temperature}')
    assert agent.provider == 'anthropic'
    assert agent.default_max_tokens == 2048
    print('OK\n')
    return agent

def test_template_rendering(agent):
    print('=== Test 2: Template-Rendering ===')
    template = 'Hallo {name}, du bist {alter} Jahre alt.'
    context = {'name': 'Max', 'alter': 25}
    result = agent._render_template(template, context)
    print(f'Template: {template}')
    print(f'Context: {context}')
    print(f'Result: {result}')
    assert result == 'Hallo Max, du bist 25 Jahre alt.'
    print('OK\n')

def test_json_parsing(agent):
    print('=== Test 3: JSON-Parsing ===')
    test_json = '{"name": "Test", "value": 42}'
    parsed = agent._try_parse_json(test_json)
    print(f'Input: {test_json}')
    print(f'Parsed: {parsed}')
    assert parsed is not None
    assert parsed['name'] == 'Test'
    assert parsed['value'] == 42
    print('OK\n')

def test_json_code_block(agent):
    print('=== Test 4: JSON in Code-Block ===')
    test_block = '''Hier ist das Ergebnis:
```json
{"status": "success"}
```'''
    parsed = agent._try_parse_json(test_block)
    print(f'Parsed: {parsed}')
    assert parsed is not None
    assert parsed['status'] == 'success'
    print('OK\n')

def test_llm_call(agent):
    print('=== Test 5: LLM-Aufruf ===')
    result = agent.run(
        user_prompt='Sage nur "Hallo". Nichts anderes.',
        max_tokens=10
    )
    print(f'Success: {result.success}')
    print(f'Response: {result.response[:50]}...' if len(result.response) > 50 else f'Response: {result.response}')
    print(f'Tokens: {result.tokens_used}')
    print(f'Duration: {result.duration_ms}ms')
    if not result.success:
        print(f'Error: {result.error}')
    assert result.success, f'LLM-Aufruf fehlgeschlagen: {result.error}'
    print('OK\n')

if __name__ == '__main__':
    print('BaseAgent Tests\n' + '='*50 + '\n')

    agent = test_instanziierung()
    test_template_rendering(agent)
    test_json_parsing(agent)
    test_json_code_block(agent)
    test_llm_call(agent)

    print('='*50)
    print('Alle Tests bestanden!')
