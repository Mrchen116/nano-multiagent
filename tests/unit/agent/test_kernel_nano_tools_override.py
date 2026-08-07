"""Workspace extension scopes retain replace semantics without cross-workspace bleed."""

from __future__ import annotations

from pathlib import Path

import tests.conftest as _conftest
from agent.sdk import LLMConfig, build_kernel


def _write_override_tool(nano_tools: Path, *, name: str, marker: str) -> None:
    nano_tools.mkdir(parents=True, exist_ok=True)
    (nano_tools / f"{name}_override.py").write_text(
        "from typing import Any, Mapping\n\n\n"
        "class _Override:\n"
        f"    name = {name!r}\n"
        f'    description = "override marker {marker}"\n'
        "    input_schema = {'type': 'object', 'properties': {}, "
        "'additionalProperties': False}\n\n"
        "    def run(self, args: Mapping[str, Any], ctx: Any) -> Mapping[str, Any]:\n"
        f"        return {{'ok': True, 'marker': {marker!r}}}\n\n\n"
        "TOOL = _Override()\n",
        encoding="utf-8",
    )


def test_build_kernel_does_not_crash_on_nano_tools_builtin_override(
    tmp_path: Path,
) -> None:
    """A .nano/tools tool named like a built-in (bash) must not crash build_kernel."""
    repo = tmp_path / "repo"
    _write_override_tool(
        repo / ".nano" / "tools", name="bash", marker="r2-bash-override"
    )

    # Before R2-1 this raised ValueError(tool already registered) → crash.
    kernel = build_kernel(
        llm=LLMConfig.from_payload(_conftest._DEFAULT_TEST_PAYLOAD),
        tools=[],
        hooks=[],
        workspace_config_dirname=".nano",
        repo_root=repo,
    )
    names = [
        t.name
        for t in kernel.list_session_tools("scope", workspace_root=repo)
    ]
    assert "bash" in names, "bash tool must still be present (override, not removed)"


def test_nano_tools_new_tool_discovered(tmp_path: Path) -> None:
    """A non-conflicting .nano/tools tool is discovered for that workspace scope."""
    repo = tmp_path / "repo2"
    _write_override_tool(
        repo / ".nano" / "tools", name="r2_probe_tool", marker="r2-probe"
    )
    kernel = build_kernel(
        llm=LLMConfig.from_payload(_conftest._DEFAULT_TEST_PAYLOAD),
        tools=[],
        hooks=[],
        workspace_config_dirname=".nano",
        repo_root=repo,
    )
    names = [
        t.name
        for t in kernel.list_session_tools("scope", workspace_root=repo)
    ]
    assert "r2_probe_tool" in names
