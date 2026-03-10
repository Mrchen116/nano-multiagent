"""Compatibility alias exposing canonical OpenAI-compatible provider package."""

import sys

from nano_multiagent.platform.llm.providers import openai_compat as _platform_openai_compat

sys.modules[__name__] = _platform_openai_compat
