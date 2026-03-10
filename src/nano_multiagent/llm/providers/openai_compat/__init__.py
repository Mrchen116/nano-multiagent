"""Canonical OpenAI-compatible provider adapter exports."""

from .client import OpenAICompatClient, _should_trust_env
from .mapper import OpenAICompatMapper

__all__ = ["OpenAICompatClient", "OpenAICompatMapper", "_should_trust_env"]
