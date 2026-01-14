"""
Anthropic Client - Verbindung zu Claude.

Infrastructure Layer: Konkrete Implementierung des LLM-Interfaces.
Unterstuetzt alle Claude API Parameter inkl. Extended Thinking und Streaming.
"""

import anthropic
from typing import List, Optional, Dict, Any, Generator

from ...domain import LLMClient, Message, LLMResponse


class AnthropicClient(LLMClient):
    """Client fuer Anthropic Claude API mit voller Parameter-Unterstuetzung."""
    
    MODELS = [
        "claude-sonnet-4-20250514",
        "claude-opus-4-20250514", 
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
        "claude-3-haiku-20240307",
    ]
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self._client = anthropic.Anthropic(api_key=api_key)
    
    def chat(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        max_tokens: int = 4096,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        stop_sequences: Optional[List[str]] = None,
        thinking: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, str]] = None,
        stream: bool = False
    ) -> LLMResponse:
        """
        Sendet Chat-Nachricht an Claude API (non-streaming).
        """
        use_model = model or self.default_model
        
        api_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
        
        kwargs: Dict[str, Any] = {
            "model": use_model,
            "max_tokens": max_tokens,
            "messages": api_messages
        }
        
        if system_prompt:
            kwargs["system"] = system_prompt
        
        if temperature is not None:
            kwargs["temperature"] = temperature
        
        if top_p is not None:
            kwargs["top_p"] = top_p
        
        if top_k is not None:
            kwargs["top_k"] = top_k
        
        if stop_sequences:
            kwargs["stop_sequences"] = stop_sequences
        
        if thinking:
            kwargs["thinking"] = thinking
            kwargs["temperature"] = 1.0
        
        if metadata:
            kwargs["metadata"] = metadata
        
        response = self._client.messages.create(**kwargs)
        
        thinking_content = None
        text_content = ""
        
        for block in response.content:
            if hasattr(block, 'type'):
                if block.type == "thinking":
                    thinking_content = block.thinking
                elif block.type == "text":
                    text_content = block.text
            elif hasattr(block, 'text'):
                text_content = block.text
        
        result = LLMResponse(
            content=text_content,
            model=use_model,
            tokens_used=response.usage.input_tokens + response.usage.output_tokens,
            provider=self.provider_name,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            stop_reason=response.stop_reason
        )
        
        if thinking_content:
            result.thinking = thinking_content
        
        return result
    
    def stream_chat(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        max_tokens: int = 4096,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        stop_sequences: Optional[List[str]] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Streaming Chat - gibt Text-Chunks als Generator zurueck.
        
        Yields:
            Dict mit 'type' und 'content':
            - {type: 'text_delta', content: 'chunk...'}
            - {type: 'message_stop', content: '', model: '...', tokens: ...}
        """
        use_model = model or self.default_model
        
        api_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
        
        # WICHTIG: Kein 'stream' Parameter - messages.stream() ist bereits streaming
        kwargs: Dict[str, Any] = {
            "model": use_model,
            "max_tokens": max_tokens,
            "messages": api_messages
        }
        
        if system_prompt:
            kwargs["system"] = system_prompt
        
        if temperature is not None:
            kwargs["temperature"] = temperature
        
        if top_p is not None:
            kwargs["top_p"] = top_p
        
        if top_k is not None:
            kwargs["top_k"] = top_k
        
        if stop_sequences:
            kwargs["stop_sequences"] = stop_sequences
        
        if metadata:
            kwargs["metadata"] = metadata
        
        total_tokens = 0
        
        with self._client.messages.stream(**kwargs) as stream:
            for event in stream:
                if hasattr(event, 'type'):
                    if event.type == 'content_block_delta':
                        if hasattr(event.delta, 'text'):
                            yield {
                                'type': 'text_delta',
                                'content': event.delta.text
                            }
                    elif event.type == 'message_delta':
                        if hasattr(event.usage, 'output_tokens'):
                            total_tokens = event.usage.output_tokens
                    elif event.type == 'message_stop':
                        yield {
                            'type': 'message_stop',
                            'content': '',
                            'model': use_model,
                            'tokens': total_tokens,
                            'provider': self.provider_name
                        }
    
    def get_available_models(self) -> List[str]:
        return self.MODELS.copy()
    
    @property
    def provider_name(self) -> str:
        return "anthropic"
    
    @property
    def default_model(self) -> str:
        return "claude-sonnet-4-20250514"
