"""
Tests fuer ReportDispatcher Service.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import sys
sys.path.insert(0, "/opt/python-modules")


class TestReportDispatcher:
    """Tests fuer ReportDispatcher."""
    
    def test_get_recipients_for_report_type(self):
        from agents.services.report_dispatcher import ReportDispatcher
        
        mock_db = Mock()
        mock_db.execute.return_value = [
            {"channel_type": "telegram", "recipients": ["123456", "789012"]},
            {"channel_type": "web", "recipients": ["session-1"]}
        ]
        
        dispatcher = ReportDispatcher(db=mock_db)
        recipients = dispatcher.get_recipients("daily_report")
        
        assert "telegram" in recipients
        assert "web" in recipients
        assert recipients["telegram"] == ["123456", "789012"]
        assert recipients["web"] == ["session-1"]
    
    def test_get_recipients_returns_empty_when_no_config(self):
        from agents.services.report_dispatcher import ReportDispatcher
        
        mock_db = Mock()
        mock_db.execute.return_value = []
        
        dispatcher = ReportDispatcher(db=mock_db)
        recipients = dispatcher.get_recipients("nonexistent_report")
        
        assert recipients == {}
    
    def test_add_recipient_creates_new_channel(self):
        from agents.services.report_dispatcher import ReportDispatcher
        
        mock_db = Mock()
        mock_db.execute_one.return_value = None  # No existing config
        mock_db.execute.return_value = [{"id": 1}]  # Insert result
        
        dispatcher = ReportDispatcher(db=mock_db)
        result = dispatcher.add_recipient("daily_report", "telegram", "123456")
        
        assert result is True
    
    def test_add_recipient_appends_to_existing(self):
        from agents.services.report_dispatcher import ReportDispatcher
        
        mock_db = Mock()
        mock_db.execute_one.return_value = {
            "id": 1,
            "recipients": ["111111"]
        }
        
        dispatcher = ReportDispatcher(db=mock_db)
        result = dispatcher.add_recipient("daily_report", "telegram", "222222")
        
        assert result is True
        # Check that execute was called to update
        update_call = [c for c in mock_db.execute.call_args_list if "UPDATE" in str(c)]
        assert len(update_call) > 0
    
    def test_remove_recipient(self):
        from agents.services.report_dispatcher import ReportDispatcher
        
        mock_db = Mock()
        mock_db.execute_one.return_value = {
            "id": 1,
            "recipients": ["111111", "222222"]
        }
        
        dispatcher = ReportDispatcher(db=mock_db)
        result = dispatcher.remove_recipient("daily_report", "telegram", "111111")
        
        assert result is True
    
    def test_get_channel_config(self):
        from agents.services.report_dispatcher import ReportDispatcher
        
        mock_db = Mock()
        mock_db.execute_one.return_value = {
            "bot_token": "123:ABC",
            "chat_id": "456"
        }
        
        dispatcher = ReportDispatcher(db=mock_db)
        config = dispatcher.get_channel_config("telegram")
        
        assert config["bot_token"] == "123:ABC"


class TestReportDispatcherSend:
    """Tests fuer send-Funktionalitaet."""
    
    def test_format_report_for_telegram(self):
        from agents.services.report_dispatcher import ReportDispatcher
        
        dispatcher = ReportDispatcher(db=Mock())
        
        report = {
            "top_3_tasks": [
                {"title": "Task 1", "why": "Important"},
                {"title": "Task 2", "why": "Urgent"}
            ],
            "summary_text": "Today is busy"
        }
        
        formatted = dispatcher.format_for_channel(report, "telegram")
        
        assert "Task 1" in formatted
        assert "Today is busy" in formatted
    
    def test_format_report_for_web(self):
        from agents.services.report_dispatcher import ReportDispatcher
        
        dispatcher = ReportDispatcher(db=Mock())
        
        report = {"top_3_tasks": [], "summary_text": "Nothing today"}
        
        formatted = dispatcher.format_for_channel(report, "web")
        
        # Web format returns dict
        assert isinstance(formatted, dict)
