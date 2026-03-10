"""Compatibility shim for canonical Anthropic provider client."""

from nano_multiagent.platform.llm.providers.anthropic.client import AnthropicClient, _should_trust_env

__all__ = ["AnthropicClient", "_should_trust_env"]
