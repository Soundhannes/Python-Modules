"""Test: BaseAgent Refactoring - Name als Parameter."""

import sys
sys.path.insert(0, "/opt/python-modules")

from agents.core.base_agent import BaseAgent, AgentResult


def test_name_in_constructor():
    print("=== Test 1: Name im Konstruktor ===")
    
    agent = BaseAgent("my_agent", provider="anthropic")
    assert agent.name == "my_agent"
    assert agent.provider == "anthropic"
    print(f"Name: {agent.name}")
    print(f"Provider: {agent.provider}")
    print("OK\n")
    return agent


def test_default_name():
    print("=== Test 2: Default Name ===")
    
    agent = BaseAgent()
    assert agent.name == "agent"
    print(f"Default Name: {agent.name}")
    print("OK\n")


def test_name_in_result():
    print("=== Test 3: Name im Result ===")
    
    agent = BaseAgent("test_agent", provider="anthropic", model="claude-sonnet-4-20250514")
    result = agent.run("Antworte nur mit OK", max_tokens=10)
    
    assert result.agent_name == "test_agent"
    print(f"Result Agent Name: {result.agent_name}")
    print(f"Response: {result.response[:20]}...")
    print("OK\n")


def test_backwards_compatibility():
    print("=== Test 4: Rückwärtskompatibilität ===")
    
    # Alte Nutzung: provider als erstes Argument - NICHT MEHR MÖGLICH
    # Neue Nutzung: provider als keyword
    agent = BaseAgent(provider="anthropic")
    assert agent.name == "agent"  # Default
    assert agent.provider == "anthropic"
    print("Keyword provider funktioniert: OK")
    
    print("OK\n")


if __name__ == "__main__":
    print("BaseAgent Refactor Tests\n" + "="*50 + "\n")
    
    test_name_in_constructor()
    test_default_name()
    test_name_in_result()
    test_backwards_compatibility()
    
    print("="*50)
    print("Alle Tests bestanden!")
