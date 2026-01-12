"""
Tests fuer ChannelRouter Service.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
import sys
sys.path.insert(0, "/opt/python-modules")


class TestChannelContext:
    """Tests fuer ChannelContext Datenklasse."""
    
    def test_web_channel_context(self):
        from agents.services.channel_router import ChannelContext
        
        ctx = ChannelContext(channel="web", channel_id="session-123")
        
        assert ctx.channel == "web"
        assert ctx.channel_id == "session-123"
        assert ctx.is_web is True
        assert ctx.is_telegram is False
    
    def test_telegram_channel_context(self):
        from agents.services.channel_router import ChannelContext
        
        ctx = ChannelContext(channel="telegram", channel_id="12345678")
        
        assert ctx.channel == "telegram"
        assert ctx.channel_id == "12345678"
        assert ctx.is_web is False
        assert ctx.is_telegram is True
    
    def test_unknown_channel_defaults_to_web(self):
        from agents.services.channel_router import ChannelContext
        
        ctx = ChannelContext()  # No params
        
        assert ctx.channel == "web"
        assert ctx.is_web is True


class TestChannelRouter:
    """Tests fuer ChannelRouter."""
    
    def test_create_context_web(self):
        from agents.services.channel_router import ChannelRouter
        
        router = ChannelRouter()
        ctx = router.create_context(channel="web", channel_id="sess-1")
        
        assert ctx.channel == "web"
        assert ctx.channel_id == "sess-1"
    
    def test_create_context_telegram(self):
        from agents.services.channel_router import ChannelRouter
        
        router = ChannelRouter()
        ctx = router.create_context(channel="telegram", channel_id="987654")
        
        assert ctx.channel == "telegram"
        assert ctx.channel_id == "987654"
    
    def test_get_response_target_web(self):
        from agents.services.channel_router import ChannelRouter, ChannelContext
        
        router = ChannelRouter()
        ctx = ChannelContext(channel="web", channel_id="sess-1")
        
        target = router.get_response_target(ctx)
        
        assert target["type"] == "web"
        assert target["session_id"] == "sess-1"
    
    def test_get_response_target_telegram(self):
        from agents.services.channel_router import ChannelRouter, ChannelContext
        
        router = ChannelRouter()
        ctx = ChannelContext(channel="telegram", channel_id="123456")
        
        target = router.get_response_target(ctx)
        
        assert target["type"] == "telegram"
        assert target["chat_id"] == "123456"
    
    def test_should_send_to_channel_same_channel(self):
        from agents.services.channel_router import ChannelRouter, ChannelContext
        
        router = ChannelRouter()
        ctx = ChannelContext(channel="telegram", channel_id="123")
        
        assert router.should_send_to_channel(ctx, "telegram") is True
    
    def test_should_not_send_to_different_channel(self):
        from agents.services.channel_router import ChannelRouter, ChannelContext
        
        router = ChannelRouter()
        ctx = ChannelContext(channel="telegram", channel_id="123")
        
        # Anfrage kam via Telegram, also nicht an Web senden
        assert router.should_send_to_channel(ctx, "web") is False


class TestChannelRouterWithDB:
    """Tests mit DB-Integration."""
    
    def test_get_telegram_config_returns_config(self):
        from agents.services.channel_router import ChannelRouter
        
        mock_db = Mock()
        mock_db.execute_one.return_value = {
            "bot_token": "123:ABC",
            "chat_id": "456789"
        }
        
        router = ChannelRouter(db=mock_db)
        config = router.get_telegram_config()
        
        assert config["bot_token"] == "123:ABC"
        assert config["chat_id"] == "456789"
    
    def test_get_telegram_config_returns_none_when_not_configured(self):
        from agents.services.channel_router import ChannelRouter
        
        mock_db = Mock()
        mock_db.execute_one.return_value = None
        
        router = ChannelRouter(db=mock_db)
        config = router.get_telegram_config()
        
        assert config is None
