"""
Tests fuer Telegram Command Handler.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
import sys
sys.path.insert(0, "/opt/python-modules")


class TestCommandParser:
    """Tests fuer Command-Parsing."""
    
    def test_parse_help_command(self):
        from agents.services.telegram_commands import TelegramCommandHandler
        
        handler = TelegramCommandHandler(db=Mock())
        parsed = handler.parse_command("/help")
        
        assert parsed["is_command"] is True
        assert parsed["command"] == "help"
        assert parsed["args"] == []
    
    def test_parse_command_with_args(self):
        from agents.services.telegram_commands import TelegramCommandHandler
        
        handler = TelegramCommandHandler(db=Mock())
        parsed = handler.parse_command("/query Projekt Alpha")
        
        assert parsed["is_command"] is True
        assert parsed["command"] == "query"
        assert parsed["args"] == ["Projekt", "Alpha"]
    
    def test_parse_freetext_not_command(self):
        from agents.services.telegram_commands import TelegramCommandHandler
        
        handler = TelegramCommandHandler(db=Mock())
        parsed = handler.parse_command("Das ist normaler Text")
        
        assert parsed["is_command"] is False
        assert parsed["freetext"] == "Das ist normaler Text"


class TestCommandExecution:
    """Tests fuer Command-Ausfuehrung."""
    
    def test_help_command_returns_list(self):
        from agents.services.telegram_commands import TelegramCommandHandler
        
        handler = TelegramCommandHandler(db=Mock())
        result = handler.execute_command("help", [])
        
        assert "/help" in result
        assert "/status" in result
    
    def test_status_command_queries_db(self):
        from agents.services.telegram_commands import TelegramCommandHandler
        
        mock_db = Mock()
        mock_db.execute_one.return_value = {"count": 5}
        mock_db.execute.return_value = [{"count": 3}]
        
        handler = TelegramCommandHandler(db=mock_db)
        result = handler.execute_command("status", [])
        
        assert "Status" in result or "Aufgaben" in result
    
    def test_unknown_command_returns_error(self):
        from agents.services.telegram_commands import TelegramCommandHandler
        
        handler = TelegramCommandHandler(db=Mock())
        result = handler.execute_command("unknown_command", [])
        
        assert "unbekannt" in result.lower() or "nicht" in result.lower()


class TestCommandHandler:
    """Tests fuer kompletten Handler-Flow."""
    
    def test_handle_returns_command_result_for_slash(self):
        from agents.services.telegram_commands import TelegramCommandHandler
        
        handler = TelegramCommandHandler(db=Mock())
        result = handler.handle("/help")
        
        assert result["handled"] is True
        assert "response" in result
    
    def test_handle_returns_unhandled_for_freetext(self):
        from agents.services.telegram_commands import TelegramCommandHandler
        
        handler = TelegramCommandHandler(db=Mock())
        result = handler.handle("Normaler Text")
        
        assert result["handled"] is False
    
    def test_available_commands_list(self):
        from agents.services.telegram_commands import TelegramCommandHandler
        
        handler = TelegramCommandHandler(db=Mock())
        commands = handler.get_available_commands()
        
        assert "help" in commands
        assert "status" in commands
