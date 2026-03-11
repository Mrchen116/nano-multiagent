"""Compatibility shim for canonical OpenAI-compatible provider adapters."""

import sys

from .client import OpenAICompatClient, _should_trust_env
from .mapper import OpenAICompatMapper

_LEGACY_OPENAI_COMPAT_PACKAGE = "agent" + ".llm.providers" + ".openai_compat"
sys.modules.setdefault(_LEGACY_OPENAI_COMPAT_PACKAGE, sys.modules[__name__])

__all__ = ["OpenAICompatClient", "OpenAICompatMapper", "_should_trust_env"]
