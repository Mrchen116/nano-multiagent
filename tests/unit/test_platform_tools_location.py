"""Verify platform/tools is the canonical home for loader, safety, and builtins."""

from importlib.util import find_spec

import nano_multiagent.platform.tools.builtins as platform_builtins
from nano_multiagent.platform.tools.base import ToolContext
from nano_multiagent.platform.tools.constants import DEFAULT_MAX_BYTES, DEFAULT_MAX_KILOBYTES, DEFAULT_MAX_LINES
from nano_multiagent.platform.tools.registry import ToolRegistry
from nano_multiagent.platform.tools.builtins import builtin_tools, register_builtin_tools
from nano_multiagent.platform.tools.loader import (
    build_tool_registry,
    discover_tool_files,
    load_tools_from_directory,
)
from nano_multiagent.platform.tools.safety import (
    CommandExecution,
    CommandPolicyDecision,
    ToolSafety,
    ToolSafetyConfig,
    load_tool_safety_config,
)



def test_platform_tools_loader_is_canonical_home() -> None:
    """Platform tool loader functions must originate from platform modules."""
    assert build_tool_registry.__module__ == "nano_multiagent.platform.tools.loader"
    assert discover_tool_files.__module__ == "nano_multiagent.platform.tools.loader"
    assert load_tools_from_directory.__module__ == "nano_multiagent.platform.tools.loader"



def test_platform_tools_safety_is_canonical_home() -> None:
    """Platform tool safety types must originate from platform modules."""
    assert ToolSafety.__module__ == "nano_multiagent.platform.tools.safety"
    assert ToolSafetyConfig.__module__ == "nano_multiagent.platform.tools.safety"
    assert CommandPolicyDecision.__module__ == "nano_multiagent.platform.tools.safety"
    assert CommandExecution.__module__ == "nano_multiagent.platform.tools.safety"
    assert load_tool_safety_config.__module__ == "nano_multiagent.platform.tools.safety"



def test_platform_tool_contracts_are_canonical_home() -> None:
    """Platform tool contracts/constants must originate from platform modules."""
    assert ToolContext.__module__ == "nano_multiagent.platform.tools.base"
    assert ToolRegistry.__module__ == "nano_multiagent.platform.tools.registry"
    assert DEFAULT_MAX_LINES == 2000
    assert DEFAULT_MAX_BYTES == 50 * 1024
    assert DEFAULT_MAX_KILOBYTES == 50



def test_platform_tools_builtins_is_canonical_home() -> None:
    """Platform builtins helpers must live under the platform tools package."""
    assert platform_builtins.__name__ == "nano_multiagent.platform.tools.builtins"
    assert builtin_tools.__module__ == "nano_multiagent.platform.tools.builtins"
    assert register_builtin_tools.__module__ == "nano_multiagent.platform.tools.builtins"



def test_legacy_tools_root_is_removed() -> None:
    assert find_spec("nano_multiagent.tools") is None
