"""
OutputParser - Strukturierte Daten aus LLM-Antworten extrahieren.

Unterstützt:
- JSON (direkt, in Code-Blöcken, eingebettet)
- Markdown Listen
- Key-Value Paare
- Schema-Validierung

Verwendung:
    parser = OutputParser()

    # JSON extrahieren
    data = parser.parse_json(llm_response)

    # Mit Schema validieren
    data = parser.parse_json(llm_response, schema={
        "name": {"type": str, "required": True},
        "count": {"type": int, "default": 0}
    })

    # Liste extrahieren
    items = parser.parse_list(llm_response)
"""

import json
import re
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass


@dataclass
class ParseResult:
    """Ergebnis eines Parse-Vorgangs."""
    success: bool
    data: Any
    raw: str
    format_detected: str
    errors: List[str]


class OutputParser:
    """
    Parser für LLM-Ausgaben.

    Extrahiert strukturierte Daten aus Freitext-Antworten.
    """

    def __init__(self):
        """Initialisiert den Parser."""
        pass

    # === JSON Parsing ===

    def parse_json(
        self,
        text: str,
        schema: Dict[str, Dict] = None,
        strict: bool = False
    ) -> ParseResult:
        """
        Extrahiert JSON aus Text.

        Sucht in folgender Reihenfolge:
        1. Gesamter Text als JSON
        2. ```json ... ``` Code-Blöcke
        3. Erster { ... } Block

        Args:
            text: LLM-Antwort
            schema: Optionales Schema für Validierung
            strict: Bei True schlägt fehl wenn Schema nicht erfüllt

        Returns:
            ParseResult
        """
        errors = []
        data = None
        format_detected = "none"

        # Versuch 1: Gesamter Text
        try:
            data = json.loads(text.strip())
            format_detected = "json_direct"
        except json.JSONDecodeError:
            pass

        # Versuch 2: JSON Code-Block
        if data is None and "```json" in text:
            try:
                match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
                if match:
                    data = json.loads(match.group(1))
                    format_detected = "json_codeblock"
            except (json.JSONDecodeError, AttributeError):
                pass

        # Versuch 3: Allgemeiner Code-Block
        if data is None and "```" in text:
            try:
                match = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
                if match:
                    data = json.loads(match.group(1))
                    format_detected = "json_codeblock"
            except (json.JSONDecodeError, AttributeError):
                pass

        # Versuch 4: Eingebetteter JSON-Block
        if data is None and "{" in text:
            data = self._extract_json_block(text)
            if data is not None:
                format_detected = "json_embedded"

        # Versuch 5: JSON-Array
        if data is None and "[" in text:
            data = self._extract_array_block(text)
            if data is not None:
                format_detected = "json_array"

        # Kein JSON gefunden
        if data is None:
            return ParseResult(
                success=False,
                data=None,
                raw=text,
                format_detected="none",
                errors=["Kein JSON gefunden"]
            )

        # Schema-Validierung
        if schema:
            data, validation_errors = self._validate_schema(data, schema, strict)
            errors.extend(validation_errors)

        return ParseResult(
            success=len(errors) == 0,
            data=data,
            raw=text,
            format_detected=format_detected,
            errors=errors
        )

    def _extract_json_block(self, text: str) -> Optional[Dict]:
        """Extrahiert ersten { ... } Block."""
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

    def _extract_array_block(self, text: str) -> Optional[List]:
        """Extrahiert ersten [ ... ] Block."""
        try:
            start = text.index("[")
            depth = 0
            for i, char in enumerate(text[start:], start):
                if char == "[":
                    depth += 1
                elif char == "]":
                    depth -= 1
                    if depth == 0:
                        return json.loads(text[start:i+1])
        except (ValueError, json.JSONDecodeError):
            pass
        return None

    def _validate_schema(
        self,
        data: Dict,
        schema: Dict[str, Dict],
        strict: bool
    ) -> tuple:
        """Validiert Daten gegen Schema."""
        errors = []
        result = {}

        if not isinstance(data, dict):
            return data, ["Daten sind kein Dict"]

        for field, rules in schema.items():
            value = data.get(field)

            # Required Check
            if rules.get("required", False) and value is None:
                if "default" in rules:
                    value = rules["default"]
                elif strict:
                    errors.append(f"{field}: Pflichtfeld fehlt")
                    continue
                else:
                    continue

            # Default setzen
            if value is None and "default" in rules:
                value = rules["default"]

            if value is None:
                continue

            # Type Coercion
            expected_type = rules.get("type")
            if expected_type:
                value, type_error = self._coerce_type(value, expected_type, field)
                if type_error:
                    errors.append(type_error)
                    if strict:
                        continue

            result[field] = value

        # Zusätzliche Felder übernehmen
        for key, value in data.items():
            if key not in result:
                result[key] = value

        return result, errors

    def _coerce_type(self, value: Any, expected_type: type, field: str) -> tuple:
        """Versucht Typ-Konvertierung."""
        if isinstance(value, expected_type):
            return value, None

        try:
            if expected_type == int:
                return int(float(value)), None
            elif expected_type == float:
                return float(value), None
            elif expected_type == str:
                return str(value), None
            elif expected_type == bool:
                if isinstance(value, str):
                    return value.lower() in ("true", "1", "yes", "ja"), None
                return bool(value), None
            elif expected_type == list:
                if isinstance(value, str):
                    return [v.strip() for v in value.split(",")], None
                return list(value), None
        except (ValueError, TypeError):
            pass

        return value, f"{field}: Kann nicht zu {expected_type.__name__} konvertiert werden"

    # === List Parsing ===

    def parse_list(
        self,
        text: str,
        pattern: str = None
    ) -> ParseResult:
        """
        Extrahiert Liste aus Text.

        Erkennt:
        - Markdown Listen (-, *, 1.)
        - Nummerierte Listen
        - Komma-getrennte Werte
        - Zeilenweise Aufzählung

        Args:
            text: LLM-Antwort
            pattern: Optionales Regex-Pattern für Items

        Returns:
            ParseResult
        """
        items = []
        format_detected = "none"

        # Versuch 1: JSON-Array
        if text.strip().startswith("["):
            try:
                items = json.loads(text.strip())
                if isinstance(items, list):
                    format_detected = "json_array"
            except json.JSONDecodeError:
                pass

        # Versuch 2: Markdown Liste
        if not items:
            md_pattern = r'^[\s]*[-*]\s+(.+)$'
            matches = re.findall(md_pattern, text, re.MULTILINE)
            if matches:
                items = [m.strip() for m in matches]
                format_detected = "markdown_list"

        # Versuch 3: Nummerierte Liste
        if not items:
            num_pattern = r'^[\s]*\d+[.)]\s+(.+)$'
            matches = re.findall(num_pattern, text, re.MULTILINE)
            if matches:
                items = [m.strip() for m in matches]
                format_detected = "numbered_list"

        # Versuch 4: Custom Pattern
        if not items and pattern:
            matches = re.findall(pattern, text, re.MULTILINE)
            if matches:
                items = [m.strip() if isinstance(m, str) else m[0].strip() for m in matches]
                format_detected = "custom_pattern"

        # Versuch 5: Komma-getrennt (einzeilig)
        if not items and "," in text and "\n" not in text.strip():
            items = [v.strip() for v in text.split(",") if v.strip()]
            format_detected = "comma_separated"

        # Versuch 6: Zeilenweise
        if not items:
            lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
            if len(lines) > 1:
                items = lines
                format_detected = "line_separated"

        return ParseResult(
            success=len(items) > 0,
            data=items,
            raw=text,
            format_detected=format_detected,
            errors=[] if items else ["Keine Liste gefunden"]
        )

    # === Key-Value Parsing ===

    def parse_key_value(
        self,
        text: str,
        separator: str = ":"
    ) -> ParseResult:
        """
        Extrahiert Key-Value Paare aus Text.

        Args:
            text: LLM-Antwort
            separator: Trennzeichen zwischen Key und Value

        Returns:
            ParseResult
        """
        data = {}
        errors = []

        # Zeile für Zeile
        for line in text.strip().split("\n"):
            line = line.strip()
            if not line or separator not in line:
                continue

            # Erstes Vorkommen des Separators
            idx = line.index(separator)
            key = line[:idx].strip()
            value = line[idx+1:].strip()

            # Markdown-Formatting entfernen
            key = re.sub(r'^\*\*(.+)\*\*$', r'\1', key)
            key = re.sub(r'^[-*]\s*', '', key)

            if key:
                # Wert-Typ erkennen
                data[key] = self._infer_type(value)

        return ParseResult(
            success=len(data) > 0,
            data=data,
            raw=text,
            format_detected="key_value",
            errors=errors if not data else []
        )

    def _infer_type(self, value: str) -> Any:
        """Erkennt und konvertiert Typ eines Wertes."""
        value = value.strip()

        # Boolean
        if value.lower() in ("true", "yes", "ja"):
            return True
        if value.lower() in ("false", "no", "nein"):
            return False

        # None/Null
        if value.lower() in ("null", "none", ""):
            return None

        # Integer
        try:
            if "." not in value:
                return int(value)
        except ValueError:
            pass

        # Float
        try:
            return float(value)
        except ValueError:
            pass

        # String (ohne Anführungszeichen)
        if value.startswith('"') and value.endswith('"'):
            return value[1:-1]
        if value.startswith("'") and value.endswith("'"):
            return value[1:-1]

        return value


# Globale Instanz
_parser_instance: Optional[OutputParser] = None


def get_output_parser() -> OutputParser:
    """Gibt die globale OutputParser-Instanz zurück."""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = OutputParser()
    return _parser_instance
