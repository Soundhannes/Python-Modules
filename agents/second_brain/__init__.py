"""
Second Brain - Intelligentes Notiz- und Aufgabensystem.

Komponenten:
- ConfigurableAgent: Basis für DB-konfigurierte Agents
- IntentAgent: Erkennt Intent aus User-Text
- StructureAgent: Strukturiert Text zu DB-Einträgen
- DailyReportAgent: Täglicher Fokus-Report
- WeeklyReportAgent: Wöchentlicher Überblick
- SecondBrainOrchestrator: Steuert den gesamten Flow

Verwendung:
    from agents.second_brain import get_orchestrator

    orchestrator = get_orchestrator(db_connection, telegram_chat_id="123")
    result = orchestrator.process("Reibekuchenofen ist fertig")

    if result["success"]:
        print(f"Erledigt: {result['message']}")
    elif result.get("needs_clarification"):
        print(f"Rückfrage: {result['question']}")
"""

from .db_wrapper import (
    DatabaseWrapper,
    get_db_wrapper
)

from .configurable_agent import (
    ConfigurableAgent,
    ConfigManager,
    get_configurable_agent,
    get_config_manager
)

from .intent_agent import (
    IntentAgent,
    get_intent_agent
)

from .structure_agent import (
    StructureAgent,
    get_structure_agent
)

from .daily_report_agent import (
    DailyReportAgent,
    get_daily_report_agent
)

from .weekly_report_agent import (
    WeeklyReportAgent,
    get_weekly_report_agent
)

from .orchestrator import (
    SecondBrainOrchestrator,
    get_orchestrator
)


__all__ = [
    # Database
    "DatabaseWrapper",
    "get_db_wrapper",

    # Base
    "ConfigurableAgent",
    "ConfigManager",
    "get_configurable_agent",
    "get_config_manager",

    # Agents
    "IntentAgent",
    "get_intent_agent",
    "StructureAgent",
    "get_structure_agent",
    "DailyReportAgent",
    "get_daily_report_agent",
    "WeeklyReportAgent",
    "get_weekly_report_agent",

    # Orchestrator
    "SecondBrainOrchestrator",
    "get_orchestrator",
]
