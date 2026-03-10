"""Compatibility alias exposing canonical Anthropic provider client module."""

import sys

from nano_multiagent.platform.llm.providers.anthropic import client as _platform_client

sys.modules[__name__] = _platform_client
