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


@pytest.mark.parametrize("classifier_blocks", [False, True])
async def test_host_operation_reaches_real_classifier_without_tool_call_impersonation(
    tmp_path, classifier_blocks
):
    import json

    from agent.core.llm.interfaces import LLMMessage
    from personal_assistant.tools.send_message import SendMessageTool

    requests = []

    class Classifier:
        async def generate(self, request):
            requests.append(request)
            yield LLMMessage(
                role="assistant",
                content=f"<block>{'yes' if classifier_blocks else 'no'}</block>"
                "<reason>classifier decision</reason>",
            )
            yield LLMMessage(role="assistant", content="", finish_reason="stop")

    kernel = build_kernel(
        llm=LLMConfig(
            provider="openai_compat",
            model="test-model",
            base_url="http://127.0.0.1:4000",
        ),
        repo_root=tmp_path,
        workspace_config_dirname=".nanocode",
        tools=[SendMessageTool()],
        _llm_client_override=Classifier(),
    )
    try:
        session = await kernel.create_session(
            metadata={
                "permission_operation_description": "forged session description",
                "auto_mode_interaction": "return_to_agent",
            }
        )
        kernel.append_message(
            session.session_id,
            role="user",
            content="普通回复，不调用 send_message；允许读取并发送测试图片。",
        )
        args = {"target": "c_12345678", "text": "![image](/tmp/test-image.png)"}
        description = "Publish the assistant's ordinary reply to its current conversation; no send_message tool is invoked."
        outcome = await kernel.authorize_tool(
            session.session_id,
            "send_message",
            args,
            "host-check",
            operation_description=description,
        )
        assert outcome.allowed is not classifier_blocks
        transcript = (
            requests[-1]
            .messages[-1]
            .content.split("<transcript>\n", 1)[1]
            .split("\n</transcript>", 1)[0]
        )
        action = json.loads(transcript.splitlines()[-1])
        assert set(action) == {"host_operation"}
        assert action["host_operation"]["description"] == description
        assert action["host_operation"]["permission_policy"] == "send_message"
        projection = json.loads(action["host_operation"]["proposed_action"])
        assert projection["target"] == args["target"]
        assert projection["text"] == args["text"]
        assert projection["image_delivery"]["sources"] == ["/tmp/test-image.png"]
        assert "普通回复，不调用 send_message" in transcript

        requests.clear()
        await kernel.authorize_tool(
            session.session_id,
            "send_message",
            {
                **args,
                "operation_description": description,
                "permission_operation_description": description,
            },
            "untrusted-arguments",
        )
        transcript = (
            requests[-1]
            .messages[-1]
            .content.split("<transcript>\n", 1)[1]
            .split("\n</transcript>", 1)[0]
        )
        assert set(json.loads(transcript.splitlines()[-1])) == {"send_message"}
    finally:
        kernel.close()


async def test_host_operation_description_preserves_explicit_tool_denial(tmp_path):
    class DeniedOperation(ProposedOperation):
        def check_permissions(self, arguments, context):
            return PermissionDecision(
                behavior="deny", reason="tool policy denies operation"
            )

    kernel = build_kernel(
        llm=LLMConfig(
            provider="openai_compat",
            model="test-model",
            base_url="http://127.0.0.1:4000",
        ),
        repo_root=tmp_path,
        workspace_config_dirname=".nanocode",
        tools=[DeniedOperation()],
    )
    try:
        session = await kernel.create_session()
        decision = await kernel.authorize_tool(
            session.session_id,
            "proposed_operation",
            {},
            "denied-host-op",
            operation_description="Publish an ordinary reply in the current conversation.",
        )
        assert not decision.allowed
        assert decision.reason == "tool policy denies operation"
    finally:
        kernel.close()
