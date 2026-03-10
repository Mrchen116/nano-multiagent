"""Compatibility alias exposing canonical Anthropic provider package."""

import sys

from nano_multiagent.platform.llm.providers import anthropic as _platform_anthropic

sys.modules[__name__] = _platform_anthropic
