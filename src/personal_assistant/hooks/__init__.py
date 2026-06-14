"""personal_assistant hooks — supplied to build_kernel(hooks=…) by the PA factory.

refactor-406-M2: PA hooks live here (not in the dissolved agent/products/) and are
wired via ``build_pa_kernel(hooks=[…])`` (build_kernel hooks= entry, 决策 2).
"""

from __future__ import annotations

from personal_assistant.hooks import chat_history

__all__ = ["chat_history"]
