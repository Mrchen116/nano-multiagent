import asyncio
from pathlib import Path

from agent.core.llm.interfaces import LLMGenerateRequest, LLMMessage, LLMToolCall
from agent.platform.permissions.broker import PermissionDecision
from agent.sdk import LLMConfig, LLMModel, LLMProvider, build_kernel


def _llm_config() -> LLMConfig:
    model = LLMModel(name="window-model", context_window=30_000)
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


def _request_text(request: LLMGenerateRequest) -> str:
    return "\n".join(str(message.content) for message in request.messages)


def _is_summary_request(request: LLMGenerateRequest) -> bool:
    return request.tools == ()


async def _wait_for_terminal(kernel, run_id: str):  # noqa: ANN001, ANN201
    deadline = asyncio.get_running_loop().time() + 3
    while asyncio.get_running_loop().time() < deadline:
        run = kernel.get_run(run_id)
        if run is not None and run.status in {"completed", "failed", "cancelled"}:
            return run
        await asyncio.sleep(0.02)
    raise AssertionError(f"run {run_id} did not finish")


async def test_compaction_refreshes_memory_and_resets_file_read_window(
    tmp_path: Path,
) -> None:
    memory_root = tmp_path / ".nanotest" / "memory"
    memory_root.mkdir(parents=True)
    (memory_root / "MEMORY.md").write_text("MEMORY-OLD", encoding="utf-8")
    (memory_root / "USER.md").write_text("USER-OLD", encoding="utf-8")
    tracked_file = tmp_path / "tracked.txt"
    tracked_file.write_text("FILE-WINDOW-MARKER", encoding="utf-8")

    start_requests: list[LLMGenerateRequest] = []
    tool_followups: list[LLMGenerateRequest] = []
    call_count = 0

    class _ReadClient:
        async def generate(self, request: LLMGenerateRequest):  # noqa: ANN201
            nonlocal call_count
            if _is_summary_request(request):
                yield LLMMessage(
                    role="assistant", content="<summary>WINDOW-RESET</summary>"
                )
                yield LLMMessage(role="assistant", content="", finish_reason="stop")
                return
            if request.messages[-1].role == "tool":
                tool_followups.append(request)
                yield LLMMessage(
                    role="assistant", content="read-done", finish_reason="stop"
                )
                return
            start_requests.append(request)
            call_count += 1
            yield LLMMessage(
                role="assistant",
                content="reading",
                tool_calls=(
                    LLMToolCall(
                        call_id=f"call-read-{call_count}",
                        name="read",
                        arguments={"path": str(tracked_file)},
                    ),
                ),
            )

    async def _allow_all(_tool, _tool_input, _ctx):  # noqa: ANN001, ANN202
        return PermissionDecision(behavior="allow")

    kernel = build_kernel(
        llm=_llm_config(),
        repo_root=tmp_path,
        workspace_config_dirname=".nanotest",
        can_use_tool=_allow_all,
        _llm_client_override=_ReadClient(),
    )
    try:
        session = await kernel.create_session(
            workspace_root=tmp_path,
            enabled_tools=["read"],
        )

        first = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "read first"}],
            workspace_root=tmp_path,
        )
        assert (await _wait_for_terminal(kernel, first.run_id)).status == "completed"
        assert "MEMORY-OLD" in _request_text(start_requests[-1])
        assert "USER-OLD" in _request_text(start_requests[-1])
        assert "FILE-WINDOW-MARKER" in _request_text(tool_followups[-1])

        (memory_root / "MEMORY.md").write_text("MEMORY-NEW", encoding="utf-8")
        (memory_root / "USER.md").write_text("USER-NEW", encoding="utf-8")
        frozen = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "read frozen"}],
            workspace_root=tmp_path,
        )
        assert (await _wait_for_terminal(kernel, frozen.run_id)).status == "completed"
        frozen_prompt = _request_text(start_requests[-1])
        assert "MEMORY-OLD" in frozen_prompt and "MEMORY-NEW" not in frozen_prompt
        assert "USER-OLD" in frozen_prompt and "USER-NEW" not in frozen_prompt
        assert "earlier Read tool_result" in _request_text(tool_followups[-1])

        assert (
            await kernel.compact(session.session_id, workspace_root=tmp_path)
            is not None
        )
        refreshed = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "read refreshed"}],
            workspace_root=tmp_path,
        )
        assert (await _wait_for_terminal(kernel, refreshed.run_id)).status == (
            "completed"
        )
        refreshed_prompt = _request_text(start_requests[-1])
        assert "MEMORY-NEW" in refreshed_prompt and "MEMORY-OLD" not in refreshed_prompt
        assert "USER-NEW" in refreshed_prompt and "USER-OLD" not in refreshed_prompt
        refreshed_tool_context = _request_text(tool_followups[-1])
        assert "FILE-WINDOW-MARKER" in refreshed_tool_context
        assert "earlier Read tool_result" not in refreshed_tool_context
    finally:
        kernel.close()
