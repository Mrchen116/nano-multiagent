"""Permission-only operations use real session capabilities and no execution."""

import asyncio
import threading

import pytest

from agent.sdk import LLMConfig, PermissionDecision, build_kernel


class ProposedOperation:
    name = "proposed_operation"
    description = "Operation with an approval policy"
    input_schema = {"type": "object"}

    def check_permissions(self, arguments, context):
        return PermissionDecision(behavior="ask", reason="approve operation")

    def run(self, arguments, context):
        raise AssertionError("permission checks must not execute tools")


async def test_sdk_authorization_real_context_concurrent_sessions_and_cancellation(
    tmp_path,
):
    checked = []
    approvals = []
    parked = threading.Event()
    cancelled = threading.Event()

    async def approve(name, arguments, context):
        approvals.append((name, arguments, context))
        if arguments.get("park"):
            parked.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
        return PermissionDecision(behavior="deny" if arguments.get("deny") else "allow")

    def observe(api):
        async def inspect(event, context):
            checked.append(context)

        api.on("tool_call", inspect, mode="intercept", priority=0)

    kernel = build_kernel(
        llm=LLMConfig(
            provider="openai_compat",
            model="test-model",
            base_url="http://127.0.0.1:4000",
        ),
        repo_root=tmp_path,
        workspace_config_dirname=".nanocode",
        tools=[ProposedOperation()],
        hooks=[observe],
        can_use_tool=approve,
    )
    try:
        roots = [tmp_path / "workspace-a", tmp_path / "workspace-b"]
        for root in roots:
            root.mkdir()
        sessions = [
            await kernel.create_session(
                metadata={"source": str(i)}, workspace_root=root
            )
            for i, root in enumerate(roots)
        ]
        outcomes = await asyncio.gather(
            *(
                kernel.authorize_tool(
                    s.session_id,
                    "proposed_operation",
                    {"deny": i == 1},
                    f"op-{i}",
                    workspace_root=roots[i],
                )
                for i, s in enumerate(sessions)
            )
        )
        assert [o.allowed for o in outcomes] == [True, False]
        assert {c.session_id for c in checked} == {s.session_id for s in sessions}
        assert {c.metadata["source"] for c in checked} == {"0", "1"}
        assert {c.repo_root for c in checked} == set(roots)
        assert all(c.metadata["cwd"] == str(c.repo_root) for c in checked)
        assert {c.metadata["tool_call_id"] for c in checked} == {"op-0", "op-1"}
        assert len(approvals) == 2
        pending = asyncio.create_task(
            kernel.authorize_tool(
                sessions[0].session_id,
                "proposed_operation",
                {"park": True},
                "parked-op",
                workspace_root=roots[0],
            )
        )
        assert await asyncio.to_thread(parked.wait, 3)
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
        assert await asyncio.to_thread(cancelled.wait, 3)
        with pytest.raises(ValueError, match="does not belong"):
            await kernel.authorize_tool(
                sessions[0].session_id,
                "proposed_operation",
                {},
                "bad",
                run_id="unknown",
            )
    finally:
        kernel.close()


async def test_permission_after_completed_run_retains_source_and_runtime(tmp_path):
    from agent.core.llm.interfaces import LLMMessage
    from agent.sdk import RunOrigin

    contexts = []

    class Client:
        async def generate(self, request):
            yield LLMMessage(role="assistant", content="done")
            yield LLMMessage(role="assistant", content="", finish_reason="stop")

    async def allow(name, arguments, context):
        return PermissionDecision(behavior="allow")

    def hooks(api):
        async def inspect(event, context):
            contexts.append(context)

        api.on("tool_call", inspect, mode="intercept", priority=0)

    kernel = build_kernel(
        llm=LLMConfig(
            provider="openai_compat",
            model="test-model",
            base_url="http://127.0.0.1:4000",
        ),
        repo_root=tmp_path,
        tools=[ProposedOperation()],
        hooks=[hooks],
        workspace_config_dirname=".nanocode",
        can_use_tool=allow,
        _llm_client_override=Client(),
    )
    try:
        session = await kernel.create_session()
        run = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "proposal"}],
            origin=RunOrigin.HUMAN,
        )
        async with asyncio.timeout(5):
            async for event in kernel.stream(session_id=session.session_id):
                if (
                    event.get("event") == "run_status"
                    and event.get("run_id") == run.run_id
                    and event.get("status") in {"completed", "failed", "cancelled"}
                ):
                    assert event["status"] == "completed", event
                    break
        outcome = await kernel.authorize_tool(
            session.session_id, "proposed_operation", {}, "after-run", run_id=run.run_id
        )
        assert outcome.allowed
        context = contexts[-1]
        assert context.metadata["run_id"] == run.run_id
        assert context.metadata["run_origin"] == RunOrigin.HUMAN.value
        assert "proposal" in str(context.message_history)
        assert "done" in str(context.message_history)
    finally:
        kernel.close()
