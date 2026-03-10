"""Compatibility shim exposing canonical shared LLM provider adapters."""

from nano_multiagent.llm.providers import anthropic, openai_compat

__all__ = ["anthropic", "openai_compat"]
