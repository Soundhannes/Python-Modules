"""
Tests fuer iCalendar Parser.
"""
# import pytest
from datetime import datetime
from icalendar_parser import ICalendarParser, CalendarEvent


class TestICalendarParser:
    """Tests fuer ICalendarParser."""
    
    def setup_method(self):
        self.parser = ICalendarParser()
    
    def test_parse_simple_event(self):
        """Parsed einfaches Event."""
        ics = '''BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:test-123
SUMMARY:Meeting
DTSTART:20260115T100000Z
DTEND:20260115T110000Z
END:VEVENT
END:VCALENDAR'''
        
        events = self.parser.parse(ics)
        
        assert len(events) == 1
        assert events[0].title == "Meeting"
        assert events[0].icloud_uid == "test-123"
        assert events[0].start_time == datetime(2026, 1, 15, 10, 0, 0)
        assert events[0].end_time == datetime(2026, 1, 15, 11, 0, 0)
    
    def test_parse_all_day_event(self):
        """Parsed Ganztages-Event."""
        ics = '''BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:allday-456
SUMMARY:Urlaub
DTSTART;VALUE=DATE:20260120
DTEND;VALUE=DATE:20260125
END:VEVENT
END:VCALENDAR'''
        
        events = self.parser.parse(ics)
        
        assert len(events) == 1
        assert events[0].title == "Urlaub"
        assert events[0].all_day == True
    
    def test_parse_event_with_location(self):
        """Parsed Event mit Ort."""
        ics = '''BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:loc-789
SUMMARY:Konferenz
DTSTART:20260115T140000Z
LOCATION:Hamburg, Rathaus
END:VEVENT
END:VCALENDAR'''
        
        events = self.parser.parse(ics)
        
        assert events[0].location == "Hamburg, Rathaus"
    
    def test_parse_event_with_description(self):
        """Parsed Event mit Beschreibung."""
        ics = '''BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:desc-101
SUMMARY:Workshop
DTSTART:20260115T090000Z
DESCRIPTION:Wichtiger Workshop mit Team
END:VEVENT
END:VCALENDAR'''
        
        events = self.parser.parse(ics)
        
        assert events[0].description == "Wichtiger Workshop mit Team"
    
    def test_serialize_event(self):
        """Serialisiert Event zu iCalendar."""
        event = CalendarEvent(
            title="Test Event",
            start_time=datetime(2026, 1, 20, 14, 0, 0),
            end_time=datetime(2026, 1, 20, 15, 0, 0),
            icloud_uid="serialize-test"
        )
        
        ics = self.parser.serialize(event)
        
        assert "BEGIN:VCALENDAR" in ics
        assert "BEGIN:VEVENT" in ics
        assert "SUMMARY:Test Event" in ics
        assert "UID:serialize-test" in ics
        assert "END:VEVENT" in ics
        assert "END:VCALENDAR" in ics


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
