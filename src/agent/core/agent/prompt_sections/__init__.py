"""Prompt-section assembler framework for the agent core.

Core contract:
- PromptSection and PromptContext live here (core-owned, no product imports).
- Product segments are defined in their respective product packages and
  injected through ProductProfile.prompt_sections by bootstrap — core never
  imports product sections directly.

Public surface:

    from agent.core.agent.prompt_sections import (
        PromptContext,
        PromptSection,
        assemble_system_prompt,
        resolve_effective_prompt,
    )
"""
from agent.core.agent.prompt_sections.base import (
    PromptContext,
    PromptSection,
    assemble_system_prompt,
    resolve_effective_prompt,
)

__all__ = [
    "PromptContext",
    "PromptSection",
    "assemble_system_prompt",
    "resolve_effective_prompt",
]
