"""
TextPreprocessor - Deterministische Vorverarbeitung fuer Agents.

Verschiebt regelbasierte Logik aus LLM-Prompts in Python-Code:
- Datums-Berechnung (morgen, naechste Woche, etc.)
- Uhrzeit-Erkennung (abends, morgens, etc.)
- Priority-Mapping (dringend -> 1, normal -> 2, niedrig -> 3)
- Status-Mapping (erledigt -> done, wartend -> waiting, etc.)
"""

import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum


class Priority(Enum):
    HIGH = 1
    MEDIUM = 2
    LOW = 3


@dataclass
class DateResult:
    """Ergebnis einer Datums-Aufloesung."""
    date: str  # YYYY-MM-DD
    original: str  # Originaler Text
    confidence: float  # 0-1


@dataclass
class TimeResult:
    """Ergebnis einer Uhrzeit-Aufloesung."""
    time: str  # HH:MM
    original: str
    confidence: float


@dataclass
class PreprocessResult:
    """Ergebnis der Vorverarbeitung."""
    text: str
    resolved_date: Optional[str]
    resolved_time: Optional[str]
    priority: int
    status: str
    detected_patterns: Dict[str, str]


class TextPreprocessor:
    """Preprocessor fuer deterministische Text-Transformationen."""
    
    # === Datums-Patterns ===
    DATE_PATTERNS: List[Tuple[str, str, int]] = [
        (r"\bheute\b", "relative", 0),
        (r"\bmorgen\b", "relative", 1),
        (r"\bübermorgen\b", "relative", 2),
        (r"\bnächste woche\b", "relative", 7),
        (r"\bin einer woche\b", "relative", 7),
        (r"\bnächsten montag\b", "weekday", 0),
        (r"\bnächsten dienstag\b", "weekday", 1),
        (r"\bnächsten mittwoch\b", "weekday", 2),
        (r"\bnächsten donnerstag\b", "weekday", 3),
        (r"\bnächsten freitag\b", "weekday", 4),
        (r"\bnächsten samstag\b", "weekday", 5),
        (r"\bnächsten sonntag\b", "weekday", 6),
        (r"\bsamstag\b", "weekday", 5),
        (r"\bsonntag\b", "weekday", 6),
        (r"\bmontag\b", "weekday", 0),
        (r"\bdienstag\b", "weekday", 1),
        (r"\bmittwoch\b", "weekday", 2),
        (r"\bdonnerstag\b", "weekday", 3),
        (r"\bfreitag\b", "weekday", 4),
        (r"\bende der woche\b", "end_of_week", 0),
        (r"\bende des monats\b", "end_of_month", 0),
    ]
    
    # Dynamic patterns (with capture groups)
    DYNAMIC_DATE_PATTERNS = [
        (r"\bin (\d+) tagen?\b", "offset_days"),
        (r"\bin (\d+) wochen?\b", "offset_weeks"),
    ]
    
    # === Uhrzeit-Patterns ===
    TIME_PATTERNS: List[Tuple[str, str]] = [
        (r"\bmorgens\b", "08:00"),
        (r"\bvormittags?\b", "10:00"),
        (r"\bmittags?\b", "12:00"),
        (r"\bnachmittags?\b", "15:00"),
        (r"\babends?\b", "18:00"),
        (r"\bnachts?\b", "22:00"),
        (r"\bfrueh\b", "07:00"),
        (r"\bspaet\b", "20:00"),
    ]
    
    # Explizite Uhrzeiten
    EXPLICIT_TIME_PATTERNS = [
        (r"(\d{1,2}):(\d{2})\s*(?:uhr)?", "hhmm"),
        (r"(\d{1,2})\s*uhr", "hh"),
        (r"um\s+(\d{1,2}):(\d{2})", "hhmm"),
        (r"um\s+(\d{1,2})\s*uhr", "hh"),
    ]
    
    # === Priority-Keywords ===
    PRIORITY_HIGH = ["dringend", "asap", "sofort", "wichtig", "urgent", "kritisch", "eilig"]
    PRIORITY_LOW = ["irgendwann", "wenn zeit", "niedrig", "low", "unwichtig", "someday"]
    
    # === Status-Keywords pro Kategorie ===
    STATUS_KEYWORDS: Dict[str, Dict[str, List[str]]] = {
        "tasks": {
            "next": ["als nächstes", "jetzt", "sofort anfangen", "next"],
            "waiting": ["warte auf", "wartend", "blocked", "blockiert"],
            "someday": ["irgendwann", "someday", "vielleicht", "maybe"],
            "done": ["erledigt", "done", "fertig", "abgeschlossen"],
        },
        "ideas": {
            "done": ["umgesetzt", "erledigt", "done"],
        },
        "projects": {
            "on_hold": ["pausiert", "on hold", "pause"],
            "completed": ["abgeschlossen", "fertig", "completed"],
            "cancelled": ["abgebrochen", "cancelled", "storniert"],
        },
    }
    
    # Default status per category
    DEFAULT_STATUS = {
        "tasks": "inbox",
        "ideas": "inbox",
        "projects": "active",
        "people": None,
        "calendar_events": None,
    }
    
    def __init__(self, reference_date: datetime = None):
        """
        Initialisiert Preprocessor.
        
        Args:
            reference_date: Referenzdatum fuer relative Berechnungen (default: heute)
        """
        self.reference_date = reference_date or datetime.now()
    
    def resolve_date(self, text: str) -> Optional[DateResult]:
        """Loest relative Datumsangaben auf."""
        text_lower = text.lower()
        
        # Static patterns
        for pattern, date_type, value in self.DATE_PATTERNS:
            match = re.search(pattern, text_lower)
            if not match:
                continue
            
            resolved_date = None
            
            if date_type == "relative":
                resolved_date = self.reference_date + timedelta(days=value)
                
            elif date_type == "weekday":
                current_weekday = self.reference_date.weekday()
                days_ahead = value - current_weekday
                if days_ahead <= 0:
                    days_ahead += 7
                resolved_date = self.reference_date + timedelta(days=days_ahead)
                
            elif date_type == "end_of_week":
                days_ahead = 4 - self.reference_date.weekday()
                if days_ahead < 0:
                    days_ahead += 7
                resolved_date = self.reference_date + timedelta(days=days_ahead)
                
            elif date_type == "end_of_month":
                next_month = self.reference_date.replace(day=28) + timedelta(days=4)
                resolved_date = next_month - timedelta(days=next_month.day)
            
            if resolved_date:
                return DateResult(
                    date=resolved_date.strftime("%Y-%m-%d"),
                    original=match.group(0),
                    confidence=1.0
                )
        
        # Dynamic patterns
        for pattern, date_type in self.DYNAMIC_DATE_PATTERNS:
            match = re.search(pattern, text_lower)
            if match:
                value = int(match.group(1))
                if date_type == "offset_days":
                    resolved_date = self.reference_date + timedelta(days=value)
                elif date_type == "offset_weeks":
                    resolved_date = self.reference_date + timedelta(weeks=value)
                
                return DateResult(
                    date=resolved_date.strftime("%Y-%m-%d"),
                    original=match.group(0),
                    confidence=1.0
                )
        
        # Explicit dates (DD.MM.YYYY or YYYY-MM-DD)
        explicit_patterns = [
            (r"(\d{1,2})\.(\d{1,2})\.(\d{4})", "dmy"),
            (r"(\d{4})-(\d{1,2})-(\d{1,2})", "ymd"),
        ]
        
        for pattern, format_type in explicit_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    if format_type == "dmy":
                        d, m, y = match.groups()
                        resolved_date = datetime(int(y), int(m), int(d))
                    else:
                        y, m, d = match.groups()
                        resolved_date = datetime(int(y), int(m), int(d))
                    
                    return DateResult(
                        date=resolved_date.strftime("%Y-%m-%d"),
                        original=match.group(0),
                        confidence=1.0
                    )
                except ValueError:
                    pass  # Invalid date
        
        return None
    
    def resolve_time(self, text: str) -> Optional[TimeResult]:
        """
        Loest Uhrzeiten aus Text.
        
        Args:
            text: Text mit potentieller Zeitangabe
            
        Returns:
            TimeResult oder None
        """
        text_lower = text.lower()
        
        # Explizite Uhrzeiten zuerst (hoehere Prioritaet)
        for pattern, time_type in self.EXPLICIT_TIME_PATTERNS:
            match = re.search(pattern, text_lower)
            if match:
                if time_type == "hhmm":
                    h, m = int(match.group(1)), int(match.group(2))
                else:
                    h, m = int(match.group(1)), 0
                
                if 0 <= h <= 23 and 0 <= m <= 59:
                    return TimeResult(
                        time=f"{h:02d}:{m:02d}",
                        original=match.group(0),
                        confidence=1.0
                    )
        
        # Relative Zeitangaben
        for pattern, time_str in self.TIME_PATTERNS:
            if re.search(pattern, text_lower):
                return TimeResult(
                    time=time_str,
                    original=pattern.strip("\\b"),
                    confidence=0.8
                )
        
        return None
    
    def resolve_priority(self, text: str) -> int:
        """Erkennt Priority aus Text."""
        text_lower = text.lower()
        
        for keyword in self.PRIORITY_HIGH:
            if keyword in text_lower:
                return Priority.HIGH.value
        
        for keyword in self.PRIORITY_LOW:
            if keyword in text_lower:
                return Priority.LOW.value
        
        return Priority.MEDIUM.value
    
    def resolve_status(self, text: str, category: str) -> str:
        """Erkennt Status aus Text basierend auf Kategorie."""
        text_lower = text.lower()
        
        if category not in self.STATUS_KEYWORDS:
            return self.DEFAULT_STATUS.get(category, "inbox") or "inbox"
        
        status_map = self.STATUS_KEYWORDS[category]
        
        for status, keywords in status_map.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return status
        
        return self.DEFAULT_STATUS.get(category, "inbox") or "inbox"
    
    def preprocess(self, text: str, category: str = "tasks") -> PreprocessResult:
        """Fuehrt komplette Vorverarbeitung durch."""
        detected = {}
        
        # Datum aufloesen
        date_result = self.resolve_date(text)
        resolved_date = None
        if date_result:
            resolved_date = date_result.date
            detected["date"] = f"{date_result.original} -> {date_result.date}"
        
        # Uhrzeit aufloesen
        time_result = self.resolve_time(text)
        resolved_time = None
        if time_result:
            resolved_time = time_result.time
            detected["time"] = f"{time_result.original} -> {time_result.time}"
        
        # Priority erkennen
        priority = self.resolve_priority(text)
        if priority != 2:
            detected["priority"] = str(priority)
        
        # Status erkennen
        status = self.resolve_status(text, category)
        if status not in ["inbox", "active"]:
            detected["status"] = status
        
        return PreprocessResult(
            text=text,
            resolved_date=resolved_date,
            resolved_time=resolved_time,
            priority=priority,
            status=status,
            detected_patterns=detected
        )
    
    def get_context_for_prompt(self, text: str, category: str = "tasks") -> Dict[str, Any]:
        """
        Erzeugt Kontext-Dict fuer LLM-Prompt.
        
        Args:
            text: Eingabetext
            category: Ziel-Kategorie
            
        Returns:
            Dict mit vorverarbeiteten Werten
        """
        result = self.preprocess(text, category)
        
        # Fuer calendar_events: start_time zusammenbauen
        resolved_start_time = None
        if category == "calendar_events" and result.resolved_date:
            time_part = result.resolved_time or "12:00"  # Default Mittag
            resolved_start_time = f"{result.resolved_date}T{time_part}:00"
        
        return {
            "text": text,
            "current_date": self.reference_date.strftime("%Y-%m-%d"),
            "resolved_due_date": result.resolved_date,
            "resolved_time": result.resolved_time,
            "resolved_start_time": resolved_start_time,
            "resolved_priority": result.priority,
            "resolved_status": result.status,
            "preprocessing_hints": result.detected_patterns,
        }


# === Factory-Funktion ===
_preprocessor_instance: Optional[TextPreprocessor] = None


def get_text_preprocessor(reference_date: datetime = None) -> TextPreprocessor:
    """Gibt TextPreprocessor-Instanz zurueck."""
    global _preprocessor_instance
    
    if _preprocessor_instance is None or reference_date:
        _preprocessor_instance = TextPreprocessor(reference_date)
    
    return _preprocessor_instance
