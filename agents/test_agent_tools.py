"""Test: BaseAgent Erweiterung - tools Parameter."""

import sys
import warnings
sys.path.insert(0, "/opt/python-modules")

from agents.core.base_agent import BaseAgent, AgentResult, ToolDefinition, ToolCall


def test_tools_in_constructor():
    print("=== Test 1: Tools im Konstruktor ===")

    # Warnung abfangen
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        tool = ToolDefinition(
            name="get_weather",
            description="Holt Wetterdaten",
            parameters={"location": {"type": "string"}}
        )
        agent = BaseAgent("tool_agent", tools=[tool])

        assert len(agent.tools) == 1
        assert agent.tools[0].name == "get_weather"
        print(f"Tools: {[t.name for t in agent.tools]}")

        # Warnung sollte erscheinen
        assert len(w) == 1
        assert "Function Calling noch nicht" in str(w[0].message)
        print(f"Warnung: {w[0].message}")

    print("OK\n")


def test_no_tools():
    print("=== Test 2: Agent ohne Tools ===")

    # Keine Warnung ohne Tools
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        agent = BaseAgent("no_tools")
        assert len(agent.tools) == 0
        assert len(w) == 0  # Keine Warnung

    print("Keine Warnung ohne Tools: OK")
    print("OK\n")


def test_add_tool():
    print("=== Test 3: Tool hinzufügen ===")

    agent = BaseAgent("dynamic_tools")

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        tool = ToolDefinition(
            name="calculate",
            description="Berechnet etwas",
            parameters={"expression": {"type": "string"}}
        )
        agent.add_tool(tool)

        assert len(agent.tools) == 1
        assert len(w) == 1
        print(f"Tool hinzugefügt: {agent.tools[0].name}")

    print("OK\n")


def test_tool_calls_in_result():
    print("=== Test 4: ToolCalls im Result ===")

    agent = BaseAgent("result_test", provider="anthropic", model="claude-sonnet-4-20250514")
    result = agent.run("Sage OK", max_tokens=10)

    # tool_calls sollte leere Liste sein (noch nicht implementiert)
    assert result.tool_calls == []
    print(f"tool_calls (leer): {result.tool_calls}")
    print(f"Response: {result.response[:20]}...")

    print("OK\n")


def test_use_tools_warning():
    print("=== Test 5: use_tools Warnung ===")

    agent = BaseAgent("warning_test", provider="anthropic", model="claude-sonnet-4-20250514")

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        # use_tools=True ohne Tools
        result = agent.run("Sage OK", max_tokens=10, use_tools=True)

        assert len(w) == 1
        assert "keine Tools definiert" in str(w[0].message)
        print(f"Warnung: {w[0].message}")

    print("OK\n")


def test_backwards_compatibility():
    print("=== Test 6: Rückwärtskompatibilität ===")

    # Alte Nutzung ohne tools
    agent = BaseAgent("compat", provider="anthropic", model="claude-sonnet-4-20250514")
    result = agent.run("Sage OK", max_tokens=10)

    assert result.success
    assert result.tool_calls == []
    print(f"Alte Nutzung funktioniert: {result.response[:20]}...")

    print("OK\n")


if __name__ == "__main__":
    print("BaseAgent Tools Tests\n" + "="*50 + "\n")

    test_tools_in_constructor()
    test_no_tools()
    test_add_tool()
    test_tool_calls_in_result()
    test_use_tools_warning()
    test_backwards_compatibility()

    print("="*50)
    print("Alle Tests bestanden!")
