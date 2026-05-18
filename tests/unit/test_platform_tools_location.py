"""Verify platform/tools is the canonical home for loader, safety, and builtins."""

from importlib.util import find_spec

import agent.platform.tools.builtins as platform_builtins
from agent.platform.tools.base import ToolContext
from agent.platform.tools.constants import DEFAULT_MAX_BYTES, DEFAULT_MAX_KILOBYTES, DEFAULT_MAX_LINES
from agent.platform.tools.registry import ToolRegistry
from agent.platform.tools.builtins import builtin_tools, register_builtin_tools
from agent.platform.tools.loader import (
    build_tool_registry,
    discover_tool_files,
    load_tools_from_directory,
)
from agent.platform.tools.safety import (
    CommandExecution,
    CommandPolicyDecision,
    ToolSafety,
    ToolSafetyConfig,
    load_tool_safety_config,
)



def test_platform_tools_loader_is_canonical_home() -> None:
    """Platform tool loader functions must originate from platform modules."""
    assert build_tool_registry.__module__ == "agent.platform.tools.loader"
    assert discover_tool_files.__module__ == "agent.platform.tools.loader"
    assert load_tools_from_directory.__module__ == "agent.platform.tools.loader"



def test_platform_tools_safety_is_canonical_home() -> None:
    """Platform tool safety types must originate from platform modules.

    After M6 (bugfix-355): CommandPolicyDecision moved to bash_policy.py.
    safety.py retains a shim re-export for backward compat, but the canonical
    home is agent.platform.tools.builtins.bash_policy.
    """
    assert ToolSafety.__module__ == "agent.platform.tools.safety"
    assert ToolSafetyConfig.__module__ == "agent.platform.tools.safety"
    # CommandPolicyDecision moved to bash_policy in M6; shim re-exported from safety.
    assert CommandPolicyDecision.__module__ == "agent.platform.tools.builtins.bash_policy"
    assert CommandExecution.__module__ == "agent.platform.tools.safety"
    assert load_tool_safety_config.__module__ == "agent.platform.tools.safety"



def test_platform_tool_contracts_are_compatibility_facades() -> None:
    """Platform tool contracts stay importable while canonical home lives in core."""
    assert ToolContext.__module__ == "agent.core.tools.base"
    assert ToolRegistry.__module__ == "agent.core.tools.registry"
    assert DEFAULT_MAX_LINES == 2000
    assert DEFAULT_MAX_BYTES == 50 * 1024
    assert DEFAULT_MAX_KILOBYTES == 50



def test_platform_tools_builtins_is_canonical_home() -> None:
    """Platform builtins helpers must live under the platform tools package."""
    assert platform_builtins.__name__ == "agent.platform.tools.builtins"
    assert builtin_tools.__module__ == "agent.platform.tools.builtins"
    assert register_builtin_tools.__module__ == "agent.platform.tools.builtins"



def test_legacy_tools_root_is_removed() -> None:
    assert find_spec("agent.tools") is None
