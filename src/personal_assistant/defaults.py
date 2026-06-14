"""Personal-assistant package-level constants.

Single source of truth (refactor-406: agent.products dissolved); lives here
so that personal_assistant code can reference them without crossing the
agent internals (forbidden by the SDK boundary contract).
"""

from __future__ import annotations

# Workspace config directory name used by the personal-assistant product.
# Single source of truth for the PA workspace config dirname (products/ dissolved).
WORKSPACE_CONFIG_DIRNAME = ".nanoassistant"
