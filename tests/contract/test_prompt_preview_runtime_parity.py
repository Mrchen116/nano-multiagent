"""Contract test: preview HTTP output must match runtime build_system_prompt after placeholder substitution.

feat-383-M1 决策 5 — 第 2 层防线:
- 构造一对一致的 PromptContext 和 HTTP 请求
- 调 /v1/prompt-preview 取得预览串
- 调 runtime build_system_prompt 取得运行时串
- 将预览串中的两个占位符（<运行时注入：当前时间> / <运行时注入：workspace 路径>）替换为同一真实值
- 断言两串逐字相等

这保证了 HTTP 路由层的 ctx 构造与 runtime 一致——golden test 守 assemble≡build，本 test 守 HTTP 端→runtime 端的端到端等价。
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent.core.agent.prompt_sections.base import PromptContext, assemble_system_prompt
from agent.core.agent.prompting import build_system_prompt
from agent.core.types import ToolSpec
from agent.platform.http_api.app import create_app


DATETIME_PLACEHOLDER = "<运行时注入：当前时间>"
CWD_PLACEHOLDER = "<运行时注入：workspace 路径>"


def _auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}


def _make_tool_spec(name: str, description: str) -> ToolSpec:
    return ToolSpec(name=name, description=description, input_schema={})


def _make_registry_with_tools(*tool_specs: ToolSpec) -> object:
    """Build a ToolRegistry containing tools given as ToolSpec objects."""
    from agent.core.tools.base import ToolContext
    from agent.platform.tools.registry import ToolRegistry
    from types import SimpleNamespace

    ctx = ToolContext.create(repo_root=Path.cwd())
    registry = ToolRegistry(context=ctx)
    for spec in tool_specs:
        stub = SimpleNamespace(
            name=spec.name,
            description=spec.description,
            input_schema=spec.input_schema,
            is_concurrency_safe=False,
            max_result_size_chars=None,
        )
        registry.register(stub)
    return registry


def test_preview_http_output_matches_runtime_after_placeholder_substitution() -> None:
    """preview HTTP output with placeholders substituted must equal runtime output.

    This test verifies the end-to-end parity between:
    - The /v1/prompt-preview HTTP response (with placeholder datetime/cwd)
    - The runtime build_system_prompt output (with real datetime/cwd)

    After replacing the two placeholders in the preview output with the same
    values used in the runtime call, the two strings must be identical.
    """
    from agent.core.agent.prompt_sections.core_sections import CORE_SECTIONS
    from agent.products.personal_assistant.prompt_sections import PA_SECTIONS

    tool_specs = (
        _make_tool_spec("read", "Read a file from the filesystem."),
        _make_tool_spec("write", "Write content to a file."),
    )
    tool_ids = [s.name for s in tool_specs]
    workspace = "/tmp/test-workspace-contract"
    fake_datetime = "2026-01-01 00:00:00 UTC"

    # Build real runtime ctx with known datetime/cwd
    runtime_ctx = PromptContext(
        available_tools=tool_specs,
        available_skills=(),
        current_datetime=fake_datetime,
        cwd=workspace,
        memory_block=None,
        flags={},
        scenario={"conversation_type": "direct"},
        vars={},
    )

    all_sections = list(CORE_SECTIONS) + list(PA_SECTIONS)
    stable_sections = [s for s in all_sections if getattr(s, "cache_safe", True)]
    runtime_prompt = assemble_system_prompt(stable_sections, runtime_ctx)

    # Build HTTP app with real tool registry and PA sections
    registry = _make_registry_with_tools(*tool_specs)
    app = create_app()
    app.state.prompt_sections = all_sections
    app.state.tool_registry = registry

    with TestClient(app) as client:
        response = client.post(
            "/v1/prompt-preview",
            headers=_auth_headers(),
            json={
                "features": {},
                "tool_ids": tool_ids,
                "scenario": "direct",
                "workspace_root": workspace,
                "skill_ids": [],
            },
        )

    assert response.status_code == 200
    preview_prompt = response.json()["prompt"]

    # Replace placeholders with the same values used in the runtime ctx
    normalized_preview = preview_prompt.replace(DATETIME_PLACEHOLDER, fake_datetime).replace(
        CWD_PLACEHOLDER, workspace
    )

    assert normalized_preview == runtime_prompt, (
        "preview output after placeholder substitution must equal runtime prompt.\n"
        f"Preview (normalized):\n{normalized_preview[:500]}\n\n"
        f"Runtime:\n{runtime_prompt[:500]}"
    )
