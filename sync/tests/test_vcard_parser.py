"""
TDD Tests fuer vCard Parser.

Test-First: Diese Tests definieren das erwartete Verhalten.
"""
import pytest
from datetime import date
from sync.providers.base import Contact
from sync.vcard_parser import VCardParser


class TestVCardToContact:
    """Tests fuer vCard String -> Contact Konvertierung."""

    def test_parse_minimal_vcard(self):
        """Minimale vCard mit nur Namen."""
        vcard = """BEGIN:VCARD
VERSION:3.0
FN:Max Mustermann
N:Mustermann;Max;;;
END:VCARD"""
        
        parser = VCardParser()
        contact = parser.parse(vcard)
        
        assert contact.first_name == "Max"
        assert contact.last_name == "Mustermann"

    def test_parse_full_vcard(self):
        """Vollstaendige vCard mit allen Feldern."""
        vcard = """BEGIN:VCARD
VERSION:3.0
FN:Dr. Max Peter Mustermann
N:Mustermann;Max;Peter;;Dr.
TEL;TYPE=CELL:+49 171 1234567
EMAIL;TYPE=HOME:max@example.de
ADR;TYPE=HOME:;;Musterstrasse 42;Duesseldorf;;40210;Germany
BDAY:1990-05-15
UID:abc-123-def
END:VCARD"""
        
        parser = VCardParser()
        contact = parser.parse(vcard)
        
        assert contact.first_name == "Max"
        assert contact.middle_name == "Peter"
        assert contact.last_name == "Mustermann"
        assert contact.phone == "+49 171 1234567"
        assert contact.email == "max@example.de"
        assert contact.street == "Musterstrasse"
        assert contact.house_nr == "42"
        assert contact.city == "Duesseldorf"
        assert contact.zip == "40210"
        assert contact.country == "Germany"
        assert len(contact.important_dates) == 1
        assert contact.important_dates[0]["type"] == "birthday"
        assert contact.important_dates[0]["date"] == "1990-05-15"

    def test_parse_multiple_phones(self):
        """Erste Telefonnummer wird verwendet."""
        vcard = """BEGIN:VCARD
VERSION:3.0
FN:Test Person
N:Person;Test;;;
TEL;TYPE=CELL:+49 171 1111111
TEL;TYPE=WORK:+49 211 2222222
END:VCARD"""
        
        parser = VCardParser()
        contact = parser.parse(vcard)
        
        # Erste Nummer wird genommen
        assert contact.phone == "+49 171 1111111"

    def test_parse_anniversary(self):
        """Jahrestag wird als important_date gespeichert."""
        vcard = """BEGIN:VCARD
VERSION:3.0
FN:Test Person
N:Person;Test;;;
ANNIVERSARY:2015-08-22
END:VCARD"""
        
        parser = VCardParser()
        contact = parser.parse(vcard)
        
        assert len(contact.important_dates) == 1
        assert contact.important_dates[0]["type"] == "anniversary"
        assert contact.important_dates[0]["date"] == "2015-08-22"


class TestContactToVCard:
    """Tests fuer Contact -> vCard String Konvertierung."""

    def test_serialize_minimal_contact(self):
        """Minimaler Contact erzeugt gueltige vCard."""
        contact = Contact(first_name="Max", last_name="Mustermann")
        
        parser = VCardParser()
        vcard = parser.serialize(contact)
        
        assert "BEGIN:VCARD" in vcard
        assert "VERSION:3.0" in vcard
        assert "FN:Max Mustermann" in vcard
        assert "N:Mustermann;Max;;;" in vcard
        assert "END:VCARD" in vcard

    def test_serialize_with_phone_and_email(self):
        """Contact mit Telefon und Email."""
        contact = Contact(
            first_name="Max",
            last_name="Mustermann",
            phone="+49 171 1234567",
            email="max@example.de"
        )
        
        parser = VCardParser()
        vcard = parser.serialize(contact)
        
        assert "TEL" in vcard
        assert "+49 171 1234567" in vcard
        assert "EMAIL" in vcard
        assert "max@example.de" in vcard

    def test_serialize_with_address(self):
        """Contact mit vollstaendiger Adresse."""
        contact = Contact(
            first_name="Max",
            last_name="Mustermann",
            street="Musterstrasse",
            house_nr="42",
            zip="40210",
            city="Duesseldorf",
            country="Germany"
        )
        
        parser = VCardParser()
        vcard = parser.serialize(contact)
        
        assert "ADR" in vcard
        assert "Musterstrasse 42" in vcard
        assert "Duesseldorf" in vcard
        assert "40210" in vcard

    def test_serialize_with_birthday(self):
        """Contact mit Geburtstag."""
        contact = Contact(
            first_name="Max",
            last_name="Mustermann",
            important_dates=[{"type": "birthday", "date": "1990-05-15"}]
        )
        
        parser = VCardParser()
        vcard = parser.serialize(contact)
        
        assert "BDAY:1990-05-15" in vcard

    def test_serialize_preserves_uid(self):
        """UID wird beibehalten wenn vorhanden."""
        contact = Contact(
            first_name="Max",
            last_name="Mustermann",
            nextcloud_uid="abc-123-def"
        )
        
        parser = VCardParser()
        vcard = parser.serialize(contact, provider="nextcloud")
        
        assert "UID:abc-123-def" in vcard


class TestRoundTrip:
    """Tests fuer Parse -> Serialize -> Parse Konsistenz."""

    def test_roundtrip_preserves_data(self):
        """Daten bleiben nach Roundtrip erhalten."""
        original = Contact(
            first_name="Max",
            middle_name="Peter",
            last_name="Mustermann",
            phone="+49 171 1234567",
            email="max@example.de",
            street="Musterstrasse",
            house_nr="42",
            zip="40210",
            city="Duesseldorf",
            country="Germany",
            important_dates=[{"type": "birthday", "date": "1990-05-15"}]
        )
        
        parser = VCardParser()
        vcard = parser.serialize(original)
        restored = parser.parse(vcard)
        
        assert restored.first_name == original.first_name
        assert restored.middle_name == original.middle_name
        assert restored.last_name == original.last_name
        assert restored.phone == original.phone
        assert restored.email == original.email
        assert restored.city == original.city


class TestEdgeCases:
    """Edge Cases und Fehlerbehandlung."""

    def test_parse_empty_vcard_raises(self):
        """Leere vCard wirft Fehler."""
        parser = VCardParser()
        
        with pytest.raises(ValueError, match="Invalid vCard"):
            parser.parse("")

    def test_parse_invalid_vcard_raises(self):
        """Ungueltige vCard wirft Fehler."""
        parser = VCardParser()
        
        with pytest.raises(ValueError, match="Invalid vCard"):
            parser.parse("Das ist keine vCard")

    def test_parse_handles_special_characters(self):
        """Sonderzeichen werden korrekt verarbeitet."""
        vcard = """BEGIN:VCARD
VERSION:3.0
FN:Hans-Peter Mueller
N:Mueller;Hans-Peter;;;
END:VCARD"""
        
        parser = VCardParser()
        contact = parser.parse(vcard)
        
        assert contact.first_name == "Hans-Peter"
        assert contact.last_name == "Mueller"
