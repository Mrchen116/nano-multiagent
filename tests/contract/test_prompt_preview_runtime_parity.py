"""Contract test: preview stable-prefix must match runtime output after placeholder substitution.

feat-383-M1 决策 5 — 第 2 层防线（feat-385-M3-fix-r2 P1 修订：volatile 段就地内联占位符，
不再使用末尾堆叠块）:
- 构造一对一致的 PromptContext 和 HTTP 请求
- 调 /v1/prompt-preview 取得预览串
- 调 runtime assemble_system_prompt(stable_only) 取得运行时 stable-only 串
- 将预览串中的占位符（<运行时注入：当前时间> / <运行时注入：workspace 路径>）替换为真实值
- 断言 preview 以 runtime stable-only 串为前缀（stable 段字节一致）
- 断言 preview 包含 volatile 段内联占位符（<运行时注入：...>，在 stable 前缀之后）

P1 之后 preview 不再有末尾 "---" 分隔块；volatile 段在其自然 order 位置以内联占位符出现。
契约：stable 前缀字节一致 + volatile 内联占位符存在，不再截断分隔符。
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
    """preview HTTP output with placeholders substituted must start with runtime stable output.

    This test verifies the end-to-end parity between:
    - The /v1/prompt-preview HTTP response (volatile sections appear inline as '运行时注入' placeholders)
    - The runtime assemble_system_prompt output (stable-only, volatile sections absent/None)

    After replacing the datetime/cwd placeholders in the preview output with the same
    values used in the runtime call, the preview must start with the runtime stable-only
    string byte-for-byte.  Volatile inline placeholders appear after this stable prefix.

    feat-385-M3-fix-r2 P1: no '---' footer separator expected; volatile sections appear
    inline at their order position as '<运行时注入：...>' strings.
    """
    from agent.core.agent.prompt_sections.base import RenderMode
    from agent.products.personal_assistant.prompt_sections import build_pa_system_prompt

    tool_specs = (
        _make_tool_spec("read", "Read a file from the filesystem."),
        _make_tool_spec("write", "Write content to a file."),
    )
    tool_ids = [s.name for s in tool_specs]
    workspace = "/tmp/test-workspace-contract"
    fake_datetime = "2026-01-01 00:00:00 UTC"

    # M4: use build_pa_system_prompt() for correctly ordered section list
    all_sections = build_pa_system_prompt()
    stable_sections = [s for s in all_sections if getattr(s, "cache_safe", True)]

    # Build real runtime ctx with known datetime/cwd, no memory (volatile=None/RUNTIME mode).
    runtime_ctx = PromptContext(
        available_tools=tool_specs,
        available_skills=(),
        current_datetime=fake_datetime,
        cwd=workspace,
        render_mode=RenderMode.RUNTIME,
        flags={},
        scenario={"conversation_type": "direct"},
        vars={},
    )

    # Runtime with volatile=None: only stable sections render; volatile sections (memory_block,
    # user_profile_block, communication_context) are absent because enabled_when returns False.
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

    # Replace placeholders with the same values used in the runtime ctx.
    normalized_preview = preview_prompt.replace(DATETIME_PLACEHOLDER, fake_datetime).replace(
        CWD_PLACEHOLDER, workspace
    )

    # feat-385-M3-fix-r2 P1: volatile sections render as inline '运行时注入' placeholders at
    # their order position (after stable sections).  The preview string must therefore start
    # with the runtime stable-only output (byte-identical prefix).
    # No '---' footer separator; volatile placeholders are embedded in the prompt body.
    assert normalized_preview.startswith(runtime_prompt), (
        "preview (after placeholder substitution) must start with runtime stable-only output byte-for-byte.\n"
        f"Runtime stable prefix (first 500 chars):\n{runtime_prompt[:500]}\n\n"
        f"Normalized preview (first 500 chars):\n{normalized_preview[:500]}"
    )

    # Confirm volatile inline placeholders are present after the stable prefix.
    volatile_suffix = normalized_preview[len(runtime_prompt):]
    # In the scenario="direct" request, pa.communication_context is not active
    # (requires conversation_type="group").  memory_block and user_profile_block
    # placeholders should appear.
    assert "运行时注入" in volatile_suffix, (
        "preview must contain inline '运行时注入' placeholders for volatile sections "
        f"(suffix after stable prefix: {volatile_suffix[:200]!r})"
    )

    # No M2-style footer stacking markers should appear anywhere.
    assert "---" not in normalized_preview, (
        "M2-style '---' footer separator must not appear in preview (feat-385-M3-fix-r2 P1)"
    )
    assert "runtime fills]" not in normalized_preview, (
        "M2-style '[section — runtime fills]' footer list must not appear in preview"
    )
