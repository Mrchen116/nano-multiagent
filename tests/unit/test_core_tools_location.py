"""Verify core/tools is the canonical home for shared tool contracts."""

from agent.core.tools.base import Tool as CoreTool
from agent.core.tools.base import ToolContext as CoreToolContext
from agent.core.tools.registry import ToolRegistry as CoreToolRegistry
from agent.platform.tools.base import Tool as PlatformTool
from agent.platform.tools.base import ToolContext as PlatformToolContext
from agent.platform.tools.registry import ToolRegistry as PlatformToolRegistry



def test_core_tools_is_canonical_home() -> None:
    assert CoreTool is PlatformTool
    assert CoreToolContext is PlatformToolContext
    assert CoreToolRegistry is PlatformToolRegistry

    assert CoreToolContext.__module__ == "agent.core.tools.base"
    assert CoreToolRegistry.__module__ == "agent.core.tools.registry"
