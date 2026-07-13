import asyncio
import threading
from pathlib import Path
from typing import Any

from agent.core.llm.interfaces import LLMGenerateRequest, LLMMessage
from agent.core.types import TokenUsage
from agent.sdk import LLMConfig, LLMModel, LLMProvider, build_kernel


def _is_summary_request(request: LLMGenerateRequest) -> bool:
    return any(
        "Do NOT call any tools" in str(message.content)
        for message in request.messages
    )


def _compaction_llm() -> LLMConfig:
    model = LLMModel(name="threshold-model", context_window=30_000)
    return LLMConfig(
        provider="openai_compat",
        model=model.name,
        base_url="http://127.0.0.1:4000",
        default_model=model.name,
        providers=(
            LLMProvider(
                name="openai_compat",
                base_url="http://127.0.0.1:4000",
                models=(model,),
            ),
        ),
    )


async def _wait_for_terminal(kernel, run_id: str, *, timeout: float = 3.0):  # noqa: ANN001, ANN201
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        record = kernel.get_run(run_id)
        if record is not None and record.status in {
            "completed",
            "failed",
            "cancelled",
        }:
            return record
        await asyncio.sleep(0.02)
    raise AssertionError(f"run {run_id} did not finish")


def _request_text(request: LLMGenerateRequest) -> str:
    return "\n".join(str(message.content) for message in request.messages)


async def test_threshold_compaction_replaces_live_history_for_next_turn(
    tmp_path: Path,
) -> None:
    normal_requests: list[LLMGenerateRequest] = []

    class _Client:
        async def generate(self, request: LLMGenerateRequest):  # noqa: ANN201
            if _is_summary_request(request):
                yield LLMMessage(
                    role="assistant", content="<summary>COMPACTED-CONTEXT</summary>"
                )
                yield LLMMessage(role="assistant", content="", finish_reason="stop")
                return
            normal_requests.append(request)
            yield LLMMessage(
                role="assistant", content=f"reply-{len(normal_requests)}"
            )
            prompt_tokens = 10_000 if len(normal_requests) == 1 else 100
            yield LLMMessage(
                role="assistant",
                content="",
                finish_reason="stop",
                usage=TokenUsage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=10,
                    total_tokens=prompt_tokens + 10,
                ),
            )

    kernel = build_kernel(
        llm=_compaction_llm(),
        repo_root=tmp_path,
        _llm_client_override=_Client(),
    )
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        for text in ("old-context", "triggers-threshold"):
            run = kernel.submit(
                session_id=session.session_id,
                parts=[{"type": "text", "text": text}],
                workspace_root=tmp_path,
            )
            assert (await _wait_for_terminal(kernel, run.run_id)).status == "completed"

        followup = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "after-compaction"}],
            workspace_root=tmp_path,
        )
        assert (await _wait_for_terminal(kernel, followup.run_id)).status == "completed"

        context = _request_text(normal_requests[-1])
        assert "COMPACTED-CONTEXT" in context
        assert "old-context" not in context
    finally:
        kernel.close()


async def test_threshold_compaction_rejects_stale_external_epoch(
    tmp_path: Path,
) -> None:
    summary_started = threading.Event()
    release_summary = threading.Event()
    normal_requests: list[LLMGenerateRequest] = []

    class _Client:
        async def generate(self, request: LLMGenerateRequest):  # noqa: ANN201
            if _is_summary_request(request):
                summary_started.set()
                await asyncio.to_thread(release_summary.wait)
                yield LLMMessage(
                    role="assistant", content="<summary>STALE-SUMMARY</summary>"
                )
                yield LLMMessage(role="assistant", content="", finish_reason="stop")
                return
            normal_requests.append(request)
            yield LLMMessage(role="assistant", content="ack")
            prompt_tokens = 10_000 if len(normal_requests) == 1 else 100
            yield LLMMessage(
                role="assistant",
                content="",
                finish_reason="stop",
                usage=TokenUsage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=10,
                    total_tokens=prompt_tokens + 10,
                ),
            )

    kernel = build_kernel(
        llm=_compaction_llm(),
        repo_root=tmp_path,
        _llm_client_override=_Client(),
    )
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        first = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "seed-threshold"}],
            workspace_root=tmp_path,
        )
        assert (await _wait_for_terminal(kernel, first.run_id)).status == "completed"

        compacting = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "start-summary"}],
            workspace_root=tmp_path,
        )
        assert await asyncio.to_thread(summary_started.wait, 2)
        kernel.append_message(
            session.session_id,
            role="user",
            content="external-during-summary",
            workspace_root=tmp_path,
        )
        release_summary.set()
        assert (await _wait_for_terminal(kernel, compacting.run_id)).status == "completed"

        followup = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "after-stale-summary"}],
            workspace_root=tmp_path,
        )
        assert (await _wait_for_terminal(kernel, followup.run_id)).status == "completed"
        assert "external-during-summary" in _request_text(normal_requests[-1])
    finally:
        release_summary.set()
        kernel.close()


async def test_manual_compaction_refreshes_agents_md_prompt(tmp_path: Path) -> None:
    agents_md = tmp_path / "AGENTS.md"
    agents_md.write_text("PROMPT-MARKER-OLD", encoding="utf-8")
    normal_requests: list[LLMGenerateRequest] = []

    class _Client:
        async def generate(self, request: LLMGenerateRequest):  # noqa: ANN201
            if _is_summary_request(request):
                yield LLMMessage(
                    role="assistant", content="<summary>MANUAL-COMPACT</summary>"
                )
                yield LLMMessage(role="assistant", content="", finish_reason="stop")
                return
            normal_requests.append(request)
            yield LLMMessage(role="assistant", content="ack")
            yield LLMMessage(role="assistant", content="", finish_reason="stop")

    kernel = build_kernel(
        llm=_compaction_llm(),
        repo_root=tmp_path,
        _llm_client_override=_Client(),
    )
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        first = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "freeze prompt"}],
            workspace_root=tmp_path,
        )
        assert (await _wait_for_terminal(kernel, first.run_id)).status == "completed"
        assert "PROMPT-MARKER-OLD" in _request_text(normal_requests[-1])

        agents_md.write_text("PROMPT-MARKER-NEW", encoding="utf-8")
        frozen = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "still frozen"}],
            workspace_root=tmp_path,
        )
        assert (await _wait_for_terminal(kernel, frozen.run_id)).status == "completed"
        frozen_prompt = _request_text(normal_requests[-1])
        assert "PROMPT-MARKER-OLD" in frozen_prompt
        assert "PROMPT-MARKER-NEW" not in frozen_prompt

        assert await kernel.compact(
            session.session_id, workspace_root=tmp_path
        ) is not None

        second = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "refresh prompt"}],
            workspace_root=tmp_path,
        )
        assert (await _wait_for_terminal(kernel, second.run_id)).status == "completed"
        refreshed = _request_text(normal_requests[-1])
        assert "PROMPT-MARKER-NEW" in refreshed
        assert "PROMPT-MARKER-OLD" not in refreshed
    finally:
        kernel.close()
