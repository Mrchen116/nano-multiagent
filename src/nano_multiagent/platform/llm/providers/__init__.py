"""Compatibility shim exposing canonical shared LLM provider adapters."""

import sys

from . import anthropic, openai_compat

_LEGACY_PROVIDER_PACKAGE = "nano_multiagent" + ".llm.providers"
sys.modules.setdefault(_LEGACY_PROVIDER_PACKAGE, sys.modules[__name__])

__all__ = ["anthropic", "openai_compat"]
