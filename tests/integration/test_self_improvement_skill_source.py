"""Integration coverage for automatic Skill Review creation provenance."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest

from agent.core.llm.interfaces import LLMGenerateRequest, LLMMessage, LLMToolCall
from agent.sdk import (
    LLMConfig,
    PromptSlots,
    SessionRuntimeConfig,
    build_kernel,
)


class _KernelSkillReviewClient:
    """Run one main-turn tool call, then create a Skill in the review fork."""

    def __init__(self) -> None:
        self._round = 0

    def generate(
        self, request: LLMGenerateRequest
    ) -> AsyncIterator[LLMMessage]:
        """Return the scripted two-round Skill Review response."""

        _ = request
        self._round += 1
        round_no = self._round

        async def _stream() -> AsyncIterator[LLMMessage]:
            if round_no == 1:
                yield LLMMessage(
                    role="assistant",
                    content="",
                    tool_calls=(
                        LLMToolCall(
                            call_id="list-skills",
                            name="skill_manage",
                            arguments={"action": "list"},
                        ),
                    ),
                )
                yield LLMMessage(
                    role="assistant", content="", finish_reason="tool_calls"
                )
                return
            if round_no == 3:
                yield LLMMessage(
                    role="assistant",
                    content="",
                    tool_calls=(
                        LLMToolCall(
                            call_id="view-manual-skill",
                            name="skill_view",
                            arguments={"name": "manual-skill"},
                        ),
                        LLMToolCall(
                            call_id="create-auto-skill",
                            name="skill_manage",
                            arguments={
                                "action": "create",
                                "name": "auto-review-skill",
                                "scope": "agent",
                                "content": (
                                    "---\nname: auto-review-skill\n"
                                    "description: Created by an automatic review\n"
                                    "---\n\n# Instructions\n\nReuse the reviewed workflow.\n"
                                ),
                            },
                        ),
                    ),
                )
                yield LLMMessage(
                    role="assistant", content="", finish_reason="tool_calls"
                )
                return
            yield LLMMessage(role="assistant", content="review complete")
            yield LLMMessage(role="assistant", content="", finish_reason="stop")

        return _stream()


async def _wait_terminal(kernel: Any, run_id: str) -> None:
    while True:
        record = kernel.get_run(run_id)
        if record is not None and record.status in {
            "completed",
            "failed",
            "cancelled",
        }:
            return
        await asyncio.sleep(0.01)


async def _wait_for_usage_records(
    path: Path, expected_names: set[str]
) -> dict[str, Any]:
    for _ in range(200):
        if path.is_file():
            usage = json.loads(path.read_text(encoding="utf-8"))
            if expected_names <= usage.keys():
                return usage
        await asyncio.sleep(0.01)
    raise AssertionError(
        f"timed out waiting for background Review records {expected_names}: {path}"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("memory_threshold", [100, 1], ids=["skill-only", "combined"])
async def test_background_skill_review_create_records_f3_source(
    tmp_path: Path, memory_threshold: int
) -> None:
    """Persist F3 when a skill-only or combined background Review creates a Skill."""

    config_root = tmp_path / ".nanoassistant"
    config_root.mkdir()
    manual_skill_file = config_root / "skills" / "manual-skill" / "SKILL.md"
    manual_skill_file.parent.mkdir(parents=True)
    manual_skill_file.write_text(
        "---\nname: manual-skill\ndescription: Existing manual skill\n"
        "---\n\n# Instructions\n\nKeep the existing behavior.\n",
        encoding="utf-8",
    )
    (config_root / "config.yaml").write_text(
        "auto_mode:\n"
        "  dangerously_skip_permissions: true\n"
        "self_evolution:\n"
        "  enabled: true\n"
        "  skill_creation: true\n"
        "  memory_curation: true\n"
        "  skill_nudge_interval: 1\n"
        f"  memory_nudge_interval: {memory_threshold}\n",
        encoding="utf-8",
    )
    client = _KernelSkillReviewClient()
    kernel = build_kernel(
        llm=LLMConfig(
            provider="openai_compat",
            model="test-model",
            base_url="http://127.0.0.1:1",
        ),
        workspace_config_dirname=".nanoassistant",
        repo_root=tmp_path,
        _llm_client_override=client,
    )
    runtime = SessionRuntimeConfig(
        model="test-model",
        prompt=PromptSlots(),
        skills=None,
        enabled_tools=["skill_manage", "skill_view", "memory"],
        features={"skill_creation": True, "memory_curation": True},
    )
    usage_path = config_root / "skills" / ".usage.json"
    try:
        session = await kernel.create_session(workspace_root=tmp_path, runtime=runtime)
        run = kernel.submit(
            session_id=session.session_id,
            workspace_root=tmp_path,
            parts=[{"type": "text", "text": "Inspect the available skills."}],
        )
        await _wait_terminal(kernel, run.run_id)
        usage = await _wait_for_usage_records(
            usage_path, {"auto-review-skill", "manual-skill"}
        )

        assert usage["auto-review-skill"]["source"] == "F3"
        assert usage["manual-skill"]["source"] == "F1"
    finally:
        await kernel.aclose()
