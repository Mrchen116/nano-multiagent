#!/usr/bin/env python3
"""Live evidence for bugfix-468-M3: drive edit with wrong parameter names.

Runs through ToolRegistry.execute so the full validation path fires.
Wrong parameter names (old_string/new_string instead of oldText/newText)
should produce a CC-style ToolError naming the missing fields.
"""

import asyncio
import tempfile
from pathlib import Path

from agent.core.errors import ToolError
from agent.core.tools.base import (
    set_tool_safety_factory,
    set_tool_safety_config_factory,
)
from agent.core.tools.registry import ToolRegistry
from agent.platform.tools.base import ToolContext
from agent.platform.tools.builtins.edit import EditTool
from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig

set_tool_safety_factory(ToolSafety)
set_tool_safety_config_factory(ToolSafetyConfig)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ctx = ToolContext.create(repo_root=Path(tmp))
        registry = ToolRegistry(context=ctx)
        registry.register(EditTool())

        try:
            asyncio.run(
                registry.execute(
                    "edit",
                    {
                        "path": "demo.txt",
                        # Intentionally wrong parameter names to trigger validation.
                        "old_string": "hello",
                        "new_string": "world",
                    },
                )
            )
        except ToolError as exc:
            print("--- ToolError message ---")
            print(str(exc))
            print("--- details ---")
            print(exc.details)


if __name__ == "__main__":
    main()
