"""Platform LLM provider adapters.

Canonical location: nano_multiagent.platform.llm.providers
Shim (backward compat): nano_multiagent.llm.protocols
"""

from nano_multiagent.llm.protocols import anthropic, openai_compat

__all__ = ["anthropic", "openai_compat"]
