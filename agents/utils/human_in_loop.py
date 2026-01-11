"""
HumanInLoop - Menschliche Entscheidungen in Automationen.

Ermöglicht:
- Genehmigungsanfragen vor kritischen Aktionen
- Entscheidungen zwischen Optionen
- Freitext-Eingaben

Anfragen werden in DB gespeichert und können über API/UI beantwortet werden.
"""

import sys
import json
import time
from typing import Optional, Any, Dict, List
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

sys.path.insert(0, "/opt/python-modules")
from llm.infrastructure.database import get_database


class RequestStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ANSWERED = "answered"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class HumanRequest:
    id: int
    automation: str
    request_type: str  # approval, choice, input
    question: str
    options: Optional[List[str]]
    status: str
    response: Optional[str]
    created_at: datetime
    answered_at: Optional[datetime]


class HumanInLoop:
    """
    Menschliche Entscheidungen in Automationen.
    
    Verwendung:
        hil = HumanInLoop('my_automation')
        
        # Genehmigung einholen
        approved = hil.request_approval('Datei löschen?', timeout=300)
        
        # Auswahl
        choice = hil.request_choice('Welche Option?', ['A', 'B', 'C'])
        
        # Freitext
        input_text = hil.request_input('Bitte Namen eingeben:')
    """
    
    TABLE_NAME = "human_requests"
    
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
                    request_type VARCHAR(20) NOT NULL,
                    question TEXT NOT NULL,
                    options JSONB,
                    status VARCHAR(20) DEFAULT 'pending',
                    response TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    answered_at TIMESTAMP
                )
            """)
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.TABLE_NAME}_status
                ON {self.TABLE_NAME}(automation, status)
            """)
            self._db.commit()
    
    def _create_request(self, request_type: str, question: str, options: List[str] = None) -> int:
        """Erstellt eine neue Anfrage."""
        with self._db.get_cursor() as cursor:
            cursor.execute(f"""
                INSERT INTO {self.TABLE_NAME} (automation, request_type, question, options)
                VALUES (%s, %s, %s, %s::jsonb)
                RETURNING id
            """, (self.automation, request_type, question, json.dumps(options) if options else None))
            request_id = cursor.fetchone()["id"]
            self._db.commit()
            return request_id
    
    def _wait_for_response(self, request_id: int, timeout: int = 300, poll_interval: int = 2) -> Optional[HumanRequest]:
        """Wartet auf Antwort (Polling)."""
        start = time.time()
        
        while time.time() - start < timeout:
            with self._db.get_cursor() as cursor:
                cursor.execute(f"""
                    SELECT * FROM {self.TABLE_NAME} WHERE id = %s
                """, (request_id,))
                row = cursor.fetchone()
                
                if row and row["status"] != "pending":
                    return HumanRequest(
                        id=row["id"],
                        automation=row["automation"],
                        request_type=row["request_type"],
                        question=row["question"],
                        options=row["options"] if isinstance(row["options"], list) else json.loads(row["options"]) if row["options"] else None,
                        status=row["status"],
                        response=row["response"],
                        created_at=row["created_at"],
                        answered_at=row["answered_at"]
                    )
            
            time.sleep(poll_interval)
        
        # Timeout - Request als timeout markieren
        with self._db.get_cursor() as cursor:
            cursor.execute(f"""
                UPDATE {self.TABLE_NAME} SET status = 'timeout' WHERE id = %s
            """, (request_id,))
            self._db.commit()
        
        return None
    
    # === Request-Methoden ===
    
    def request_approval(self, question: str, timeout: int = 300) -> bool:
        """
        Fragt nach Genehmigung (Ja/Nein).
        
        Returns:
            True wenn genehmigt, False wenn abgelehnt oder Timeout
        """
        request_id = self._create_request("approval", question, ["approve", "reject"])
        result = self._wait_for_response(request_id, timeout)
        
        if result and result.status == "approved":
            return True
        return False
    
    def request_choice(self, question: str, options: List[str], timeout: int = 300) -> Optional[str]:
        """
        Fragt nach Auswahl aus Optionen.
        
        Returns:
            Gewählte Option oder None bei Timeout
        """
        request_id = self._create_request("choice", question, options)
        result = self._wait_for_response(request_id, timeout)
        
        if result and result.status == "answered":
            return result.response
        return None
    
    def request_input(self, question: str, timeout: int = 300) -> Optional[str]:
        """
        Fragt nach Freitext-Eingabe.
        
        Returns:
            Eingegebener Text oder None bei Timeout
        """
        request_id = self._create_request("input", question)
        result = self._wait_for_response(request_id, timeout)
        
        if result and result.status == "answered":
            return result.response
        return None
    
    # === Antwort-Methoden (für API/UI) ===
    
    def get_pending_requests(self) -> List[HumanRequest]:
        """Holt alle offenen Anfragen."""
        with self._db.get_cursor() as cursor:
            cursor.execute(f"""
                SELECT * FROM {self.TABLE_NAME}
                WHERE automation = %s AND status = 'pending'
                ORDER BY created_at
            """, (self.automation,))
            
            return [
                HumanRequest(
                    id=row["id"],
                    automation=row["automation"],
                    request_type=row["request_type"],
                    question=row["question"],
                    options=row["options"] if isinstance(row["options"], list) else json.loads(row["options"]) if row["options"] else None,
                    status=row["status"],
                    response=row["response"],
                    created_at=row["created_at"],
                    answered_at=row["answered_at"]
                )
                for row in cursor.fetchall()
            ]
    
    def respond(self, request_id: int, response: str, approved: bool = None) -> bool:
        """
        Beantwortet eine Anfrage.
        
        Args:
            request_id: ID der Anfrage
            response: Antwort-Text
            approved: Für approval-Requests: True=genehmigt, False=abgelehnt
        """
        if approved is not None:
            status = "approved" if approved else "rejected"
        else:
            status = "answered"
        
        with self._db.get_cursor() as cursor:
            cursor.execute(f"""
                UPDATE {self.TABLE_NAME}
                SET status = %s, response = %s, answered_at = CURRENT_TIMESTAMP
                WHERE id = %s AND status = 'pending'
            """, (status, response, request_id))
            updated = cursor.rowcount > 0
            self._db.commit()
            return updated
    
    def cancel_request(self, request_id: int) -> bool:
        """Bricht eine Anfrage ab."""
        with self._db.get_cursor() as cursor:
            cursor.execute(f"""
                UPDATE {self.TABLE_NAME}
                SET status = 'cancelled'
                WHERE id = %s AND status = 'pending'
            """, (request_id,))
            updated = cursor.rowcount > 0
            self._db.commit()
            return updated


def get_human_in_loop(automation: str = "default") -> HumanInLoop:
    return HumanInLoop(automation)
