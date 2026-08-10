"""Integration coverage for explicit zero-Skill Kernel sessions."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from agent.core.llm.interfaces import LLMMessage, LLMToolCall
from agent.sdk import (
    LLMConfig,
    PermissionDecision,
    PromptSlots,
    SessionRuntimeConfig,
    build_kernel,
)


async def _allow_all(_tool: str, _input: Any, _context: Any) -> PermissionDecision:
    return PermissionDecision(behavior="allow")


class _SkillViewAttemptClient:
    def __init__(self) -> None:
        self.requests: list[Any] = []

    def generate(self, request: Any):
        self.requests.append(request)
        return self._stream(first=len(self.requests) == 1)

    async def _stream(self, *, first: bool):
        if first:
            yield LLMMessage(
                role="assistant",
                content="",
                tool_calls=(
                    LLMToolCall(
                        call_id="skill-view-1",
                        name="skill_view",
                        arguments={"name": "secret-skill"},
                    ),
                ),
            )
            yield LLMMessage(role="assistant", content="", finish_reason="tool_calls")
            return
        yield LLMMessage(role="assistant", content="done")
        yield LLMMessage(role="assistant", content="", finish_reason="stop")


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


async def test_explicit_empty_skills_survive_real_session_and_block_skill_view(
    tmp_path: Path,
) -> None:
    skill_file = tmp_path / ".nanoassistant" / "skills" / "secret-skill" / "SKILL.md"
    skill_file.parent.mkdir(parents=True)
    skill_file.write_text(
        "---\nname: secret-skill\ndescription: hidden\n---\n\nSECRET SKILL BODY\n",
        encoding="utf-8",
    )
    client = _SkillViewAttemptClient()
    kernel = build_kernel(
        llm=LLMConfig(
            provider="openai_compat",
            model="test-model",
            base_url="http://127.0.0.1:1",
        ),
        can_use_tool=_allow_all,
        workspace_config_dirname=".nanoassistant",
        repo_root=tmp_path,
        _llm_client_override=client,
    )
    runtime = SessionRuntimeConfig(
        model="test-model",
        prompt=PromptSlots(),
        skills=[],
        enabled_tools=["skill_view"],
        features={},
    )
    try:
        session = await kernel.create_session(workspace_root=tmp_path, runtime=runtime)
        persisted = await kernel.get_session_runtime(
            session_id=session.session_id,
            workspace_root=tmp_path,
        )
        run = kernel.submit(
            session_id=session.session_id,
            workspace_root=tmp_path,
            parts=[{"type": "text", "text": "Continue without project skills."}],
        )
        await _wait_terminal(kernel, run.run_id)

        assert persisted is not None
        assert persisted.runtime.skills == []
        assert len(client.requests) == 2
        first_context = "\n".join(
            str(message.content) for message in client.requests[0].messages
        )
        assert "<name>secret-skill</name>" not in first_context
        second_context = "\n".join(
            str(message.content) for message in client.requests[1].messages
        )
        assert "not enabled for this session" in second_context
        assert "SECRET SKILL BODY" not in second_context
    finally:
        await kernel.aclose()
