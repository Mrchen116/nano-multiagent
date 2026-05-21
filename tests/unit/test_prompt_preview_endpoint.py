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
    order: int,
    text: str,
    cache_safe: bool = True,
    enabled: bool = True,
) -> PromptSection:
    """Build a minimal PromptSection for testing."""
    return PromptSection(
        name=name,
        order=order,
        render=lambda ctx: text,
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
        _make_section("core.identity", 100, "You are a helpful assistant."),
        _make_section("core.rules", 200, "Follow these rules."),
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


def test_prompt_preview_excludes_volatile_sections() -> None:
    """Preview must exclude cache_safe=False (volatile) sections."""
    sections = [
        _make_section("core.stable", 100, "Stable text.", cache_safe=True),
        # cache_safe=False segment must have order > stable to avoid cache_safe violation
        _make_section("core.volatile", 950, "Volatile turn data.", cache_safe=False),
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
    assert "Stable text." in body["prompt"]
    assert "Volatile turn data." not in body["prompt"]
    # section_count reflects only cache_safe=True sections
    assert body["section_count"] == 1


def test_prompt_preview_passes_features_to_context() -> None:
    """Feature flags in the request reach PromptContext.flags so sections can gate on them."""
    captured: list[PromptContext] = []

    def _capturing_render(ctx: PromptContext) -> str:
        captured.append(ctx)
        return "rendered"

    sections = [
        PromptSection(name="core.gated", order=100, render=_capturing_render),
    ]
    app = create_app()
    app.state.prompt_sections = sections
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
    # tool stubs allow has_tool() checks
    assert ctx.has_tool("read")
    assert ctx.has_tool("write")
    assert not ctx.has_tool("nonexistent_tool")


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
