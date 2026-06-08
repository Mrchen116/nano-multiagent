"""Personal-assistant package-level constants.

Mirrors the values in agent.products.personal_assistant.defaults but lives here
so that personal_assistant code can reference them without crossing the
agent.products boundary (which is forbidden by the SDK boundary contract).
"""

from __future__ import annotations

# Workspace config directory name used by the personal-assistant product.
# Must stay in sync with agent.products.personal_assistant.defaults.WORKSPACE_CONFIG_DIRNAME.
WORKSPACE_CONFIG_DIRNAME = ".nanoassistant"
