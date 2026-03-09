"""Compatibility shim re-exporting the canonical core LLM factory."""

from nano_multiagent.core.llm.factory import LLMFactoryConfig, create_llm_client

__all__ = ["LLMFactoryConfig", "create_llm_client"]
