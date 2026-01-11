"""Test: OutputParser - Strukturierte Daten aus LLM-Antworten."""

import sys
sys.path.insert(0, "/opt/python-modules")

from agents.utils.output_parser import OutputParser, ParseResult, get_output_parser


def test_parse_json_direct():
    print("=== Test 1: JSON direkt ===")

    parser = OutputParser()
    text = '{"name": "Test", "count": 42}'

    result = parser.parse_json(text)

    assert result.success
    assert result.data["name"] == "Test"
    assert result.data["count"] == 42
    assert result.format_detected == "json_direct"
    print(f"Format: {result.format_detected}")
    print(f"Data: {result.data}")
    print("OK\n")


def test_parse_json_codeblock():
    print("=== Test 2: JSON in Code-Block ===")

    parser = OutputParser()
    text = '''Hier ist das Ergebnis:

```json
{"status": "ok", "items": [1, 2, 3]}
```

Das war's.'''

    result = parser.parse_json(text)

    assert result.success
    assert result.data["status"] == "ok"
    assert result.data["items"] == [1, 2, 3]
    assert result.format_detected == "json_codeblock"
    print(f"Format: {result.format_detected}")
    print(f"Data: {result.data}")
    print("OK\n")


def test_parse_json_embedded():
    print("=== Test 3: JSON eingebettet ===")

    parser = OutputParser()
    text = '''Die Analyse ergibt folgendes Ergebnis: {"score": 85, "grade": "B"} basierend auf den Daten.'''

    result = parser.parse_json(text)

    assert result.success
    assert result.data["score"] == 85
    assert result.data["grade"] == "B"
    assert result.format_detected == "json_embedded"
    print(f"Format: {result.format_detected}")
    print(f"Data: {result.data}")
    print("OK\n")


def test_parse_json_with_schema():
    print("=== Test 4: JSON mit Schema ===")

    parser = OutputParser()
    text = '{"name": "Test", "value": "123"}'

    schema = {
        "name": {"type": str, "required": True},
        "value": {"type": int},
        "optional": {"type": str, "default": "default_value"}
    }

    result = parser.parse_json(text, schema=schema)

    assert result.success
    assert result.data["name"] == "Test"
    assert result.data["value"] == 123  # Konvertiert zu int
    assert result.data["optional"] == "default_value"
    print(f"Data: {result.data}")
    print("OK\n")


def test_parse_list_markdown():
    print("=== Test 5: Markdown Liste ===")

    parser = OutputParser()
    text = '''Hier sind die Punkte:
- Erster Punkt
- Zweiter Punkt
- Dritter Punkt'''

    result = parser.parse_list(text)

    assert result.success
    assert len(result.data) == 3
    assert result.data[0] == "Erster Punkt"
    assert result.format_detected == "markdown_list"
    print(f"Format: {result.format_detected}")
    print(f"Items: {result.data}")
    print("OK\n")


def test_parse_list_numbered():
    print("=== Test 6: Nummerierte Liste ===")

    parser = OutputParser()
    text = '''Die Schritte:
1. Schritt eins
2. Schritt zwei
3. Schritt drei'''

    result = parser.parse_list(text)

    assert result.success
    assert len(result.data) == 3
    assert result.format_detected == "numbered_list"
    print(f"Format: {result.format_detected}")
    print(f"Items: {result.data}")
    print("OK\n")


def test_parse_list_comma():
    print("=== Test 7: Komma-getrennte Liste ===")

    parser = OutputParser()
    text = "rot, grün, blau, gelb"

    result = parser.parse_list(text)

    assert result.success
    assert len(result.data) == 4
    assert "rot" in result.data
    assert result.format_detected == "comma_separated"
    print(f"Format: {result.format_detected}")
    print(f"Items: {result.data}")
    print("OK\n")


def test_parse_key_value():
    print("=== Test 8: Key-Value Paare ===")

    parser = OutputParser()
    text = '''Name: Max Mustermann
Alter: 30
Aktiv: true
Score: 85.5'''

    result = parser.parse_key_value(text)

    assert result.success
    assert result.data["Name"] == "Max Mustermann"
    assert result.data["Alter"] == 30
    assert result.data["Aktiv"] == True
    assert result.data["Score"] == 85.5
    print(f"Data: {result.data}")
    print("OK\n")


def test_no_json_found():
    print("=== Test 9: Kein JSON gefunden ===")

    parser = OutputParser()
    text = "Das ist einfach nur Text ohne JSON."

    result = parser.parse_json(text)

    assert not result.success
    assert result.data is None
    assert "Kein JSON gefunden" in result.errors
    print(f"Errors: {result.errors}")
    print("OK\n")


def test_json_array():
    print("=== Test 10: JSON Array ===")

    parser = OutputParser()
    text = '["apple", "banana", "cherry"]'

    result = parser.parse_json(text)

    assert result.success
    assert len(result.data) == 3
    assert "apple" in result.data
    print(f"Format: {result.format_detected}")
    print(f"Data: {result.data}")
    print("OK\n")


def test_factory():
    print("=== Test 11: Factory Funktion ===")

    parser = get_output_parser()
    assert isinstance(parser, OutputParser)

    # Gleiche Instanz
    parser2 = get_output_parser()
    assert parser is parser2

    print("Factory funktioniert: OK")
    print("OK\n")


if __name__ == "__main__":
    print("OutputParser Tests\n" + "="*50 + "\n")

    test_parse_json_direct()
    test_parse_json_codeblock()
    test_parse_json_embedded()
    test_parse_json_with_schema()
    test_parse_list_markdown()
    test_parse_list_numbered()
    test_parse_list_comma()
    test_parse_key_value()
    test_no_json_found()
    test_json_array()
    test_factory()

    print("="*50)
    print("Alle Tests bestanden!")
