"""
iCloud CalDAV Provider.

Nutzt dieselbe Authentifizierung wie CardDAV (Apple ID + App-Passwort).
"""
import re
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
import requests
import logging

from ..icalendar_parser import ICalendarParser, CalendarEvent

logger = logging.getLogger(__name__)


class Calendar:
    """Kalender-Datenstruktur."""
    def __init__(self, uid: str, name: str, color: Optional[str] = None, ctag: Optional[str] = None):
        self.uid = uid
        self.name = name
        self.color = color
        self.ctag = ctag
        self.url: Optional[str] = None


class ICloudCalendarProvider:
    """
    CalDAV Provider fuer iCloud.
    
    Endpoint: caldav.icloud.com
    Auth: Apple ID + App-spezifisches Passwort (gleich wie CardDAV)
    """
    
    CALDAV_URL = "https://caldav.icloud.com"
    NAMESPACES = {
        'd': 'DAV:',
        'cal': 'urn:ietf:params:xml:ns:caldav',
        'cs': 'http://calendarserver.org/ns/',
        'apple': 'http://apple.com/ns/ical/'
    }
    
    def __init__(self):
        self.session: Optional[requests.Session] = None
        self.calendar_home_url: Optional[str] = None
        self.parser = ICalendarParser()
    
    def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """
        Authentifiziert mit iCloud CalDAV.
        
        Args:
            credentials: Dict mit apple_id, app_password
            
        Returns:
            True bei Erfolg
        """
        required = ['apple_id', 'app_password']
        missing = [k for k in required if k not in credentials or not credentials[k]]
        if missing:
            raise ValueError(f"Missing required credentials: {missing}")
        
        apple_id = credentials['apple_id'].strip()
        app_password = credentials['app_password'].replace('-', '').replace(' ', '').strip()
        
        logger.info(f"CalDAV auth attempt for: {apple_id[:3]}***")
        
        self.session = requests.Session()
        self.session.auth = (apple_id, app_password)
        self.session.headers.update({
            'User-Agent': 'DAVx5/4.3.1-ose',
            'Accept': '*/*',
        })
        
        try:
            # Finde Principal URL
            propfind_body = '''<?xml version="1.0" encoding="UTF-8"?>
<d:propfind xmlns:d="DAV:">
  <d:prop>
    <d:current-user-principal/>
  </d:prop>
</d:propfind>'''
            
            response = self.session.request(
                'PROPFIND',
                self.CALDAV_URL,
                data=propfind_body,
                headers={'Content-Type': 'application/xml; charset=utf-8', 'Depth': '0'},
                timeout=30
            )
            
            if response.status_code == 401:
                logger.error("CalDAV auth failed: 401")
                return False
            
            if response.status_code not in (200, 207):
                logger.error(f"CalDAV unexpected status: {response.status_code}")
                return False
            
            # Parse Principal URL und finde Calendar Home
            self.calendar_home_url = self._discover_calendar_home(response)
            
            if self.calendar_home_url:
                logger.info(f"CalDAV calendar home: {self.calendar_home_url}")
                return True
            
            return False
            
        except requests.RequestException as e:
            logger.error(f"CalDAV connection error: {e}")
            return False
    
    def _discover_calendar_home(self, initial_response) -> Optional[str]:
        """Findet Calendar Home URL."""
        try:
            root = ET.fromstring(initial_response.text)
            
            # Finde current-user-principal
            principal = root.find('.//{DAV:}current-user-principal/{DAV:}href')
            if principal is not None and principal.text:
                principal_url = principal.text
                if not principal_url.startswith('http'):
                    principal_url = self.CALDAV_URL + principal_url
                
                logger.info(f"Found principal: {principal_url}")
                
                # Hole calendar-home-set
                propfind_body = '''<?xml version="1.0" encoding="UTF-8"?>
<d:propfind xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav">
  <d:prop>
    <cal:calendar-home-set/>
  </d:prop>
</d:propfind>'''
                
                r = self.session.request(
                    'PROPFIND',
                    principal_url,
                    data=propfind_body,
                    headers={'Content-Type': 'application/xml; charset=utf-8', 'Depth': '0'},
                    timeout=15
                )
                
                if r.status_code in (200, 207):
                    root2 = ET.fromstring(r.text)
                    home = root2.find('.//{urn:ietf:params:xml:ns:caldav}calendar-home-set/{DAV:}href')
                    if home is not None and home.text:
                        home_url = home.text
                        if not home_url.startswith('http'):
                            home_url = self.CALDAV_URL.rstrip('/') + home_url
                        return home_url
                        
        except ET.ParseError as e:
            logger.error(f"XML parse error: {e}")
        except Exception as e:
            logger.error(f"Discovery error: {e}")
        
        return None
    
    def list_calendars(self) -> List[Calendar]:
        """
        Listet alle Kalender.
        
        Returns:
            Liste von Calendar Objekten
        """
        if not self.session or not self.calendar_home_url:
            raise RuntimeError("Not authenticated")
        
        propfind_body = '''<?xml version="1.0" encoding="UTF-8"?>
<d:propfind xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav" xmlns:cs="http://calendarserver.org/ns/" xmlns:apple="http://apple.com/ns/ical/">
  <d:prop>
    <d:resourcetype/>
    <d:displayname/>
    <apple:calendar-color/>
    <cs:getctag/>
  </d:prop>
</d:propfind>'''
        
        response = self.session.request(
            'PROPFIND',
            self.calendar_home_url,
            data=propfind_body,
            headers={'Content-Type': 'application/xml; charset=utf-8', 'Depth': '1'},
            timeout=30
        )
        
        if response.status_code != 207:
            logger.error(f"Failed to list calendars: {response.status_code}")
            return []
        
        calendars = []
        try:
            root = ET.fromstring(response.text)
            
            for resp in root.findall('.//{DAV:}response'):
                resourcetype = resp.find('.//{DAV:}resourcetype')
                if resourcetype is not None:
                    if resourcetype.find('.//{urn:ietf:params:xml:ns:caldav}calendar') is not None:
                        href = resp.find('.//{DAV:}href')
                        displayname = resp.find('.//{DAV:}displayname')
                        color = resp.find('.//{http://apple.com/ns/ical/}calendar-color')
                        ctag = resp.find('.//{http://calendarserver.org/ns/}getctag')
                        
                        if href is not None:
                            # UID aus URL extrahieren
                            uid = href.text.rstrip('/').split('/')[-1]
                            name = displayname.text if displayname is not None else uid
                            
                            cal = Calendar(
                                uid=uid,
                                name=name,
                                color=color.text if color is not None else None,
                                ctag=ctag.text if ctag is not None else None
                            )
                            cal.url = self.CALDAV_URL + href.text if not href.text.startswith('http') else href.text
                            calendars.append(cal)
                            
        except ET.ParseError as e:
            logger.error(f"XML parse error: {e}")
        
        return calendars
    
    def pull_events(self, calendar: Calendar, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[CalendarEvent]:
        """
        Holt alle Events aus einem Kalender.
        
        Args:
            calendar: Calendar Objekt
            start_date: Optional Start-Datum (YYYYMMDD)
            end_date: Optional End-Datum (YYYYMMDD)
            
        Returns:
            Liste von CalendarEvent Objekten
        """
        if not self.session:
            raise RuntimeError("Not authenticated")
        
        # Time-Range Filter wenn Daten angegeben
        time_range = ""
        if start_date and end_date:
            time_range = f'''<cal:time-range start="{start_date}T000000Z" end="{end_date}T235959Z"/>'''
        
        report_body = f'''<?xml version="1.0" encoding="UTF-8"?>
<cal:calendar-query xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav">
  <d:prop>
    <d:getetag/>
    <cal:calendar-data/>
  </d:prop>
  <cal:filter>
    <cal:comp-filter name="VCALENDAR">
      <cal:comp-filter name="VEVENT">
        {time_range}
      </cal:comp-filter>
    </cal:comp-filter>
  </cal:filter>
</cal:calendar-query>'''
        
        response = self.session.request(
            'REPORT',
            calendar.url,
            data=report_body,
            headers={'Content-Type': 'application/xml; charset=utf-8', 'Depth': '1'},
            timeout=60
        )
        
        if response.status_code != 207:
            logger.error(f"Failed to fetch events: {response.status_code}")
            return []
        
        events = []
        try:
            root = ET.fromstring(response.text)
            
            for resp in root.findall('.//{DAV:}response'):
                cal_data = resp.find('.//{urn:ietf:params:xml:ns:caldav}calendar-data')
                etag = resp.find('.//{DAV:}getetag')
                
                if cal_data is not None and cal_data.text:
                    parsed = self.parser.parse(cal_data.text)
                    for event in parsed:
                        if etag is not None:
                            event.etag = etag.text.strip('"')
                        events.append(event)
                        
        except ET.ParseError as e:
            logger.error(f"XML parse error: {e}")
        
        return events
    
    def push_event(self, calendar: Calendar, event: CalendarEvent) -> Optional[str]:
        """
        Erstellt oder aktualisiert ein Event.
        
        Args:
            calendar: Ziel-Kalender
            event: Event zum Speichern
            
        Returns:
            UID des Events bei Erfolg
        """
        if not self.session:
            raise RuntimeError("Not authenticated")
        
        import uuid
        
        # UID generieren wenn nicht vorhanden
        if not event.icloud_uid:
            event.icloud_uid = str(uuid.uuid4())
        
        ics = self.parser.serialize(event)
        url = f"{calendar.url}{event.icloud_uid}.ics"
        
        response = self.session.request(
            'PUT',
            url,
            data=ics,
            headers={'Content-Type': 'text/calendar; charset=utf-8'},
            timeout=15
        )
        
        if response.status_code in (201, 204):
            return event.icloud_uid
        
        logger.error(f"Failed to push event: {response.status_code}")
        return None
    
    def delete_event(self, calendar: Calendar, event_uid: str) -> bool:
        """
        Loescht ein Event.
        
        Args:
            calendar: Kalender des Events
            event_uid: UID des Events
            
        Returns:
            True bei Erfolg
        """
        if not self.session:
            raise RuntimeError("Not authenticated")
        
        url = f"{calendar.url}{event_uid}.ics"
        response = self.session.request('DELETE', url, timeout=15)
        
        return response.status_code in (200, 204)
