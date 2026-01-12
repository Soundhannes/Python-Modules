"""
vCard Parser fuer bidirektionale CardDAV-Synchronisation.

Konvertiert zwischen vCard 3.0 Format und Contact Dataclass.
"""
import re
from typing import Optional, List, Dict
from .providers.base import Contact


class VCardParser:
    """Parser fuer vCard 3.0 Format."""
    
    def parse(self, vcard_string: str) -> Contact:
        """
        Parsed vCard String zu Contact Objekt.
        
        Args:
            vcard_string: vCard im String-Format
            
        Returns:
            Contact Objekt mit extrahierten Daten
            
        Raises:
            ValueError: Bei ungueltigem vCard Format
        """
        if not vcard_string or "BEGIN:VCARD" not in vcard_string:
            raise ValueError("Invalid vCard format")
        
        # Daten extrahieren
        data = {
            "first_name": "",
            "middle_name": None,
            "last_name": "",
            "phone": None,
            "email": None,
            "street": None,
            "house_nr": None,
            "zip": None,
            "city": None,
            "country": None,
            "important_dates": [],
        }
        
        lines = vcard_string.strip().split("\n")
        
        for line in lines:
            line = line.strip()
            
            # N: Nachname;Vorname;2.Vorname;Prefix;Suffix
            if line.startswith("N:") or line.startswith("N;"):
                self._parse_name(line, data)
            
            # TEL: Telefonnummer (nur erste)
            elif 'TEL:' in line or 'TEL;' in line and not data["phone"]:
                data["phone"] = self._extract_value(line)
            
            # EMAIL: E-Mail Adresse (nur erste)
            elif 'EMAIL:' in line or 'EMAIL;' in line and not data["email"]:
                data["email"] = self._extract_value(line)
            
            # ADR: ;;Strasse;Stadt;;PLZ;Land
            elif 'ADR:' in line or 'ADR;' in line:
                self._parse_address(line, data)
            
            # BDAY: Geburtstag
            elif line.startswith('BDAY:') or line.startswith('BDAY;'):
                bday = self._extract_value(line)
                if bday:
                    data["important_dates"].append({
                        "type": "birthday",
                        "date": bday
                    })
            
            # ANNIVERSARY: Jahrestag
            elif line.startswith("ANNIVERSARY:"):
                anniversary = self._extract_value(line)
                if anniversary:
                    data["important_dates"].append({
                        "type": "anniversary",
                        "date": anniversary
                    })
        
        return Contact(**data)
    
    def _parse_name(self, line: str, data: dict) -> None:
        """Parsed N: Zeile in Name-Komponenten."""
        value = self._extract_value(line)
        parts = value.split(";")
        
        if len(parts) >= 2:
            data["last_name"] = parts[0] or ""
            data["first_name"] = parts[1] or ""
        if len(parts) >= 3 and parts[2]:
            data["middle_name"] = parts[2]
    
    def _parse_address(self, line: str, data: dict) -> None:
        """Parsed ADR: Zeile in Adress-Komponenten."""
        value = self._extract_value(line)
        parts = value.split(";")
        
        # ADR Format: PO Box;Extended;Street;City;Region;PostalCode;Country
        if len(parts) >= 3 and parts[2]:
            street_parts = parts[2].rsplit(" ", 1)
            if len(street_parts) == 2 and street_parts[1].isdigit():
                data["street"] = street_parts[0]
                data["house_nr"] = street_parts[1]
            else:
                # Hausnummer am Ende mit Buchstabe
                match = re.match(r"(.+?)\s+(\d+\w*)$", parts[2])
                if match:
                    data["street"] = match.group(1)
                    data["house_nr"] = match.group(2)
                else:
                    data["street"] = parts[2]
        
        if len(parts) >= 4 and parts[3]:
            data["city"] = parts[3]
        if len(parts) >= 6 and parts[5]:
            data["zip"] = parts[5]
        if len(parts) >= 7 and parts[6]:
            data["country"] = parts[6]
    
    def _extract_value(self, line: str) -> str:
        """Extrahiert Wert nach dem Doppelpunkt."""
        if ":" in line:
            return line.split(":", 1)[1].strip()
        return ""
    
    def serialize(self, contact: Contact, provider: Optional[str] = None) -> str:
        """
        Serialisiert Contact zu vCard 3.0 String.
        
        Args:
            contact: Contact Objekt
            provider: Optional Provider-Name fuer UID-Auswahl
            
        Returns:
            vCard String
        """
        lines = [
            "BEGIN:VCARD",
            "VERSION:3.0",
            f"FN:{contact.full_name}",
            f"N:{contact.last_name};{contact.first_name};{contact.middle_name or ''};;",
        ]
        
        # Telefon
        if contact.phone:
            lines.append(f"TEL;TYPE=CELL:{contact.phone}")
        
        # Email
        if contact.email:
            lines.append(f"EMAIL;TYPE=HOME:{contact.email}")
        
        # Adresse
        if any([contact.street, contact.city, contact.zip, contact.country]):
            street_full = f"{contact.street or ''} {contact.house_nr or ''}".strip()
            lines.append(
                f"ADR;TYPE=HOME:;;{street_full};{contact.city or ''};;{contact.zip or ''};{contact.country or ''}"
            )
        
        # Wichtige Daten
        for date_entry in contact.important_dates:
            if date_entry.get("type") == "birthday":
                lines.append(f"BDAY:{date_entry.get('date', '')}")
            elif date_entry.get("type") == "anniversary":
                lines.append(f"ANNIVERSARY:{date_entry.get('date', '')}")
        
        # UID basierend auf Provider
        uid = None
        if provider == "icloud":
            uid = contact.icloud_uid
        elif provider == "google":
            uid = contact.google_uid
        elif provider == "nextcloud":
            uid = contact.nextcloud_uid
        
        if uid:
            lines.append(f"UID:{uid}")
        
        lines.append("END:VCARD")
        
        return "\n".join(lines)
