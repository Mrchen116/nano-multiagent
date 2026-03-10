"""Compatibility alias exposing canonical OpenAI-compatible provider mapper module."""

import sys

from nano_multiagent.platform.llm.providers.openai_compat import mapper as _platform_mapper

sys.modules[__name__] = _platform_mapper
