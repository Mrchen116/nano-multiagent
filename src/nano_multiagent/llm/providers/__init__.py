"""Compatibility alias exposing canonical platform LLM provider package."""

import sys

from nano_multiagent.platform.llm import providers as _platform_providers

sys.modules[__name__] = _platform_providers
