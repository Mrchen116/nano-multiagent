"""Compatibility shim for canonical Anthropic provider adapters."""

from nano_multiagent.llm.providers.anthropic import AnthropicClient, AnthropicMapper, _should_trust_env

__all__ = ["AnthropicClient", "AnthropicMapper", "_should_trust_env"]
