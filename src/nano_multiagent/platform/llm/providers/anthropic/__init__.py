"""Compatibility shim for canonical Anthropic provider adapters."""

import sys

from .client import AnthropicClient, _should_trust_env
from .mapper import AnthropicMapper

_LEGACY_ANTHROPIC_PACKAGE = "nano_multiagent" + ".llm.providers" + ".anthropic"
sys.modules.setdefault(_LEGACY_ANTHROPIC_PACKAGE, sys.modules[__name__])

__all__ = ["AnthropicClient", "AnthropicMapper", "_should_trust_env"]
