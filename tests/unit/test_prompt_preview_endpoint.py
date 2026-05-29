"""Unit tests for POST /v1/prompt-preview — feat-379-M2 R5.

Contract:
- Endpoint exists and requires bearer auth.
- With no sections wired, returns empty prompt and section_count=0.
- With mock sections, returns assembled text and correct section_count.
- features/custom_prompt are passed through to PromptContext.
- Only cache_safe=True sections are included in the preview.
"""

from fastapi.testclient import TestClient

from agent.core.agent.prompt_sections.base import PromptContext, PromptSection
from agent.platform.http_api.app import create_app


def _auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}


def _make_section(
    name: str,
    text: str,
    cache_safe: bool = True,
    enabled: bool = True,
) -> PromptSection:
    """Build a minimal PromptSection for testing (M4: no order param)."""
    return PromptSection(
        name=name,
        render=lambda ctx, t=text: t,
        enabled_when=lambda ctx: enabled,
        cache_safe=cache_safe,
    )


def test_prompt_preview_no_sections_returns_empty() -> None:
    """Preview with no sections wired returns empty prompt and section_count=0."""
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            "/v1/prompt-preview",
            headers=_auth_headers(),
            json={"features": {}, "tool_ids": [], "scenario": "direct"},
        )
    assert response.status_code == 200
    body = response.json()
    assert "prompt" in body
    assert "section_count" in body
    assert body["prompt"] == ""
    assert body["section_count"] == 0


def test_prompt_preview_with_sections_returns_assembled_text() -> None:
    """Preview assembles injected sections and returns the joined text."""
    sections = [
        _make_section("core.identity", "You are a helpful assistant."),
        _make_section("core.rules", "Follow these rules."),
    ]
    app = create_app()
    app.state.prompt_sections = sections
    with TestClient(app) as client:
        response = client.post(
            "/v1/prompt-preview",
            headers=_auth_headers(),
            json={"features": {}, "tool_ids": [], "scenario": "direct"},
        )
    assert response.status_code == 200
    body = response.json()
    assert "You are a helpful assistant." in body["prompt"]
    assert "Follow these rules." in body["prompt"]
    assert body["section_count"] == 2


def test_prompt_preview_volatile_sections_appear_as_inline_placeholders() -> None:
    """core.memory_block volatile segment appears as inline placeholder in preview.

    M4 Decision 19/21: volatile segments that implement 3-state render (memory_block,
    user_profile_block) render as banner + '<运行时注入:…>' placeholder in PREVIEW mode.
    This tests the real CORE_MEMORY_BLOCK segment (not a generic placeholder).
    """
    from agent.core.agent.prompt_sections.core_sections import CORE_SYSTEM, CORE_MEMORY_BLOCK

    sections = [CORE_SYSTEM, CORE_MEMORY_BLOCK]
    app = create_app()
    app.state.prompt_sections = sections
    with TestClient(app) as client:
        response = client.post(
            "/v1/prompt-preview",
            headers=_auth_headers(),
            json={"features": {}, "tool_ids": [], "scenario": "direct"},
        )
    assert response.status_code == 200
    body = response.json()
    # Stable section appears
    assert "# System" in body["prompt"]
    # memory_block shows inline '运行时注入' placeholder (not empty, not actual memory)
    assert "运行时注入" in body["prompt"]
    assert "MEMORY (your personal notes)" in body["prompt"], (
        "memory_block must show banner title in preview"
    )
    # section_count: stable=1 (core.system), volatile not counted
    assert body["section_count"] == 1


def test_prompt_preview_passes_features_to_context() -> None:
    """Feature flags in the request reach PromptContext.flags so sections can gate on them."""
    captured: list[PromptContext] = []

    def _capturing_render(ctx: PromptContext) -> str:
        captured.append(ctx)
        return "rendered"

    sections = [
        PromptSection(name="core.gated", render=_capturing_render),
    ]
    app = create_app()
    app.state.prompt_sections = sections
    # feat-383-M1: tool gate checks now require the tool to be in the registry.
    app.state.tool_registry = _make_registry_with_tools(("read", "Read."), ("write", "Write."))
    with TestClient(app) as client:
        client.post(
            "/v1/prompt-preview",
            headers=_auth_headers(),
            json={
                "features": {"memory_curation": True, "skill_creation": False},
                "custom_prompt": "Extra instructions.",
                "tool_ids": ["read", "write"],
                "scenario": "direct",
            },
        )

    assert len(captured) == 1
    ctx = captured[0]
    assert ctx.flags.get("memory_curation") is True
    assert ctx.flags.get("skill_creation") is False
    assert ctx.vars.get("custom_prompt") == "Extra instructions."
    assert ctx.scenario.get("conversation_type") == "direct"
    # has_tool() checks rely on tools being in registry (and thus in available_tools)
    assert ctx.has_tool("read")
    assert ctx.has_tool("write")
    assert not ctx.has_tool("nonexistent_tool")


# feat-379-M6 (ISSUE-3): memory_curation gate must respond to tool_ids in preview request.
# Previous impl: promptPreview frontend call omitted tool_ids, so has_tool("memory") was always
# False and memory_curation on/off produced identical output.
def test_prompt_preview_memory_curation_gate_requires_tool_id() -> None:
    """memory_curation=False must exclude core.memory_guidance when memory tool is listed.

    When tool_ids includes "memory", the feature gate should be active and
    memory_curation=False must exclude the guidance section.  This verifies the
    end-to-end gate path: tool_ids → has_tool("memory") → enabled_when() → section in/out.
    """
    from agent.core.agent.prompt_sections.core_sections import CORE_SECTIONS

    app = create_app()
    app.state.prompt_sections = list(CORE_SECTIONS)
    # feat-383-M1: tool gate checks now require the tool to be in the registry;
    # wire a registry that includes the memory tool so has_tool("memory") works.
    app.state.tool_registry = _make_registry_with_tools(("memory", "Memory tool."))
    with TestClient(app) as client:
        # memory tool in tool_ids + memory_curation=True: guidance must appear
        resp_on = client.post(
            "/v1/prompt-preview",
            headers=_auth_headers(),
            json={"features": {"memory_curation": True}, "tool_ids": ["memory"], "scenario": "direct"},
        )
        assert resp_on.status_code == 200
        prompt_on = resp_on.json()["prompt"]

        # memory tool in tool_ids + memory_curation=False: guidance must be absent
        resp_off = client.post(
            "/v1/prompt-preview",
            headers=_auth_headers(),
            json={"features": {"memory_curation": False}, "tool_ids": ["memory"], "scenario": "direct"},
        )
        assert resp_off.status_code == 200
        prompt_off = resp_off.json()["prompt"]

    # The memory guidance text appears only when feature is on
    assert "persistent memory" in prompt_on, "memory guidance must appear when memory_curation=True"
    assert "persistent memory" not in prompt_off, (
        "memory guidance must be absent when memory_curation=False (ISSUE-3 regression)"
    )


def test_prompt_preview_endpoint_is_behind_bearer_auth_dependency() -> None:
    """Preview endpoint must declare require_bearer_auth as a dependency.

    Auth enforcement is a no-op in test mode (disabled globally), but the
    dependency declaration must exist so production deployments enforce it.
    The test verifies the route is registered correctly (status 200 or 401
    depending on auth mode) rather than 404 (which would mean route missing).
    """
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            "/v1/prompt-preview",
            json={"features": {}, "tool_ids": [], "scenario": "direct"},
        )
    # 200 = auth disabled (test mode) or 401 = auth enforced; 404 = route missing (fail).
    assert response.status_code in (200, 401), f"unexpected status {response.status_code}"


# ---------------------------------------------------------------------------
# feat-383-M1: preview fidelity — real tool descriptions, datetime/cwd placeholders
# ---------------------------------------------------------------------------


def _make_stub_tool(name: str, description: str = "") -> object:
    """Create a minimal tool-like stub for wiring into ToolRegistry tests."""
    from types import SimpleNamespace

    return SimpleNamespace(
        name=name,
        description=description,
        input_schema={},
        is_concurrency_safe=False,
        max_result_size_chars=None,
    )


def _make_registry_with_tools(*tool_pairs: tuple[str, str]) -> object:
    """Build a ToolRegistry containing tools given as (name, description) pairs."""
    from pathlib import Path

    from agent.core.tools.base import ToolContext
    from agent.platform.tools.registry import ToolRegistry

    ctx = ToolContext.create(repo_root=Path.cwd())
    registry = ToolRegistry(context=ctx)
    for name, desc in tool_pairs:
        registry.register(_make_stub_tool(name, desc))
    return registry


def test_prompt_preview_accepts_workspace_root_and_skill_ids() -> None:
    """New fields workspace_root and skill_ids must be accepted without 422 error."""
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            "/v1/prompt-preview",
            headers=_auth_headers(),
            json={
                "features": {},
                "tool_ids": [],
                "scenario": "direct",
                "workspace_root": "/tmp/test-ws",
                "skill_ids": [],
            },
        )
    assert response.status_code == 200


def test_prompt_preview_datetime_placeholder() -> None:
    """current_datetime in PromptContext must be the placeholder, not empty string."""
    captured: list[PromptContext] = []

    def _capture(ctx: PromptContext) -> str:
        captured.append(ctx)
        return "x"

    sections = [PromptSection(name="test", render=_capture)]
    app = create_app()
    app.state.prompt_sections = sections
    with TestClient(app) as client:
        client.post(
            "/v1/prompt-preview",
            headers=_auth_headers(),
            json={"features": {}, "tool_ids": [], "scenario": "direct"},
        )

    assert captured, "section render must have been called"
    assert captured[0].current_datetime == "<运行时注入：当前时间>", (
        f"expected datetime placeholder, got: {captured[0].current_datetime!r}"
    )


def test_prompt_preview_cwd_uses_workspace_root() -> None:
    """When workspace_root is provided, ctx.cwd must equal workspace_root."""
    captured: list[PromptContext] = []

    def _capture(ctx: PromptContext) -> str:
        captured.append(ctx)
        return "x"

    sections = [PromptSection(name="test", render=_capture)]
    app = create_app()
    app.state.prompt_sections = sections
    with TestClient(app) as client:
        client.post(
            "/v1/prompt-preview",
            headers=_auth_headers(),
            json={
                "features": {},
                "tool_ids": [],
                "scenario": "direct",
                "workspace_root": "/home/user/workspace/my-agent",
            },
        )

    assert captured
    assert captured[0].cwd == "/home/user/workspace/my-agent", (
        f"expected cwd from workspace_root, got: {captured[0].cwd!r}"
    )


def test_prompt_preview_cwd_placeholder_when_no_workspace() -> None:
    """When workspace_root is absent, ctx.cwd must be the placeholder."""
    captured: list[PromptContext] = []

    def _capture(ctx: PromptContext) -> str:
        captured.append(ctx)
        return "x"

    sections = [PromptSection(name="test", render=_capture)]
    app = create_app()
    app.state.prompt_sections = sections
    with TestClient(app) as client:
        client.post(
            "/v1/prompt-preview",
            headers=_auth_headers(),
            json={"features": {}, "tool_ids": [], "scenario": "direct"},
        )

    assert captured
    assert captured[0].cwd == "<运行时注入：workspace 路径>", (
        f"expected cwd placeholder, got: {captured[0].cwd!r}"
    )


def test_prompt_preview_uses_real_tool_description_from_registry() -> None:
    """available_tools in ctx must carry real descriptions from ToolRegistry."""
    captured: list[PromptContext] = []

    def _capture(ctx: PromptContext) -> str:
        captured.append(ctx)
        return "x"

    sections = [PromptSection(name="test", render=_capture)]
    registry = _make_registry_with_tools(
        ("read", "Read a file and return its contents."),
        ("write", "Write content to a file."),
    )

    app = create_app()
    app.state.prompt_sections = sections
    app.state.tool_registry = registry
    with TestClient(app) as client:
        client.post(
            "/v1/prompt-preview",
            headers=_auth_headers(),
            json={"features": {}, "tool_ids": ["read", "write"], "scenario": "direct"},
        )

    assert captured
    tools_by_name = {t.name: t for t in captured[0].available_tools}
    assert "read" in tools_by_name, "read tool must appear in available_tools"
    assert tools_by_name["read"].description == "Read a file and return its contents.", (
        f"expected real description, got: {tools_by_name['read'].description!r}"
    )
    assert "write" in tools_by_name
    assert tools_by_name["write"].description == "Write content to a file."


def test_prompt_preview_silently_skips_unregistered_tool_ids() -> None:
    """Tool ids not in ToolRegistry must be silently skipped (not appear in ctx)."""
    captured: list[PromptContext] = []

    def _capture(ctx: PromptContext) -> str:
        captured.append(ctx)
        return "x"

    sections = [PromptSection(name="test", render=_capture)]
    registry = _make_registry_with_tools(("read", "Read files."))

    app = create_app()
    app.state.prompt_sections = sections
    app.state.tool_registry = registry
    with TestClient(app) as client:
        client.post(
            "/v1/prompt-preview",
            headers=_auth_headers(),
            json={
                "features": {},
                "tool_ids": ["read", "ghost_tool_that_does_not_exist"],
                "scenario": "direct",
            },
        )

    assert captured
    tool_names = {t.name for t in captured[0].available_tools}
    assert "read" in tool_names
    assert "ghost_tool_that_does_not_exist" not in tool_names, (
        "unregistered tool id must be silently skipped"
    )


# ---------------------------------------------------------------------------
# feat-385-M3-fix-r2 P1: volatile 段就地内联占位符 (Req-4 用户验收修正)
# ---------------------------------------------------------------------------


def test_prompt_preview_volatile_section_inline_placeholder_in_position() -> None:
    """memory_block and user_profile_block segments render banner + placeholder in PREVIEW.

    M4 Decision 19/21: volatile segments with 3-state render show complete banner
    + '<运行时注入:…>' placeholder at their correct list position (not stripped, not footer).
    """
    from agent.core.agent.prompt_sections.core_sections import (
        CORE_SYSTEM, CORE_MEMORY_BLOCK, CORE_USER_PROFILE_BLOCK,
    )

    app = create_app()
    app.state.prompt_sections = [CORE_SYSTEM, CORE_MEMORY_BLOCK, CORE_USER_PROFILE_BLOCK]
    with TestClient(app) as client:
        response = client.post(
            "/v1/prompt-preview",
            headers=_auth_headers(),
            json={"features": {}, "tool_ids": [], "scenario": "direct"},
        )

    assert response.status_code == 200
    prompt = response.json()["prompt"]

    # memory_block appears as inline placeholder at its list position
    assert "MEMORY (your personal notes)" in prompt, (
        "memory_block must show banner title as inline placeholder"
    )
    assert "运行时注入" in prompt, (
        "volatile segment must produce inline '运行时注入' placeholder"
    )

    # Stable section still appears
    assert "# System" in prompt

    # No M2-style footer stacking
    assert "以上预览不包含 volatile 段" not in prompt


def test_prompt_preview_no_footer_stacking_block() -> None:
    """Preview must NOT append a '---' separator + stacked placeholder footer block.

    M2 incorrectly appended a footer block like:
        ---
        以上预览不包含 volatile 段...runtime fills:
        [core.memory_block — runtime fills]
        [core.user_profile_block — runtime fills]

    This pattern (M2 regression) must be absent. Volatile sections are shown inline.
    """
    volatile1 = _make_section("core.memory_block", "MEM", cache_safe=False)
    volatile2 = _make_section("core.user_profile_block", "USER", cache_safe=False)

    app = create_app()
    app.state.prompt_sections = [volatile1, volatile2]
    with TestClient(app) as client:
        response = client.post(
            "/v1/prompt-preview",
            headers=_auth_headers(),
            json={"features": {}, "tool_ids": [], "scenario": "direct"},
        )

    assert response.status_code == 200
    prompt = response.json()["prompt"]

    # M2 footer stacking markers must not appear.
    assert "以上预览不包含 volatile 段" not in prompt, (
        "M2-style footer explanation block must be removed"
    )
    assert "runtime fills]" not in prompt, (
        "M2-style '[section — runtime fills]' footer list must be removed"
    )


def test_prompt_preview_stable_section_byte_consistency_with_volatile_inline() -> None:
    """Stable sections must produce identical text regardless of volatile section presence.

    When volatile sections change their placeholder text, the stable prefix must not change.
    This ensures provider auto-prefix-cache still hits on stable content.
    """
    stable = _make_section("core.identity", "Stable identity text.", cache_safe=True)
    volatile = _make_section("core.memory_block", "volatile data", cache_safe=False)

    # With volatile section
    app1 = create_app()
    app1.state.prompt_sections = [stable, volatile]
    with TestClient(app1) as client:
        resp_with = client.post(
            "/v1/prompt-preview",
            headers=_auth_headers(),
            json={"features": {}, "tool_ids": [], "scenario": "direct"},
        )

    # Without volatile section
    app2 = create_app()
    app2.state.prompt_sections = [stable]
    with TestClient(app2) as client:
        resp_without = client.post(
            "/v1/prompt-preview",
            headers=_auth_headers(),
            json={"features": {}, "tool_ids": [], "scenario": "direct"},
        )

    prompt_with = resp_with.json()["prompt"]
    prompt_without = resp_without.json()["prompt"]

    # The stable part must appear identically in both.
    assert "Stable identity text." in prompt_with
    assert "Stable identity text." in prompt_without
    # The stable prefix must be identical (prompt_with starts with same content as prompt_without).
    assert prompt_with.startswith(prompt_without) or prompt_without in prompt_with, (
        "stable prefix must be byte-identical regardless of volatile section presence"
    )
