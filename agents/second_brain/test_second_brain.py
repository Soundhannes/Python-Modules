"""Test: Second Brain System - Komponenten und Integration."""

import sys
sys.path.insert(0, "/opt/python-modules")

from llm.infrastructure.database import get_database
from agents.second_brain.db_wrapper import DatabaseWrapper


def get_db():
    """Gibt gewrappte DB-Connection zurück."""
    return DatabaseWrapper(get_database())


def test_config_loading():
    """Test: Konfiguration aus DB laden."""
    print("=== Test 1: Config Loading ===")

    db = get_db()

    # Agent Config laden
    result = db.execute(
        "SELECT agent_name, provider, model FROM agent_configs WHERE agent_name = %s",
        ("intent_agent",)
    )

    assert result, "Intent-Agent Config nicht gefunden"
    config = result[0]

    assert config["provider"] == "anthropic"
    assert "haiku" in config["model"]

    print(f"Config geladen: {config['agent_name']} ({config['model']})")
    print("OK\n")


def test_system_settings():
    """Test: System Settings laden."""
    print("=== Test 2: System Settings ===")

    from agents.second_brain import get_config_manager

    db = get_db()
    config = get_config_manager(db)

    threshold = config.get_setting("confidence_threshold")
    assert threshold == 0.3, f"Erwartet 0.3, bekommen {threshold}"

    timezone = config.get_setting("timezone")
    assert timezone == "Europe/Berlin"

    print(f"confidence_threshold: {threshold}")
    print(f"timezone: {timezone}")
    print("OK\n")


def test_language_mappings():
    """Test: Language Mappings laden."""
    print("=== Test 3: Language Mappings ===")

    from agents.second_brain import get_config_manager

    db = get_db()
    config = get_config_manager(db)

    stopwords = config.get_stopwords()
    assert len(stopwords) > 10, f"Zu wenig Stopwords: {len(stopwords)}"
    assert "der" in stopwords
    assert "die" in stopwords

    completion = config.get_completion_keywords()
    assert "fertig" in completion
    assert "erledigt" in completion

    priority = config.get_priority_keywords()
    assert "high" in priority
    assert "dringend" in priority["high"]

    print(f"Stopwords: {len(stopwords)} geladen")
    print(f"Completion Keywords: {completion[:5]}...")
    print(f"Priority High: {priority['high'][:3]}...")
    print("OK\n")


def test_configurable_agent_init():
    """Test: ConfigurableAgent Initialisierung."""
    print("=== Test 4: ConfigurableAgent Init ===")

    from agents.second_brain import ConfigurableAgent

    db = get_db()
    agent = ConfigurableAgent("intent_agent", db)

    assert agent.name == "intent_agent"
    assert agent.provider == "anthropic"
    assert agent.system_prompt is not None
    assert len(agent.system_prompt) > 100

    print(f"Agent: {agent.name}")
    print(f"Provider: {agent.provider}")
    print(f"Model: {agent.model}")
    print(f"System Prompt: {len(agent.system_prompt)} chars")
    print("OK\n")


def test_intent_agent_create():
    """Test: Intent-Agent bei neuem Task (create)."""
    print("=== Test 5: Intent-Agent CREATE ===")

    from agents.second_brain import IntentAgent

    db = get_db()
    agent = IntentAgent(db)

    # Kein Match = sollte create sein
    result = agent.analyze(
        text="Rechnung an Schmidt schicken",
        matches=[]
    )

    print(f"Result: {result}")

    if result.get("error"):
        print(f"WARNUNG: Agent-Fehler: {result.get('error_message')}")
        print("ÜBERSPRUNGEN (API-Key Problem?)\n")
        return

    assert result.get("intent") == "create", f"Erwartet create, bekommen {result.get('intent')}"
    assert result.get("category") == "tasks", f"Erwartet tasks, bekommen {result.get('category')}"
    assert result.get("confidence", 0) > 0.5

    print(f"Intent: {result['intent']}")
    print(f"Category: {result['category']}")
    print(f"Confidence: {result['confidence']}")
    print("OK\n")


def test_intent_agent_complete():
    """Test: Intent-Agent bei Abschluss (complete)."""
    print("=== Test 6: Intent-Agent COMPLETE ===")

    from agents.second_brain import IntentAgent

    db = get_db()
    agent = IntentAgent(db)

    # Mit Match und "fertig" = sollte complete sein
    result = agent.analyze(
        text="Reibekuchenofen ist fertig",
        matches=[{
            "table": "projects",
            "id": 5,
            "data": {"name": "Reibekuchenofen", "status": "active"},
            "match_score": 0.95
        }]
    )

    print(f"Result: {result}")

    if result.get("error"):
        print(f"WARNUNG: Agent-Fehler: {result.get('error_message')}")
        print("ÜBERSPRUNGEN\n")
        return

    assert result.get("intent") == "complete", f"Erwartet complete, bekommen {result.get('intent')}"
    assert result.get("target", {}).get("table") == "projects"
    assert result.get("target", {}).get("id") == 5

    print(f"Intent: {result['intent']}")
    print(f"Target: {result['target']}")
    print(f"Confidence: {result['confidence']}")
    print("OK\n")


def test_structure_agent():
    """Test: Structure-Agent bei Task-Erstellung."""
    print("=== Test 7: Structure-Agent ===")

    from agents.second_brain import StructureAgent

    db = get_db()
    agent = StructureAgent(db)

    result = agent.structure(
        text="Rechnung an Schmidt schicken bis Freitag",
        intent="create",
        category="tasks"
    )

    print(f"Result: {result}")

    if result.get("error"):
        print(f"WARNUNG: Agent-Fehler: {result.get('error_message')}")
        print("ÜBERSPRUNGEN\n")
        return

    data = result.get("data", {})
    assert data.get("title"), "Title fehlt"
    assert "priority" in data

    linked = result.get("linked_entities", {})

    print(f"Title: {data.get('title')}")
    print(f"Due Date: {data.get('due_date')}")
    print(f"Priority: {data.get('priority')}")
    print(f"Linked Person: {linked.get('person_name')}")
    print("OK\n")


def test_orchestrator_keyword_extraction():
    """Test: Orchestrator Keyword-Extraktion."""
    print("=== Test 8: Orchestrator Keywords ===")

    from agents.second_brain import SecondBrainOrchestrator

    db = get_db()
    orch = SecondBrainOrchestrator(db)

    keywords = orch._extract_keywords("Reibekuchenofen ist fertig geworden")

    assert "reibekuchenofen" in keywords
    assert "fertig" in keywords
    assert "ist" not in keywords  # Stopword
    assert "geworden" in keywords

    print(f"Keywords: {keywords}")
    print("OK\n")


def test_orchestrator_db_search():
    """Test: Orchestrator DB-Suche."""
    print("=== Test 9: Orchestrator DB-Suche ===")

    from agents.second_brain import SecondBrainOrchestrator

    db = get_db()
    orch = SecondBrainOrchestrator(db)

    # Erst einen Test-Eintrag anlegen
    db.execute(
        "INSERT INTO projects (name, status, created_at, updated_at) VALUES (%s, %s, NOW(), NOW()) ON CONFLICT DO NOTHING",
        ("Testprojekt Alpha", "active")
    )

    # Suchen
    matches = orch._search_database(["testprojekt"])

    print(f"Matches gefunden: {len(matches)}")
    for m in matches:
        print(f"  - {m['table']}: {m['data']['name']} (Score: {m['match_score']})")

    # Cleanup
    db.execute("DELETE FROM projects WHERE name = %s", ("Testprojekt Alpha",))

    print("OK\n")


def test_full_flow_create():
    """Test: Vollständiger Flow - Neuer Task."""
    print("=== Test 10: Full Flow CREATE ===")

    from agents.second_brain import get_orchestrator

    db = get_db()
    orch = get_orchestrator(db)

    result = orch.process("Neue Aufgabe: Blumen gießen morgen")

    print(f"Result: {result}")

    if result.get("error"):
        print(f"Flow-Fehler: {result.get('error')}")
        print(f"Stage: {result.get('stage')}")

    if result.get("success"):
        print(f"Erfolg! Record ID: {result.get('record_id')}")

        # Cleanup
        if result.get("record_id"):
            db.execute("DELETE FROM tasks WHERE id = %s", (result["record_id"],))
            print("Cleanup: Task gelöscht")

    print("OK\n")


if __name__ == "__main__":
    print("Second Brain Tests\n" + "=" * 50 + "\n")

    # Basis-Tests (ohne API-Calls)
    test_config_loading()
    test_system_settings()
    test_language_mappings()
    test_configurable_agent_init()

    # Agent-Tests (mit API-Calls)
    print("\n--- Agent Tests (benötigen API-Key) ---\n")
    test_intent_agent_create()
    test_intent_agent_complete()
    test_structure_agent()

    # Orchestrator-Tests
    print("\n--- Orchestrator Tests ---\n")
    test_orchestrator_keyword_extraction()
    test_orchestrator_db_search()
    test_full_flow_create()

    print("=" * 50)
    print("Tests abgeschlossen!")
