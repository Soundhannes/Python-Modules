"""
Tests für Prefix-Parser (? Query, ! Edit, default Create)
"""
import pytest
from prefix_parser import parse_prefix, PrefixType


class TestPrefixParser:
    """Test parse_prefix Funktion."""

    def test_query_prefix_simple(self):
        """? am Anfang = Query"""
        result = parse_prefix("?wann ist mein nächster Termin")
        assert result.type == PrefixType.QUERY
        assert result.text == "wann ist mein nächster Termin"

    def test_query_prefix_with_space(self):
        """? mit Leerzeichen"""
        result = parse_prefix("? wie ist die Email von Tim")
        assert result.type == PrefixType.QUERY
        assert result.text == "wie ist die Email von Tim"

    def test_edit_prefix_simple(self):
        """! am Anfang = Edit"""
        result = parse_prefix("!Task 13 erledigt")
        assert result.type == PrefixType.EDIT
        assert result.text == "Task 13 erledigt"

    def test_edit_prefix_with_space(self):
        """! mit Leerzeichen"""
        result = parse_prefix("! ändere Status von Task 5 auf done")
        assert result.type == PrefixType.EDIT
        assert result.text == "ändere Status von Task 5 auf done"

    def test_create_no_prefix(self):
        """Kein Prefix = Create"""
        result = parse_prefix("Meeting morgen mit Tim")
        assert result.type == PrefixType.CREATE
        assert result.text == "Meeting morgen mit Tim"

    def test_create_question_in_middle(self):
        """? in der Mitte ist kein Query"""
        result = parse_prefix("Meeting morgen um 14 Uhr?")
        assert result.type == PrefixType.CREATE
        assert result.text == "Meeting morgen um 14 Uhr?"

    def test_create_exclamation_in_middle(self):
        """! in der Mitte ist kein Edit"""
        result = parse_prefix("Das ist wichtig!")
        assert result.type == PrefixType.CREATE
        assert result.text == "Das ist wichtig!"

    def test_empty_after_prefix(self):
        """Nur Prefix ohne Text"""
        result = parse_prefix("?")
        assert result.type == PrefixType.QUERY
        assert result.text == ""

    def test_whitespace_handling(self):
        """Whitespace wird getrimmt"""
        result = parse_prefix("  ?  nächster Termin  ")
        assert result.type == PrefixType.QUERY
        assert result.text == "nächster Termin"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
