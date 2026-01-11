"""
BaseAgent - Wiederverwendbare Agent-Klasse für LLM-Aufrufe.

Standardisierter Agent der:
- LLM-Provider flexibel nutzt
- System- und User-Prompts mit Templates unterstützt
- Strukturierte Ausgaben (JSON) ermöglicht
- Tools/Function Calling (vorbereitet)
- Fehlerbehandlung eingebaut hat

Verwendung:
    agent = BaseAgent("analyst", provider="anthropic")
    result = agent.run(
        system_prompt="Du bist ein Analyst.",
        user_prompt="Analysiere: {data}",
        context={"data": "Verkaufszahlen..."}
    )
    print(result.response)
"""

import sys
import json
import time
import warnings
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime

sys.path.insert(0, "/opt/python-modules")
from llm import get_client, Message


@dataclass
class ToolDefinition:
    """Definition eines Tools für Function Calling."""
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema
    handler: Optional[Callable] = None  # Optionale Handler-Funktion


@dataclass
class ToolCall:
    """Ein Tool-Aufruf vom LLM."""
    name: str
    arguments: Dict[str, Any]
    result: Optional[Any] = None


@dataclass
class AgentResult:
    """Ergebnis eines Agent-Aufrufs."""
    agent_name: str                        # Name des Agents
    response: str                          # LLM-Antwort (Text)
    structured: Optional[Dict[str, Any]]   # Geparste JSON-Antwort (falls möglich)
    tool_calls: List[ToolCall]             # Tool-Aufrufe (falls vorhanden)
    tokens_used: int                       # Token-Verbrauch
    model: str                             # Verwendetes Modell
    provider: str                          # Verwendeter Provider
    success: bool                          # Erfolgreich?
    error: Optional[str]                   # Fehlermeldung
    duration_ms: int                       # Dauer in Millisekunden
    timestamp: datetime = field(default_factory=datetime.now)


class BaseAgent:
    """
    Basis-Agent für LLM-Aufrufe.

    Args:
        name: Name des Agents (für Logging/Tracking)
        provider: LLM-Provider ('anthropic', 'openai', 'google')
        model: Spezifisches Modell (optional)
        tools: Liste von Tool-Definitionen für Function Calling
        default_max_tokens: Standard max_tokens
        default_temperature: Standard temperature

    Kann vererbt werden für spezialisierte Agents:
        class AnalystAgent(BaseAgent):
            def __init__(self):
                super().__init__('analyst', provider='anthropic')
    """

    def __init__(
        self,
        name: str = "agent",
        provider: str = "anthropic",
        model: Optional[str] = None,
        tools: List[ToolDefinition] = None,
        default_max_tokens: int = 2048,
        default_temperature: float = 0.7
    ):
        self.name = name
        self.provider = provider
        self.model = model
        self.tools = tools or []
        self.default_max_tokens = default_max_tokens
        self.default_temperature = default_temperature
        self._client = None

        # Warnung wenn Tools definiert aber nicht unterstützt
        if self.tools:
            warnings.warn(
                f"Agent '{name}': Tools sind definiert, aber das LLM-Modul "
                "unterstützt Function Calling noch nicht. Tools werden ignoriert.",
                UserWarning
            )

    def _get_client(self):
        if self._client is None:
            self._client = get_client(self.provider)
        return self._client

    def _render_template(self, template: str, context: Dict[str, Any]) -> str:
        try:
            return template.format(**context)
        except KeyError as e:
            raise ValueError(f"Template-Variable nicht gefunden: {e}")

    def _try_parse_json(self, text: str) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        if "```json" in text:
            try:
                start = text.index("```json") + 7
                end = text.index("```", start)
                return json.loads(text[start:end].strip())
            except (ValueError, json.JSONDecodeError):
                pass

        if "{" in text and "}" in text:
            try:
                start = text.index("{")
                depth = 0
                for i, char in enumerate(text[start:], start):
                    if char == "{":
                        depth += 1
                    elif char == "}":
                        depth -= 1
                        if depth == 0:
                            return json.loads(text[start:i+1])
            except (ValueError, json.JSONDecodeError):
                pass

        return None

    def _make_result(
        self,
        response: str = "",
        structured: Optional[Dict[str, Any]] = None,
        tool_calls: List[ToolCall] = None,
        tokens_used: int = 0,
        model: str = "",
        success: bool = True,
        error: Optional[str] = None,
        duration_ms: int = 0
    ) -> AgentResult:
        return AgentResult(
            agent_name=self.name,
            response=response,
            structured=structured,
            tool_calls=tool_calls or [],
            tokens_used=tokens_used,
            model=model or self.model or "unknown",
            provider=self.provider,
            success=success,
            error=error,
            duration_ms=duration_ms
        )

    def add_tool(self, tool: ToolDefinition):
        """Fügt ein Tool hinzu."""
        self.tools.append(tool)
        warnings.warn(
            f"Tool '{tool.name}' hinzugefügt, aber Function Calling "
            "wird noch nicht unterstützt.",
            UserWarning
        )

    def run(
        self,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, str]]] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        expect_json: bool = False,
        use_tools: bool = False
    ) -> AgentResult:
        """
        Führt den Agent aus.

        Args:
            user_prompt: User-Nachricht (kann Template sein)
            system_prompt: System-Prompt (optional)
            context: Variablen für Templates
            history: Vorherige Nachrichten [{role, content}, ...]
            max_tokens: Max. Antwortlänge
            temperature: Kreativität (0-1)
            expect_json: Fügt JSON-Anweisung zum Prompt hinzu
            use_tools: Aktiviert Tool/Function Calling (noch nicht implementiert)

        Returns:
            AgentResult mit Antwort und Metadaten
        """
        start_time = time.time()

        context = context or {}
        max_tokens = max_tokens or self.default_max_tokens
        temperature = temperature or self.default_temperature

        # Warnung wenn use_tools aber keine Tools oder nicht unterstützt
        if use_tools:
            if not self.tools:
                warnings.warn("use_tools=True aber keine Tools definiert.", UserWarning)
            else:
                warnings.warn(
                    "use_tools=True aber Function Calling wird noch nicht unterstützt.",
                    UserWarning
                )

        try:
            rendered_user = self._render_template(user_prompt, context)
            rendered_system = None
            if system_prompt:
                rendered_system = self._render_template(system_prompt, context)

            if expect_json:
                rendered_user += "\n\nAntworte ausschließlich mit validem JSON."

            messages = []
            if history:
                for msg in history:
                    messages.append(Message(role=msg["role"], content=msg["content"]))
            messages.append(Message(role="user", content=rendered_user))

            client = self._get_client()
            response = client.chat(
                messages=messages,
                model=self.model,
                max_tokens=max_tokens,
                system_prompt=rendered_system
            )

            duration_ms = int((time.time() - start_time) * 1000)
            structured = self._try_parse_json(response.content)

            return self._make_result(
                response=response.content,
                structured=structured,
                tokens_used=response.tokens_used,
                model=response.model,
                success=True,
                duration_ms=duration_ms
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return self._make_result(
                success=False,
                error=str(e),
                duration_ms=duration_ms
            )

    def run_with_retry(
        self,
        user_prompt: str,
        max_retries: int = 3,
        **kwargs
    ) -> AgentResult:
        """
        Führt Agent mit Retry bei Fehlern aus.

        Args:
            user_prompt: User-Nachricht
            max_retries: Maximale Versuche
            **kwargs: Weitere Argumente für run()

        Returns:
            AgentResult
        """
        last_result = None

        for attempt in range(max_retries):
            result = self.run(user_prompt, **kwargs)
            if result.success:
                return result
            last_result = result
            time.sleep(1 * (attempt + 1))

        return last_result
