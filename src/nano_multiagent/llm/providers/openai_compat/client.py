"""Compatibility alias exposing canonical OpenAI-compatible provider client module."""

import sys

from nano_multiagent.platform.llm.providers.openai_compat import client as _platform_client

sys.modules[__name__] = _platform_client
