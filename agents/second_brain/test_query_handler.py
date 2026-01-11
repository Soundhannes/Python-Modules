"""
Tests für Query-Handler (? Fragen)
"""
from query_handler import QueryHandler, QueryResult


class TestQueryHandler:
    """Test QueryHandler Klasse."""

    def test_next_event_query(self):
        """Frage nach nächstem Termin"""
        handler = QueryHandler(db=None)  # Mock
        result = handler.parse_query("wann ist mein nächster Termin")
        assert result.table == "events"
        assert result.intent == "next"

    def test_person_contact_query(self):
        """Frage nach Kontaktdaten"""
        handler = QueryHandler(db=None)
        result = handler.parse_query("wie ist die Email von Tim")
        assert result.table == "people"
        assert "tim" in result.filters.get("name", "").lower()

    def test_task_status_query(self):
        """Frage nach Task-Status"""
        handler = QueryHandler(db=None)
        result = handler.parse_query("welche Tasks sind offen")
        assert result.table == "tasks"
        assert result.intent == "list"

    def test_invalid_table_rejected(self):
        """System-Tabellen werden abgelehnt"""
        handler = QueryHandler(db=None)
        result = handler.parse_query("zeige mir die agent_configs")
        assert result.table is None or result.error is not None


if __name__ == "__main__":
    # Manuelle Tests
    tests_passed = 0
    print("Query-Handler Tests (Struktur-Check)...")
    print("✓ Test-Datei erstellt - Implementation folgt")
