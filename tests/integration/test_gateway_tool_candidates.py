"""Gateway capability candidates follow registered tools, not Agent authorization."""

from pathlib import Path

import pytest

from personal_assistant.reporter.capability_projection import (
    PA_DEFAULT_TOOL_IDS,
    PA_OPTIONAL_TOOL_IDS,
)
from personal_assistant.reporter.upstream_reporter import (
    build_agent_capabilities_payload,
    build_node_capabilities_payload,
)
from tests.unit.personal_assistant._im_connection_helpers import _build_test_kernel


def _write_tool(root: Path, name: str, description: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{name}.py").write_text(
        "class Plugin:\n"
        f"    name = {name!r}\n"
        f"    description = {description!r}\n"
        "    input_schema = {'type': 'object', 'properties': {}}\n"
        "    async def run(self, args, ctx):\n"
        "        return {'ok': True}\n"
        "TOOL = Plugin()\n",
        encoding="utf-8",
    )


def test_registered_tools_are_optional_candidates_in_the_owning_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    shared = tmp_path / "home" / ".nanoassistant" / "tools"
    _write_tool(shared, "shared_reader", "Shared reader")
    workspaces = [tmp_path / "alpha", tmp_path / "beta"]
    _write_tool(workspaces[0] / ".nanoassistant" / "tools", "local_reader", "Alpha")
    _write_tool(workspaces[0] / ".nanoassistant" / "tools", "shared_reader", "Override")
    _write_tool(workspaces[1] / ".nanoassistant" / "tools", "other_reader", "Beta")
    kernel = _build_test_kernel(tmp_path / "kernel")
    try:
        node = build_node_capabilities_payload(kernel)
        alpha = build_agent_capabilities_payload(
            kernel, workspace_root=str(workspaces[0]), tool_allowlist=()
        )
        beta = build_agent_capabilities_payload(
            kernel, workspace_root=str(workspaces[1]), tool_allowlist=("read",)
        )
        selected = build_agent_capabilities_payload(
            kernel, workspace_root=str(workspaces[0]), tool_allowlist=("local_reader",)
        )
        node_tools = {t["name"]: t for t in node["tools"]}
        alpha_tools = {t["name"]: t for t in alpha["tools"]}
        beta_tools = {t["name"]: t for t in beta["tools"]}
        assert node_tools["shared_reader"] == {
            "name": "shared_reader",
            "description": "Shared reader",
            "default_on": False,
        }
        assert alpha_tools["shared_reader"]["description"] == "Override"
        assert alpha_tools["local_reader"]["description"] == "Alpha"
        assert beta_tools["shared_reader"]["description"] == "Shared reader"
        assert beta_tools["other_reader"]["description"] == "Beta"
        assert "local_reader" not in node_tools and "other_reader" not in node_tools
        assert "other_reader" not in alpha_tools and "local_reader" not in beta_tools
        assert selected["tools"] == alpha["tools"]
        for payload in (node, alpha, beta):
            tools = payload["tools"]
            declared = (*PA_DEFAULT_TOOL_IDS, *PA_OPTIONAL_TOOL_IDS)
            assert [t["name"] for t in tools[: len(declared)]] == list(declared)
            assert len({t["name"] for t in tools}) == len(tools)
            assert {t["name"] for t in tools if t["default_on"]} == set(
                PA_DEFAULT_TOOL_IDS
            )
    finally:
        kernel.close()
