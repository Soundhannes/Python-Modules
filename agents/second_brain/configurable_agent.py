"""
ConfigurableAgent - Agent der seine Konfiguration aus der Datenbank lädt.

Ermöglicht:
- Prompt-Änderungen ohne Code-Deployment
- Hot-Reload der Konfiguration
- Fallback auf alternatives Modell
- Tracking von Aufrufen und Fehlern

Verwendung:
    agent = ConfigurableAgent("intent_agent", db)
    result = agent.run(text="Hallo Welt", matches=[])
"""

import sys
import json
import time
from datetime import datetime
from typing import Optional, Dict, Any, List

sys.path.insert(0, "/opt/python-modules")

from agents.core.base_agent import BaseAgent, AgentResult
from agents.utils.output_parser import get_output_parser


class ConfigurableAgent(BaseAgent):
    """
    Agent der seine Konfiguration aus der Datenbank lädt.

    Erweitert BaseAgent um:
    - DB-basierte Konfiguration
    - Template-Rendering für User-Prompts
    - Schema-Validierung via OutputParser
    - Fallback-Modell bei Fehlern
    - Aufruf-Tracking
    """

    def __init__(self, agent_name: str, db_connection):
        """
        Initialisiert Agent mit Konfiguration aus DB.

        Args:
            agent_name: Name des Agents in agent_configs Tabelle
            db_connection: Datenbank-Verbindung
        """
        self.db = db_connection
        self.config = self._load_config(agent_name)
        self.parser = get_output_parser()

        # BaseAgent initialisieren mit DB-Werten
        super().__init__(
            name=self.config["agent_name"],
            provider=self.config["provider"],
            model=self.config["model"],
            default_max_tokens=self.config["max_tokens"],
            default_temperature=float(self.config["temperature"])
        )

        # Zusätzliche Config-Felder
        self.system_prompt = self.config["system_prompt"]
        self.user_prompt_template = self.config.get("user_prompt_template")
        self.output_schema = self.config.get("output_schema")
        self.retry_count = self.config.get("retry_count", 3)
        self.timeout_seconds = self.config.get("timeout_seconds", 30)

        # Fallback
        self.fallback_provider = self.config.get("fallback_provider")
        self.fallback_model = self.config.get("fallback_model")

    # Mapping von JSON Schema Typen zu Python Typen
    TYPE_MAP = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict,
    }

    def _convert_schema_types(self, schema: Dict) -> Dict:
        """Konvertiert JSON Schema Typ-Strings zu Python Typen."""
        if not schema:
            return schema

        converted = {}
        for field, rules in schema.items():
            if isinstance(rules, dict):
                new_rules = {}
                for key, value in rules.items():
                    if key == "type" and isinstance(value, str):
                        # String-Typ zu Python-Typ konvertieren
                        new_rules[key] = self.TYPE_MAP.get(value, str)
                    else:
                        new_rules[key] = value
                converted[field] = new_rules
            else:
                converted[field] = rules

        return converted

    def _load_config(self, agent_name: str) -> Dict[str, Any]:
        """Lädt Konfiguration aus der Datenbank."""
        query = """
            SELECT * FROM agent_configs
            WHERE agent_name = %s AND is_active = TRUE
        """
        result = self.db.execute(query, (agent_name,))

        if not result:
            raise ValueError(f"Agent config not found or inactive: {agent_name}")

        config = dict(result[0])

        # JSONB-Felder parsen falls sie Strings sind
        for field in ["input_schema", "output_schema"]:
            if config.get(field) and isinstance(config[field], str):
                config[field] = json.loads(config[field])

        # Schema-Typen konvertieren
        if config.get("output_schema"):
            config["output_schema"] = self._convert_schema_types(config["output_schema"])

        return config

    def reload_config(self):
        """Lädt Konfiguration neu (Hot-Reload)."""
        self.config = self._load_config(self.name)

        # Felder aktualisieren
        self.provider = self.config["provider"]
        self.model = self.config["model"]
        self.default_max_tokens = self.config["max_tokens"]
        self.default_temperature = float(self.config["temperature"])
        self.system_prompt = self.config["system_prompt"]
        self.user_prompt_template = self.config.get("user_prompt_template")
        self.output_schema = self.config.get("output_schema")

        # Client neu initialisieren
        self._client = None

    def _render_template(self, template: str, context: Dict[str, Any]) -> str:
        """
        Überschreibt BaseAgent._render_template für sichere String-Ersetzung.

        Verwendet einfache Ersetzung statt format() um JSON-Beispiele
        in Prompts zu unterstützen.
        """
        result = template

        for key, value in context.items():
            placeholder = "{" + key + "}"

            if isinstance(value, (dict, list)):
                replacement = json.dumps(value, ensure_ascii=False)
            elif value is None:
                replacement = "null"
            else:
                replacement = str(value)

            result = result.replace(placeholder, replacement)

        return result

    def _render_user_prompt(self, context: Dict[str, Any]) -> str:
        """Rendert User-Prompt mit Kontext-Variablen."""
        if not self.user_prompt_template:
            raise ValueError("No user_prompt_template configured")

        result = self.user_prompt_template

        # Einfache String-Ersetzung für Platzhalter
        for key, value in context.items():
            placeholder = "{" + key + "}"

            # JSON-Serialisierung für komplexe Typen
            if isinstance(value, (dict, list)):
                replacement = json.dumps(value, ensure_ascii=False)
            elif value is None:
                replacement = "null"
            else:
                replacement = str(value)

            result = result.replace(placeholder, replacement)

        # Escaped braces zurück konvertieren
        result = result.replace("{{", "{").replace("}}", "}")

        return result

    def _update_tracking(self, success: bool):
        """Aktualisiert Tracking-Felder in der Datenbank."""
        if success:
            query = """
                UPDATE agent_configs
                SET total_calls = total_calls + 1,
                    last_used_at = NOW(),
                    updated_at = NOW()
                WHERE agent_name = %s
            """
        else:
            query = """
                UPDATE agent_configs
                SET total_calls = total_calls + 1,
                    error_count = error_count + 1,
                    last_used_at = NOW(),
                    updated_at = NOW()
                WHERE agent_name = %s
            """

        try:
            self.db.execute(query, (self.name,))
        except Exception:
            pass  # Tracking-Fehler nicht propagieren

    def _try_fallback(self, user_prompt: str) -> Optional[AgentResult]:
        """Versucht Aufruf mit Fallback-Modell."""
        if not self.fallback_provider or not self.fallback_model:
            return None

        # Temporär Provider/Model wechseln
        original_provider = self.provider
        original_model = self.model

        try:
            self.provider = self.fallback_provider
            self.model = self.fallback_model
            self._client = None  # Client neu initialisieren

            result = super().run(
                user_prompt=user_prompt,
                system_prompt=self.system_prompt,
                max_tokens=self.default_max_tokens,
                temperature=self.default_temperature
            )

            return result
        finally:
            # Original wiederherstellen
            self.provider = original_provider
            self.model = original_model
            self._client = None

    def execute(self, **context) -> Dict[str, Any]:
        """
        Führt Agent mit Kontext-Variablen aus.

        Args:
            **context: Variablen für das User-Prompt Template

        Returns:
            Geparste und validierte Antwort als Dict
        """
        # User-Prompt rendern
        user_prompt = self._render_user_prompt(context)

        # Mit Retry ausführen
        result = self.run_with_retry(
            user_prompt=user_prompt,
            system_prompt=self.system_prompt,
            max_retries=self.retry_count
        )

        # Bei Fehler: Fallback versuchen
        if not result.success and self.fallback_provider:
            fallback_result = self._try_fallback(user_prompt)
            if fallback_result and fallback_result.success:
                result = fallback_result

        # Tracking aktualisieren
        self._update_tracking(result.success)

        if not result.success:
            return {
                "error": "Agent execution failed",
                "error_code": "AGENT_ERROR",
                "error_message": result.error,
                "agent_name": self.name
            }

        # Output parsen und validieren
        print(f"[DEBUG] LLM raw response: {result.response[:500]}")
        parsed = self.parser.parse_json(result.response, schema=self.output_schema)
        if not parsed.success:
            print(f"[ERROR] Parse failed. Raw: {result.response[:1000]}")

        if not parsed.success:
            return {
                "error": "JSON parsing failed",
                "error_code": "PARSE_ERROR",
                "error_message": f"JSON parsing failed: {parsed.errors}",
                "raw_response": result.response[:500],
                "agent_name": self.name
            }

        return parsed.data


class ConfigManager:
    """
    Manager für System-Settings und Language-Mappings.

    Bietet einfachen Zugriff auf konfigurierbare Werte.
    """

    def __init__(self, db_connection):
        self.db = db_connection
        self._cache = {}
        self._cache_time = None
        self._cache_ttl = 60  # Sekunden

    def _is_cache_valid(self) -> bool:
        """Prüft ob Cache noch gültig ist."""
        if not self._cache_time:
            return False
        return (datetime.now() - self._cache_time).seconds < self._cache_ttl

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Holt einen System-Setting Wert."""
        query = """
            SELECT setting_value FROM system_settings
            WHERE setting_key = %s
        """
        result = self.db.execute(query, (key,))

        if not result:
            return default

        value = result[0]["setting_value"]

        # JSONB kommt als Python-Objekt, falls es ein String ist parsen
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value

        return value

    def set_setting(self, key: str, value: Any, description: str = None):
        """Setzt einen System-Setting Wert."""
        json_value = json.dumps(value)

        query = """
            INSERT INTO system_settings (setting_key, setting_value, description, updated_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (setting_key)
            DO UPDATE SET setting_value = %s, updated_at = NOW()
        """

        self.db.execute(query, (key, json_value, description, json_value))

    def get_language_mapping(self, mapping_type: str, mapping_key: str = "default", language: str = "de") -> Any:
        """Holt ein Language-Mapping."""
        query = """
            SELECT mapping_value FROM language_mappings
            WHERE mapping_type = %s AND mapping_key = %s AND language = %s AND is_active = TRUE
        """
        result = self.db.execute(query, (mapping_type, mapping_key, language))

        if not result:
            return None

        value = result[0]["mapping_value"]

        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value

        return value

    def get_all_mappings(self, mapping_type: str, language: str = "de") -> Dict[str, Any]:
        """Holt alle Mappings eines Typs."""
        query = """
            SELECT mapping_key, mapping_value FROM language_mappings
            WHERE mapping_type = %s AND language = %s AND is_active = TRUE
        """
        results = self.db.execute(query, (mapping_type, language))

        mappings = {}
        for row in results:
            key = row["mapping_key"]
            value = row["mapping_value"]

            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    pass

            mappings[key] = value

        return mappings

    def get_stopwords(self, language: str = "de") -> List[str]:
        """Holt Stopwords für eine Sprache."""
        return self.get_language_mapping("stopwords", "default", language) or []

    def get_priority_keywords(self, language: str = "de") -> Dict[str, List[str]]:
        """Holt Priority-Keywords (high, medium, low)."""
        return self.get_all_mappings("priority", language)

    def get_completion_keywords(self, language: str = "de") -> List[str]:
        """Holt Completion-Keywords."""
        return self.get_language_mapping("completion", "default", language) or []

    def get_deletion_keywords(self, language: str = "de") -> List[str]:
        """Holt Deletion-Keywords."""
        return self.get_language_mapping("deletion", "default", language) or []

    def get_date_patterns(self, language: str = "de") -> Dict[str, Dict]:
        """Holt Date-Patterns."""
        return self.get_all_mappings("date", language)


# Factory-Funktionen
_agent_cache: Dict[str, ConfigurableAgent] = {}
_config_manager: Optional[ConfigManager] = None


def get_configurable_agent(agent_name: str, db_connection) -> ConfigurableAgent:
    """
    Gibt eine ConfigurableAgent Instanz zurück.

    Cached Instanzen für Wiederverwendung.
    """
    cache_key = f"{agent_name}_{id(db_connection)}"

    if cache_key not in _agent_cache:
        _agent_cache[cache_key] = ConfigurableAgent(agent_name, db_connection)

    return _agent_cache[cache_key]


def get_config_manager(db_connection) -> ConfigManager:
    """Gibt die ConfigManager Instanz zurück."""
    global _config_manager

    if _config_manager is None:
        _config_manager = ConfigManager(db_connection)

    return _config_manager
