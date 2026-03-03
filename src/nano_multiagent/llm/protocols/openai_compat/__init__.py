"""OpenAI-compatible provider adapter implementation."""

from .client import OpenAICompatClient
from .mapper import OpenAICompatMapper

__all__ = ["OpenAICompatClient", "OpenAICompatMapper"]
