"""Compatibility alias exposing canonical Anthropic provider mapper module."""

import sys

from nano_multiagent.platform.llm.providers.anthropic import mapper as _platform_mapper

sys.modules[__name__] = _platform_mapper
