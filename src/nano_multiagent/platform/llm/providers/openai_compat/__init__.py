"""Compatibility shim for canonical OpenAI-compatible provider adapters."""

from nano_multiagent.llm.providers.openai_compat import OpenAICompatClient, OpenAICompatMapper, _should_trust_env

__all__ = ["OpenAICompatClient", "OpenAICompatMapper", "_should_trust_env"]
