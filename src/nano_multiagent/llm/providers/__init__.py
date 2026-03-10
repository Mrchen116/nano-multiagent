"""Canonical provider adapter package for shared LLM transports."""

from . import anthropic, openai_compat

__all__ = ["anthropic", "openai_compat"]
