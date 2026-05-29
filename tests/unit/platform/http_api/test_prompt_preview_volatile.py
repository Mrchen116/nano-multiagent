"""Tests for /v1/prompt-preview volatile segment placeholder rendering (feat-385-M2 I2)."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from agent.core.agent.prompt_sections.base import PromptSection
from agent.platform.http_api.app import create_app


def _make_volatile_section(name: str, content: str = "volatile content") -> PromptSection:
    """Create a fake volatile (cache_safe=False) prompt section."""
    section = MagicMock(spec=PromptSection)
    section.name = name
    section.cache_safe = False
    section.order = 950
    return section


def _make_stable_section(name: str) -> PromptSection:
    section = MagicMock(spec=PromptSection)
    section.name = name
    section.cache_safe = True
    section.order = 100
    return section


@pytest.fixture()
def app_with_volatile_sections(tmp_path):
    """Create a test app that has both stable and volatile sections registered."""
    from agent.products.local_coding import LOCAL_CODING_PROFILE

    return create_app(product_profile=LOCAL_CODING_PROFILE, repo_root=tmp_path)


def test_prompt_preview_volatile_sections_shown_as_placeholders(app_with_volatile_sections) -> None:
    """Volatile segments must appear as recognizable placeholders in preview, not silently skipped."""
    client = TestClient(app_with_volatile_sections, raise_server_exceptions=True)
    resp = client.post(
        "/v1/prompt-preview",
        json={"features": {"memory_curation": True}, "tool_ids": [], "scenario": "direct"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status_code == 200
    body = resp.json()
    prompt = body["prompt"]
    # The preview must contain a note about volatile segments being excluded
    # (either as a placeholder inline or as a trailing explanation)
    assert any(
        keyword in prompt
        for keyword in ["runtime", "volatile", "运行时", "memory snapshot", "memory_block", "user_profile"]
    ), f"Preview must mention volatile segment placeholder, got:\n{prompt}"


def test_prompt_preview_has_trailing_volatile_explanation(app_with_volatile_sections) -> None:
    """Preview response must contain an explanation about volatile segments at the end."""
    client = TestClient(app_with_volatile_sections, raise_server_exceptions=True)
    resp = client.post(
        "/v1/prompt-preview",
        json={"features": {"memory_curation": True}, "tool_ids": [], "scenario": "direct"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status_code == 200
    prompt = resp.json()["prompt"]
    # Trailing explanation about volatile exclusion must be present
    assert any(
        phrase in prompt
        for phrase in [
            "volatile",
            "memory_block",
            "user_profile_block",
            "runtime fills",
            "运行时",
            "不包含",
            "实填",
        ]
    ), f"Preview must have trailing volatile explanation, got last 300 chars:\n{prompt[-300:]}"
