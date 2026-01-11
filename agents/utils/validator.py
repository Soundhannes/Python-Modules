"""
Validator - Datenvalidierung für Agent-Automationen.

Bietet:
- Schema-Validierung (required fields, types)
- Typ-Prüfungen
- Custom-Validatoren
"""

from typing import Any, Dict, List, Optional, Callable, Union
from dataclasses import dataclass


@dataclass
class ValidationResult:
    valid: bool
    errors: List[str]
    data: Any  # Validierte/transformierte Daten


class Validator:
    """
    Daten-Validator mit Schema-Unterstützung.
    
    Verwendung:
        validator = Validator()
        
        # Einfache Prüfung
        result = validator.validate(data, {
            'name': {'type': str, 'required': True},
            'age': {'type': int, 'min': 0, 'max': 150},
            'email': {'type': str, 'pattern': r'.*@.*'},
        })
        
        if result.valid:
            print(result.data)
        else:
            print(result.errors)
    """
    
    def __init__(self):
        self._custom_validators: Dict[str, Callable] = {}
    
    def register_validator(self, name: str, func: Callable[[Any], bool]):
        """Registriert einen Custom-Validator."""
        self._custom_validators[name] = func
    
    def validate(self, data: Dict[str, Any], schema: Dict[str, Dict]) -> ValidationResult:
        """
        Validiert Daten gegen ein Schema.
        
        Schema-Optionen pro Feld:
            type: Erwarteter Typ (str, int, float, bool, list, dict)
            required: Pflichtfeld (default: False)
            default: Standardwert wenn nicht vorhanden
            min: Minimum (für int/float) oder Mindestlänge (für str/list)
            max: Maximum (für int/float) oder Maximallänge (für str/list)
            pattern: Regex-Pattern (für str)
            choices: Erlaubte Werte
            validator: Name eines Custom-Validators
        """
        errors = []
        validated_data = {}
        
        for field, rules in schema.items():
            value = data.get(field)
            
            # Required Check
            if rules.get('required', False) and value is None:
                if 'default' in rules:
                    value = rules['default']
                else:
                    errors.append(f"{field}: Pflichtfeld fehlt")
                    continue
            
            # Default setzen
            if value is None and 'default' in rules:
                value = rules['default']
            
            if value is None:
                continue
            
            # Type Check
            expected_type = rules.get('type')
            if expected_type and not isinstance(value, expected_type):
                # Versuche Konvertierung
                try:
                    if expected_type == int:
                        value = int(value)
                    elif expected_type == float:
                        value = float(value)
                    elif expected_type == str:
                        value = str(value)
                    elif expected_type == bool:
                        value = bool(value)
                    else:
                        errors.append(f"{field}: Erwartet {expected_type.__name__}, bekommen {type(value).__name__}")
                        continue
                except (ValueError, TypeError):
                    errors.append(f"{field}: Kann nicht zu {expected_type.__name__} konvertiert werden")
                    continue
            
            # Min/Max für Zahlen
            if isinstance(value, (int, float)):
                if 'min' in rules and value < rules['min']:
                    errors.append(f"{field}: Wert {value} ist kleiner als Minimum {rules['min']}")
                    continue
                if 'max' in rules and value > rules['max']:
                    errors.append(f"{field}: Wert {value} ist größer als Maximum {rules['max']}")
                    continue
            
            # Min/Max für Strings/Listen (Länge)
            if isinstance(value, (str, list)):
                if 'min' in rules and len(value) < rules['min']:
                    errors.append(f"{field}: Länge {len(value)} ist kleiner als Minimum {rules['min']}")
                    continue
                if 'max' in rules and len(value) > rules['max']:
                    errors.append(f"{field}: Länge {len(value)} ist größer als Maximum {rules['max']}")
                    continue
            
            # Pattern für Strings
            if isinstance(value, str) and 'pattern' in rules:
                import re
                if not re.match(rules['pattern'], value):
                    errors.append(f"{field}: Wert entspricht nicht dem Pattern {rules['pattern']}")
                    continue
            
            # Choices
            if 'choices' in rules and value not in rules['choices']:
                errors.append(f"{field}: Wert {value} nicht in erlaubten Werten {rules['choices']}")
                continue
            
            # Custom Validator
            if 'validator' in rules:
                validator_name = rules['validator']
                if validator_name in self._custom_validators:
                    if not self._custom_validators[validator_name](value):
                        errors.append(f"{field}: Custom-Validierung '{validator_name}' fehlgeschlagen")
                        continue
            
            validated_data[field] = value
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            data=validated_data
        )
    
    # === Convenience-Methoden ===
    
    def is_valid(self, data: Dict[str, Any], schema: Dict[str, Dict]) -> bool:
        """Schnelle Prüfung ob Daten valide sind."""
        return self.validate(data, schema).valid
    
    def validate_type(self, value: Any, expected_type: type) -> bool:
        """Prüft ob Wert vom erwarteten Typ ist."""
        return isinstance(value, expected_type)
    
    def validate_not_empty(self, value: Any) -> bool:
        """Prüft ob Wert nicht leer ist."""
        if value is None:
            return False
        if isinstance(value, (str, list, dict)):
            return len(value) > 0
        return True
    
    def validate_email(self, value: str) -> bool:
        """Einfache E-Mail-Validierung."""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, value))
    
    def validate_url(self, value: str) -> bool:
        """Einfache URL-Validierung."""
        import re
        pattern = r'^https?://[^\s]+$'
        return bool(re.match(pattern, value))


def get_validator() -> Validator:
    return Validator()
