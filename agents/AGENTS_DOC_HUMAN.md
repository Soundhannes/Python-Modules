# Agent Framework - Dokumentation für Anwender

Diese Dokumentation erklärt, was das Agent Framework kann und wie man es nutzt - ohne Programmierkenntnisse.

---

## Was ist das Agent Framework?

Das Agent Framework ist ein Baukasten für automatisierte Abläufe. Stell dir vor, du hast einen digitalen Assistenten, der:

- **Texte analysieren** kann (z.B. Zusammenfassungen schreiben)
- **Daten speichern** und wieder abrufen kann
- **Benachrichtigungen senden** kann (z.B. via Telegram)
- **Auf deine Eingaben warten** kann (z.B. "Bitte bestätigen")
- **Protokollieren** kann, was passiert ist

---

## Die Bausteine im Überblick

| Baustein | Was macht er? | Beispiel |
|----------|---------------|----------|
| **Agent** | Denkt nach, schreibt Texte | "Fasse diesen Artikel zusammen" |
| **Orchestrator** | Steuert mehrere Agents | "Erst analysieren, dann bewerten" |
| **Storage** | Speichert Daten | "Merke dir diese Kundendaten" |
| **Notification** | Sendet Nachrichten | "Schicke mir eine Telegram-Nachricht" |
| **Logger** | Protokolliert Ereignisse | "Schreibe auf, was passiert ist" |
| **Validator** | Prüft Eingaben | "Ist das eine gültige E-Mail?" |
| **HumanInLoop** | Wartet auf Menschen | "Bitte bestätige diese Aktion" |
| **InputCollector** | Sammelt Eingaben | "Fülle dieses Formular aus" |
| **OutputParser** | Liest Antworten | "Extrahiere die JSON-Daten" |

---

## 1. Agent - Der Denker

### Was kann er?
Ein Agent ist wie ein Mitarbeiter, der Texte liest, versteht und darauf antwortet.

### Beispiel-Anwendungen
- Zusammenfassungen schreiben
- E-Mails beantworten
- Texte übersetzen
- Fragen beantworten
- Daten analysieren

### Einstellungen

| Einstellung | Bedeutung | Beispiel |
|-------------|-----------|----------|
| **Name** | Wie heißt der Agent? | "E-Mail-Assistent" |
| **Provider** | Welche KI nutzen? | Anthropic (Claude), OpenAI (GPT), Google (Gemini) |
| **Modell** | Welches Modell genau? | claude-sonnet-4-20250514 |
| **Max Tokens** | Wie lang darf die Antwort sein? | 2048 (ca. 1500 Wörter) |
| **Temperatur** | Wie kreativ? | 0.0 = sachlich, 1.0 = kreativ |

### So funktioniert es
1. Du gibst dem Agent eine Aufgabe ("Fasse diesen Text zusammen")
2. Optional: Du gibst ihm Kontext ("Der Text handelt von...")
3. Der Agent denkt nach
4. Du bekommst eine Antwort

### Was du zurückbekommst
- **Antwort**: Der generierte Text
- **Tokens**: Wie viel "Denkleistung" verbraucht wurde
- **Erfolg**: Hat es geklappt?
- **Fehler**: Falls nicht, warum?

---

## 2. Orchestrator - Der Koordinator

### Was kann er?
Der Orchestrator steuert mehrere Agents gleichzeitig oder nacheinander.

### Beispiel-Anwendungen
- Erst übersetzen, dann zusammenfassen
- Mehrere Dokumente parallel analysieren
- Ergebnisse von verschiedenen Agents kombinieren

### Ablauf-Arten

| Art | Bedeutung | Wann nutzen? |
|-----|-----------|--------------|
| **Sequentiell** | Einer nach dem anderen | Wenn Schritt 2 von Schritt 1 abhängt |
| **Parallel** | Alle gleichzeitig | Wenn die Aufgaben unabhängig sind |
| **Bedingt** | Nur wenn Bedingung erfüllt | "Nur wenn Kategorie = Beschwerde" |

### Einstellungen

| Einstellung | Bedeutung | Beispiel |
|-------------|-----------|----------|
| **Name** | Wie heißt der Orchestrator? | "Dokument-Workflow" |
| **Max Workers** | Wie viele parallel? | 4 (Standard) |

---

## 3. Storage - Das Gedächtnis

### Was kann er?
Der Storage speichert Daten dauerhaft in einer Datenbank.

### Beispiel-Anwendungen
- Kundendaten speichern
- Analyseergebnisse aufbewahren
- Einstellungen merken

### Einstellungen

| Einstellung | Bedeutung | Beispiel |
|-------------|-----------|----------|
| **Namespace** | In welchem "Ordner" speichern? | "kunden", "projekte" |

### Aktionen

| Aktion | Was passiert? | Beispiel |
|--------|---------------|----------|
| **Speichern** | Daten ablegen | Speichere Kunde mit ID "K001" |
| **Laden** | Daten abrufen | Hole Kunde mit ID "K001" |
| **Aktualisieren** | Daten ändern | Ändere Telefonnummer von "K001" |
| **Löschen** | Daten entfernen | Lösche Kunde "K001" |
| **Auflisten** | Alle anzeigen | Zeige alle Kunden |

---

## 4. Notification - Der Bote

### Was kann er?
Der Notification-Service sendet Benachrichtigungen über verschiedene Kanäle.

### Kanäle

| Kanal | Was? | Benötigt |
|-------|------|----------|
| **Telegram** | Chat-Nachricht | Bot-Token + Chat-ID |
| **Webhook** | HTTP-Anfrage | URL |

### Einstellungen

| Einstellung | Bedeutung | Beispiel |
|-------------|-----------|----------|
| **Automation** | Welcher Prozess sendet? | "täglicher-report" |

### Nachrichten-Typen

| Typ | Wann? | Beispiel |
|-----|-------|----------|
| **Info** | Normale Information | "Prozess gestartet" |
| **Success** | Erfolgreiche Aktion | "10 Dateien verarbeitet" |
| **Warning** | Warnung | "Nur noch 5% Speicher frei" |
| **Error** | Fehler | "Verbindung fehlgeschlagen" |

---

## 5. Logger - Der Protokollant

### Was kann er?
Der Logger schreibt auf, was in deinem System passiert.

### Einstellungen

| Einstellung | Bedeutung | Beispiel |
|-------------|-----------|----------|
| **Automation** | Welcher Prozess loggt? | "bestellungs-system" |
| **Tags** | Kategorien zum Filtern | ["produktion", "kritisch"] |
| **Min Level** | Ab welcher Wichtigkeit? | "INFO" (ignoriert DEBUG) |

### Log-Level (Wichtigkeit)

| Level | Bedeutung | Beispiel |
|-------|-----------|----------|
| **DEBUG** | Details für Entwickler | "Variable x = 5" |
| **INFO** | Normale Ereignisse | "Benutzer hat sich angemeldet" |
| **WARNING** | Potenzielle Probleme | "Speicher zu 80% voll" |
| **ERROR** | Fehler aufgetreten | "Datei nicht gefunden" |
| **CRITICAL** | Systemkritisch | "Datenbank nicht erreichbar" |

---

## 6. Validator - Der Prüfer

### Was kann er?
Der Validator prüft, ob Daten korrekt sind.

### Prüfungen

| Prüfung | Was wird geprüft? | Beispiel |
|---------|-------------------|----------|
| **Typ** | Ist es der richtige Datentyp? | Text, Zahl, Wahrheitswert |
| **Pflichtfeld** | Wurde etwas eingegeben? | E-Mail darf nicht leer sein |
| **Minimum** | Ist der Wert groß genug? | Alter mindestens 18 |
| **Maximum** | Ist der Wert klein genug? | Menge maximal 100 |
| **Pattern** | Passt das Format? | E-Mail muss @ enthalten |
| **Auswahl** | Ist es ein erlaubter Wert? | Nur "rot", "grün", "blau" |

### Beispiel-Schema

```
Name:
  - Typ: Text
  - Pflichtfeld: Ja

Alter:
  - Typ: Zahl
  - Minimum: 18
  - Maximum: 120

E-Mail:
  - Typ: Text
  - Muss Pattern enthalten: @

Status:
  - Typ: Auswahl
  - Erlaubte Werte: aktiv, inaktiv, pausiert
```

---

## 7. HumanInLoop - Der Wartende

### Was kann er?
HumanInLoop pausiert den Prozess und wartet auf menschliche Eingabe.

### Anfrage-Typen

| Typ | Was wird erwartet? | Beispiel |
|-----|-------------------|----------|
| **Bestätigung** | Ja oder Nein | "Möchtest du fortfahren?" |
| **Auswahl** | Eine Option wählen | "Welche Aktion: A, B oder C?" |
| **Eingabe** | Freier Text | "Bitte Kommentar eingeben" |
| **Überprüfung** | Daten kontrollieren | "Sind diese Daten korrekt?" |

### Einstellungen

| Einstellung | Bedeutung | Beispiel |
|-------------|-----------|----------|
| **Automation** | Welcher Prozess fragt? | "bestellfreigabe" |
| **Timeout** | Wie lange warten? | 3600 Sekunden = 1 Stunde |

### Ablauf
1. System erstellt Anfrage ("Bitte Bestellung prüfen")
2. Mensch bekommt Benachrichtigung
3. Mensch antwortet ("Genehmigt")
4. System fährt fort

---

## 8. InputCollector - Der Fragesteller

### Was kann er?
Der InputCollector sammelt mehrere Eingaben in einem Formular.

### Feld-Typen

| Typ | Eingabe | Beispiel |
|-----|---------|----------|
| **text** | Einzeilig | Name, E-Mail |
| **textarea** | Mehrzeilig | Beschreibung, Kommentar |
| **number** | Zahl | Alter, Menge |
| **select** | Dropdown | Auswahl aus Liste |
| **checkbox** | Ja/Nein | Newsletter abonnieren? |
| **date** | Datum | Geburtsdatum |

### Beispiel-Formular

```
Kundendaten-Formular:

1. Name
   - Typ: Text
   - Pflichtfeld: Ja
   - Beschreibung: Vor- und Nachname

2. Kundennummer
   - Typ: Zahl
   - Pflichtfeld: Ja

3. Kategorie
   - Typ: Auswahl
   - Optionen: Privat, Geschäft, Premium
   - Vorauswahl: Privat

4. Newsletter
   - Typ: Checkbox
   - Vorauswahl: Nein

5. Bemerkungen
   - Typ: Textbereich
   - Pflichtfeld: Nein
```

---

## 9. OutputParser - Der Übersetzer

### Was kann er?
Der OutputParser extrahiert strukturierte Daten aus KI-Antworten.

### Was er erkennt

| Format | Beschreibung | Beispiel |
|--------|--------------|----------|
| **JSON direkt** | Reiner JSON-Text | `{"name": "Max"}` |
| **JSON im Code-Block** | JSON in ```json ... ``` | Formatierte Ausgabe |
| **JSON eingebettet** | JSON im Fließtext | "Das Ergebnis ist {score: 85}" |
| **Markdown-Liste** | Mit - oder * | - Punkt 1, - Punkt 2 |
| **Nummerierte Liste** | Mit 1., 2., etc. | 1. Erster, 2. Zweiter |
| **Key-Value** | Name: Wert Format | Name: Max, Alter: 30 |

### Beispiele

**Eingabe (KI-Antwort):**
```
Basierend auf der Analyse ergibt sich folgendes Ergebnis:
{"score": 85, "kategorie": "gut", "empfehlung": "fortfahren"}
Ende der Analyse.
```

**Ausgabe (extrahierte Daten):**
```
score: 85
kategorie: gut
empfehlung: fortfahren
```

---

## Zusammenspiel der Bausteine

### Beispiel: Automatische E-Mail-Bearbeitung

```
1. E-Mail kommt rein

2. AGENT analysiert:
   → "Diese E-Mail ist eine Beschwerde"
   → "Priorität: Hoch"
   → "Thema: Lieferverzögerung"

3. STORAGE speichert:
   → Ticket-ID: T-2025-001
   → Alle Analyse-Daten

4. HUMANINLOOP fragt:
   → "Beschwerde von Kunde XY. Eskalieren?"

5. Mensch antwortet:
   → "Ja, eskalieren"

6. NOTIFICATION sendet:
   → Telegram an Support-Team
   → "Neue Eskalation: T-2025-001"

7. LOGGER protokolliert:
   → Alle Schritte mit Zeitstempel
```

### Beispiel: Täglicher Report

```
1. ORCHESTRATOR startet um 08:00

2. Parallel laufen 3 AGENTS:
   → Agent 1: Verkaufszahlen analysieren
   → Agent 2: Lagerbestand prüfen
   → Agent 3: Kundenfeedback auswerten

3. ORCHESTRATOR kombiniert Ergebnisse

4. STORAGE speichert Report

5. NOTIFICATION sendet:
   → Report-PDF an Telegram
   → Zusammenfassung per Webhook ans Dashboard

6. LOGGER protokolliert:
   → "Täglicher Report erstellt"
   → Tags: ["report", "täglich", "erfolgreich"]
```

---

## Glossar

| Begriff | Erklärung |
|---------|-----------|
| **Agent** | Ein KI-gesteuerter "Mitarbeiter" für Textaufgaben |
| **API** | Schnittstelle zur Kommunikation zwischen Programmen |
| **JSON** | Strukturiertes Datenformat (wie ein Formular) |
| **Namespace** | Abgetrenner Bereich für Daten (wie ein Ordner) |
| **Provider** | Anbieter von KI-Diensten (Anthropic, OpenAI, Google) |
| **Template** | Vorlage mit Platzhaltern |
| **Token** | Einheit für KI-Verbrauch (ca. 0.75 Wörter) |
| **Webhook** | Automatische Benachrichtigung an eine URL |
| **Workflow** | Ablauf mehrerer Schritte |

---

## Häufige Fragen

### Wie teuer ist die Nutzung?
Die Kosten entstehen durch die KI-Provider (Anthropic, OpenAI, Google). Jeder Aufruf verbraucht Tokens. Die genauen Preise findest du bei den jeweiligen Anbietern.

### Kann ich ohne Programmierkenntnisse arbeiten?
Ja, wenn das Framework einmal eingerichtet ist. Die Konfiguration erfolgt über einfache Einstellungen (Name, Provider, etc.). Für neue Workflows brauchst du jedoch jemanden mit Programmierkenntnissen.

### Wie lange dauert eine Antwort?
Typisch 1-5 Sekunden pro Agent-Aufruf. Bei komplexen Aufgaben oder langen Texten kann es länger dauern.

### Was passiert bei Fehlern?
Jeder Baustein meldet Erfolg oder Fehler zurück. Du kannst Fehler protokollieren (Logger), Benachrichtigungen senden (Notification) und Wiederholungen einbauen.

### Kann ich mehrere Provider nutzen?
Ja. Du kannst pro Agent einen anderen Provider wählen. Zum Beispiel: Claude für Zusammenfassungen, GPT für Übersetzungen.

---

## Nächste Schritte

1. **Anwendungsfall definieren**: Was soll automatisiert werden?
2. **Bausteine auswählen**: Welche Komponenten werden gebraucht?
3. **Workflow skizzieren**: In welcher Reihenfolge?
4. **Entwickler briefen**: Mit dieser Dokumentation
5. **Testen**: Erst mit Beispieldaten, dann produktiv

---

*Stand: Januar 2025*
*Framework Version: 1.0*
