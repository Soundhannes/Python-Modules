"""
InputCollector - Strukturierte Daten-Eingabe für Automationen.

Ermöglicht:
- Formular-Definitionen mit Feldern
- Validierung der Eingaben
- Timeout und Default-Werte
"""

import sys
import json
import time
from typing import Optional, Any, Dict, List
from dataclasses import dataclass, field
from datetime import datetime

sys.path.insert(0, "/opt/python-modules")
from llm.infrastructure.database import get_database


@dataclass
class FormField:
    name: str
    label: str
    field_type: str = "text"  # text, number, email, choice, boolean
    required: bool = False
    default: Any = None
    choices: List[str] = None
    min_value: Any = None
    max_value: Any = None


@dataclass
class FormSubmission:
    id: int
    automation: str
    form_name: str
    fields: List[Dict]
    status: str
    data: Optional[Dict[str, Any]]
    created_at: datetime
    submitted_at: Optional[datetime]


class InputCollector:
    """
    Sammelt strukturierte Eingaben über Formulare.
    
    Verwendung:
        collector = InputCollector('my_automation')
        
        # Formular definieren
        fields = [
            FormField('name', 'Name', required=True),
            FormField('age', 'Alter', field_type='number', min_value=0),
            FormField('role', 'Rolle', field_type='choice', choices=['admin', 'user']),
        ]
        
        # Eingabe anfordern
        data = collector.collect('user_form', fields, timeout=300)
    """
    
    TABLE_NAME = "input_forms"
    
    def __init__(self, automation: str = "default"):
        self.automation = automation
        self._db = get_database()
        self._ensure_table()
    
    def _ensure_table(self):
        with self._db.get_cursor() as cursor:
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                    id SERIAL PRIMARY KEY,
                    automation VARCHAR(100) NOT NULL,
                    form_name VARCHAR(100) NOT NULL,
                    fields JSONB NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending',
                    data JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    submitted_at TIMESTAMP
                )
            """)
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.TABLE_NAME}_status
                ON {self.TABLE_NAME}(automation, status)
            """)
            self._db.commit()
    
    def _fields_to_dict(self, fields: List[FormField]) -> List[Dict]:
        return [
            {
                'name': f.name,
                'label': f.label,
                'field_type': f.field_type,
                'required': f.required,
                'default': f.default,
                'choices': f.choices,
                'min_value': f.min_value,
                'max_value': f.max_value,
            }
            for f in fields
        ]
    
    def _validate_data(self, data: Dict[str, Any], fields: List[Dict]) -> tuple:
        """Validiert Eingabedaten gegen Feld-Definition."""
        errors = []
        validated = {}
        
        for field in fields:
            name = field['name']
            value = data.get(name)
            
            # Required
            if field.get('required') and value is None:
                if field.get('default') is not None:
                    value = field['default']
                else:
                    errors.append(f"{field['label']}: Pflichtfeld")
                    continue
            
            if value is None:
                if field.get('default') is not None:
                    validated[name] = field['default']
                continue
            
            # Type validation
            field_type = field.get('field_type', 'text')
            
            if field_type == 'number':
                try:
                    value = float(value) if '.' in str(value) else int(value)
                except (ValueError, TypeError):
                    errors.append(f"{field['label']}: Muss eine Zahl sein")
                    continue
                
                if field.get('min_value') is not None and value < field['min_value']:
                    errors.append(f"{field['label']}: Minimum ist {field['min_value']}")
                    continue
                if field.get('max_value') is not None and value > field['max_value']:
                    errors.append(f"{field['label']}: Maximum ist {field['max_value']}")
                    continue
            
            elif field_type == 'boolean':
                if isinstance(value, str):
                    value = value.lower() in ('true', '1', 'yes', 'ja')
                else:
                    value = bool(value)
            
            elif field_type in ('choice', 'select'):
                if field.get('choices') and value not in field['choices']:
                    errors.append(f"{field['label']}: Ungültige Auswahl")
                    continue
            
            elif field_type == 'email':
                if '@' not in str(value):
                    errors.append(f"{field['label']}: Ungültige E-Mail")
                    continue
            
            validated[name] = value
        
        return validated, errors
    
    # === Collect-Methoden ===
    
    def create_form(self, form_name: str, fields: List[FormField]) -> int:
        """Erstellt ein neues Formular."""
        fields_json = json.dumps(self._fields_to_dict(fields))
        
        with self._db.get_cursor() as cursor:
            cursor.execute(f"""
                INSERT INTO {self.TABLE_NAME} (automation, form_name, fields)
                VALUES (%s, %s, %s::jsonb)
                RETURNING id
            """, (self.automation, form_name, fields_json))
            form_id = cursor.fetchone()["id"]
            self._db.commit()
            return form_id
    
    def collect(self, form_name: str, fields: List[FormField], timeout: int = 300) -> Optional[Dict[str, Any]]:
        """
        Erstellt Formular und wartet auf Eingabe.
        
        Returns:
            Eingabedaten oder None bei Timeout
        """
        form_id = self.create_form(form_name, fields)
        return self.wait_for_submission(form_id, timeout)
    
    def wait_for_submission(self, form_id: int, timeout: int = 300, poll_interval: int = 2) -> Optional[Dict[str, Any]]:
        """Wartet auf Formular-Eingabe."""
        start = time.time()
        
        while time.time() - start < timeout:
            with self._db.get_cursor() as cursor:
                cursor.execute(f"""
                    SELECT * FROM {self.TABLE_NAME} WHERE id = %s
                """, (form_id,))
                row = cursor.fetchone()
                
                if row and row["status"] == "submitted":
                    data = row["data"]
                    return data if isinstance(data, dict) else json.loads(data) if data else None
            
            time.sleep(poll_interval)
        
        # Timeout
        with self._db.get_cursor() as cursor:
            cursor.execute(f"UPDATE {self.TABLE_NAME} SET status = 'timeout' WHERE id = %s", (form_id,))
            self._db.commit()
        
        return None
    
    # === Submit-Methoden (für API/UI) ===
    
    def get_pending_forms(self) -> List[FormSubmission]:
        """Holt alle offenen Formulare."""
        with self._db.get_cursor() as cursor:
            cursor.execute(f"""
                SELECT * FROM {self.TABLE_NAME}
                WHERE automation = %s AND status = 'pending'
                ORDER BY created_at
            """, (self.automation,))
            
            return [
                FormSubmission(
                    id=row["id"],
                    automation=row["automation"],
                    form_name=row["form_name"],
                    fields=row["fields"] if isinstance(row["fields"], list) else json.loads(row["fields"]),
                    status=row["status"],
                    data=row["data"] if isinstance(row["data"], dict) else json.loads(row["data"]) if row["data"] else None,
                    created_at=row["created_at"],
                    submitted_at=row["submitted_at"]
                )
                for row in cursor.fetchall()
            ]
    
    def submit(self, form_id: int, data: Dict[str, Any]) -> tuple:
        """
        Sendet Formulardaten.
        
        Returns:
            (success, errors)
        """
        # Formular holen
        with self._db.get_cursor() as cursor:
            cursor.execute(f"SELECT fields FROM {self.TABLE_NAME} WHERE id = %s", (form_id,))
            row = cursor.fetchone()
            
            if not row:
                return False, ["Formular nicht gefunden"]
            
            fields = row["fields"] if isinstance(row["fields"], list) else json.loads(row["fields"])
        
        # Validieren
        validated, errors = self._validate_data(data, fields)
        
        if errors:
            return False, errors
        
        # Speichern
        with self._db.get_cursor() as cursor:
            cursor.execute(f"""
                UPDATE {self.TABLE_NAME}
                SET status = 'submitted', data = %s::jsonb, submitted_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (json.dumps(validated), form_id))
            self._db.commit()
        
        return True, []


def get_input_collector(automation: str = "default") -> InputCollector:
    return InputCollector(automation)
