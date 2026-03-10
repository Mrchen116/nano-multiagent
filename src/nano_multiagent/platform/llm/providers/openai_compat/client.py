"""Compatibility shim for the canonical OpenAI-compatible provider client."""

from nano_multiagent.llm.providers.openai_compat.client import OpenAICompatClient, _should_trust_env

__all__ = ["OpenAICompatClient", "_should_trust_env"]
