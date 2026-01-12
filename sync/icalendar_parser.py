"""
iCalendar Parser fuer CalDAV-Synchronisation.

Konvertiert zwischen iCalendar (.ics) Format und CalendarEvent Dataclass.
"""
import re
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import List, Optional


@dataclass
class CalendarEvent:
    """Event-Datenstruktur fuer Kalender-Sync."""
    title: str = ""
    description: Optional[str] = None
    location: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    all_day: bool = False
    recurrence: Optional[str] = None
    icloud_uid: Optional[str] = None
    etag: Optional[str] = None
    calendar_id: Optional[int] = None
    is_local: bool = False


class ICalendarParser:
    """Parser fuer iCalendar Format."""
    
    def parse(self, ics_string: str) -> List[CalendarEvent]:
        """
        Parsed iCalendar String zu Liste von CalendarEvent.
        
        Args:
            ics_string: iCalendar im String-Format
            
        Returns:
            Liste von CalendarEvent Objekten
        """
        events = []
        
        # Finde alle VEVENT Bloecke
        vevent_pattern = r'BEGIN:VEVENT(.*?)END:VEVENT'
        matches = re.findall(vevent_pattern, ics_string, re.DOTALL)
        
        for vevent_content in matches:
            event = self._parse_vevent(vevent_content)
            if event:
                events.append(event)
        
        return events
    
    def _parse_vevent(self, vevent_content: str) -> Optional[CalendarEvent]:
        """Parsed einzelnes VEVENT."""
        event = CalendarEvent()
        
        lines = vevent_content.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            
            # UID
            if line.startswith('UID:'):
                event.icloud_uid = line[4:].strip()
            
            # SUMMARY (Title)
            elif line.startswith('SUMMARY:'):
                event.title = line[8:].strip()
            
            # DESCRIPTION
            elif line.startswith('DESCRIPTION:'):
                event.description = line[12:].strip()
            
            # LOCATION
            elif line.startswith('LOCATION:'):
                event.location = line[9:].strip()
            
            # DTSTART
            elif line.startswith('DTSTART'):
                event.start_time, event.all_day = self._parse_datetime(line)
            
            # DTEND
            elif line.startswith('DTEND'):
                event.end_time, _ = self._parse_datetime(line)
            
            # RRULE (Recurrence)
            elif line.startswith('RRULE:'):
                event.recurrence = line[6:].strip()
        
        return event if event.title or event.icloud_uid else None
    
    def _parse_datetime(self, line: str) -> tuple:
        """
        Parsed DTSTART/DTEND Zeile.
        
        Returns:
            (datetime, is_all_day)
        """
        is_all_day = False
        
        # Extrahiere Wert nach dem letzten Doppelpunkt
        if ':' in line:
            value = line.split(':')[-1].strip()
        else:
            return None, False
        
        # Check fuer VALUE=DATE (Ganztages-Event)
        if 'VALUE=DATE' in line:
            is_all_day = True
            try:
                # Format: YYYYMMDD
                dt = datetime.strptime(value, '%Y%m%d')
                return dt, is_all_day
            except ValueError:
                return None, is_all_day
        
        # Standard DateTime Format
        try:
            # Format: YYYYMMDDTHHMMSSZ oder YYYYMMDDTHHMMSS
            value = value.rstrip('Z')
            if 'T' in value:
                dt = datetime.strptime(value, '%Y%m%dT%H%M%S')
                return dt, is_all_day
        except ValueError:
            pass
        
        return None, is_all_day
    
    def serialize(self, event: CalendarEvent) -> str:
        """
        Serialisiert CalendarEvent zu iCalendar String.
        
        Args:
            event: CalendarEvent Objekt
            
        Returns:
            iCalendar String
        """
        lines = [
            'BEGIN:VCALENDAR',
            'VERSION:2.0',
            'PRODID:-//Second Brain//CalDAV//EN',
            'BEGIN:VEVENT'
        ]
        
        # UID
        if event.icloud_uid:
            lines.append(f'UID:{event.icloud_uid}')
        
        # SUMMARY
        if event.title:
            lines.append(f'SUMMARY:{event.title}')
        
        # DESCRIPTION
        if event.description:
            lines.append(f'DESCRIPTION:{event.description}')
        
        # LOCATION
        if event.location:
            lines.append(f'LOCATION:{event.location}')
        
        # DTSTART
        if event.start_time:
            if event.all_day:
                lines.append(f'DTSTART;VALUE=DATE:{event.start_time.strftime("%Y%m%d")}')
            else:
                lines.append(f'DTSTART:{event.start_time.strftime("%Y%m%dT%H%M%SZ")}')
        
        # DTEND
        if event.end_time:
            if event.all_day:
                lines.append(f'DTEND;VALUE=DATE:{event.end_time.strftime("%Y%m%d")}')
            else:
                lines.append(f'DTEND:{event.end_time.strftime("%Y%m%dT%H%M%SZ")}')
        
        # RRULE
        if event.recurrence:
            lines.append(f'RRULE:{event.recurrence}')
        
        lines.append('END:VEVENT')
        lines.append('END:VCALENDAR')
        
        return '\n'.join(lines)
