"""Verify platform/tools is the canonical home for loader, safety, and builtins."""

import nano_multiagent.platform.tools.builtins as platform_builtins
import nano_multiagent.tools.builtins as legacy_builtins
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
from nano_multiagent.tools.loader import (
    build_tool_registry as legacy_build_tool_registry,
)
from nano_multiagent.tools.loader import (
    discover_tool_files as legacy_discover_tool_files,
)
from nano_multiagent.tools.loader import (
    load_tools_from_directory as legacy_load_tools_from_directory,
)
from nano_multiagent.tools.safety import CommandExecution as LegacyCommandExecution
from nano_multiagent.tools.safety import (
    CommandPolicyDecision as LegacyCommandPolicyDecision,
)
from nano_multiagent.tools.safety import ToolSafety as LegacyToolSafety
from nano_multiagent.tools.safety import ToolSafetyConfig as LegacyToolSafetyConfig
from nano_multiagent.tools.safety import (
    load_tool_safety_config as legacy_load_tool_safety_config,
)
from nano_multiagent.tools.builtins import builtin_tools as legacy_builtin_tools
from nano_multiagent.tools.builtins import (
    register_builtin_tools as legacy_register_builtin_tools,
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


def test_platform_tools_builtins_is_canonical_home() -> None:
    """Platform builtins helpers must live under the platform tools package."""
    assert platform_builtins.__name__ == "nano_multiagent.platform.tools.builtins"
    assert builtin_tools.__module__ == "nano_multiagent.platform.tools.builtins"
    assert register_builtin_tools.__module__ == "nano_multiagent.platform.tools.builtins"


def test_old_tools_paths_are_compat_shims() -> None:
    """Legacy tool modules must re-export the canonical platform objects."""
    assert legacy_build_tool_registry is build_tool_registry
    assert legacy_discover_tool_files is discover_tool_files
    assert legacy_load_tools_from_directory is load_tools_from_directory

    assert LegacyToolSafety is ToolSafety
    assert LegacyToolSafetyConfig is ToolSafetyConfig
    assert LegacyCommandPolicyDecision is CommandPolicyDecision
    assert LegacyCommandExecution is CommandExecution
    assert legacy_load_tool_safety_config is load_tool_safety_config

    assert legacy_builtins is platform_builtins
    assert legacy_builtin_tools is builtin_tools
    assert legacy_register_builtin_tools is register_builtin_tools
